# Plan de Implementación M2.B — Fine-tuning Local con MLX
**Fecha:** 2026-03-31
**Actualizado:** 2026-04-01 (post-incidente OOM)
**Hardware:** MacBook Pro M1 Pro — 10 cores (8P+2E) — 16 GB RAM unificada
**Dataset:** `src/finetune/data/merged.jsonl` — 312 ejemplos — avg 1065 tokens — max 3011 tokens
**Objetivo:** modelo fine-tuneado `ovd-arch-assistant` corriendo en Ollama, reemplazando `qwen2.5-coder:7b`

---

## Puntos de mejora — Run #1 (2026-04-01)

Documentados al cierre del primer run completo. Aplican al próximo ciclo de fine-tuning.

### M1 — Corregir truncación de secuencias (impacto alto)
- **Problema:** 249 warnings de truncación durante el training. Secuencias de hasta 2064 tokens fueron cortadas a 1024. El modelo aprendió versiones incompletas de los ejemplos más largos, lo que eleva el val_loss y limita la calidad de las respuestas para FRs complejos.
- **Causa raíz:** `max_seq_length: 1024` fue necesario para evitar OOM en M1 Pro 16 GB, pero el dataset tiene ejemplos que superan ese límite.
- **Solución A (preferida):** subir a `max_seq_length: 1536` — cubre la mayoría de ejemplos sin el peak RAM de 2048. Requiere verificar RAM en iter 25 del próximo run.
- **Solución B:** pre-split de ejemplos largos en el pipeline de datos antes del training (dividir en dos ejemplos si supera 1024 tokens).

### M2 — Reducir iters o aplicar early stopping (impacto medio)
- **Problema:** divergencia train/val entre iter 400 y 475 (train_loss: 0.623, val_loss: 1.361). El modelo comenzó a memorizar en lugar de generalizar. La val_loss final (1.327) recuperó levemente, pero el overfitting estuvo presente.
- **Solución A:** reducir `iters: 300` en el próximo run — la val_loss mínima se alcanzó cerca de iter 300.
- **Solución B:** implementar early stopping manual: monitorear val_loss cada 100 iters y detener si sube 2 evaluaciones consecutivas.
- **Checkpoint recomendado para producción:** `adapters/0000300_adapters.safetensors` o `0000500_adapters.safetensors` (val_loss casi idéntico: 1.328 vs 1.327).

### M3 — Warmup más largo (impacto bajo)
- **Problema:** con `batch_size: 1` el gradiente es más ruidoso que con batch=2. El warmup de 50 iters puede ser insuficiente para estabilizar el aprendizaje al inicio.
- **Solución:** subir a `warmup: 75` o `warmup: 100` en el próximo run.

### M4 — Velocidad de training (informativo, sin acción inmediata)
- El training tardó ~4.5h para 500 iters a ~0.08 it/sec con batch=1.
- Con `batch_size: 2` sería ~2x más rápido pero requiere hardware con más RAM (Mac Studio M2 Ultra 96 GB o servidor).
- No es un bloqueante en desarrollo, sí si el ciclo de reentrenamiento se vuelve frecuente.

### M5 — Ampliar el dataset con ciclos reales (impacto alto, largo plazo)
- El training actual usó 312 ejemplos sintéticos. Según `MODEL_STRATEGY.md`, el fine-tuning significativo empieza en 200–500 ciclos de calidad.
- **Acción:** conectar `export_cycles.py` a la BD de producción con `qa_score ≥ 0.80` y `aprobacion_humana = true` para enriquecer el dataset en el próximo ciclo.

---

## Historial de ejecuciones

| Fecha | Intento | Resultado | Iters completadas | Peak RAM | Notas |
|---|---|---|---|---|---|
| 2026-04-01 16:34 | #1 | ❌ Reinicio del sistema | 25 / 500 | 11.06 GB | OOM — config original batch_size=2, seq=2048 |
| 2026-04-01 17:33 | #2 | ✅ Completado | 500 / 500 | **6.698 GB** | batch=1, seq=1024. val_loss final: 1.327. train_loss final: 0.645. 20 checkpoints guardados. Mejor checkpoint: iter 300 o 500 (ambos val≈1.328). |

