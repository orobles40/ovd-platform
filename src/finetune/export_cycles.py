"""
OVD Platform — Exportador de ciclos para fine-tuning (SM1.A)
Copyright 2026 Omar Robles

Lee los ciclos completados de ovd_cycle_logs y genera un archivo JSONL
en formato compatible con la Anthropic Fine-tuning API.

Cada ejemplo de entrenamiento captura uno de los tres momentos clave del ciclo:
  1. analyze_fr:   FR → análisis estructurado
  2. generate_sdd: FR + análisis → SDD completo
  3. qa_review:    SDD + implementación → resultado QA

Filtros de calidad (SM1 — CRÍTICOS para integridad del dataset):
  --min-qa-score 0.80     Solo ciclos con qa_score >= 0.80 (default)
  --require-approval      Solo ciclos con aprobación humana explícita
  --exclude-auto-approve  Excluir ciclos con auto_approve=true

  Sin estos filtros, el modelo puede aprender de outputs de baja calidad
  o de ciclos que nadie revisó, degradando la calidad del modelo propio.

Uso:
  # Exportación con filtros de calidad (recomendado para fine-tuning)
  python export_cycles.py --output data/ovd_cycles.jsonl \\
    --min-qa-score 0.80 --require-approval --exclude-auto-approve

  # Exportación sin filtros (solo para análisis/debug)
  python export_cycles.py --output data/ovd_cycles.jsonl --no-quality-filters

  # Filtrar por org
  python export_cycles.py --output data/ovd_cycles.jsonl --org-id omar-demo

  # Marcar como exportados al terminar (para no re-exportar en el próximo run)
  python export_cycles.py --output data/ovd_cycles.jsonl --mark-exported
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATABASE_URL = os.environ.get("DATABASE_URL", "")

SYSTEM_ANALYZE_FR = (
    "Eres un arquitecto de software senior en Omar Robles. "
    "Analiza el Feature Request y extrae: tipo exacto (bug/feature/refactor/security/performance), "
    "componentes afectados, riesgos, si involucra Oracle, complejidad y un resumen conciso. "
    "Responde en JSON estructurado."
)

SYSTEM_GENERATE_SDD = (
    "Eres un arquitecto siguiendo la metodología Spec-Driven Development (SDD). "
    "Genera una especificación completa con: requirements, design, constraints y tasks. "
    "Formato Markdown, estructura clara y concisa."
)

SYSTEM_QA_REVIEW = (
    "Eres un revisor QA/Security senior. Evalúa el resultado de implementación contra: "
    "1) Requisitos del SDD, 2) Seguridad OWASP, 3) Multi-tenancy (org_id), "
    "4) Compatibilidad Oracle 12c/19c si aplica. "
    "Responde en JSON estructurado con: passed, score, issues, owasp_concerns, rls_compliant, oracle_compat, summary."
)

# ---------------------------------------------------------------------------
# Generadores de ejemplos
# ---------------------------------------------------------------------------

def example_analyze_fr(row: dict) -> dict | None:
    """FR → análisis estructurado (FRAnalysisOutput)."""
    fr = (row.get("feature_request") or "").strip()
    if not fr:
        return None

    try:
        analysis = json.loads(row.get("fr_analysis_json") or "{}")
    except json.JSONDecodeError:
        return None

    if not analysis or not analysis.get("type"):
        return None

    assistant_content = json.dumps({
        "fr_type":        analysis.get("type", "feature"),
        "complexity":     analysis.get("complexity", "medium"),
        "components":     analysis.get("components", []),
        "oracle_involved": analysis.get("oracle_involved", False),
        "risks":          analysis.get("risks", []),
        "summary":        analysis.get("summary", analysis.get("raw", "")[:300]),
    }, ensure_ascii=False)

    return {
        "messages": [
            {"role": "user", "content": f"Feature Request:\n{fr}"},
            {"role": "assistant", "content": assistant_content},
        ],
        "_meta": {"type": "analyze_fr", "session_id": row["session_id"]},
    }


def example_generate_sdd(row: dict) -> dict | None:
    """FR + análisis → SDD."""
    fr = (row.get("feature_request") or "").strip()
    if not fr:
        return None

    try:
        analysis = json.loads(row.get("fr_analysis_json") or "{}")
        sdd = json.loads(row.get("sdd_json") or "{}")
    except json.JSONDecodeError:
        return None

    sdd_content = sdd.get("content", "").strip()
    if len(sdd_content) < 100:  # SDD demasiado corto = probablemente vacío
        return None

    analysis_summary = analysis.get("raw") or analysis.get("summary") or ""

    return {
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Feature Request:\n{fr}\n\n"
                    f"Análisis previo:\n{analysis_summary[:500]}"
                ),
            },
            {"role": "assistant", "content": sdd_content},
        ],
        "_meta": {"type": "generate_sdd", "session_id": row["session_id"]},
    }


def example_qa_review(row: dict) -> dict | None:
    """SDD + implementación → resultado QA."""
    try:
        sdd = json.loads(row.get("sdd_json") or "{}")
        agent_results = json.loads(row.get("agent_results_json") or "[]")
        qa = json.loads(row.get("qa_result_json") or "{}")
    except json.JSONDecodeError:
        return None

    sdd_content = sdd.get("content", "")[:2000]
    agent_output = "\n\n".join(
        r.get("output", "") for r in agent_results if isinstance(r, dict)
    )[:3000]

    if not agent_output or not qa.get("summary"):
        return None

    assistant_content = json.dumps({
        "passed":        qa.get("passed", True),
        "score":         qa.get("score", 85),
        "issues":        qa.get("issues", []),
        "owasp_concerns": qa.get("owasp_concerns", []),
        "rls_compliant": qa.get("rls_compliant", True),
        "oracle_compat": qa.get("oracle_compat", True),
        "summary":       qa.get("summary", qa.get("raw", "")[:300]),
    }, ensure_ascii=False)

    return {
        "messages": [
            {
                "role": "user",
                "content": (
                    f"SDD aprobado:\n{sdd_content}\n\n"
                    f"Resultado de implementación a revisar:\n{agent_output}"
                ),
            },
            {"role": "assistant", "content": assistant_content},
        ],
        "_meta": {"type": "qa_review", "session_id": row["session_id"]},
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def fetch_cycles(
    org_id: str | None,
    only_pending: bool,
    min_qa_score: float = 0.0,
    require_approval: bool = False,
    exclude_auto_approve: bool = False,
) -> list[dict]:
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL no configurada", file=sys.stderr)
        sys.exit(1)

    conditions = []
    params: list = []

    if only_pending:
        conditions.append("exported = false")
    if org_id:
        conditions.append("org_id = %s")
        params.append(org_id)
    if min_qa_score > 0.0:
        conditions.append("qa_score >= %s")
        params.append(min_qa_score)
    if require_approval:
        conditions.append("approval_decision = 'approved'")
    if exclude_auto_approve:
        conditions.append("(auto_approve = false OR auto_approve IS NULL)")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT * FROM ovd_cycle_logs {where} ORDER BY time_created DESC"

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def mark_exported(ids: list[str]) -> None:
    if not ids:
        return
    now = datetime.utcnow().isoformat()
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ovd_cycle_logs SET exported = true, exported_at = %s WHERE id = ANY(%s)",
                (now, ids),
            )
        conn.commit()


def export(args: argparse.Namespace) -> None:
    # Determinar filtros de calidad
    no_filters = getattr(args, "no_quality_filters", False)
    min_qa     = 0.0          if no_filters else getattr(args, "min_qa_score", 0.80)
    req_appr   = False        if no_filters else getattr(args, "require_approval", False)
    excl_auto  = False        if no_filters else getattr(args, "exclude_auto_approve", False)

    print("Conectando a PostgreSQL...")
    if no_filters:
        print("  [ADVERTENCIA] Filtros de calidad desactivados — solo para análisis/debug")
    else:
        active = []
        if min_qa > 0.0:
            active.append(f"qa_score >= {min_qa}")
        if req_appr:
            active.append("aprobación humana requerida")
        if excl_auto:
            active.append("excluir auto_approve")
        if active:
            print(f"  Filtros activos: {', '.join(active)}")

    rows = fetch_cycles(
        args.org_id,
        not args.all,
        min_qa_score=min_qa,
        require_approval=req_appr,
        exclude_auto_approve=excl_auto,
    )
    print(f"  {len(rows)} ciclo(s) encontrado(s)")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    generators = [example_analyze_fr, example_generate_sdd, example_qa_review]
    written = 0
    skipped = 0
    exported_ids: list[str] = []

    with output_path.open("w", encoding="utf-8") as f:
        for row in rows:
            for gen in generators:
                example = gen(row)
                if example is None:
                    skipped += 1
                    continue
                # Quitar _meta antes de escribir (es solo para debug)
                meta = example.pop("_meta", {})
                line = json.dumps(example, ensure_ascii=False)
                f.write(line + "\n")
                written += 1

            exported_ids.append(row["id"])

    print(f"  {written} ejemplos escritos en {output_path}")
    print(f"  {skipped} ejemplos omitidos (datos insuficientes)")

    if args.mark_exported and exported_ids:
        mark_exported(exported_ids)
        print(f"  {len(exported_ids)} ciclos marcados como exportados")

    if written == 0:
        print("\nWARNING: no se exportó ningún ejemplo. Verifica que existan ciclos completos en ovd_cycle_logs.")
        sys.exit(1)

    print(f"\nDataset listo: {output_path} ({output_path.stat().st_size / 1024:.1f} KB)")
    print("Siguiente paso: python validate_dataset.py --input", output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Exporta ciclos OVD a JSONL para fine-tuning")
    parser.add_argument("--output", default="data/ovd_cycles.jsonl", help="Archivo JSONL de salida")
    parser.add_argument("--org-id", help="Filtrar por org_id (default: todos)")
    parser.add_argument("--all", action="store_true", help="Incluir ciclos ya exportados")
    parser.add_argument("--mark-exported", action="store_true", help="Marcar ciclos como exportados al terminar")

    # Filtros de calidad SM1 — CRÍTICOS para integridad del dataset
    qf = parser.add_argument_group(
        "filtros de calidad",
        "Controlan qué ciclos se incluyen en el dataset de fine-tuning",
    )
    qf.add_argument(
        "--min-qa-score",
        type=float,
        default=0.80,
        metavar="SCORE",
        help="Solo ciclos con qa_score >= SCORE (default: 0.80)",
    )
    qf.add_argument(
        "--require-approval",
        action="store_true",
        help="Solo ciclos con aprobación humana explícita (approval_decision='approved')",
    )
    qf.add_argument(
        "--exclude-auto-approve",
        action="store_true",
        help="Excluir ciclos procesados con auto_approve=true",
    )
    qf.add_argument(
        "--no-quality-filters",
        action="store_true",
        help="Desactivar todos los filtros de calidad (solo para análisis/debug)",
    )

    args = parser.parse_args()
    export(args)
