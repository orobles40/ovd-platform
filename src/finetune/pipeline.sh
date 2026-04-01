#!/usr/bin/env bash
# OVD Platform — Pipeline de fine-tuning SM1
# Copyright 2026 Omar Robles
#
# Orquesta el pipeline completo:
#   1. Genera datos sintéticos  (generate_synthetic.py)
#   2. Exporta ciclos reales    (export_cycles.py, con filtros de calidad)
#   3. Merge + deduplicación   (merge_datasets.py o jq inline)
#   4. Validación               (validate_dataset.py)
#   5. Reporte final
#
# Uso:
#   ./pipeline.sh                       # pipeline completo
#   ./pipeline.sh --skip-synthetic      # solo ciclos reales (sin generar sintéticos)
#   ./pipeline.sh --skip-export         # solo sintéticos (sin exportar de BD)
#   ./pipeline.sh --dry-run             # simular sin llamar APIs ni BD
#   ./pipeline.sh --count 100           # solo 100 ejemplos sintéticos
#   ./pipeline.sh --org-id omar    # filtrar ciclos por org_id
#
# Variables de entorno requeridas:
#   ANTHROPIC_API_KEY   — para generate_synthetic.py
#   DATABASE_URL        — para export_cycles.py (postgresql://...)
#
# Salida:
#   data/synthetic.jsonl      — ejemplos sintéticos
#   data/real_cycles.jsonl    — ciclos reales exportados
#   data/merged.jsonl         — dataset combinado sin duplicados
#   data/pipeline_report.txt  — reporte de ejecución

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${SCRIPT_DIR}/data"
LOG_FILE="${DATA_DIR}/pipeline.log"

SYNTHETIC_OUTPUT="${DATA_DIR}/synthetic.jsonl"
REAL_OUTPUT="${DATA_DIR}/real_cycles.jsonl"
MERGED_OUTPUT="${DATA_DIR}/merged.jsonl"
REPORT_FILE="${DATA_DIR}/pipeline_report.txt"

SYNTH_COUNT=350
ORG_ID=""
DRY_RUN=false
SKIP_SYNTHETIC=false
SKIP_EXPORT=false

# Filtros de calidad para export_cycles (SM1 — críticos para integridad del dataset)
MIN_QA_SCORE=0.80
REQUIRE_APPROVAL=true
EXCLUDE_AUTO_APPROVE=true

# ---------------------------------------------------------------------------
# Parseo de argumentos
# ---------------------------------------------------------------------------

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-synthetic)   SKIP_SYNTHETIC=true ;;
        --skip-export)      SKIP_EXPORT=true ;;
        --dry-run)          DRY_RUN=true ;;
        --count)            SYNTH_COUNT="$2"; shift ;;
        --org-id)           ORG_ID="$2"; shift ;;
        --min-qa-score)     MIN_QA_SCORE="$2"; shift ;;
        --no-quality-filters) MIN_QA_SCORE=0; REQUIRE_APPROVAL=false; EXCLUDE_AUTO_APPROVE=false ;;
        *)
            echo "Argumento desconocido: $1" >&2
            echo "Uso: $0 [--skip-synthetic] [--skip-export] [--dry-run] [--count N] [--org-id ID]" >&2
            exit 1
            ;;
    esac
    shift
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "${LOG_FILE}"; }
step() { echo; echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; log "PASO $*"; }
ok()   { log "  OK: $*"; }
warn() { log "  ADVERTENCIA: $*"; }
fail() { log "  ERROR: $*"; exit 1; }

count_lines() {
    local file="$1"
    if [[ -f "$file" ]]; then
        wc -l < "$file" | tr -d ' '
    else
        echo "0"
    fi
}

# ---------------------------------------------------------------------------
# Inicio del pipeline
# ---------------------------------------------------------------------------

mkdir -p "${DATA_DIR}"
: > "${LOG_FILE}"

log "OVD Platform — Pipeline de fine-tuning SM1"
log "Fecha: $(date '+%Y-%m-%d %H:%M:%S')"
log "Directorio: ${DATA_DIR}"
[[ "$DRY_RUN" == "true" ]] && log "  [DRY-RUN] modo simulación activo"

# Verificar dependencias
command -v python3 >/dev/null 2>&1 || fail "python3 no encontrado"
python3 -c "import anthropic" 2>/dev/null || warn "anthropic no instalado — generate_synthetic.py fallará"
python3 -c "import psycopg"   2>/dev/null || warn "psycopg no instalado — export_cycles.py fallará"