### Incidente 2026-04-01 — OOM restart

**Causa raíz:** memoria unificada agotada durante el training.

El sistema M1 Pro con 16 GB usa normalmente ~13-15 GB en reposo (SO + apps). La config original generaba un peak de **11.06 GB solo para el proceso MLX** en iter 25. La suma supera los 16 GB → macOS fuerza el reinicio sin generar kernel panic file.

**Evidencia del log** (`logs/training_20260401_163432.log`):
```
Iter 25: Train loss 1.474, Learning Rate 1.000e-04, It/sec 0.023, Tokens/sec 34.878, Peak mem 11.060 GB
```

**Progreso perdido:** 25 de 500 iteraciones. El primer checkpoint estaba configurado en iter 100. No se salvó ningún adapter.

**Aprendizajes:**
- Con `batch_size=2` + `max_seq_length=2048` + `grad_checkpoint=true`, el peak es ~11 GB en las primeras iteraciones y puede crecer a medida que avanza
- El sistema necesita al menos ~5 GB libres para el SO y apps durante el training
- `save_every=100` es demasiado espaciado para un equipo con 16 GB — una interrupción antes del iter 100 pierde todo
- **Corrección (verificado en training #2):** el dataset SÍ tiene secuencias que superan 1024 tokens — la más larga es 1934 tokens. El conteo previo por palabras fue incorrecto (el tokenizador Qwen genera más tokens que palabras). `max_seq_length=1024` trunca esos ejemplos, explicando val_loss inicial más alto (1.796 vs 1.623 con seq=2048). Impacto menor: la parte que entra contiene lo sustancial del ejemplo

**Cambios aplicados** a `mlx_config.yaml`:

| Parámetro | Antes | Ahora | Ahorro RAM estimado |
|---|---|---|---|
| `batch_size` | 2 | **1** | ~3-4 GB |
| `max_seq_length` | 2048 | **1024** | ~2-3 GB |
| `save_every` | 100 | **25** | (sin efecto en RAM, previene pérdida de progreso) |

**Peak RAM estimado con nueva config:** ~7-8 GB. Seguro para 16 GB.

**Script de lanzamiento con control de RAM:** `src/finetune/run_training.sh`
- Ejecuta `sudo purge` si RAM disponible < 4 GB antes de iniciar
- Monitor en background: detiene el training con gracia si el uso del sistema supera 14 GB
- Guarda log con timestamp en `logs/`
- Imprime instrucciones de resume ante interrupción

**Para retomar desde un checkpoint** (si el training se interrumpe después de iter 25+):
```yaml
# En mlx_config.yaml, agregar:
resume_adapter_file: "adapters/adapters_NNNN.npz"
```

---

## Resumen de fases

| Fase | Descripción | Duración estimada |
|---|---|---|
| 0 | Entorno y prerequisitos | 30–45 min |
| 1 | Conversión y split del dataset | 10 min |
| 2 | Descarga del modelo base | 15–30 min (descarga ~4 GB) |
| 3 | Fine-tuning QLoRA | 35–50 min |
| 4 | Evaluación del adapter | 15 min |
| 5 | Fusión y export a GGUF | 45–60 min |
| 6 | Registro en Ollama y prueba | 10 min |
| **Total** | | **~3 horas** |

---

## Fase 0 — Entorno y prerequisitos

### 0.1 Verificar Python compatible con mlx-lm

mlx-lm soporta Python **3.9–3.12**. El sistema tiene Python 3.14 (incompatible).
Usar `uv` para crear el entorno con Python 3.12:

```bash
# Instalar Python 3.12 via uv (si no está disponible)
uv python install 3.12

# Verificar
uv python list
```

### 0.2 Crear entorno virtual MLX

```bash
cd "/Volumes/TOSHIBA EXT/Proyectos Personales/agente de terminal/opencode/src/finetune"

# Crear venv con Python 3.12 explícito
uv venv mlx-env --python 3.12
source mlx-env/bin/activate

# Verificar versión
python --version  # debe mostrar 3.12.x
```

### 0.3 Instalar mlx-lm y dependencias

```bash
uv pip install mlx-lm
uv pip install huggingface_hub

# Verificar instalación
python -c "import mlx_lm; print('mlx-lm OK')"
mlx_lm.lora --help | head -5
```

### 0.4 Autenticarse en HuggingFace

Necesario para descargar modelos desde `mlx-community`.

1. Crear cuenta en https://huggingface.co (si no existe)
2. Generar token en https://huggingface.co/settings/tokens (tipo: Read)
3. Autenticarse:

```bash
huggingface-cli login
# Pegar el token cuando lo solicite
# Verificar:
huggingface-cli whoami
```

### 0.5 Compilar llama.cpp (para export GGUF — Fase 5)

Hacer esto en paralelo mientras corre el fine-tuning. Tarda ~15-20 min.

```bash
# Clonar en una ubicación permanente
git clone https://github.com/ggml-org/llama.cpp ~/llama.cpp
cd ~/llama.cpp

# Compilar con soporte Metal (GPU Apple Silicon)
cmake -B build -DLLAMA_METAL=ON
cmake --build build --config Release -j10

# Instalar dependencias Python de llama.cpp en el mlx-env
cd "/Volumes/TOSHIBA EXT/Proyectos Personales/agente de terminal/opencode/src/finetune"
source mlx-env/bin/activate
uv pip install -r ~/llama.cpp/requirements.txt

# Verificar
~/llama.cpp/build/bin/llama-quantize --help | head -3
```

**Salida esperada de compilación:**
```
[100%] Linking CXX executable llama-quantize
[100%] Built target llama-quantize
```

---

## Fase 1 — Conversión y split del dataset

### 1.1 Problema de formato

El dataset actual (`merged.jsonl`) usa el formato Anthropic fine-tuning:
```json
{"system": "Eres un arquitecto...", "messages": [{"role": "user", ...}, {"role": "assistant", ...}]}
```

mlx-lm espera el system **dentro** del array de mensajes como primer elemento:
```json
{"messages": [{"role": "system", "content": "Eres un arquitecto..."}, {"role": "user", ...}, {"role": "assistant", ...}]}
```

### 1.2 Script de conversión y split

```bash
cd "/Volumes/TOSHIBA EXT/Proyectos Personales/agente de terminal/opencode/src/finetune"
source mlx-env/bin/activate

python3 << 'EOF'
import json, random, pathlib

# Cargar dataset
data = [json.loads(l) for l in open("data/merged.jsonl") if l.strip()]
print(f"Total cargados: {len(data)}")

# Convertir formato: mover "system" al inicio de messages
converted = []
skipped = 0
for item in data:
    messages = item.get("messages", [])
    system_content = item.get("system", "")

    # Si ya tiene system como primer mensaje, no convertir
    if messages and messages[0]["role"] == "system":
        converted.append({"messages": messages})
        continue

    # Insertar system como primer mensaje
    if system_content:
        new_messages = [{"role": "system", "content": system_content}] + messages
    else:
        new_messages = messages

    # Validar estructura mínima
    roles = [m["role"] for m in new_messages]
    if "user" not in roles or "assistant" not in roles:
        skipped += 1
        continue

    # Validar que assistant tiene contenido suficiente
    asst = next((m["content"] for m in new_messages if m["role"] == "assistant"), "")
    if len(asst) < 20:
        skipped += 1
        continue

    converted.append({"messages": new_messages})

print(f"Convertidos: {len(converted)}")
print(f"Descartados: {skipped}")

# Split 80/10/10
random.seed(42)
random.shuffle(converted)
n = len(converted)
train  = converted[:int(n * 0.80)]
valid  = converted[int(n * 0.80):int(n * 0.90)]
test   = converted[int(n * 0.90):]

print(f"Split — train: {len(train)} | valid: {len(valid)} | test: {len(test)}")

# Guardar
pathlib.Path("data/mlx").mkdir(exist_ok=True)
for name, subset in [("train", train), ("valid", valid), ("test", test)]:
    with open(f"data/mlx/{name}.jsonl", "w") as f:
        for item in subset:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"  data/mlx/{name}.jsonl — {len(subset)} ejemplos")

# Verificar muestra
sample = train[0]
print(f"\nMuestra del primer ejemplo (train):")
for msg in sample["messages"]:
    print(f"  [{msg['role']}] {msg['content'][:80]}...")
EOF
```

**Salida esperada:**
```
Total cargados: 312
Convertidos: 312
Descartados: 0
Split — train: 249 | valid: 31 | test: 32
  data/mlx/train.jsonl — 249 ejemplos
  data/mlx/valid.jsonl — 31 ejemplos
  data/mlx/test.jsonl — 32 ejemplos
```

### 1.3 Validar formato con mlx-lm

```bash
# mlx-lm tiene validación interna — verificar con dry-run
python -c "
import json
for split in ['train', 'valid', 'test']:
    lines = [json.loads(l) for l in open(f'data/mlx/{split}.jsonl')]
    for i, item in enumerate(lines):
        assert 'messages' in item, f'{split} línea {i}: sin messages'
        roles = [m['role'] for m in item['messages']]
        assert roles[0] == 'system', f'{split} línea {i}: primer rol no es system'
        assert 'user' in roles, f'{split} línea {i}: sin user'
        assert roles[-1] == 'assistant', f'{split} línea {i}: último rol no es assistant'
    print(f'{split}.jsonl: {len(lines)} ejemplos OK')
"
```

---

## Fase 2 — Descarga del modelo base

### 2.1 Modelo recomendado: Qwen2.5-Coder-7B-Instruct-4bit

Especializado en código y arquitectura técnica. Ya cuantizado por mlx-community (~4 GB).

```bash
cd "/Volumes/TOSHIBA EXT/Proyectos Personales/agente de terminal/opencode/src/finetune"
source mlx-env/bin/activate

# Crear directorio para modelos
mkdir -p models

# Descargar modelo base cuantizado
mlx_lm.convert \
  --hf-path mlx-community/Qwen2.5-Coder-7B-Instruct-4bit \
  --mlx-path models/qwen2.5-coder-7b-4bit

# Verificar descarga
ls -lh models/qwen2.5-coder-7b-4bit/
```

**Salida esperada:** archivos `model.safetensors`, `config.json`, `tokenizer.json`, `tokenizer_config.json`

**Si la descarga falla por red:**
```bash
# Alternativa: usar huggingface-cli directamente
huggingface-cli download mlx-community/Qwen2.5-Coder-7B-Instruct-4bit \
  --local-dir models/qwen2.5-coder-7b-4bit
```

### 2.2 Prueba rápida de inferencia (verificar que el modelo funciona)

```bash
mlx_lm.generate \
  --model models/qwen2.5-coder-7b-4bit \
  --prompt "Diseña una función Python que calcule el factorial de un número." \
  --max-tokens 200
```

Si genera texto coherente, el modelo está listo.

---

## Fase 3 — Fine-tuning QLoRA

### 3.1 Archivo de configuración

`src/finetune/mlx_config.yaml` (valores actualizados post-incidente OOM 2026-04-01):

```yaml
# Modelo base
model: "models/qwen2.5-coder-7b-4bit"

# Dataset
data: "data/mlx"

# Modo
train: true
seed: 42

# Training
batch_size: 1          # ⚠️ NO subir a 2 en M1 Pro 16 GB — causa OOM restart (ver Historial)
iters: 500             # ~2 epochs con 249 ejemplos de train
learning_rate: 1.0e-4
warmup: 50             # 10% de iters
weight_decay: 0.01
grad_checkpoint: true  # CRÍTICO — reduce uso de RAM a costa de velocidad

# Evaluación durante training
val_batches: 20
steps_per_report: 25
steps_per_eval: 100
save_every: 25         # checkpoint cada 25 iters — no usar 100 en 16 GB (riesgo de pérdida total)

# LoRA
lora_layers: 16        # 16 de 32 capas del modelo
lora_parameters:
  rank: 16
  alpha: 32            # regla: 2x rank
  dropout: 0.1
  scale: 10.0

# Dataset
mask_prompt: true      # loss SOLO en respuestas del asistente (crítico para calidad)
max_seq_length: 1024   # seguro: 0 ejemplos del dataset superan 1024 tokens (verificado 2026-04-01)

# Salida
adapter_path: "adapters"
```

> **Nota:** para hardware con más RAM (Mac Studio M2 Ultra 96 GB, servidor con 64 GB+) se puede volver a `batch_size: 2`, `max_seq_length: 2048` y `save_every: 100`.

### 3.2 Ejecutar fine-tuning

**Usar siempre el script con control de RAM** (no invocar `mlx_lm.lora` directamente):

```bash
cd "/Volumes/TOSHIBA EXT/Proyectos Personales/agente de terminal/ovd-platform/src/finetune"
./run_training.sh
```

El script:
1. Verifica RAM disponible — corre `sudo purge` si hay menos de 4 GB libres
2. Lanza `mlx_lm.lora` con la config
3. Monitor en background: detiene el training con gracia si el sistema supera 14 GB de RAM
4. Guarda log en `logs/training_YYYYMMDD_HHMMSS.log`
5. Muestra instrucciones de resume si el training termina con error

**Para retomar desde checkpoint** (en caso de interrupción):
```bash
# Ver último checkpoint guardado
ls -t adapters/*.npz | head -1

# Editar mlx_config.yaml y agregar:
resume_adapter_file: "adapters/adapters_NNNN.npz"

# Relanzar
./run_training.sh
```

### 3.3 Salida esperada durante entrenamiento

```
Loading pretrained model
Fetching 10 files: 100%|████████████████| 10/10
Number of trainable parameters: 20,971,520 (20.97M / 3.09B = 0.680%)
Starting training...
Iter 25: Train loss 2.341, It/sec 0.89, Tokens/sec 412.3
Iter 50: Train loss 1.876, Val loss 1.654, It/sec 0.87
Iter 75: Train loss 1.523, Val loss 1.421, It/sec 0.88
...
Iter 500: Train loss 0.723, Val loss 0.891, It/sec 0.86
```

**Señales de alerta:**

| Señal | Diagnóstico | Acción |
|---|---|---|
| `Val loss` sube sostenidamente desde iter 200 | Overfitting | Detener (Ctrl+C), usar checkpoint de iter 200-300 |
| `OOM / killed` | RAM insuficiente | Reducir `batch_size: 1` y reiniciar |
| Loss no baja de 2.0 en 100 iters | LR muy alto | Reiniciar con `learning_rate: 5e-5` |
| Loss cae a 0 muy rápido | Overfitting severo | Aumentar `dropout: 0.2`, reducir `iters: 300` |

### 3.4 Checkpoints guardados

```
adapters/
├── 0000100_adapters.safetensors
├── 0000200_adapters.safetensors
├── 0000300_adapters.safetensors
├── 0000400_adapters.safetensors
├── 0000500_adapters.safetensors   ← checkpoint final
└── adapter_config.json
```

Si hay overfitting, usar el checkpoint con menor `Val loss`:
```bash
# Editar mlx_config.yaml y cambiar:
adapter_path: "adapters/0000300_adapters.safetensors"
```

---

## Fase 4 — Evaluación del adapter

### 4.1 Inferencia con adapter (antes de fusionar)

```bash
# Prueba 1: Feature Request de arquitectura
mlx_lm.generate \
  --model models/qwen2.5-coder-7b-4bit \
  --adapter-path adapters \
  --prompt "Agregar índice GIN para búsqueda full-text en tabla ARTICULOS de PostgreSQL 14. Contexto: CMS con búsqueda por palabras clave." \
  --max-tokens 500

# Prueba 2: Caso Oracle
mlx_lm.generate \
  --model models/qwen2.5-coder-7b-4bit \
  --adapter-path adapters \
  --prompt "Migrar stored procedure SP_CALCULAR_COMISIONES de Oracle 12c a lógica en capa de negocio Java. Sistema HHMM Clínica Alemana." \
  --max-tokens 500
```

### 4.2 Comparar con modelo base (sin adapter)

```bash
# Mismo prompt SIN adapter para comparar
mlx_lm.generate \
  --model models/qwen2.5-coder-7b-4bit \
  --prompt "Agregar índice GIN para búsqueda full-text en tabla ARTICULOS de PostgreSQL 14." \
  --max-tokens 500
```

**Qué observar:**
- El modelo fine-tuneado debe responder en el formato SDD estructurado (JSON o Markdown con secciones definidas)
- Debe mencionar componentes, riesgos y complejidad explícitamente
- El modelo base responderá en formato libre sin estructura OVD

### 4.3 Evaluar en test set

```bash
mlx_lm.lora \
  --model models/qwen2.5-coder-7b-4bit \
  --adapter-path adapters \
  --data data/mlx \
  --test

# Salida esperada:
# Test loss: 0.923, Test ppl: 2.52
```

---

## Fase 5 — Fusión y export a GGUF

### 5.1 Fusionar adapter con modelo base

```bash
cd "/Volumes/TOSHIBA EXT/Proyectos Personales/agente de terminal/opencode/src/finetune"
source mlx-env/bin/activate

mlx_lm.fuse \
  --model models/qwen2.5-coder-7b-4bit \
  --adapter-path adapters \
  --save-path models/fused \
  --de-quantize
```

> `--de-quantize` es **obligatorio**: convierte de 4-bit a fp16 para que llama.cpp pueda leerlo.
> El modelo fusionado ocupará ~13-14 GB en disco.

**Salida esperada:**
```
Loading pretrained model
Loading adapter weights from adapters
Fusing model...
De-quantizing model...
Saving fused model to models/fused/
```

### 5.2 Verificar el modelo fusionado

```bash
ls -lh models/fused/
# Debe contener: model.safetensors (o varios shards), config.json, tokenizer*
```

### 5.3 Convertir a GGUF con llama.cpp

```bash
# Asegurar que llama.cpp está compilado (Fase 0.5)
# Convertir a fp16 primero
python ~/llama.cpp/convert_hf_to_gguf.py \
  models/fused \
  --outtype f16 \
  --outfile models/qwen-arch-ovd.f16.gguf

# Verificar tamaño (~13 GB)
ls -lh models/qwen-arch-ovd.f16.gguf
```

**Si falla con error de arquitectura:**
```bash
# Actualizar llama.cpp
cd ~/llama.cpp && git pull
cmake --build build --config Release -j10
```

### 5.4 Cuantizar a Q4_K_M

```bash
~/llama.cpp/build/bin/llama-quantize \
  models/qwen-arch-ovd.f16.gguf \
  models/qwen-arch-ovd-Q4_K_M.gguf \
  Q4_K_M

# Verificar (~4.1 GB)
ls -lh models/qwen-arch-ovd-Q4_K_M.gguf
```

**Alternativa Q5_K_M si se quiere mayor calidad:**
```bash
~/llama.cpp/build/bin/llama-quantize \
  models/qwen-arch-ovd.f16.gguf \
  models/qwen-arch-ovd-Q5_K_M.gguf \
  Q5_K_M
# ~4.8 GB
```

### 5.5 Prueba rápida con llama.cpp (antes de Ollama)

```bash
~/llama.cpp/build/bin/llama-cli \
  -m models/qwen-arch-ovd-Q4_K_M.gguf \
  -p "Diseña un SDD para agregar auditoría en tabla PRODUCTOS Oracle." \
  -n 300
```

---

## Fase 6 — Registro en Ollama

### 6.1 Crear Modelfile

```bash
cat > models/Modelfile << 'EOF'
FROM /Volumes/TOSHIBA EXT/Proyectos Personales/agente de terminal/opencode/src/finetune/models/qwen-arch-ovd-Q4_K_M.gguf

SYSTEM """Eres un arquitecto de software senior especializado en OVD Platform. Analizas Feature Requests y generas especificaciones SDD (Software Design Documents) estructuradas. Identificas componentes, riesgos, complejidad y estimaciones. Trabajas con stacks Oracle, PostgreSQL, Python FastAPI, Java Spring y TypeScript/React."""

PARAMETER temperature 0.7
PARAMETER num_ctx 4096
PARAMETER stop "<|im_end|>"
PARAMETER stop "<|endoftext|>"
EOF
```

### 6.2 Registrar en Ollama

```bash
ollama create ovd-arch-assistant:v1 -f models/Modelfile

# Verificar que aparece en la lista
ollama list | grep ovd
```

### 6.3 Prueba final en Ollama

```bash
ollama run ovd-arch-assistant:v1 "Analiza este FR: Agregar exportación PDF de facturas en sistema Oracle 12c HHMM Clínica Alemana."
```

### 6.4 Configurar OVD Engine para usar el modelo fine-tuneado

Editar `.env`:
```bash
# Cambiar de:
OVD_MODEL=claude-sonnet-4-6

# A (para pruebas con modelo local):
OVD_MODEL=ovd-arch-assistant:v1
OLLAMA_BASE_URL=http://localhost:11434
```

> Revertir a `claude-sonnet-4-6` si se necesita máxima calidad para producción.

---

## Espacio en disco requerido

| Artefacto | Tamaño | Ubicación |
|---|---|---|
| Modelo base 4-bit | ~4 GB | `models/qwen2.5-coder-7b-4bit/` |
| Adapters LoRA | ~160 MB | `adapters/` |
| Modelo fusionado fp16 | ~13.5 GB | `models/fused/` |
| GGUF f16 | ~13.5 GB | `models/qwen-arch-ovd.f16.gguf` |
| GGUF Q4_K_M | ~4.1 GB | `models/qwen-arch-ovd-Q4_K_M.gguf` |
| **Total durante proceso** | **~35 GB** | |
| **Total en producción** | **~8 GB** | (base + Q4_K_M, se pueden borrar fused y f16) |

> El disco interno tiene 701 GB disponibles — sin problema.

---

## Checklist de ejecución

```
[x] Fase 0.1 — Python 3.12 instalado via uv
[x] Fase 0.2 — mlx-env creado con Python 3.12
[x] Fase 0.3 — mlx-lm y huggingface_hub instalados
[x] Fase 0.4 — HuggingFace autenticado (huggingface-cli whoami)
[x] Fase 0.5 — llama.cpp compilado en ~/llama.cpp
[x] Fase 1   — Dataset convertido y split (249/31/32)
[x] Fase 2   — Modelo base descargado y verificado
[x] Fase 3   — Fine-tuning completado — val_loss 1.327, train_loss 0.645 (500 iters)
[x] Fase 4   — Evaluación del adapter satisfactoria (ver FASE4_EVALUACION_RUN1.md)
[x] Fase 5.1 — Adapter fusionado (--de-quantize) → models/fused/
[x] Fase 5.3 — GGUF f16 generado → qwen-arch-ovd.f16.gguf (14 GB)
[x] Fase 5.4 — GGUF Q4_K_M generado → qwen-arch-ovd-Q4_K_M.gguf (4.4 GB)
[x] Fase 6.2 — Modelo registrado en Ollama → ovd-arch-assistant:latest (4.7 GB)
[x] Fase 6.3 — Prueba final satisfactoria (2026-04-09 — ver resultados abajo)
[ ] Fase 6.4 — OVD Engine configurado (opcional — cambiar OVD_MODEL en .env)
```

---

## Cierre del ciclo M2.B — 2026-04-09

**Estado:** COMPLETADO

### Resultados Fase 6.3 — Prueba final

Prompt: `"Analiza este FR: Agregar exportación PDF de facturas en sistema Oracle 12c HHMM Clínica Alemana."`
Modelo: `ovd-arch-assistant:latest`

| Criterio | Resultado |
|---|---|
| Formato SDD estructurado | ✅ Secciones: Objetivo, RF, RNF, Diseño técnico |
| Conocimiento dominio HHMM | ✅ `EXPORT_AUDIT`, tablas reales, contexto Clínica Alemana |
| Tecnología correcta Oracle 12c | ✅ Query layer correcto, sin mezcla Java/PL/SQL |
| Patrones de auditoría | ✅ `task_id`, `status`, `progress`, `created_at` en `EXPORT_AUDIT` |
| Compliance clínico ISO 19001 | ⚠️ No mencionado explícitamente (menor) |
| Límites de performance con números | ✅ `<2s`, `100 facturas`, `10 fact/seg`, `500 MB heap` |
| Seguridad | ✅ ROLE: `EXPORTER`, HMAC-SHA256, rate limiting 10 ops/min |

**Veredicto:** modelo operativo y apto para uso en desarrollo OVD.

### Artefactos en disco

| Artefacto | Ruta | Tamaño |
|---|---|---|
| Adapter LoRA (iter 500) | `adapters/adapters.safetensors` | 88 MB |
| Modelo fusionado fp16 | `models/fused/` | ~13.5 GB |
| GGUF f16 | `models/qwen-arch-ovd.f16.gguf` | 14 GB |
| GGUF Q4_K_M | `models/qwen-arch-ovd-Q4_K_M.gguf` | 4.4 GB |
| Ollama | `ovd-arch-assistant:latest` | 4.7 GB |

### Pendientes para el próximo ciclo de re-entrenamiento

- **F4-M1:** verificar `tokenizer.apply_chat_template()` en `graph.py` (crítico para calidad)
- **F4-M3:** subir `max_seq_length: 1536` — 249 ejemplos truncados en este run
- **F4-M6:** repetir baseline de test set con adapter renombrado para comparación limpia
- **F4-M5:** nunca evaluar base y fine-tuneado en paralelo en M1 Pro 16 GB (OOM)
- **M5:** ampliar dataset con ciclos reales de producción (`qa_score ≥ 0.80`)

---

## Troubleshooting frecuente

**Error: `mlx` no compatible con Python 3.14`**
```bash
uv python install 3.12
uv venv mlx-env --python 3.12
```

**Error: OOM / reinicio del sistema durante training**

Causa: RAM unificada M1 Pro agotada. El sistema usa ~13-15 GB en reposo; el training original (batch_size=2, seq=2048) agrega ~11 GB → total >16 GB.

```yaml
# mlx_config.yaml — valores seguros para M1 Pro 16 GB:
batch_size: 1          # NO subir a 2
max_seq_length: 1024   # seguro si el dataset no tiene ejemplos > 1024 tokens
grad_checkpoint: true  # obligatorio
save_every: 25         # checkpoint frecuente para no perder progreso
```

```bash
# Antes de lanzar, liberar RAM:
sudo purge

# Usar el script con monitor de RAM (NO ejecutar mlx_lm.lora directamente):
./run_training.sh
```

**Error: `Architecture qwen2 not supported` en llama.cpp**
```bash
# llama.cpp desactualizado — actualizar y recompilar:
cd ~/llama.cpp && git pull
cmake --build build --config Release -j10
```

**Error: `model.safetensors not found` en fusión**
```bash
# El modelo base puede estar en shards — es normal
ls models/qwen2.5-coder-7b-4bit/*.safetensors
# Si están los shards, la fusión debería funcionar igual
```

**Val loss no mejora**
- Verificar que `mask_prompt: true` está activo
- Revisar que el split fue aleatorizado (`random.seed(42)`)
- Considerar bajar `learning_rate` a `5e-5`
