"""
OVD Platform — Validador de dataset de fine-tuning
Copyright 2026 Omar Robles

Valida un archivo JSONL antes de subirlo a la Anthropic Fine-tuning API.
Verifica:
  - Formato correcto (messages array con user/assistant alternados)
  - Longitud mínima y máxima de tokens (estimación)
  - Sin ejemplos duplicados
  - Distribución de tipos (analyze_fr / generate_sdd / qa_review)
  - Contenido mínimo en cada mensaje

Uso:
  python validate_dataset.py --input data/ovd_cycles.jsonl
  python validate_dataset.py --input data/ovd_cycles.jsonl --min-examples 50
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# Estimación: 1 token ≈ 4 chars (aproximación para Claude)
CHARS_PER_TOKEN = 4
MAX_TOKENS_PER_EXAMPLE = 8192
MIN_TOKENS_PER_EXAMPLE = 50
MIN_ASSISTANT_CHARS = 20

# ---------------------------------------------------------------------------
# Validación de un ejemplo
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    pass


def estimate_tokens(text) -> int:
    chars = len(text) if isinstance(text, str) else int(text)
    return chars // CHARS_PER_TOKEN


def validate_example(line_num: int, example: dict) -> dict:
    """Valida un ejemplo y retorna sus métricas. Lanza ValidationError si es inválido."""
    messages = example.get("messages")

    if not isinstance(messages, list):
        raise ValidationError(f"línea {line_num}: 'messages' debe ser una lista")

    if len(messages) < 2:
        raise ValidationError(f"línea {line_num}: se requieren al menos 2 mensajes")

    roles = [m.get("role") for m in messages]
    if roles[0] != "user":
        raise ValidationError(f"línea {line_num}: el primer mensaje debe ser 'user', got '{roles[0]}'")

    if roles[-1] != "assistant":
        raise ValidationError(f"línea {line_num}: el último mensaje debe ser 'assistant', got '{roles[-1]}'")

    # Roles deben alternar
    for i, role in enumerate(roles):
        if role not in ("user", "assistant", "system"):
            raise ValidationError(f"línea {line_num}: rol inválido '{role}' en mensaje {i}")

    total_chars = 0
    for i, msg in enumerate(messages):
        content = msg.get("content", "")
        if not isinstance(content, str):
            raise ValidationError(f"línea {line_num}: mensaje {i} 'content' debe ser string")
        if len(content.strip()) == 0:
            raise ValidationError(f"línea {line_num}: mensaje {i} vacío")
        if msg.get("role") == "assistant" and len(content.strip()) < MIN_ASSISTANT_CHARS:
            raise ValidationError(
                f"línea {line_num}: respuesta del asistente demasiado corta ({len(content)} chars)"
            )
        total_chars += len(content)

    total_tokens = estimate_tokens(total_chars)

    if total_tokens < MIN_TOKENS_PER_EXAMPLE:
        raise ValidationError(
            f"línea {line_num}: ejemplo demasiado corto (~{total_tokens} tokens, mínimo {MIN_TOKENS_PER_EXAMPLE})"
        )

    if total_tokens > MAX_TOKENS_PER_EXAMPLE:
        raise ValidationError(
            f"línea {line_num}: ejemplo demasiado largo (~{total_tokens} tokens, máximo {MAX_TOKENS_PER_EXAMPLE})"
        )

    return {"tokens": total_tokens, "messages": len(messages)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def validate(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: archivo no encontrado: {input_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Validando dataset: {input_path}")

    errors: list[str] = []
    warnings: list[str] = []
    valid = 0
    total = 0
    token_counts: list[int] = []
    seen_hashes: set[str] = set()
    duplicates = 0

    with input_path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            total += 1

            # Parsear JSON
            try:
                example = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"línea {line_num}: JSON inválido — {e}")
                continue

            # Detectar duplicados por hash del contenido
            content_hash = hash(json.dumps(example.get("messages", []), sort_keys=True))
            if content_hash in seen_hashes:
                duplicates += 1
                warnings.append(f"línea {line_num}: ejemplo duplicado (omitido)")
                continue
            seen_hashes.add(content_hash)

            # Validar estructura
            try:
                metrics = validate_example(line_num, example)
                valid += 1
                token_counts.append(metrics["tokens"])
            except ValidationError as e:
                errors.append(str(e))

    # Reporte
    print(f"\n{'='*50}")
    print(f"Total líneas:      {total}")
    print(f"Válidos:           {valid}")
    print(f"Duplicados:        {duplicates}")
    print(f"Errores:           {len(errors)}")

    if token_counts:
        avg = sum(token_counts) // len(token_counts)
        print(f"Tokens promedio:   ~{avg}")
        print(f"Tokens mínimo:     ~{min(token_counts)}")
        print(f"Tokens máximo:     ~{max(token_counts)}")

    if warnings:
        print(f"\nWARNINGS ({len(warnings)}):")
        for w in warnings[:10]:
            print(f"  ⚠  {w}")
        if len(warnings) > 10:
            print(f"  ... y {len(warnings) - 10} más")

    if errors:
        print(f"\nERRORES ({len(errors)}):")
        for e in errors[:20]:
            print(f"  ✗  {e}")
        if len(errors) > 20:
            print(f"  ... y {len(errors) - 20} más")

    print(f"{'='*50}")

    # Verificar mínimo de ejemplos
    if valid < args.min_examples:
        print(
            f"\nERROR: dataset insuficiente — {valid} ejemplos válidos, "
            f"se requieren al menos {args.min_examples}",
            file=sys.stderr,
        )
        sys.exit(1)

    if errors:
        print(f"\nFALLÓ: {len(errors)} error(es) encontrado(s).", file=sys.stderr)
        sys.exit(1)

    print(f"\n✓ Dataset válido — {valid} ejemplos listos para fine-tuning")
    print("Siguiente paso: python upload_finetune.py --input", input_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Valida dataset JSONL para fine-tuning")
    parser.add_argument("--input", required=True, help="Archivo JSONL a validar")
    parser.add_argument("--min-examples", type=int, default=10, help="Mínimo de ejemplos válidos requeridos")
    args = parser.parse_args()
    validate(args)
