"""
OVD Platform — Research Agent (GAP-009)
Copyright 2026 Omar Robles

Agente de investigacion que actualiza el RAG del proyecto con:
  - CVEs recientes relevantes al stack tecnologico
  - Deprecaciones de librerias/APIs del stack
  - Cambios breaking en versiones recientes
  - Mejores practicas de seguridad actualizadas

El agente usa el LLM con conocimiento a la fecha de corte para:
  1. Identificar riesgos de seguridad conocidos en el stack
  2. Detectar patrones o APIs deprecadas
  3. Indexar los hallazgos en pgvector via el Bridge

Uso CLI:
  python research.py --org-id ORG --project-id PROJ --token JWT
  python research.py --org-id ORG --project-id PROJ --token JWT --stack "FastAPI,PostgreSQL,React"
  python research.py --org-id ORG --project-id PROJ --token JWT --topic "auth vulnerabilities"

Uso como modulo:
  from research import ResearchAgent
  agent = ResearchAgent(bridge_url=..., jwt_token=..., org_id=..., project_id=...)
  result = await agent.run(project_context="...")
"""
from __future__ import annotations
import asyncio
import json
import os
from datetime import datetime
from typing import Any

import httpx
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Schema de structured output para los hallazgos
# ---------------------------------------------------------------------------

class CVEFinding(BaseModel):
    """Un CVE o vulnerabilidad conocida relevante al stack."""
    cve_id: str = Field(
        description="ID del CVE (ej: 'CVE-2024-XXXXX') o identificador unico si no es CVE formal",
    )
    severity: str = Field(
        description="Severidad: 'critical' | 'high' | 'medium' | 'low' | 'info'",
    )
    component: str = Field(
        description="Componente afectado del stack (ej: 'FastAPI', 'PostgreSQL 14', 'React')",
    )
    description: str = Field(
        description="Descripcion clara de la vulnerabilidad y como afecta al proyecto",
    )
    affected_versions: str = Field(
        description="Versiones afectadas (ej: '< 0.103.0' o 'todas antes de 2024-01')",
    )
    remediation: str = Field(
        description="Accion recomendada: actualizar, parchear, cambiar configuracion, etc.",
    )
    references: list[str] = Field(
        default_factory=list,
        description="URLs de referencia (NVD, GitHub advisories, blog del proveedor)",
    )


class DeprecationFinding(BaseModel):
    """Una API, patron o libreria deprecada en el stack."""
    component: str = Field(
        description="Componente o libreria afectada",
    )
    deprecated_item: str = Field(
        description="Funcion, clase, endpoint o patron especifico deprecado",
    )
    deprecation_version: str = Field(
        description="Version donde se depreco o cuando se anuncio",
    )
    removal_version: str = Field(
        default="",
        description="Version donde se eliminara (si se conoce)",
    )
    replacement: str = Field(
        description="Alternativa recomendada para migrar",
    )
    migration_effort: str = Field(
        description="Esfuerzo estimado de migracion: 'trivial' | 'low' | 'medium' | 'high'",
    )


class ResearchOutput(BaseModel):
    """Resultado completo del Research Agent."""
    cve_findings: list[CVEFinding] = Field(
        default_factory=list,
        description="CVEs y vulnerabilidades identificadas para el stack del proyecto",
    )
    deprecation_findings: list[DeprecationFinding] = Field(
        default_factory=list,
        description="Deprecaciones y cambios breaking relevantes para el stack",
    )
    security_recommendations: list[str] = Field(
        default_factory=list,
        description="Recomendaciones generales de seguridad para el stack (hardening, configs)",
    )
    update_recommendations: list[str] = Field(
        default_factory=list,
        description="Actualizaciones de version recomendadas con justificacion",
    )
    summary: str = Field(
        description="Resumen ejecutivo: riesgo general del stack y principales hallazgos",
    )
    risk_level: str = Field(
        description="Nivel de riesgo general del stack: 'low' | 'medium' | 'high' | 'critical'",
    )


# ---------------------------------------------------------------------------
# Sistema de prompt del Research Agent
# ---------------------------------------------------------------------------

_RESEARCH_SYSTEM_PROMPT = """Eres un experto en seguridad de software y arquitectura de plataformas.

Tu tarea es analizar el stack tecnologico de un proyecto y producir un informe estructurado con:

1. **CVEs y vulnerabilidades conocidas** en los componentes del stack (hasta tu fecha de conocimiento)
2. **Deprecaciones y cambios breaking** en APIs, librerias o patrones del stack
3. **Recomendaciones de seguridad** especificas para la combinacion de tecnologias del proyecto
4. **Actualizaciones de version** prioritarias con justificacion de seguridad

Reglas importantes:
- Solo incluye hallazgos reales que conozcas con certeza — NO inventes CVE IDs ni versiones
- Prioriza hallazgos de severidad HIGH o CRITICAL
- Las recomendaciones deben ser accionables y especificas para el stack dado
- Si no conoces CVEs especificos para un componente, indicalo en las recomendaciones generales
- Considera la combinacion de tecnologias: algunos vectores de ataque surgen de interacciones

Contexto temporal: Tu conocimiento tiene fecha de corte. Indica cuando los hallazgos puedan
necesitar verificacion adicional en fuentes externas (NVD, GitHub Advisories, etc.)
"""


