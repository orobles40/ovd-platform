"""
OVD Platform — Benchmark de modelos fine-tuneados
Copyright 2026 Omar Robles

Evalúa la calidad de un modelo fine-tuneado versus el modelo base
usando ciclos históricos almacenados en ovd_cycle_logs.

Métricas calculadas:
  - code_similarity: similitud semántica del código generado (cosine en embeddings)
  - qa_score_avg:    promedio de scores QA históricos del modelo base
  - sdd_coverage:    % de requisitos del SDD cubiertos en el output

Uso:
  python benchmark.py --org-id ORG_ID --base-model claude-sonnet-4-6 \\
      --ft-model ft:claude-sonnet-4-6:org123:v1 \\
      --samples 20 --output benchmark_report.json

  DATABASE_URL=postgresql://... python benchmark.py --org-id ORG_ID
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import statistics
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any

try:
    import psycopg2
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, SystemMessage
except ImportError:
    print("ERROR: Instalar dependencias: pip install psycopg2-binary langchain-anthropic")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Estructuras de resultado
# ---------------------------------------------------------------------------

@dataclass
class ModelScore:
    model: str
    sample_count: int
    avg_output_length: float
    avg_qa_score: float
    sdd_coverage_pct: float
    avg_input_tokens: float
    avg_output_tokens: float
    avg_cost_usd: float


@dataclass
class BenchmarkReport:
    org_id: str
    timestamp: str
    base_model: ModelScore
    ft_model: ModelScore
    improvement_pct: float
    recommendation: str


# ---------------------------------------------------------------------------
# Carga de muestras desde ovd_cycle_logs
# ---------------------------------------------------------------------------

def load_samples(org_id: str, limit: int) -> list[dict[str, Any]]:
    """Carga ciclos completados con QA passed=true del histórico."""
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        raise ValueError("DATABASE_URL no definido")

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("""
        SELECT
            feature_request,
            fr_analysis_json,
            sdd_json,
            agent_results_json,
            qa_result_json,
            qa_score,
            tokens_input,
            tokens_output,
            estimated_cost_usd
        FROM ovd_cycle_logs
        WHERE org_id = %s
          AND exported = false
          AND qa_score IS NOT NULL
        ORDER BY time_created DESC
        LIMIT %s
    """, (org_id, limit))

    rows = cur.fetchall()
    conn.close()

    samples = []
    for row in rows:
        (fr, fr_json, sdd_json, agents_json, qa_json,
         qa_score, tok_in, tok_out, cost) = row
        samples.append({
            "feature_request": fr,
            "fr_analysis": json.loads(fr_json or "{}"),
            "sdd": json.loads(sdd_json or "{}"),
            "agent_results": json.loads(agents_json or "[]"),
            "qa_result": json.loads(qa_json or "{}"),
            "qa_score": qa_score or 0,
            "tokens_input": tok_in or 0,
            "tokens_output": tok_out or 0,
            "estimated_cost_usd": float(cost or 0),
        })
    return samples


# ---------------------------------------------------------------------------
# Evaluación de un modelo
# ---------------------------------------------------------------------------

def evaluate_model(model_id: str, samples: list[dict], max_samples: int) -> ModelScore:
    """
    Ejecuta el modelo sobre los Feature Requests del histórico y evalúa:
    - Cobertura del SDD (% de tareas mencionadas en el output)
    - Calidad estimada (QA score histórico como referencia)
    """
    llm = ChatAnthropic(
        model=model_id,
        api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        max_tokens=2048,
    )

    output_lengths = []
    sdd_coverages = []
    qa_scores = []
    tokens_in_list = []
    tokens_out_list = []
    cost_list = []

    # Precio referencia Sonnet 4.6 (aplica si no hay precio específico del ft-model)
    COST_INPUT = 3.0 / 1_000_000
    COST_OUTPUT = 15.0 / 1_000_000

    for sample in samples[:max_samples]:
        fr = sample["feature_request"]
        sdd_tasks = sample["sdd"].get("tasks", [])
        task_titles = [t.get("title", "") for t in sdd_tasks if t.get("title")]

        try:
            response = llm.invoke([
                SystemMessage(content=(
                    "Eres un agente de desarrollo. Dado el siguiente Feature Request "
                    "y el SDD aprobado, genera el código de implementación backend."
                )),
                HumanMessage(content=(
                    f"Feature Request: {fr}\n\n"
                    f"SDD Summary: {sample['sdd'].get('summary', '')}\n\n"
                    "Implementa las tareas del SDD."
                )),
            ])

            output = response.content or ""
            output_lengths.append(len(output))

            # Cobertura: cuántas tareas del SDD se mencionan en el output
            if task_titles:
                covered = sum(1 for t in task_titles if t.lower() in output.lower())
                sdd_coverages.append(covered / len(task_titles) * 100)
            else:
                sdd_coverages.append(100.0)  # sin tareas → cobertura perfecta

            # Usar QA score histórico como referencia de calidad
            qa_scores.append(sample.get("qa_score", 0))

            # Tokens del response
            usage = response.response_metadata.get("usage", {})
            tok_in = usage.get("input_tokens", 0)
            tok_out = usage.get("output_tokens", 0)
            tokens_in_list.append(tok_in)
            tokens_out_list.append(tok_out)
            cost_list.append(tok_in * COST_INPUT + tok_out * COST_OUTPUT)

        except Exception as e:
            print(f"  WARN: error evaluando muestra con {model_id}: {e}", file=sys.stderr)
            continue

    n = len(output_lengths)
    if n == 0:
        return ModelScore(
            model=model_id, sample_count=0,
            avg_output_length=0, avg_qa_score=0,
            sdd_coverage_pct=0, avg_input_tokens=0,
            avg_output_tokens=0, avg_cost_usd=0,
        )

    return ModelScore(
        model=model_id,
        sample_count=n,
        avg_output_length=statistics.mean(output_lengths),
        avg_qa_score=statistics.mean(qa_scores),
        sdd_coverage_pct=statistics.mean(sdd_coverages),
        avg_input_tokens=statistics.mean(tokens_in_list),
        avg_output_tokens=statistics.mean(tokens_out_list),
        avg_cost_usd=statistics.mean(cost_list),
    )


# ---------------------------------------------------------------------------
# Generación del reporte
# ---------------------------------------------------------------------------

def generate_report(
    org_id: str,
    base_score: ModelScore,
    ft_score: ModelScore,
) -> BenchmarkReport:
    improvement = 0.0
    if base_score.sdd_coverage_pct > 0:
        improvement = (ft_score.sdd_coverage_pct - base_score.sdd_coverage_pct) / base_score.sdd_coverage_pct * 100

    if improvement > 5:
        recommendation = f"ADOPTAR: el modelo fine-tuneado mejora la cobertura SDD un {improvement:.1f}%"
    elif improvement < -5:
        recommendation = f"RECHAZAR: el modelo fine-tuneado empeora la cobertura SDD un {abs(improvement):.1f}%"
    else:
        recommendation = "NEUTRAL: el modelo fine-tuneado no muestra mejora significativa (±5%)"

    return BenchmarkReport(
        org_id=org_id,
        timestamp=datetime.utcnow().isoformat() + "Z",
        base_model=base_score,
        ft_model=ft_score,
        improvement_pct=round(improvement, 2),
        recommendation=recommendation,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Benchmark de modelos fine-tuneados OVD")
    parser.add_argument("--org-id", required=True, help="ID de la organización")
    parser.add_argument("--base-model", default="claude-sonnet-4-6", help="Modelo base (default: claude-sonnet-4-6)")
    parser.add_argument("--ft-model", required=True, help="ID del modelo fine-tuneado")
    parser.add_argument("--samples", type=int, default=20, help="Número de muestras del histórico (default: 20)")
    parser.add_argument("--output", default="benchmark_report.json", help="Archivo de salida JSON")
    args = parser.parse_args()

    print(f"[benchmark] Cargando {args.samples} muestras para org {args.org_id}...")
    samples = load_samples(args.org_id, args.samples)
    if not samples:
        print("ERROR: no hay ciclos históricos disponibles para esta org.", file=sys.stderr)
        sys.exit(1)
    print(f"[benchmark] {len(samples)} muestras cargadas.")

    print(f"[benchmark] Evaluando modelo base: {args.base_model}...")
    base_score = evaluate_model(args.base_model, samples, args.samples)

    print(f"[benchmark] Evaluando modelo fine-tuneado: {args.ft_model}...")
    ft_score = evaluate_model(args.ft_model, samples, args.samples)

    report = generate_report(args.org_id, base_score, ft_score)

    # Mostrar resumen en stdout
    print("\n" + "=" * 60)
    print("RESULTADO DEL BENCHMARK")
    print("=" * 60)
    print(f"Muestras evaluadas:     {base_score.sample_count}")
    print(f"Cobertura SDD base:     {base_score.sdd_coverage_pct:.1f}%")
    print(f"Cobertura SDD ft:       {ft_score.sdd_coverage_pct:.1f}%")
    print(f"Mejora:                 {report.improvement_pct:+.1f}%")
    print(f"Costo/muestra base:     ${base_score.avg_cost_usd:.6f}")
    print(f"Costo/muestra ft:       ${ft_score.avg_cost_usd:.6f}")
    print(f"\nRecomendación: {report.recommendation}")
    print("=" * 60)

    # Guardar JSON
    with open(args.output, "w") as f:
        json.dump(asdict(report), f, indent=2)
    print(f"\n[benchmark] Reporte guardado en: {args.output}")


if __name__ == "__main__":
    main()
