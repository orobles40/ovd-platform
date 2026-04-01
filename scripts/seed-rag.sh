#!/usr/bin/env bash
# OVD Platform — Seed RAG por proyecto (GAP-006)
# Copyright 2026 Omar Robles
#
# Inicializa el índice RAG de un proyecto con:
#   1. El Project Profile del proyecto (constraints, stack, descripción)
#   2. Archivos adicionales de conocimiento (opcional)
#
# Uso:
#   ./scripts/seed-rag.sh --org ORG_ID --project PROJ_ID --token JWT
#   ./scripts/seed-rag.sh --org ORG_ID --project PROJ_ID --token JWT --file docs/arch.md
#   ./scripts/seed-rag.sh --org ORG_ID --project PROJ_ID --token JWT --dir docs/
#   ./scripts/seed-rag.sh --org ORG_ID --project PROJ_ID --token JWT --search "autenticacion"
#
# Variables de entorno (alternativa a flags):
#   OVD_ORG_ID    — ID de la organización
#   OVD_TOKEN     — JWT del Bridge
#   OVD_BRIDGE_URL — URL del Bridge (default: http://localhost:3000)

set -euo pipefail

BRIDGE_URL="${OVD_BRIDGE_URL:-http://localhost:3000}"
ORG_ID="${OVD_ORG_ID:-}"
TOKEN="${OVD_TOKEN:-}"
PROJECT_ID=""
FILE=""
DIR=""
SEARCH_QUERY=""

# ---------------------------------------------------------------------------
# Parse args
# ---------------------------------------------------------------------------

while [[ $# -gt 0 ]]; do
  case "$1" in
    --org)        ORG_ID="$2";      shift 2 ;;
    --project)    PROJECT_ID="$2";  shift 2 ;;
    --token)      TOKEN="$2";       shift 2 ;;
    --file)       FILE="$2";        shift 2 ;;
    --dir)        DIR="$2";         shift 2 ;;
    --search)     SEARCH_QUERY="$2"; shift 2 ;;
    --bridge-url) BRIDGE_URL="$2";  shift 2 ;;
    --help|-h)
      echo "Uso: $0 --org ORG_ID --project PROJ_ID --token JWT [--file FILE] [--dir DIR]"
      exit 0
      ;;
    *) echo "Flag desconocido: $1"; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Validar argumentos requeridos
# ---------------------------------------------------------------------------

if [[ -z "$PROJECT_ID" ]]; then
  echo "ERROR: --project es requerido"
  exit 1
fi

if [[ -z "$TOKEN" ]]; then
  echo "ERROR: --token es requerido (o exporta OVD_TOKEN)"
  exit 1
fi

# ---------------------------------------------------------------------------
# Modo búsqueda
# ---------------------------------------------------------------------------

if [[ -n "$SEARCH_QUERY" ]]; then
  echo ""
  echo "Buscando en RAG: '$SEARCH_QUERY'"
  curl -s -f \
    -H "Authorization: Bearer ${TOKEN}" \
    "${BRIDGE_URL}/ovd/rag/search?query=$(python3 -c "import urllib.parse; print(urllib.parse.quote('${SEARCH_QUERY}'))")&projectId=${PROJECT_ID}&topK=5" \
    | python3 -c "
import json, sys
data = json.load(sys.stdin)
results = data.get('results', [])
if not results:
    print('Sin resultados relevantes.')
    sys.exit(0)
for r in results:
    doc = r.get('document', {})
    print(f\"\\n[{r['score']:.2f}] {doc.get('title', '?')} ({doc.get('doc_type', '?')})\")
    print(doc.get('content', '')[:300])
"
  exit 0
fi

# ---------------------------------------------------------------------------
# Seed desde el Project Profile (siempre se ejecuta)
# ---------------------------------------------------------------------------

echo ""
echo "OVD RAG Seed — Proyecto: ${PROJECT_ID}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Bridge: ${BRIDGE_URL}"
echo ""

echo "  Indexando Project Profile..."
SEED_RESPONSE=$(curl -s -f \
  -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{}" \
  "${BRIDGE_URL}/ovd/project/${PROJECT_ID}/rag/seed")

if [[ $? -eq 0 ]]; then
  INDEXED=$(echo "$SEED_RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin).get('indexed', 0))")
  echo "  ✅ Perfil indexado (${INDEXED} documento(s))"
else
  echo "  ✗ Error al indexar el perfil"
  echo "  Respuesta: $SEED_RESPONSE"
  exit 1
fi

# ---------------------------------------------------------------------------
# Indexar archivo adicional (--file)
# ---------------------------------------------------------------------------

if [[ -n "$FILE" ]]; then
  if [[ ! -f "$FILE" ]]; then
    echo "  ✗ Archivo no encontrado: $FILE"
    exit 1
  fi

  TITLE=$(basename "$FILE" | sed 's/\.[^.]*$//' | tr '-_' ' ')
  CONTENT=$(cat "$FILE")

  echo "  Indexando archivo: $FILE"
  curl -s -f \
    -X POST \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"projectId\":\"${PROJECT_ID}\",\"docType\":\"markdown\",\"title\":\"${TITLE}\",\"content\":$(echo "$CONTENT" | python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))")}" \
    "${BRIDGE_URL}/ovd/rag/index" > /dev/null

  echo "  ✅ Archivo indexado: $TITLE"
fi

# ---------------------------------------------------------------------------
# Indexar directorio de archivos .md (--dir)
# ---------------------------------------------------------------------------

if [[ -n "$DIR" ]]; then
  if [[ ! -d "$DIR" ]]; then
    echo "  ✗ Directorio no encontrado: $DIR"
    exit 1
  fi

  echo "  Indexando directorio: $DIR"
  indexed_files=0

  while IFS= read -r -d '' md_file; do
    TITLE=$(basename "$md_file" .md | tr '-_' ' ')
    CONTENT=$(cat "$md_file")

    curl -s -f \
      -X POST \
      -H "Authorization: Bearer ${TOKEN}" \
      -H "Content-Type: application/json" \
      -d "{\"projectId\":\"${PROJECT_ID}\",\"docType\":\"markdown\",\"title\":\"${TITLE}\",\"content\":$(echo "$CONTENT" | python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))")}" \
      "${BRIDGE_URL}/ovd/rag/index" > /dev/null

    echo "  ✅ ${TITLE}"
    indexed_files=$((indexed_files + 1))
  done < <(find "$DIR" -name "*.md" -type f -print0 | sort -z)

  echo "  Total: ${indexed_files} archivo(s) indexado(s)"
fi

# ---------------------------------------------------------------------------
# Resumen
# ---------------------------------------------------------------------------

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Seed completado para proyecto: ${PROJECT_ID}"
echo "  El RAG ahora contiene contexto del stack tecnológico."
echo ""
echo "  Para verificar: $0 --project ${PROJECT_ID} --token TOKEN --search 'QUERY'"
echo ""
