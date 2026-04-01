# Credits

## Upstream Project

This software is a derivative work based on **OpenCode**, developed by Anomaly Inc.

- **Original project:** OpenCode
- **Repository:** https://github.com/anomalyco/opencode
- **License:** Apache License 2.0
- **Copyright:** Copyright 2024 Anomaly Inc.

This fork (OVD Platform) was created by Omar Robles as a separate product for internal use.
All modifications, extensions, and new features are developed independently and are not endorsed
by or affiliated with the original OpenCode project or Anomaly Inc.

### Changes from upstream — Phase 1 (Weeks 1–9)

| Module | Description |
|--------|-------------|
| `packages/opencode/src/tenant/` | Multi-tenancy: organizations, projects, users, JWT auth, RLS PostgreSQL |
| `packages/opencode/src/ovd/bridge.ts` | OVD Bridge: HTTP client to LangGraph Engine, SSE reconnect with Last-Event-ID |
| `packages/opencode/src/ovd/session.ts` | Session ↔ thread mapping (ovd_session_threads) |
| `packages/opencode/src/ovd/events.ts` | Event loop: SSE → OpenCode SDK event bus |
| `packages/opencode/src/ovd/approval.ts` | Human-in-the-loop approval via LangGraph interrupt |
| `packages/opencode/src/ovd/types.ts` | Zod schemas for all OVD events |
| `packages/opencode/src/cli/cmd/tui/component/dialog-ovd-*.tsx` | TUI dialogs: start, progress, approval, deliverables, history |
| `packages/opencode/src/server/routes/ovd.ts` | OVD API routes + rate limiting by org |
| `packages/opencode/src/server/routes/tenant.ts` | Tenant CRUD: orgs, projects, login |
| `packages/opencode/src/server/middleware/rate-limit.ts` | Sliding window rate limiter (per IP + per org) |
| `packages/opencode/drizzle.ovd.config.ts` | Drizzle config for PostgreSQL OVD tables |
| `packages/opencode/migration-ovd/` | PostgreSQL migrations (schema, RLS, pgvector) |
| `infra/postgres/` | RLS policies and pgvector setup |
| `src/mcp/oracle/` | Oracle multi-sede MCP server (CAS/CAT/CAV) |
| `src/mcp/nats/` | NATS JetStream MCP server |
| `.opencode/agent/` | Custom agents: oracle-dba, python-backend, legacy-java, integration |
| `.opencode/command/` | Project skills: consulta-oracle, fix-legacy, migration-check, etc. |
| `scripts/` | setup-db.sh, seed-demo.ts |
| `.github/workflows/ovd-ci.yml` | CI: typecheck, tests, docker build, fork compliance |

### Changes from upstream — Phase 2 (Weeks 10–14)

| Module | Description |
|--------|-------------|
| `packages/opencode/src/ovd/cycle-log.ts` | Cycle log table: captures completed FR→QA cycles for fine-tuning |
| `packages/opencode/src/ovd/rag.ts` | RAG with pgvector: semantic search over SDDs, deliverables, markdown docs |
| `packages/opencode/src/ovd/rag-indexer.ts` | Auto-indexer: scans project .md files, hash-based change detection |
| `packages/opencode/src/server/routes/dashboard.ts` | Operations dashboard: cycle metrics, QA scores, session status, engine health |
| `src/finetune/export_cycles.py` | Exports cycle logs to Anthropic fine-tuning JSONL (3 example types) |
| `src/finetune/validate_dataset.py` | Validates JSONL format, token counts, duplicates |
| `src/finetune/upload_finetune.py` | Uploads to Anthropic Fine-tuning API, polls job status |
| `src/engine/graph.py` | LangGraph graph: structured output (Pydantic), agent router (4 specialists) |
| `src/engine/api.py` | FastAPI + SSE: full graph state in done event |

All other code is derived from the upstream OpenCode project under the terms of the Apache 2.0 License.

## License

This project is licensed under the Apache License 2.0.
See the [LICENSE](LICENSE) file for the full license text.

The original OpenCode copyright notice is preserved in all upstream-derived files.
