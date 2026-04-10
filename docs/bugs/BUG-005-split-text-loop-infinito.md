# BUG-005 — `_split_text()` loop infinito cuando max_chars <= _CHUNK_OVERLAP

**Fecha detectado:** 2026-04-08
**Severidad:** Media (no afecta producción — los chunkers usan `_MAX_CHUNK_CHARS=2000` >> `_CHUNK_OVERLAP=200`)
**Módulo:** `src/knowledge/chunkers.py`
**Detectado por:** Suite de tests Fase A (test_rag_chunkers.py)

---

## Descripción

La función `_split_text(text, max_chars)` entra en loop infinito cuando
`max_chars <= _CHUNK_OVERLAP (200)`.

```python
# chunkers.py — líneas relevantes
_CHUNK_OVERLAP = 200

def _split_text(text: str, max_chars: int) -> list[str]:
    ...
    while start < len(text):
        end = min(start + max_chars, len(text))
        ...
        chunks.append(text[start:end])
        start = end - _CHUNK_OVERLAP if end < len(text) else end  # ← BUG
```

**Ejemplo que causa el loop:**
```python
_split_text("x" * 500, max_chars=200)
# Iteración 1: start=0, end=200
# start = 200 - 200 = 0  ← no avanza → loop infinito
```

---

## Impacto actual

**Nulo en producción** — todos los usos internos pasan `_MAX_CHUNK_CHARS=2000`:
- `chunk_codebase` → `_MAX_CHUNK_CHARS` (2000)
- `chunk_schema` → `_MAX_CHUNK_CHARS` (2000)
- `chunk_doc` → `_MAX_CHUNK_CHARS` (2000)
- etc.

El bug solo se activa si alguien llama `_split_text()` directamente con `max_chars <= 200`.

---

## Fix propuesto

```python
# Garantizar que start siempre avance al menos 1 carácter
next_start = end - _CHUNK_OVERLAP if end < len(text) else end
start = max(next_start, start + 1)  # evita loop infinito
```

---

## Workaround en tests

Los tests de `test_rag_chunkers.py` usan `max_chars >= 400` para evitar el cuelgue.
Comentario en el código:
```python
# max_chars debe ser > _CHUNK_OVERLAP (200) para evitar loop infinito — ver BUG-005
```

---

## Próximo paso

Corregir en la siguiente sesión antes de implementar tests E2E (Fase B).
El fix es una línea — bajo riesgo de regresión.
