#!/usr/bin/env bash
# S96-I — Clonar repos de referencia en src/knowledge/external/
# Uso: ./scripts/setup-knowledge.sh
# Los repos NO se indexan en pgvector — son para grep/lectura directa durante sesiones.

set -e

KNOWLEDGE_DIR="$(cd "$(dirname "$0")/.." && pwd)/src/knowledge/external"
mkdir -p "$KNOWLEDGE_DIR"

echo "==> Directorio: $KNOWLEDGE_DIR"
echo ""

clone_or_update() {
  local name="$1"
  local url="$2"
  local dir="$KNOWLEDGE_DIR/$name"

  if [ -d "$dir/.git" ]; then
    echo "  [UPDATE] $name"
    git -C "$dir" pull --quiet
  else
    echo "  [CLONE]  $name"
    git clone --quiet --depth=1 "$url" "$dir"
  fi
}

sparse_clone_or_update() {
  local name="$1"
  local url="$2"
  shift 2
  local dirs=("$@")
  local dir="$KNOWLEDGE_DIR/$name"

  if [ -d "$dir/.git" ]; then
    echo "  [UPDATE] $name (sparse)"
    git -C "$dir" pull --quiet
  else
    echo "  [CLONE]  $name (sparse: ${dirs[*]})"
    git clone --quiet --depth=1 --filter=blob:none --sparse "$url" "$dir"
    git -C "$dir" sparse-checkout set "${dirs[@]}"
    git -C "$dir" checkout --quiet
  fi
}

echo "--- Categoría 1: Metodología y skills ---"
clone_or_update "superpowers"   "https://github.com/obra/superpowers.git"
sparse_clone_or_update "hermes-agent" "https://github.com/NousResearch/hermes-agent.git" \
  "optional-skills/mcp/fastmcp" \
  "skills/creative/popular-web-designs" \
  "skills/github" \
  "skills/software-development" \
  "optional-skills/mlops"

echo ""
echo "--- Categoría 2: AI Coding Agents ---"
clone_or_update "opencode"    "https://github.com/anomalyco/opencode.git"
clone_or_update "aider"       "https://github.com/Aider-AI/aider.git"
clone_or_update "OpenHands"   "https://github.com/OpenHands/OpenHands.git"
clone_or_update "SWE-agent"   "https://github.com/SWE-agent/SWE-agent.git"
clone_or_update "cline"       "https://github.com/cline/cline.git"
clone_or_update "codex"       "https://github.com/openai/codex.git"

echo ""
echo "--- Categoría 3: Frameworks multi-agente ---"
clone_or_update "langgraph"   "https://github.com/langchain-ai/langgraph.git"
clone_or_update "autogen"     "https://github.com/microsoft/autogen.git"

echo ""
echo "--- Categoría 4: Stack técnico ---"
clone_or_update "litellm"                    "https://github.com/BerriAI/litellm.git"
clone_or_update "pydantic-ai"                "https://github.com/pydantic/pydantic-ai.git"
clone_or_update "full-stack-fastapi-template" "https://github.com/tiangolo/full-stack-fastapi-template.git"

echo ""
echo "==> Listo. Repos disponibles en src/knowledge/external/"
echo ""
ls -1 "$KNOWLEDGE_DIR"
