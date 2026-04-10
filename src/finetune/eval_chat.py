#!/usr/bin/env python3
"""
Evaluación cualitativa con chat template correcto — Fase 4
Compara modelo base vs fine-tuneado usando el formato de instrucción real.
"""
import sys
import argparse
from mlx_lm import load, generate

SYSTEM_PROMPT = (
    "Eres un arquitecto de software senior especializado en OVD Platform. "
    "Analizas Feature Requests y generas especificaciones SDD (Software Design Documents) "
    "estructuradas. Identificas componentes afectados, riesgos, complejidad y estimaciones. "
    "Trabajas con stacks Oracle, PostgreSQL, Python FastAPI, Java Spring y TypeScript/React."
)

PROMPTS = [
    "Agregar exportación PDF de facturas en sistema Oracle 12c HHMM Clínica Alemana.",
    "Implementar búsqueda full-text en tabla ARTICULOS de PostgreSQL 14 usando índice GIN.",
    "Migrar stored procedure SP_CALCULAR_COMISIONES de Oracle 12c a capa de negocio Python.",
]


def run(model_path, adapter_path=None, prompt_idx=0, max_tokens=700):
    label = f"CON adapter ({adapter_path})" if adapter_path else "SIN adapter (base)"
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  Prompt: {PROMPTS[prompt_idx]}")
    print(f"{'='*60}\n")

    kwargs = {"adapter_path": adapter_path} if adapter_path else {}
    model, tokenizer = load(model_path, **kwargs)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": PROMPTS[prompt_idx]},
    ]
    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    response = generate(model, tokenizer, prompt=prompt, max_tokens=max_tokens, verbose=False)
    print(response)
    print(f"\n{'='*60}\n")
    return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="models/qwen2.5-coder-7b-4bit")
    parser.add_argument("--adapter", default="adapters", help="Ruta al adapter (o 'none')")
    parser.add_argument("--prompt", type=int, default=0, help="Índice del prompt (0-2)")
    parser.add_argument("--max-tokens", type=int, default=700)
    parser.add_argument("--compare", action="store_true", help="Correr base y fine-tuneado en secuencia")
    args = parser.parse_args()

    if args.compare:
        run(args.model, adapter_path=None, prompt_idx=args.prompt, max_tokens=args.max_tokens)
        adapter = None if args.adapter == "none" else args.adapter
        run(args.model, adapter_path=adapter, prompt_idx=args.prompt, max_tokens=args.max_tokens)
    else:
        adapter = None if args.adapter == "none" else args.adapter
        run(args.model, adapter_path=adapter, prompt_idx=args.prompt, max_tokens=args.max_tokens)


if __name__ == "__main__":
    main()
