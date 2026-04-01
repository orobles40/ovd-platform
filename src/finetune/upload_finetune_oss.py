"""
OVD Platform — Pipeline Fine-tuning Open Source (GAP-013b)
Copyright 2026 Omar Robles

Fine-tunea modelos open source (Qwen, DeepSeek, Kimi, Llama, Mistral) con
los ciclos OVD acumulados en ovd_cycle_logs. Usa LoRA/QLoRA para training
eficiente. El modelo resultante se sirve via Ollama y se registra en el
Model Registry de la plataforma.

Herramientas soportadas:
  --tool unsloth      Unsloth (mas rapido, menor VRAM con QLoRA)
  --tool llamafactory LlamaFactory (mas modelos, UI web opcional)

Flujo:
  1. Lee el dataset JSONL (mismo formato que pipeline Anthropic)
  2. Convierte al formato de conversacion del tool seleccionado
  3. Aplica LoRA sobre el modelo base
  4. Guarda el adapter + modelo merged
  5. Convierte a .gguf y registra en Ollama (opcional)
  6. Registra el modelo en el Model Registry via API

Uso:
  python upload_finetune_oss.py \\
    --input data/ovd_cycles.jsonl \\
    --base-model unsloth/Qwen2.5-Coder-7B-Instruct \\
    --tool unsloth \\
    --output models/ovd-qwen-v1 \\
    --org-id mi-org \\
    --token $OVD_TOKEN

Variables de entorno:
  OVD_BRIDGE_URL   — URL del Bridge TypeScript (default: http://localhost:3000)
  HF_TOKEN         — HuggingFace token (para descargar modelos privados)
  CUDA_VISIBLE_DEVICES — GPU a usar (default: 0)

Requisitos (instalar con pip):
  unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git
  trl datasets peft transformers accelerate bitsandbytes llama-cpp-python httpx
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BRIDGE_URL = os.environ.get("OVD_BRIDGE_URL", "http://localhost:3000")

# Modelos base comunes (alias → HuggingFace repo)
BASE_MODEL_ALIASES = {
    "qwen2.5-coder-7b":  "unsloth/Qwen2.5-Coder-7B-Instruct",
    "qwen2.5-coder-14b": "unsloth/Qwen2.5-Coder-14B-Instruct",
    "qwen2.5-coder-32b": "unsloth/Qwen2.5-Coder-32B-Instruct",
    "deepseek-coder-6b": "unsloth/deepseek-coder-6.7b-instruct",
    "deepseek-coder-33b":"unsloth/DeepSeek-Coder-V2-Lite-Instruct",
    "llama3.1-8b":       "unsloth/Meta-Llama-3.1-8B-Instruct",
    "mistral-7b":        "unsloth/mistral-7b-instruct-v0.3",
    "phi-4-14b":         "unsloth/phi-4",
}


# ---------------------------------------------------------------------------
# Conversion de dataset
# ---------------------------------------------------------------------------

def load_cycles(jsonl_path: Path) -> list[dict]:
    cycles = []
    with jsonl_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                cycles.append(json.loads(line))
    return cycles


def cycles_to_conversations(cycles: list[dict], min_qa_score: int = 70) -> list[dict]:
    """
    Convierte ciclos OVD al formato de conversacion para SFT.

    Cada ciclo genera uno o mas ejemplos de entrenamiento:
      - Ejemplo 1: FR → analisis + SDD  (razonamiento)
      - Ejemplo 2: SDD → implementacion  (generacion de codigo)

    Solo incluye ciclos con qa_score >= min_qa_score para calidad del dataset.
    """
    conversations = []

    for cycle in cycles:
        qa = cycle.get("qa_result", {})
        score = qa.get("score", 0)
        if score < min_qa_score:
            continue

        fr = cycle.get("feature_request", "").strip()
        fr_analysis = cycle.get("fr_analysis", {})
        sdd = cycle.get("sdd", {})
        agent_results = cycle.get("agent_results", [])

        if not fr or not agent_results:
            continue

        fr_summary = fr_analysis.get("summary", "")
        sdd_content = sdd.get("content", "")
        agent_output = "\n\n".join(
            f"### Agente {r.get('agent', '?')}\n{r.get('output', '')}"
            for r in agent_results
            if r.get("output")
        )

        if not agent_output:
            continue

        # Ejemplo 1: FR → SDD
        if sdd_content:
            conversations.append({
                "conversations": [
                    {
                        "role": "system",
                        "content": (
                            "Eres un arquitecto de software experto en Spec-Driven Development. "
                            "Analiza el Feature Request y genera una especificacion SDD completa "
                            "con requirements, design, constraints y tasks."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Feature Request:\n{fr}",
                    },
                    {
                        "role": "assistant",
                        "content": (
                            f"## Analisis\n{fr_summary}\n\n"
                            f"## Especificacion SDD\n{sdd_content}"
                        ),
                    },
                ]
            })

        # Ejemplo 2: SDD → implementacion
        conversations.append({
            "conversations": [
                {
                    "role": "system",
                    "content": (
                        "Eres un ingeniero de software senior. "
                        "Implementa los artefactos definidos en el SDD aprobado. "
                        "Genera codigo limpio, bien comentado y siguiendo las restricciones del proyecto."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Feature Request:\n{fr}\n\n"
                        f"SDD Aprobado:\n{sdd_content or 'Ver analisis previo.'}"
                    ),
                },
                {
                    "role": "assistant",
                    "content": agent_output,
                },
            ]
        })

    return conversations


# ---------------------------------------------------------------------------
# Training con Unsloth
# ---------------------------------------------------------------------------

def train_unsloth(
    conversations: list[dict],
    base_model: str,
    output_dir: Path,
    epochs: int,
    lora_r: int,
    max_seq_len: int,
) -> dict:
    """
    Fine-tunea el modelo base con Unsloth + LoRA.
    Requiere GPU con CUDA. Usa QLoRA (4-bit) para minimizar VRAM.
    """
    try:
        from unsloth import FastLanguageModel
        from trl import SFTTrainer
        from transformers import TrainingArguments
        from datasets import Dataset
    except ImportError:
        print("ERROR: instala unsloth primero:")
        print("  pip install 'unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git'")
        print("  pip install trl datasets")
        sys.exit(1)

    print(f"\nCargando modelo base: {base_model}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=base_model,
        max_seq_length=max_seq_len,
        dtype=None,           # auto-detectar dtype
        load_in_4bit=True,    # QLoRA — reduce VRAM a la mitad
    )

    print(f"Aplicando LoRA (r={lora_r})...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=lora_r,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_alpha=lora_r * 2,
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    # Convertir conversaciones al formato de texto del tokenizer
    def format_conversation(example):
        msgs = example["conversations"]
        return {"text": tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)}

    ds = Dataset.from_list(conversations)
    ds = ds.map(format_conversation, remove_columns=["conversations"])

    print(f"\nDataset: {len(ds)} ejemplos")
    print(f"Entrenando por {epochs} epocas...\n")

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=ds,
        dataset_text_field="text",
        max_seq_length=max_seq_len,
        args=TrainingArguments(
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            warmup_steps=10,
            num_train_epochs=epochs,
            learning_rate=2e-4,
            fp16=True,
            logging_steps=10,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="cosine",
            output_dir=str(output_dir / "checkpoints"),
            save_strategy="epoch",
            report_to="none",
        ),
    )

    stats = trainer.train()
    training_loss = stats.training_loss

    print(f"\n  Training loss final: {training_loss:.4f}")

    # Guardar modelo merged (base + LoRA)
    merged_dir = output_dir / "merged"
    print(f"\nGuardando modelo merged en {merged_dir}...")
    model.save_pretrained_merged(str(merged_dir), tokenizer, save_method="merged_16bit")

    # Guardar en formato GGUF para Ollama
    gguf_path = output_dir / "model.gguf"
    print(f"Convirtiendo a GGUF: {gguf_path}...")
    model.save_pretrained_gguf(str(output_dir), tokenizer, quantization_method="q4_k_m")
    # Unsloth guarda como <output_dir>/model-unsloth-Q4_K_M.gguf
    gguf_candidates = list(output_dir.glob("*.gguf"))
    if gguf_candidates:
        gguf_path = gguf_candidates[0]

    return {
        "training_loss": training_loss,
        "model_path": str(merged_dir),
        "gguf_path": str(gguf_path) if gguf_path.exists() else None,
        "examples": len(ds),
    }


# ---------------------------------------------------------------------------
# Training con LlamaFactory
# ---------------------------------------------------------------------------

def train_llamafactory(
    conversations: list[dict],
    base_model: str,
    output_dir: Path,
    epochs: int,
    lora_r: int,
    max_seq_len: int,
) -> dict:
    """
    Fine-tunea usando LlamaFactory via su CLI (llamafactory-cli).
    Requiere LlamaFactory instalado: pip install llamafactory
    """
    import subprocess
    import tempfile

    # Guardar dataset en formato ShareGPT (que LlamaFactory acepta)
    ds_path = output_dir / "dataset.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    with ds_path.open("w") as f:
        json.dump(conversations, f, ensure_ascii=False, indent=2)

    # Crear archivo de configuracion YAML para LlamaFactory
    config = {
        "model_name_or_path": base_model,
        "stage": "sft",
        "do_train": True,
        "finetuning_type": "lora",
        "lora_rank": lora_r,
        "lora_alpha": lora_r * 2,
        "lora_target": "all",
        "dataset": "ovd_cycles",
        "dataset_dir": str(output_dir),
        "template": "qwen",
        "cutoff_len": max_seq_len,
        "max_samples": len(conversations),
        "overwrite_cache": True,
        "preprocessing_num_workers": 4,
        "output_dir": str(output_dir / "lora"),
        "logging_steps": 10,
        "save_steps": 100,
        "plot_loss": False,
        "overwrite_output_dir": True,
        "per_device_train_batch_size": 2,
        "gradient_accumulation_steps": 4,
        "learning_rate": "2e-4",
        "num_train_epochs": epochs,
        "lr_scheduler_type": "cosine",
        "warmup_ratio": 0.1,
        "bf16": True,
        "val_size": 0.1,
        "per_device_eval_batch_size": 1,
        "eval_strategy": "steps",
        "eval_steps": 100,
    }

    # LlamaFactory necesita el dataset registrado — crear dataset_info.json
    ds_info = {
        "ovd_cycles": {
            "file_name": "dataset.json",
            "formatting": "sharegpt",
            "columns": {"messages": "conversations"},
        }
    }
    with (output_dir / "dataset_info.json").open("w") as f:
        json.dump(ds_info, f)

    config_path = output_dir / "train_config.yaml"
    import yaml
    with config_path.open("w") as f:
        yaml.dump(config, f)

    print(f"\nLanzando LlamaFactory CLI...")
    result = subprocess.run(
        ["llamafactory-cli", "train", str(config_path)],
        capture_output=False,
        text=True,
    )

    if result.returncode != 0:
        print(f"ERROR: LlamaFactory retorno codigo {result.returncode}")
        sys.exit(1)

    model_path = str(output_dir / "lora")
    return {
        "training_loss": None,   # LlamaFactory escribe logs propios
        "model_path": model_path,
        "gguf_path": None,
        "examples": len(conversations),
    }


# ---------------------------------------------------------------------------
# Registro en Ollama
# ---------------------------------------------------------------------------

def register_in_ollama(gguf_path: str, model_name: str, ollama_url: str = "http://localhost:11434") -> bool:
    """
    Registra el modelo GGUF en Ollama creando un Modelfile y corriendo ollama create.
    """
    import subprocess

    modelfile_content = f"FROM {gguf_path}\n"
    modelfile_path = Path(gguf_path).parent / "Modelfile"
    modelfile_path.write_text(modelfile_content)

    print(f"\nRegistrando en Ollama como '{model_name}'...")
    result = subprocess.run(
        ["ollama", "create", model_name, "-f", str(modelfile_path)],
        capture_output=False,
        text=True,
    )

    if result.returncode == 0:
        print(f"  Modelo disponible: ollama run {model_name}")
        return True
    else:
        print(f"  Advertencia: no se pudo registrar en Ollama (codigo {result.returncode})")
        return False


# ---------------------------------------------------------------------------
# Registro en Model Registry del Bridge
# ---------------------------------------------------------------------------

def register_in_platform(
    org_id: str,
    token: str,
    pipeline: str,
    base_model: str,
    ft_model_id: str,
    serve_model_name: str,
    model_path: str,
    dataset_path: str,
    trained_on_cycles: int,
    training_loss: float | None,
    agent_role: str | None,
    project_id: str | None,
) -> dict | None:
    """Registra el modelo en el Model Registry via API del Bridge."""
    url = f"{BRIDGE_URL}/ovd/models/register"
    payload = {
        "pipeline": pipeline,
        "baseModel": base_model,
        "ftModelId": ft_model_id,
        "modelPath": model_path,
        "datasetPath": dataset_path,
        "trainedOnCycles": trained_on_cycles,
        "provider": "ollama",
        "serveModelName": serve_model_name,
    }
    if training_loss is not None:
        payload["trainingLoss"] = training_loss
    if agent_role:
        payload["agentRole"] = agent_role
    if project_id:
        payload["projectId"] = project_id

    try:
        res = httpx.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=15,
        )
        if res.is_success:
            data = res.json()
            print(f"\n  Modelo registrado en plataforma: {data.get('id')}")
            print(f"  Para activarlo: POST /ovd/models/{data.get('id')}/activate")
            return data
        else:
            print(f"\n  Advertencia: no se pudo registrar en plataforma ({res.status_code}): {res.text[:200]}")
    except Exception as exc:
        print(f"\n  Advertencia: error conectando a {BRIDGE_URL}: {exc}")
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fine-tuning OVD con modelos open source (Unsloth / LlamaFactory)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--input", required=True, help="Dataset JSONL validado (export_cycles.py output)")
    p.add_argument(
        "--base-model", default="qwen2.5-coder-7b",
        help=f"Modelo base. Alias: {', '.join(BASE_MODEL_ALIASES.keys())} o repo HuggingFace",
    )
    p.add_argument(
        "--tool", choices=["unsloth", "llamafactory"], default="unsloth",
        help="Herramienta de fine-tuning (default: unsloth)",
    )
    p.add_argument("--output", default="models/ovd-ft", help="Directorio de salida del modelo")
    p.add_argument("--epochs", type=int, default=3, help="Epocas de entrenamiento (default: 3)")
    p.add_argument("--lora-r", type=int, default=16, help="Rango LoRA (default: 16)")
    p.add_argument("--max-seq-len", type=int, default=2048, help="Longitud maxima de secuencia")
    p.add_argument("--min-qa-score", type=int, default=70, help="Score QA minimo para incluir ciclo (default: 70)")
    p.add_argument("--model-name", help="Nombre para registrar en Ollama (default: ovd-<base>-v<ts>)")
    p.add_argument("--no-ollama", action="store_true", help="No registrar en Ollama")
    p.add_argument("--org-id", default=os.environ.get("OVD_ORG_ID", ""), help="Org ID para registrar en plataforma")
    p.add_argument("--token", default=os.environ.get("OVD_TOKEN", ""), help="JWT para registrar en Model Registry")
    p.add_argument("--agent-role", choices=["frontend", "backend", "database", "devops", "qa", "security"],
                   help="Rol del agente al que aplica este modelo")
    p.add_argument("--project-id", help="Proyecto especifico (opcional, aplica a toda la org si no se indica)")
    p.add_argument("--dry-run", action="store_true", help="Solo convertir dataset, no entrenar")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Resolver alias de modelo base
    base_model = BASE_MODEL_ALIASES.get(args.base_model, args.base_model)
    model_name = args.model_name or f"ovd-{args.base_model}-v{int(time.time())}"

    print(f"\n{'='*60}")
    print(f"OVD Fine-tuning OSS Pipeline")
    print(f"{'='*60}")
    print(f"  Dataset:    {input_path}")
    print(f"  Base model: {base_model}")
    print(f"  Tool:       {args.tool}")
    print(f"  Output:     {output_dir}")
    print(f"  Epochs:     {args.epochs}")
    print(f"  LoRA r:     {args.lora_r}")
    print(f"  Min QA:     {args.min_qa_score}")
    print(f"  Model name: {model_name}")
    print(f"{'='*60}\n")

    # Cargar y convertir dataset
    print("Cargando ciclos OVD...")
    cycles = load_cycles(input_path)
    print(f"  Total ciclos: {len(cycles)}")

    conversations = cycles_to_conversations(cycles, min_qa_score=args.min_qa_score)
    print(f"  Ejemplos de entrenamiento generados: {len(conversations)}")

    if len(conversations) < 10:
        print(f"\nERROR: solo {len(conversations)} ejemplos — minimo 10 requeridos.")
        print("Reduce --min-qa-score o agrega mas ciclos al dataset.")
        sys.exit(1)

    # Guardar dataset convertido para referencia
    conv_path = output_dir / "conversations.json"
    with conv_path.open("w") as f:
        json.dump(conversations, f, ensure_ascii=False, indent=2)
    print(f"  Dataset convertido guardado en: {conv_path}")

    if args.dry_run:
        print("\n[DRY RUN] Conversion completada. Saliendo sin entrenar.")
        return

    # Entrenar
    t0 = time.time()
    if args.tool == "unsloth":
        result = train_unsloth(conversations, base_model, output_dir, args.epochs, args.lora_r, args.max_seq_len)
    else:
        result = train_llamafactory(conversations, base_model, output_dir, args.epochs, args.lora_r, args.max_seq_len)

    elapsed = time.time() - t0
    print(f"\n  Entrenamiento completado en {elapsed/60:.1f} min")
    print(f"  Loss final: {result['training_loss']}")
    print(f"  Modelo guardado en: {result['model_path']}")

    # Registrar en Ollama
    ollama_ok = False
    if not args.no_ollama and result.get("gguf_path"):
        ollama_ok = register_in_ollama(result["gguf_path"], model_name)
    elif not result.get("gguf_path"):
        print("\nNota: no se generó GGUF, no se puede registrar en Ollama automaticamente.")
        print("Usa llama.cpp convert para generar el GGUF manualmente.")

    # Registrar en Model Registry
    if args.org_id and args.token:
        register_in_platform(
            org_id=args.org_id,
            token=args.token,
            pipeline=args.tool,
            base_model=base_model,
            ft_model_id=model_name,
            serve_model_name=model_name if ollama_ok else "",
            model_path=result["model_path"],
            dataset_path=str(input_path),
            trained_on_cycles=result["examples"],
            training_loss=result.get("training_loss"),
            agent_role=args.agent_role,
            project_id=args.project_id,
        )
    else:
        print("\nNota: sin --org-id y --token no se registra en la plataforma.")
        print(f"  Registra manualmente con:")
        print(f"  POST /ovd/models/register  {{ pipeline: '{args.tool}', ftModelId: '{model_name}', ... }}")

    print(f"\n{'='*60}")
    print(f"Pipeline completado.")
    print(f"  Modelo: {model_name}")
    if ollama_ok:
        print(f"  Ollama: ollama run {model_name}")
    print(f"  Activa el modelo en la plataforma:")
    print(f"  POST /ovd/models/<id>/activate")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
