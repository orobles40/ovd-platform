#!/usr/bin/env bash
# OVD Platform — Lanzador de fine-tuning con control de RAM
# M1 Pro 16 GB — previene reinicio por OOM
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ─── Helpers de RAM ───────────────────────────────────────────────────────────
# Calcula MB disponibles: free + inactive + purgeable
# (macOS puede reclamar inactive y purgeable sin presión)
available_mb() {
    python3 -c "
import subprocess, re
out = subprocess.check_output(['vm_stat']).decode()
ps = 16384
free     = int(re.search(r'Pages free:\s+(\d+)', out).group(1))
inactive = int(re.search(r'Pages inactive:\s+(\d+)', out).group(1))
purgeable= int(re.search(r'Pages purgeable:\s+(\d+)', out).group(1))
print((free + inactive + purgeable) * ps // (1024*1024))
"
}

# Calcula GB de presión REAL: wired + active + compressor
# Excluye inactive/purgeable que macOS puede liberar libremente
pressure_gb() {
    python3 -c "
import subprocess, re
out = subprocess.check_output(['vm_stat']).decode()
ps = 16384
wired      = int(re.search(r'Pages wired down:\s+(\d+)', out).group(1))
active     = int(re.search(r'Pages active:\s+(\d+)', out).group(1))
compressor = int(re.search(r'Pages occupied by compressor:\s+(\d+)', out).group(1))
total_mb = (wired + active + compressor) * ps / (1024*1024)
print(round(total_mb / 1024, 1))
" 2>/dev/null || echo "0"
}

# ─── 1. Verificar RAM disponible ─────────────────────────────────────────────
echo "[RAM] Verificando memoria disponible..."
FREE_MB=$(available_mb)
echo "[RAM] Disponible (free+inactive+purgeable): ${FREE_MB} MB"

if [ "$FREE_MB" -lt 4096 ]; then
    echo "[RAM] ADVERTENCIA: menos de 4 GB disponibles."
    if sudo -n purge 2>/dev/null; then
        sleep 2
        FREE_MB=$(available_mb)
        echo "[RAM] Disponible tras purge: ${FREE_MB} MB"
    else
        echo "[RAM] Para liberar caché manualmente ejecuta: sudo purge"
        echo "[RAM] Continuando de todas formas (macOS gestiona la memoria)..."
    fi
fi

if [ "$FREE_MB" -lt 2048 ]; then
    echo "[ERROR] RAM crítica (${FREE_MB} MB disponibles). Cierra aplicaciones pesadas."
    echo "  Sugerencia: cierra Brave, Slack, Docker u otras apps que consuman memoria."
    exit 1
fi

# ─── 2. Monitor de RAM en background ─────────────────────────────────────────
# Detiene el training si la presión real (wired+active+compressor) supera el límite.
# La presión normal del sistema (sin training) es ~6-7 GB.
# El training MLX batch=1 agrega ~5-6 GB → total esperado: ~12-13 GB.
# Límite: 15.5 GB — deja ~0.5 GB de reserva para evitar el reinicio forzado del kernel.
RAM_PRESSURE_LIMIT=15.5

monitor_ram() {
    local pid=$1
    # Esperar a que el modelo termine de cargar antes de monitorear
    sleep 60
    while kill -0 "$pid" 2>/dev/null; do
        PRESSURE=$(pressure_gb)
        if python3 -c "exit(0 if float('${PRESSURE}') < ${RAM_PRESSURE_LIMIT} else 1)" 2>/dev/null; then
            :
        else
            echo ""
            echo "[RAM-MONITOR] ALERTA: presión RAM supera ${RAM_PRESSURE_LIMIT} GB (actual: ${PRESSURE} GB)"
            echo "[RAM-MONITOR] Deteniendo training para evitar reinicio del sistema..."
            kill "$pid" 2>/dev/null || true
            break
        fi
        sleep 15
    done
}

# ─── 3. Lanzar training ───────────────────────────────────────────────────────
echo "[MLX] Iniciando fine-tuning con mlx_lm.lora..."
echo "[MLX] Config: batch_size=1, max_seq_length=1024, save_every=25, iters=500"
echo "[MLX] Monitor RAM activo: límite de presión ${RAM_PRESSURE_LIMIT} GB"
echo ""

LOG_FILE="logs/training_$(date +%Y%m%d_%H%M%S).log"
DATE_START=$(date +"%Y-%m-%d %H:%M:%S")
mkdir -p logs

mlx-env/bin/mlx_lm.lora \
    --config mlx_config.yaml \
    2>&1 | tee "$LOG_FILE" &

TRAIN_PID=$!
echo "[MLX] PID del training: ${TRAIN_PID}"
echo "[MLX] Log: ${LOG_FILE}"
echo ""

# Activar monitor
monitor_ram "$TRAIN_PID" &
MONITOR_PID=$!

# Esperar a que termine el training
wait "$TRAIN_PID"
EXIT_CODE=$?
DATE_END=$(date +"%Y-%m-%d %H:%M:%S")

# Detener monitor
kill "$MONITOR_PID" 2>/dev/null || true

# ─── 4. Registrar métricas en el summary de runs ──────────────────────────────
echo ""
echo "[LOG] Generando registro de métricas..."

if [ "$EXIT_CODE" -eq 0 ]; then
    OUTCOME="completed"
else
    # Distinguir OOM kill (137) de interrupción normal (143 = SIGTERM)
    if [ "$EXIT_CODE" -eq 137 ]; then
        OUTCOME="oom_killed"
    else
        OUTCOME="interrupted"
    fi
fi

mlx-env/bin/python parse_training_log.py \
    "$LOG_FILE" \
    --date-start "$DATE_START" \
    --date-end "$DATE_END" \
    --outcome "$OUTCOME" \
    2>/dev/null || python3 parse_training_log.py \
    "$LOG_FILE" \
    --date-start "$DATE_START" \
    --date-end "$DATE_END" \
    --outcome "$OUTCOME"

# ─── 5. Resultado final ───────────────────────────────────────────────────────
if [ "$EXIT_CODE" -eq 0 ]; then
    echo "[MLX] Training completado exitosamente."
    echo "[MLX] Adaptadores en: adapters/"
    ls -lh adapters/*.safetensors 2>/dev/null | tail -5
else
    echo "[MLX] Training terminó con código: ${EXIT_CODE} (${OUTCOME})"
    echo "[MLX] Revisa el log: ${LOG_FILE}"
    LAST_CKPT=$(ls -t adapters/[0-9]*.safetensors 2>/dev/null | head -1 || echo "")
    if [ -n "$LAST_CKPT" ]; then
        LAST_ITER=$(echo "$LAST_CKPT" | grep -o '[0-9]\{7\}' | head -1 | sed 's/^0*//')
        echo "[MLX] Último checkpoint: ${LAST_CKPT} (iter ${LAST_ITER})"
        echo "[MLX] Para retomar, agregar en mlx_config.yaml:"
        echo "  resume_adapter_file: \"${LAST_CKPT}\""
    else
        echo "[MLX] Sin checkpoints guardados — el training debe empezar desde cero."
    fi
fi
