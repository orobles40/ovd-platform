#!/usr/bin/env python3
"""
OVD Platform — Parser de logs de fine-tuning MLX
Extrae métricas estructuradas de un log de training y las registra en runs_summary.jsonl
"""
import re
import sys
import json
import yaml
import argparse
from pathlib import Path
from datetime import datetime


def parse_log(log_path: Path) -> dict:
    text = log_path.read_text(errors="replace")
    lines = text.splitlines()

    metrics = {
        "log_file": log_path.name,
        "trainable_params": None,
        "trainable_pct": None,
        "val_loss_initial": None,
        "val_loss_curve": [],      # [{iter, val_loss}]
        "train_loss_curve": [],    # [{iter, train_loss, lr, it_sec, tok_sec, peak_mem_gb}]
        "peak_mem_max_gb": None,
        "checkpoints_saved": [],
        "truncation_warnings": 0,
        "max_truncated_tokens": 0,
        "outcome": "unknown",      # completed | interrupted | oom_killed
        "iters_completed": 0,
        "total_trained_tokens": 0,
        "final_train_loss": None,
        "final_val_loss": None,
    }

    # Trainable parameters
    m = re.search(r"Trainable parameters: ([\d.]+)% \(([\d.]+)M", text)
    if m:
        metrics["trainable_pct"] = float(m.group(1))
        metrics["trainable_params_M"] = float(m.group(2))

    for line in lines:
        # Val loss periódica: "Iter 100: Val loss 1.532, Val took 45.2s"
        m = re.match(r"Iter (\d+): Val loss ([\d.]+)", line)
        if m:
            it, vl = int(m.group(1)), float(m.group(2))
            if it == 1:
                metrics["val_loss_initial"] = vl
            metrics["val_loss_curve"].append({"iter": it, "val_loss": vl})
            metrics["final_val_loss"] = vl
            continue

        # Train loss periódica: "Iter 25: Train loss 1.721, Learning Rate 1.000e-04, It/sec 0.098, ..."
        m = re.match(
            r"Iter (\d+): Train loss ([\d.]+), Learning Rate ([\de.+-]+), "
            r"It/sec ([\d.]+), Tokens/sec ([\d.]+), Trained Tokens (\d+), Peak mem ([\d.]+) GB",
            line,
        )
        if m:
            entry = {
                "iter": int(m.group(1)),
                "train_loss": float(m.group(2)),
                "lr": float(m.group(3)),
                "it_sec": float(m.group(4)),
                "tok_sec": float(m.group(5)),
                "trained_tokens": int(m.group(6)),
                "peak_mem_gb": float(m.group(7)),
            }
            metrics["train_loss_curve"].append(entry)
            metrics["iters_completed"] = entry["iter"]
            metrics["total_trained_tokens"] = entry["trained_tokens"]
            metrics["final_train_loss"] = entry["train_loss"]
            # Máximo peak RAM a lo largo del training
            if metrics["peak_mem_max_gb"] is None or entry["peak_mem_gb"] > metrics["peak_mem_max_gb"]:
                metrics["peak_mem_max_gb"] = entry["peak_mem_gb"]
            continue

        # Checkpoints
        m = re.search(r"Saved adapter weights to .+ and (adapters/\S+\.safetensors)\.", line)
        if m:
            metrics["checkpoints_saved"].append(m.group(1))
            continue

        # Truncation warnings
        m = re.search(r"longest sentence (\d+) will be truncated", line)
        if m:
            metrics["truncation_warnings"] += 1
            tok = int(m.group(1))
            if tok > metrics["max_truncated_tokens"]:
                metrics["max_truncated_tokens"] = tok

    # Determinar outcome
    if "Training complete" in text or (
        metrics["iters_completed"] > 0
        and re.search(r"Iter 500:", text)
    ):
        metrics["outcome"] = "completed"
    elif metrics["iters_completed"] == 0:
        metrics["outcome"] = "failed_early"
    else:
        metrics["outcome"] = "interrupted"

    return metrics


def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def append_to_summary(summary_path: Path, record: dict):
    with open(summary_path, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"[LOG] Registro añadido a {summary_path.name}")


