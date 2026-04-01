"""
OVD Platform — Upload a Anthropic Fine-tuning API
Copyright 2026 Omar Robles

Sube un dataset JSONL validado a la Anthropic Fine-tuning API y
lanza un job de fine-tuning. Soporta polling del estado del job.

Uso:
  python upload_finetune.py --input data/ovd_cycles.jsonl
  python upload_finetune.py --input data/ovd_cycles.jsonl --job-id ftjob-xxx  # ver estado
  python upload_finetune.py --list  # listar jobs existentes

Variables requeridas:
  ANTHROPIC_API_KEY  — API key con permisos de fine-tuning

Referencia: https://docs.anthropic.com/en/docs/fine-tuning
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

import anthropic

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Modelo base a fine-tunear — solo haiku soporta fine-tuning actualmente
BASE_MODEL = os.environ.get("OVD_FINETUNE_BASE_MODEL", "claude-haiku-4-5-20251001")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_client() -> anthropic.Anthropic:
    if not API_KEY:
        print("ERROR: ANTHROPIC_API_KEY no configurada", file=sys.stderr)
        sys.exit(1)
    return anthropic.Anthropic(api_key=API_KEY)


def format_status(job: object) -> str:
    status = getattr(job, "status", "unknown")
    icons = {
        "pending":    "⏳",
        "running":    "🔄",
        "completed":  "✓",
        "failed":     "✗",
        "cancelled":  "⊘",
    }
    return f"{icons.get(status, '?')} {status}"


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------

def upload_and_train(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: archivo no encontrado: {input_path}", file=sys.stderr)
        sys.exit(1)

    client = get_client()
    size_kb = input_path.stat().st_size / 1024
    print(f"Dataset: {input_path} ({size_kb:.1f} KB)")

    # 1. Subir archivo de entrenamiento
    print("\nSubiendo dataset a Anthropic...")
    with input_path.open("rb") as f:
        file_response = client.beta.files.upload(
            file=(input_path.name, f, "application/jsonl"),
        )
    file_id = file_response.id
    print(f"  ✓ Archivo subido: {file_id}")

    # 2. Lanzar job de fine-tuning
    suffix = args.suffix or f"ovd-{int(time.time())}"
    print(f"\nLanzando job de fine-tuning...")
    print(f"  Modelo base:  {BASE_MODEL}")
    print(f"  Suffix:       {suffix}")

    # NOTA: La ruta exacta del SDK depende de la version del cliente Anthropic.
    # Verificar con: python -c "import anthropic; help(anthropic.Anthropic().fine_tuning)"
    # Si falla con AttributeError, el acceso al fine-tuning API puede requerir
    # acceso beta especial — contactar a Anthropic para habilitarlo.
    job = client.fine_tuning.models.jobs.create(
        training_file=file_id,
        model=BASE_MODEL,
        suffix=suffix,
        hyperparameters={
            "n_epochs": args.epochs,
        },
    )

    print(f"\n  ✓ Job creado: {job.id}")
    print(f"  Estado: {format_status(job)}")

    # Guardar job_id para referencia
    job_info = {
        "job_id": job.id,
        "file_id": file_id,
        "base_model": BASE_MODEL,
        "suffix": suffix,
        "status": getattr(job, "status", "pending"),
        "created_at": int(time.time()),
        "dataset": str(input_path),
    }
    job_log = Path("data/finetune_jobs.jsonl")
    job_log.parent.mkdir(parents=True, exist_ok=True)
    with job_log.open("a") as f:
        f.write(json.dumps(job_info) + "\n")
    print(f"  Job guardado en: {job_log}")

    if args.wait:
        poll_job(client, job.id)
    else:
        print(f"\nPara ver el estado del job:")
        print(f"  python upload_finetune.py --job-id {job.id}")


def _register_anthropic_model(job_id: str, ft_model_id: str | None, trained_tokens: int | None) -> None:
    """Registra el modelo Anthropic fine-tuneado en el Model Registry del Bridge."""
    bridge_url = os.environ.get("OVD_BRIDGE_URL", "http://localhost:3000")
    token = os.environ.get("OVD_TOKEN", "")
    org_id = os.environ.get("OVD_ORG_ID", "")

    if not (token and org_id and ft_model_id):
        print("\nNota: configura OVD_TOKEN y OVD_ORG_ID para registrar el modelo en la plataforma.")
        return

    try:
        import urllib.request
        payload = json.dumps({
            "pipeline": "anthropic",
            "baseModel": BASE_MODEL,
            "ftModelId": ft_model_id,
            "ftJobId": job_id,
            "trainedOnCycles": trained_tokens or 0,
            "provider": "anthropic",
            "serveModelName": ft_model_id,
        }).encode()
        req = urllib.request.Request(
            f"{bridge_url}/ovd/models/register",
            data=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read())
            print(f"  ✓ Modelo registrado en plataforma: {data.get('id')}")
            print(f"    Para activarlo: POST /ovd/models/{data.get('id')}/activate")
    except Exception as exc:
        print(f"  Nota: no se pudo registrar en plataforma: {exc}")


def poll_job(client: anthropic.Anthropic, job_id: str) -> None:
    print(f"\nEsperando job {job_id}...")
    while True:
        job = client.fine_tuning.models.jobs.retrieve(job_id)
        status = getattr(job, "status", "unknown")
        print(f"  {format_status(job)}", end="\r")

        if status == "completed":
            fine_tuned_model = getattr(job, "fine_tuned_model", None)
            trained_tokens = getattr(job, "trained_tokens", None)
            print(f"\n\n✓ Fine-tuning completado!")
            print(f"  Modelo: {fine_tuned_model}")
            print(f"\nAgrega a .env.local:")
            print(f"  OVD_MODEL={fine_tuned_model}")
            # Registrar en Model Registry si hay credenciales configuradas
            _register_anthropic_model(job_id, fine_tuned_model, trained_tokens)
            break
        elif status in ("failed", "cancelled"):
            error = getattr(job, "error", None)
            print(f"\n\n✗ Job {status}: {error}")
            sys.exit(1)

        time.sleep(30)


def check_job(args: argparse.Namespace) -> None:
    client = get_client()
    job = client.fine_tuning.models.jobs.retrieve(args.job_id)

    print(f"Job: {job.id}")
    print(f"Estado: {format_status(job)}")

    fine_tuned_model = getattr(job, "fine_tuned_model", None)
    if fine_tuned_model:
        print(f"Modelo: {fine_tuned_model}")
        print(f"\nPara usar el modelo fine-tuneado:")
        print(f"  OVD_MODEL={fine_tuned_model}  (en .env.local)")

    trained_tokens = getattr(job, "trained_tokens", None)
    if trained_tokens:
        print(f"Tokens entrenados: {trained_tokens:,}")


def list_jobs(args: argparse.Namespace) -> None:
    client = get_client()
    jobs = client.fine_tuning.models.jobs.list(limit=20)

    if not jobs.data:
        print("No hay jobs de fine-tuning.")
        return

    print(f"{'ID':<30} {'Estado':<15} {'Modelo':<40}")
    print("-" * 85)
    for job in jobs.data:
        model = getattr(job, "fine_tuned_model", "") or BASE_MODEL
        print(f"{job.id:<30} {format_status(job):<15} {model:<40}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sube dataset y lanza fine-tuning en Anthropic")
    sub = parser.add_subparsers(dest="cmd")

    # upload
    p_upload = sub.add_parser("upload", help="Subir dataset y lanzar job")
    p_upload.add_argument("--input", required=True, help="Archivo JSONL validado")
    p_upload.add_argument("--suffix", help="Sufijo del modelo resultante (default: ovd-<timestamp>)")
    p_upload.add_argument("--epochs", type=int, default=3, help="Épocas de entrenamiento (default: 3)")
    p_upload.add_argument("--wait", action="store_true", help="Esperar hasta que el job complete")

    # status
    p_status = sub.add_parser("status", help="Ver estado de un job")
    p_status.add_argument("--job-id", required=True)

    # list
    sub.add_parser("list", help="Listar jobs de fine-tuning")

    args = parser.parse_args()

    if args.cmd == "upload":
        upload_and_train(args)
    elif args.cmd == "status":
        check_job(args)
    elif args.cmd == "list":
        list_jobs(args)
    else:
        # Compatibilidad hacia atrás: --input sin subcomando
        parser2 = argparse.ArgumentParser()
        parser2.add_argument("--input", required=True)
        parser2.add_argument("--suffix")
        parser2.add_argument("--epochs", type=int, default=3)
        parser2.add_argument("--wait", action="store_true")
        parser2.add_argument("--job-id")
        parser2.add_argument("--list", action="store_true")
        args2 = parser2.parse_args()
        if args2.list:
            list_jobs(args2)
        elif args2.job_id:
            args2.cmd = "status"
            check_job(args2)
        else:
            upload_and_train(args2)
