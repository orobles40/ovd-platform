"""
OVD Platform — Knowledge Module (Sprint 8 — GAP-A1, KNOWLEDGE_STRATEGY.md)
Copyright 2026 Omar Robles

Ingesta multi-formato para la base de conocimiento del RAG.

Tipos de documentos soportados:
  codebase  — código fuente (chunking por AST)
  doc       — documentos PDF/Word/Markdown (chunking por sección)
  schema    — DDL de base de datos (chunking por tabla/vista/proc)
  contract  — API specs Swagger/OpenAPI (chunking por endpoint)
  ticket    — tickets/historias de usuario (chunking completo por ticket)

Uso:
  from knowledge import bootstrap
  await bootstrap.run(
      org_id="org_123",
      project_id="proj_abc",
      source_path="/ruta/al/codigo",
      doc_type="codebase",
      bridge_url="http://localhost:3000",
      jwt_token="...",
  )

  O via CLI:
  uv run python -m knowledge.cli bootstrap \\
    --org-id org_123 --project-id proj_abc \\
    --source /ruta/al/codigo --type codebase
"""
