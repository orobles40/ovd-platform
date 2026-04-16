#!/usr/bin/env bash
# OVD Platform — Actualización de skills externos
#
# Uso: ./scripts/update-skills.sh
#
# ui-ux-pro-max: actualización automática (solo datos CSV y scripts)
# superpowers:   solo muestra diff — la integración en templates es manual

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UI_UX_DIR="$REPO_ROOT/src/knowledge/ui-ux"
SP_DIR="$REPO_ROOT/src/knowledge/superpowers-upstream"

# ── ui-ux-pro-max ────────────────────────────────────────────────────────────
echo "── ui-ux-pro-max (actualización automática) ──────────────────"
if [ ! -d "$UI_UX_DIR/.git" ]; then
  echo "No encontrado. Clonando..."
  git clone --depth=1 https://github.com/nextlevelbuilder/ui-ux-pro-max-skill "$UI_UX_DIR"
else
  BEFORE=$(git -C "$UI_UX_DIR" rev-parse HEAD)
  git -C "$UI_UX_DIR" pull --ff-only origin main
  AFTER=$(git -C "$UI_UX_DIR" rev-parse HEAD)
  if [ "$BEFORE" = "$AFTER" ]; then
    echo "Sin cambios."
  else
    echo "Actualizado: $BEFORE → $AFTER"
    git -C "$UI_UX_DIR" log --oneline "$BEFORE..$AFTER"
  fi
fi

echo ""

# ── superpowers ──────────────────────────────────────────────────────────────
echo "── superpowers (solo revisión — integración manual) ──────────"
if [ ! -d "$SP_DIR/.git" ]; then
  echo "No encontrado. Clonando..."
  git clone --depth=1 https://github.com/obra/superpowers "$SP_DIR"
else
  git -C "$SP_DIR" fetch origin --quiet
  CHANGES=$(git -C "$SP_DIR" log --oneline HEAD..origin/main -- skills/ 2>/dev/null || true)
  if [ -z "$CHANGES" ]; then
    echo "Sin cambios en skills."
  else
    echo "Cambios pendientes de revisión manual:"
    echo "$CHANGES"
    echo ""
    echo "Para ver el diff completo:"
    echo "  git -C $SP_DIR diff HEAD origin/main -- skills/"
    echo ""
    echo "Skills integrados en OVD (revisar si cambiaron):"
    for skill in writing-plans verification-before-completion test-driven-development \
                 subagent-driven-development requesting-code-review receiving-code-review; do
      SKILL_CHANGES=$(git -C "$SP_DIR" log --oneline HEAD..origin/main -- "skills/$skill/" 2>/dev/null || true)
      if [ -n "$SKILL_CHANGES" ]; then
        echo "  ⚠  $skill — tiene cambios"
      fi
    done
  fi
fi

echo ""
echo "Listo."
