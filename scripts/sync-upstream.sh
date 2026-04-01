#!/usr/bin/env bash
# OVD Platform — Sync con upstream anomalyco/opencode
# Copyright 2026 Omar Robles
#
# Fusiona los cambios del upstream en una rama aislada para revisión.
# NO hace merge directo a main — crea sync/upstream-<fecha> para PR.
#
# Uso:
#   ./scripts/sync-upstream.sh              # rama desde upstream/dev
#   ./scripts/sync-upstream.sh upstream/dev # rama explicita
#   DRY_RUN=1 ./scripts/sync-upstream.sh   # solo analiza, no crea rama
#
# Requisito: git remote "upstream" apuntando a anomalyco/opencode.git

set -euo pipefail

UPSTREAM_REMOTE="upstream"
UPSTREAM_BRANCH="${1:-dev}"
UPSTREAM_REF="${UPSTREAM_REMOTE}/${UPSTREAM_BRANCH}"
SYNC_BRANCH="sync/upstream-$(date +%Y%m%d)"
DRY_RUN="${DRY_RUN:-0}"

# ---------------------------------------------------------------------------
# Colores
# ---------------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'

info()    { echo -e "${BLUE}[sync]${NC} $*"; }
success() { echo -e "${GREEN}[sync]${NC} $*"; }
warn()    { echo -e "${YELLOW}[sync]${NC} $*"; }
error()   { echo -e "${RED}[sync]${NC} $*" >&2; }

# ---------------------------------------------------------------------------
# Verificaciones previas
# ---------------------------------------------------------------------------

if ! git remote get-url "${UPSTREAM_REMOTE}" &>/dev/null; then
  error "Remote '${UPSTREAM_REMOTE}' no configurado."
  echo "  git remote add upstream git@github.com:anomalyco/opencode.git"
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  error "Hay cambios sin commitear. Haz commit o stash antes de sincronizar."
  exit 1
fi

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "${CURRENT_BRANCH}" != "main" ]; then
  warn "No estás en main (estás en ${CURRENT_BRANCH}). Continuando de todas formas."
fi

# ---------------------------------------------------------------------------
# Fetch upstream
# ---------------------------------------------------------------------------

info "Fetching ${UPSTREAM_REMOTE}..."
git fetch "${UPSTREAM_REMOTE}" --quiet

MERGE_BASE=$(git merge-base HEAD "${UPSTREAM_REF}" 2>/dev/null || echo "")
if [ -z "${MERGE_BASE}" ]; then
  error "No se encontró merge-base con ${UPSTREAM_REF}. Historiales divergentes."
  exit 1
fi

UPSTREAM_NEW=$(git log "${MERGE_BASE}..${UPSTREAM_REF}" --oneline | wc -l | tr -d ' ')
OVD_NEW=$(git log "${MERGE_BASE}..HEAD" --oneline | wc -l | tr -d ' ')

info "Merge base: $(git rev-parse --short "${MERGE_BASE}")"
info "Commits nuevos en upstream: ${UPSTREAM_NEW}"
info "Commits OVD desde el fork:  ${OVD_NEW}"

if [ "${UPSTREAM_NEW}" -eq 0 ]; then
  success "Ya estamos sincronizados con ${UPSTREAM_REF}. Nada que hacer."
  exit 0
fi

# Mostrar qué cambió en upstream
echo ""
info "Commits nuevos en ${UPSTREAM_REF}:"
git log "${MERGE_BASE}..${UPSTREAM_REF}" --oneline --no-walk=unsorted | head -30

# Archivos que el upstream modificó en módulos críticos de OVD
CONFLICT_RISK=$(git diff "${MERGE_BASE}..${UPSTREAM_REF}" --name-only 2>/dev/null | grep -E \
  "packages/opencode/src/(server/server|auth|tenant|lsp)|package\.json|bun\.lock" \
  | head -20 || true)

if [ -n "${CONFLICT_RISK}" ]; then
  echo ""
  warn "Archivos con posible conflicto (upstream toca módulos base que OVD extiende):"
  echo "${CONFLICT_RISK}" | sed 's/^/  /'
fi

if [ "${DRY_RUN}" = "1" ]; then
  echo ""
  warn "DRY_RUN=1 — análisis completado, no se creó ninguna rama."
  exit 0
fi

# ---------------------------------------------------------------------------
# Crear rama de sync y hacer merge
# ---------------------------------------------------------------------------

echo ""
info "Creando rama ${SYNC_BRANCH}..."
git checkout -b "${SYNC_BRANCH}"

info "Merging ${UPSTREAM_REF} en ${SYNC_BRANCH}..."
if git merge "${UPSTREAM_REF}" \
    --no-ff \
    -m "chore(sync): merge upstream anomalyco/opencode @ $(git rev-parse --short ${UPSTREAM_REF})

Sincronización automática de ${UPSTREAM_NEW} commit(s) del upstream.
Merge base: ${MERGE_BASE}
Rama OVD:   ${CURRENT_BRANCH} (${OVD_NEW} commits propios desde el fork)

Revisar conflictos en módulos base antes de merge a main."; then
  echo ""
  success "Merge exitoso — sin conflictos."
  echo ""
  echo "  Próximos pasos:"
  echo "  1. Revisar los cambios: git diff main...${SYNC_BRANCH}"
  echo "  2. Ejecutar typecheck:  bun run typecheck"
  echo "  3. Ejecutar tests:      bun test"
  echo "  4. Abrir PR:            gh pr create --base main --head ${SYNC_BRANCH}"
else
  echo ""
  warn "Hay conflictos. Resuélvelos manualmente:"
  git diff --name-only --diff-filter=U | sed 's/^/  CONFLICT: /'
  echo ""
  echo "  1. Resolver cada conflicto (preservar módulos OVD en src/ovd/, src/tenant/, etc.)"
  echo "  2. git add <archivos resueltos>"
  echo "  3. git merge --continue"
  echo "  4. Ejecutar typecheck y tests"
  echo "  5. Abrir PR hacia main"
  exit 1
fi

git checkout "${CURRENT_BRANCH}"
info "De vuelta en ${CURRENT_BRANCH}. Rama lista: ${SYNC_BRANCH}"