# ---------------------------------------------------------------------------
# Paso 1 — Datos sintéticos
# ---------------------------------------------------------------------------

if [[ "$SKIP_SYNTHETIC" == "false" ]]; then
    step "1/4 — Generación de datos sintéticos (${SYNTH_COUNT} ejemplos)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log "  [DRY-RUN] omitiendo generate_synthetic.py"
        SKIP_SYNTHETIC=true
    elif [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
        warn "ANTHROPIC_API_KEY no configurada — saltando generación sintética"
        SKIP_SYNTHETIC=true
    else
        SYNTH_ARGS=(
            --output "${SYNTHETIC_OUTPUT}"
            --count "${SYNTH_COUNT}"
        )

        if python3 "${SCRIPT_DIR}/generate_synthetic.py" "${SYNTH_ARGS[@]}"; then
            SYNTH_LINES=$(count_lines "${SYNTHETIC_OUTPUT}")
            ok "${SYNTH_LINES} ejemplos sintéticos generados"
        else
            warn "generate_synthetic.py terminó con error — continuando sin sintéticos"
            SKIP_SYNTHETIC=true
        fi
    fi
else
    log "  Saltando generación sintética (--skip-synthetic)"
fi

# ---------------------------------------------------------------------------
# Paso 2 — Exportar ciclos reales
# ---------------------------------------------------------------------------

if [[ "$SKIP_EXPORT" == "false" ]]; then
    step "2/4 — Exportación de ciclos reales (filtros de calidad activos)"

    if [[ -z "${DATABASE_URL:-}" ]]; then
        warn "DATABASE_URL no configurada — saltando exportación de ciclos"
        SKIP_EXPORT=true
    else
        EXPORT_ARGS=(
            --output "${REAL_OUTPUT}"
            --min-qa-score "${MIN_QA_SCORE}"
        )
        [[ "$REQUIRE_APPROVAL" == "true" ]]     && EXPORT_ARGS+=(--require-approval)
        [[ "$EXCLUDE_AUTO_APPROVE" == "true" ]] && EXPORT_ARGS+=(--exclude-auto-approve)
        [[ -n "$ORG_ID" ]]                      && EXPORT_ARGS+=(--org-id "${ORG_ID}")
        [[ "$DRY_RUN" == "true" ]] && {
            log "  [DRY-RUN] omitiendo export_cycles.py"
            SKIP_EXPORT=true
        }

        if [[ "$SKIP_EXPORT" == "false" ]]; then
            if python3 "${SCRIPT_DIR}/export_cycles.py" "${EXPORT_ARGS[@]}"; then
                REAL_LINES=$(count_lines "${REAL_OUTPUT}")
                ok "${REAL_LINES} ejemplos reales exportados"
            else
                warn "export_cycles.py terminó con error — continuando sin ciclos reales"
                SKIP_EXPORT=true
            fi
        fi
    fi
else
    log "  Saltando exportación (--skip-export)"
fi

# ---------------------------------------------------------------------------
# Paso 3 — Merge + deduplicación
# ---------------------------------------------------------------------------

step "3/4 — Merge y deduplicación de datasets"

SOURCES=()
[[ "$SKIP_SYNTHETIC" == "false" && -f "$SYNTHETIC_OUTPUT" ]] && SOURCES+=("${SYNTHETIC_OUTPUT}")
[[ "$SKIP_EXPORT"    == "false" && -f "$REAL_OUTPUT"      ]] && SOURCES+=("${REAL_OUTPUT}")

if [[ ${#SOURCES[@]} -eq 0 && "$DRY_RUN" == "false" ]]; then
    fail "No hay datasets para combinar. Verifica ANTHROPIC_API_KEY y DATABASE_URL."
elif [[ ${#SOURCES[@]} -eq 0 ]]; then
    log "  [DRY-RUN] sin fuentes — verificación de estructura completada"
fi

if [[ "$DRY_RUN" == "true" ]]; then
    log "  [DRY-RUN] omitiendo merge"
else
    # Concatenar y deduplicar por contenido del mensaje user (primera línea de cada ejemplo)
    cat "${SOURCES[@]}" > "${MERGED_OUTPUT}.tmp"

    # Deduplicar: ordenar por hash de la primera entrada de messages.content
    # Usamos Python inline para máxima portabilidad
    python3 - "${MERGED_OUTPUT}.tmp" "${MERGED_OUTPUT}" <<'PYEOF'
import json, sys, hashlib

input_file, output_file = sys.argv[1], sys.argv[2]
seen = set()
written = 0

with open(input_file) as fin, open(output_file, "w") as fout:
    for line in fin:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        messages = obj.get("messages", [])
        # Dedup por hash de (user_msg + assistant_msg[:200]) para no eliminar
        # distintos tipos de ejemplo (analyze_fr, generate_sdd, qa_review) que
        # comparten el mismo FR como user message pero tienen respuestas distintas
        user_content   = messages[0].get("content", "") if len(messages) > 0 else ""
        asst_content   = messages[1].get("content", "")[:200] if len(messages) > 1 else ""
        key_content    = user_content + "|" + asst_content
        key = hashlib.md5(key_content.encode()).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        written += 1

print(f"  {written} ejemplos únicos en dataset final")
PYEOF

    rm -f "${MERGED_OUTPUT}.tmp"

    MERGED_LINES=$(count_lines "${MERGED_OUTPUT}")
    ok "${MERGED_LINES} ejemplos en dataset final (sin duplicados)"
fi

# ---------------------------------------------------------------------------
# Paso 4 — Validación del dataset
# ---------------------------------------------------------------------------

step "4/4 — Validación del dataset"

VALIDATE_SCRIPT="${SCRIPT_DIR}/validate_dataset.py"

if [[ ! -f "$VALIDATE_SCRIPT" ]]; then
    warn "validate_dataset.py no encontrado — saltando validación"
elif [[ "$DRY_RUN" == "true" ]]; then
    log "  [DRY-RUN] omitiendo validación"
elif [[ ! -f "$MERGED_OUTPUT" ]]; then
    warn "Dataset merged no generado — saltando validación"
else
    if python3 "${VALIDATE_SCRIPT}" --input "${MERGED_OUTPUT}"; then
        ok "Validación completada sin errores"
    else
        warn "Validación reportó problemas — revisar antes de submit"
    fi
fi

# ---------------------------------------------------------------------------
# Reporte final
# ---------------------------------------------------------------------------

step "Reporte final"

{
    echo "OVD Platform — Pipeline SM1 — $(date '+%Y-%m-%d %H:%M:%S')"
    echo "============================================================"
    echo ""
    echo "Configuración:"
    echo "  Sintéticos solicitados : ${SYNTH_COUNT}"
    echo "  min_qa_score           : ${MIN_QA_SCORE}"
    echo "  require_approval       : ${REQUIRE_APPROVAL}"
    echo "  exclude_auto_approve   : ${EXCLUDE_AUTO_APPROVE}"
    echo "  org_id filter          : ${ORG_ID:-todos}"
    echo ""
    echo "Resultados:"

    if [[ -f "$SYNTHETIC_OUTPUT" ]]; then
        echo "  synthetic.jsonl        : $(count_lines "$SYNTHETIC_OUTPUT") ejemplos"
    else
        echo "  synthetic.jsonl        : no generado"
    fi

    if [[ -f "$REAL_OUTPUT" ]]; then
        echo "  real_cycles.jsonl      : $(count_lines "$REAL_OUTPUT") ejemplos"
    else
        echo "  real_cycles.jsonl      : no generado"
    fi

    if [[ -f "$MERGED_OUTPUT" ]]; then
        MERGED_FINAL=$(count_lines "$MERGED_OUTPUT")
        SIZE_KB=$(du -k "$MERGED_OUTPUT" | cut -f1)
        echo "  merged.jsonl           : ${MERGED_FINAL} ejemplos (${SIZE_KB} KB)"
        echo ""
        echo "Dataset listo para fine-tuning: ${MERGED_OUTPUT}"
        echo ""
        if [[ "$MERGED_FINAL" -lt 100 ]]; then
            echo "  ADVERTENCIA: dataset pequeño (< 100 ejemplos). Anthropic recomienda >= 100."
        elif [[ "$MERGED_FINAL" -lt 300 ]]; then
            echo "  NOTA: dataset aceptable. Para mejores resultados apuntar a 300+ ejemplos."
        else
            echo "  Dataset suficiente para fine-tuning de calidad."
        fi
    else
        echo "  merged.jsonl           : no generado (dry-run o errores)"
    fi

    echo ""
    echo "Siguiente paso:"
    echo "  Subir dataset a Anthropic fine-tuning console o usar la API:"
    echo "  https://console.anthropic.com/settings/models"
} | tee "${REPORT_FILE}"

log "Pipeline completado. Reporte: ${REPORT_FILE}"
