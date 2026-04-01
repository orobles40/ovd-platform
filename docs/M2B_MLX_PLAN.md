# Plan de Implementación M2.B — Fine-tuning Local con MLX
**Fecha:** 2026-03-31
**Hardware:** MacBook Pro M1 Pro — 10 cores (8P+2E) — 16 GB RAM unificada
**Dataset:** `src/finetune/data/merged.jsonl` — 312 ejemplos — avg 1065 tokens — max 3011 tokens
**Objetivo:** modelo fine-tuneado `ovd-arch-assistant` corriendo en Ollama, reemplazando `qwen2.5-coder:7b`

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

Crear `src/finetune/mlx_config.yaml`:

```yaml
# Modelo base
model: "models/qwen2.5-coder-7b-4bit"

# Dataset
data: "data/mlx"

# Modo
train: true
seed: 42

# Training
batch_size: 2          # conservador para 16 GB — subir a 4 si no hay OOM
iters: 500             # ~2 epochs con 249 ejemplos de train
learning_rate: 1.0e-4
warmup: 50             # 10% de iters
weight_decay: 0.01
grad_checkpoint: true  # CRÍTICO — reduce uso de RAM a costa de velocidad

# Evaluación durante training
val_batches: 20
steps_per_report: 25
steps_per_eval: 100
save_every: 100        # guardar checkpoint cada 100 iters

# LoRA
lora_layers: 16        # 16 de 32 capas del modelo
lora_parameters:
  rank: 16
  alpha: 32            # regla: 2x rank
  dropout: 0.1
  scale: 10.0

# Dataset
mask_prompt: true      # loss SOLO en respuestas del asistente (crítico para calidad)
max_seq_length: 2048   # cubre max 3011 tokens con truncación

# Salida
adapter_path: "adapters"
```

### 3.2 Ejecutar fine-tuning

**Antes de ejecutar:** cerrar Chrome, Slack y aplicaciones pesadas para liberar RAM.

```bash
cd "/Volumes/TOSHIBA EXT/Proyectos Personales/agente de terminal/opencode/src/finetune"
source mlx-env/bin/activate

mlx_lm.lora --config mlx_config.yaml 2>&1 | tee data/mlx/training.log
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
[ ] Fase 0.1 — Python 3.12 instalado via uv
[ ] Fase 0.2 — mlx-env creado con Python 3.12
[ ] Fase 0.3 — mlx-lm y huggingface_hub instalados
[ ] Fase 0.4 — HuggingFace autenticado (huggingface-cli whoami)
[ ] Fase 0.5 — llama.cpp compilado en ~/llama.cpp
[ ] Fase 1   — Dataset convertido y split (249/31/32)
[ ] Fase 2   — Modelo base descargado y verificado
[ ] Fase 3   — Fine-tuning completado (monitorear val_loss)
[ ] Fase 4   — Evaluación del adapter satisfactoria
[ ] Fase 5.1 — Adapter fusionado (--de-quantize)
[ ] Fase 5.3 — GGUF f16 generado
[ ] Fase 5.4 — GGUF Q4_K_M generado
[ ] Fase 6.2 — Modelo registrado en Ollama
[ ] Fase 6.3 — Prueba final satisfactoria
[ ] Fase 6.4 — OVD Engine configurado (opcional)
```

---

## Troubleshooting frecuente

**Error: `mlx` no compatible con Python 3.14`**
```bash
uv python install 3.12
uv venv mlx-env --python 3.12
```

**Error: `OOM` durante training**
```bash
# Reducir batch_size en mlx_config.yaml:
batch_size: 1
# Y asegurar grad_checkpoint: true
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