# ---------------------------------------------------------------------------
# Clase principal del Research Agent
# ---------------------------------------------------------------------------

class ResearchAgent:
    """
    Agente de investigacion que identifica CVEs y deprecaciones para el stack del proyecto
    y los indexa en el RAG via el Bridge HTTP.
    """

    def __init__(
        self,
        bridge_url: str,
        jwt_token: str,
        org_id: str,
        project_id: str,
        model: str | None = None,
    ):
        self.bridge_url = bridge_url.rstrip("/")
        self.jwt_token = jwt_token
        self.org_id = org_id
        self.project_id = project_id
        self._model = model or os.environ.get("OVD_MODEL", "claude-sonnet-4-6")
        self._llm = ChatAnthropic(
            model=self._model,
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        ).with_structured_output(ResearchOutput)

    async def run(
        self,
        project_context: str = "",
        topic: str = "",
    ) -> dict[str, Any]:
        """
        Ejecuta el Research Agent completo:
          1. Genera hallazgos con el LLM
          2. Indexa cada hallazgo en el RAG
          3. Retorna el resumen de hallazgos indexados

        Args:
            project_context: bloque Markdown del Project Profile (si esta disponible)
            topic: tema especifico a investigar (ej: "auth vulnerabilities", "SQL injection")
        """
        # Paso 1: obtener contexto del proyecto si no viene pre-cargado
        if not project_context:
            project_context = await self._fetch_project_context()

        # Paso 2: generar hallazgos con el LLM
        result = await self._generate_findings(project_context, topic)

        # Paso 3: indexar hallazgos en RAG
        indexed = await self._index_findings(result)

        return {
            "indexed": indexed,
            "risk_level": result.risk_level,
            "summary": result.summary,
            "cve_count": len(result.cve_findings),
            "deprecation_count": len(result.deprecation_findings),
            "cve_findings": [f.dict() for f in result.cve_findings],
            "deprecation_findings": [f.dict() for f in result.deprecation_findings],
            "security_recommendations": result.security_recommendations,
            "update_recommendations": result.update_recommendations,
        }

    async def _fetch_project_context(self) -> str:
        """Obtiene el Project Profile desde el Bridge."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.bridge_url}/ovd/project/{self.project_id}/profile",
                    headers={"Authorization": f"Bearer {self.jwt_token}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("context", "")
        except Exception:
            pass
        return ""

    async def _generate_findings(
        self, project_context: str, topic: str
    ) -> ResearchOutput:
        """Usa el LLM para identificar CVEs y deprecaciones del stack."""
        topic_section = f"\n\nTema especifico a investigar: {topic}" if topic else ""
        human_content = (
            f"Analiza el stack tecnologico de este proyecto e identifica "
            f"CVEs, deprecaciones y riesgos de seguridad conocidos.\n\n"
            f"Fecha de analisis: {datetime.utcnow().strftime('%Y-%m-%d')}"
            f"{topic_section}\n\n"
            f"Stack del proyecto:\n{project_context or '(sin informacion de stack — analiza riesgos generales de una plataforma web multi-tenant con LangGraph + FastAPI + PostgreSQL + TypeScript)'}"
        )

        result: ResearchOutput = await self._llm.ainvoke([
            SystemMessage(content=_RESEARCH_SYSTEM_PROMPT),
            HumanMessage(content=human_content),
        ])
        return result

    async def _index_findings(self, result: ResearchOutput) -> int:
        """Indexa los hallazgos del Research Agent en pgvector via el Bridge."""
        indexed = 0
        documents = []

        # Construir documentos RAG para cada CVE
        for cve in result.cve_findings:
            content = (
                f"CVE: {cve.cve_id}\n"
                f"Severidad: {cve.severity}\n"
                f"Componente: {cve.component}\n"
                f"Versiones afectadas: {cve.affected_versions}\n"
                f"Descripcion: {cve.description}\n"
                f"Remediacion: {cve.remediation}\n"
                + (f"Referencias: {', '.join(cve.references)}" if cve.references else "")
            )
            documents.append({
                "projectId": self.project_id,
                "docType": "cve",
                "title": f"{cve.cve_id} — {cve.component} ({cve.severity})",
                "content": content,
                "metadata": {
                    "severity": cve.severity,
                    "component": cve.component,
                    "source": "research_agent",
                    "indexed_at": datetime.utcnow().isoformat(),
                },
            })

        # Construir documentos RAG para deprecaciones
        for dep in result.deprecation_findings:
            content = (
                f"Deprecacion en: {dep.component}\n"
                f"Item deprecado: {dep.deprecated_item}\n"
                f"Desde version: {dep.deprecation_version}\n"
                + (f"Eliminado en: {dep.removal_version}\n" if dep.removal_version else "")
                + f"Alternativa recomendada: {dep.replacement}\n"
                f"Esfuerzo de migracion: {dep.migration_effort}"
            )
            documents.append({
                "projectId": self.project_id,
                "docType": "deprecation",
                "title": f"Deprecacion: {dep.deprecated_item} en {dep.component}",
                "content": content,
                "metadata": {
                    "component": dep.component,
                    "migration_effort": dep.migration_effort,
                    "source": "research_agent",
                    "indexed_at": datetime.utcnow().isoformat(),
                },
            })

        # Documento de resumen general del research
        if result.security_recommendations or result.update_recommendations:
            rec_content = ""
            if result.security_recommendations:
                rec_content += "## Recomendaciones de seguridad\n"
                rec_content += "\n".join(f"- {r}" for r in result.security_recommendations)
            if result.update_recommendations:
                rec_content += "\n\n## Actualizaciones recomendadas\n"
                rec_content += "\n".join(f"- {r}" for r in result.update_recommendations)
            documents.append({
                "projectId": self.project_id,
                "docType": "security_recommendations",
                "title": f"Research Agent — Resumen de seguridad ({datetime.utcnow().strftime('%Y-%m-%d')})",
                "content": f"Riesgo general: {result.risk_level}\n\n{result.summary}\n\n{rec_content}",
                "metadata": {
                    "risk_level": result.risk_level,
                    "source": "research_agent",
                    "indexed_at": datetime.utcnow().isoformat(),
                },
            })

        # Indexar en el RAG via Bridge
        async with httpx.AsyncClient(timeout=30.0) as client:
            for doc in documents:
                try:
                    resp = await client.post(
                        f"{self.bridge_url}/ovd/rag/index",
                        headers={
                            "Authorization": f"Bearer {self.jwt_token}",
                            "Content-Type": "application/json",
                        },
                        json=doc,
                    )
                    if resp.status_code in (200, 201):
                        indexed += 1
                except Exception:
                    pass  # continuar aunque falle un documento individual

        return indexed


# ---------------------------------------------------------------------------
# Helper para usar desde api.py sin instanciar la clase
# ---------------------------------------------------------------------------

async def run_research(
    org_id: str,
    project_id: str,
    jwt_token: str,
    bridge_url: str,
    project_context: str = "",
    topic: str = "",
    model: str | None = None,
) -> dict[str, Any]:
    """Shortcut para ejecutar el Research Agent sin instanciar la clase."""
    agent = ResearchAgent(
        bridge_url=bridge_url,
        jwt_token=jwt_token,
        org_id=org_id,
        project_id=project_id,
        model=model,
    )
    return await agent.run(project_context=project_context, topic=topic)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OVD Research Agent — GAP-009")
    parser.add_argument("--org-id", required=True, help="ID de la organizacion")
    parser.add_argument("--project-id", required=True, help="ID del proyecto")
    parser.add_argument("--token", required=True, help="JWT del Bridge")
    parser.add_argument("--bridge-url", default="http://localhost:3000")
    parser.add_argument("--stack", default="", help="Descripcion del stack (si no hay Project Profile)")
    parser.add_argument("--topic", default="", help="Tema especifico a investigar")
    parser.add_argument("--model", default=None, help="Modelo Claude a usar (default: OVD_MODEL env)")
    parser.add_argument("--json", action="store_true", help="Salida en JSON puro")
    args = parser.parse_args()

    async def _main():
        result = await run_research(
            org_id=args.org_id,
            project_id=args.project_id,
            jwt_token=args.token,
            bridge_url=args.bridge_url,
            project_context=args.stack,
            topic=args.topic,
            model=args.model,
        )

        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        print(f"\nResearch Agent — Proyecto: {args.project_id}")
        print("=" * 60)
        print(f"  Riesgo general: {result['risk_level'].upper()}")
        print(f"  CVEs encontrados: {result['cve_count']}")
        print(f"  Deprecaciones: {result['deprecation_count']}")
        print(f"  Documentos indexados en RAG: {result['indexed']}")
        print(f"\nResumen:\n  {result['summary']}")

        if result["cve_findings"]:
            print("\nCVEs criticos/altos:")
            for cve in result["cve_findings"]:
                if cve["severity"] in ("critical", "high"):
                    print(f"  [{cve['severity'].upper()}] {cve['cve_id']} — {cve['component']}")
                    print(f"    {cve['description'][:100]}...")

        if result["update_recommendations"]:
            print("\nActualizaciones recomendadas:")
            for rec in result["update_recommendations"][:5]:
                print(f"  - {rec}")

    asyncio.run(_main())