def print_report(record: dict):
    cfg = record.get("config", {})
    m = record.get("metrics", {})
    print("\n" + "=" * 60)
    print(f"  RESUMEN DE EJECUCIÓN — {record['run_id']}")
    print("=" * 60)
    print(f"  Fecha inicio   : {record.get('date_start', '—')}")
    print(f"  Fecha fin      : {record.get('date_end', '—')}")
    print(f"  Outcome        : {m.get('outcome', '—')}")
    print(f"  Iters          : {m.get('iters_completed', 0)} / {cfg.get('iters', '?')}")
    print(f"  Checkpoints    : {len(m.get('checkpoints_saved', []))}")
    print(f"\n  Config")
    print(f"    batch_size   : {cfg.get('batch_size', '—')}")
    print(f"    max_seq_len  : {cfg.get('max_seq_length', '—')}")
    print(f"    lr           : {cfg.get('learning_rate', '—')}")
    print(f"    lora rank    : {cfg.get('lora_parameters', {}).get('rank', '—')}")
    print(f"    lora layers  : {cfg.get('lora_layers', '—')}")
    print(f"\n  Pérdida (loss)")
    print(f"    val_loss ini : {m.get('val_loss_initial', '—')}")
    print(f"    train_loss fin: {m.get('final_train_loss', '—')}")
    print(f"    val_loss fin  : {m.get('final_val_loss', '—')}")
    print(f"\n  Hardware")
    print(f"    peak_mem_max : {m.get('peak_mem_max_gb', '—')} GB")
    print(f"\n  Dataset")
    print(f"    truncaciones : {m.get('truncation_warnings', 0)} warnings")
    print(f"    max tokens   : {m.get('max_truncated_tokens', 0)}")

    # Curva de loss (resumen)
    curve = m.get("train_loss_curve", [])
    if len(curve) >= 2:
        print(f"\n  Curva de train_loss")
        step = max(1, len(curve) // 5)
        for entry in curve[::step]:
            print(f"    iter {entry['iter']:>4}: {entry['train_loss']:.4f}  (peak {entry['peak_mem_gb']} GB)")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Parsear log de training MLX y registrar en summary")
    parser.add_argument("log_file", nargs="?", help="Ruta al log de training (default: más reciente en logs/)")
    parser.add_argument("--config", default="mlx_config.yaml", help="Config usada (default: mlx_config.yaml)")
    parser.add_argument("--summary", default="logs/runs_summary.jsonl", help="Archivo de summary (default: logs/runs_summary.jsonl)")
    parser.add_argument("--outcome", default=None, help="Forzar outcome: completed|interrupted|oom_killed")
    parser.add_argument("--date-start", default=None, help="Fecha de inicio (ISO)")
    parser.add_argument("--date-end", default=None, help="Fecha de fin (ISO)")
    parser.add_argument("--notes", default="", help="Notas adicionales")
    args = parser.parse_args()

    base_dir = Path(__file__).parent

    # Resolver log
    if args.log_file:
        log_path = Path(args.log_file)
        if not log_path.is_absolute():
            log_path = base_dir / log_path
    else:
        logs = sorted((base_dir / "logs").glob("training_*.log"))
        if not logs:
            print("[ERROR] No se encontró ningún log en logs/")
            sys.exit(1)
        log_path = logs[-1]
        print(f"[LOG] Usando log más reciente: {log_path.name}")

    config_path = base_dir / args.config
    summary_path = base_dir / args.summary

    # Parsear
    metrics = parse_log(log_path)
    config = load_config(config_path)

    if args.outcome:
        metrics["outcome"] = args.outcome

    # Inferir run_id desde nombre del log
    run_id = log_path.stem.replace("training_", "run_")

    record = {
        "run_id": run_id,
        "date_start": args.date_start or run_id.replace("run_", "").replace("_", "T", 1).replace("_", ":").replace("T", " ", 1),
        "date_end": args.date_end or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "notes": args.notes,
        "config": {
            "model": config.get("model"),
            "batch_size": config.get("batch_size"),
            "max_seq_length": config.get("max_seq_length"),
            "iters": config.get("iters"),
            "learning_rate": config.get("learning_rate"),
            "warmup": config.get("warmup"),
            "weight_decay": config.get("weight_decay"),
            "grad_checkpoint": config.get("grad_checkpoint"),
            "save_every": config.get("save_every"),
            "lora_layers": config.get("lora_layers"),
            "lora_parameters": config.get("lora_parameters"),
            "mask_prompt": config.get("mask_prompt"),
        },
        "metrics": metrics,
    }

    print_report(record)
    append_to_summary(summary_path, record)


if __name__ == "__main__":
    main()
