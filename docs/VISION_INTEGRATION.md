# Integración de Visión — qwen2-vl:7b en OVD Platform

**Estado:** Borrador — pendiente de revisión e iteración  
**Fecha:** 2026-04-21  
**Autor:** Omar Robles  

---

## Contexto

OVD Platform actualmente acepta Feature Requests como texto plano. Este documento describe cómo integrar un modelo de visión open-source (`qwen2-vl:7b` via Ollama) para que los usuarios puedan adjuntar imágenes, wireframes o screenshots como parte del FR, enriqueciendo el contexto que llega a los agentes.

---

## Modelo seleccionado: qwen2-vl:7b

| Atributo | Valor |
|---|---|
| Proveedor | Alibaba (open-source) |
| Tamaño | ~5 GB en RAM (Q4) |
| Fortaleza | Mejor modelo 7B para layouts, documentos y UI |
| Resolución | Dinámica — no degrada la imagen al procesarla |
| Formato | Disponible en Ollama: `ollama pull qwen2-vl:7b` |

**Por qué este modelo sobre los demás:**
- Entrenado específicamente en screenshots, documentos y layouts
- Soporta "dynamic resolution" — preserva detalles de UI complejos
- 5 GB caben junto al stack actual (~61 GB totales con qwen3-coder-next + deepseek-r1)
- Mejor relación calidad/tamaño para describir jerarquía visual de componentes

**Alternativas evaluadas:** `llama3.2-vision:11b` (8 GB, más lento), `gemma3:12b` (8 GB, mejor en español), `minicpm-v:8b` (multi-imagen), `llava:7b` (obsoleto).

---

## Arquitectura propuesta

El modelo de visión actúa como **pre-procesador**, no como reemplazo de ningún agente existente. El grafo LangGraph no cambia su lógica interna — solo se enriquece el input.

```
[usuario adjunta imagen/wireframe]
          ↓
    describe_image (nuevo nodo)
    qwen2-vl:7b → descripción textual del layout
          ↓
    analyze_fr (sin cambios internos)
    recibe: feature_request + image_description
          ↓
    generate_sdd → agentes → ... (sin cambios)
```

### Principio clave

`analyze_fr` y los agentes downstream **no saben que hubo una imagen**. Solo reciben texto enriquecido. Esto mantiene el grafo desacoplado del modelo de visión y permite cambiar `qwen2-vl:7b` por cualquier otro modelo futuro sin tocar el flujo.

---

## Cambios requeridos por componente

### 1. Engine — `src/engine/api.py`

**Archivo:** `src/engine/api.py` — clase `StartSessionRequest` (~línea 151)

Agregar dos campos opcionales:

```python
class StartSessionRequest(BaseModel):
    # ... campos existentes sin cambios ...
    image_base64: str = ""       # imagen cruda codificada en base64 (PNG/JPG/WEBP)
    image_description: str = ""  # descripción ya procesada (si el cliente hizo el proceso)
```

**Decisión de diseño:** Dos campos separados porque:
- `image_base64` → el engine llama a qwen2-vl internamente (más simple para el cliente)
- `image_description` → el cliente procesó la imagen externamente (más flexible)
- Si llega `image_description` no vacía, el nodo `describe_image` lo omite (no procesa de nuevo)

---

### 2. Engine — `src/engine/graph.py`

#### 2a. Nuevo campo en OVDState (~línea 298)

```python
class OVDState(TypedDict):
    # ... campos existentes sin cambios ...
    image_base64: str        # imagen cruda (se descarta después de describe_image)
    image_description: str   # descripción generada por qwen2-vl (fluye al analyze_fr)
```

#### 2b. Nuevo nodo `describe_image`

```python
async def describe_image(state: OVDState) -> dict:
    """
    Pre-procesa imagen adjunta con qwen2-vl:7b antes de analyze_fr.
    Si no hay imagen, es un no-op transparente.
    Si ya hay image_description, también es no-op (evita reprocesar).
    """
    if not state.get("image_base64") or state.get("image_description"):
        return {}

    llm_vision = build_llm(ResolvedConfig(
        provider="ollama",
        model=os.environ.get("OVD_VISION_MODEL", "qwen2-vl:7b"),
        ...
    ))

    prompt = (
        "Eres un asistente técnico especializado en UI/UX. "
        "Describe este diseño/wireframe/screenshot con el nivel de detalle necesario "
        "para que un desarrollador frontend pueda implementarlo sin ver la imagen. "
        "Incluye: estructura general, componentes visibles, jerarquía visual, "
        "colores dominantes, tipografía, espaciado aparente y flujo de interacción."
    )

    response = await llm_vision.ainvoke([
        HumanMessage(content=[
            {"type": "image_url", "image_url": {
                "url": f"data:image/png;base64,{state['image_base64']}"
            }},
            {"type": "text", "text": prompt},
        ])
    ])

    return {"image_description": response.content}
```

#### 2c. Inyectar descripción en `analyze_fr` (~línea 558)

```python
# Antes (sin cambios en la lógica):
human_content = f"Feature Request:\n{state['feature_request']}"

# Agregar (3 líneas):
image_desc = state.get("image_description", "")
if image_desc:
    human_content += f"\n\nDescripción visual del diseño adjunto:\n{image_desc}"

HumanMessage(content=human_content)
```

#### 2d. Posición en el grafo

```python
# build_graph() — agregar nodo y edge antes de analyze_fr
graph.add_node("describe_image", describe_image)
graph.add_edge(START, "describe_image")
graph.add_edge("describe_image", "analyze_fr")
# Remover el edge directo START → analyze_fr
```

---

### 3. Dashboard — `src/dashboard/src/pages/FrLauncher.tsx`

**Cambios en estado:**

```typescript
const [imageBase64, setImageBase64] = useState<string>('')
const [imagePreview, setImagePreview] = useState<string>('')
const [imageName, setImageName]     = useState<string>('')
```

**Handler de upload:**

```typescript
function handleImageUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
        const result = reader.result as string
        setImagePreview(result)                    // para mostrar preview
        setImageBase64(result.split(',')[1])       // solo el base64 puro
        setImageName(file.name)
    }
    reader.readAsDataURL(file)
}

function handleRemoveImage() {
    setImageBase64('')
    setImagePreview('')
    setImageName('')
}
```

**Envío:**

```typescript
body: JSON.stringify({
    feature_request: frText.trim(),
    auto_approve: autoApprove,
    project_id: selectedProject,
    org_id: orgId,
    image_base64: imageBase64 || undefined,
})
```

**UX recomendada para el formulario:**

- Drop zone encima o al lado del textarea (drag & drop + click)
- Preview inmediata de la imagen subida (miniatura 200x200px)
- Botón "×" para remover la imagen
- Label: "Adjuntar diseño / wireframe / screenshot (opcional)"
- Formatos aceptados: PNG, JPG, WEBP
- Sin multipart — viaja como base64 en el mismo JSON del POST

**Argumento UX:** El usuario no debe percibir que hay un modelo de visión. La experiencia es simplemente "adjunto mi boceto + escribo qué quiero". La imagen es contexto visual del FR, no una operación técnica separada.

---

### 4. TUI — `src/tui/src/ui/session.rs`

El TUI ya tiene `Ctrl+O` para cargar archivos `.md`. Se proponen dos opciones:

#### Opción A — `Ctrl+I` interactivo (similar a Ctrl+O)

```rust
pub struct SessionFormScreen {
    pub text: String,
    pub auto_approve: bool,
    pub file_mode: bool,
    pub file_input: String,
    pub image_mode: bool,      // nuevo
    pub image_path: String,    // nuevo — ruta escrita por el usuario
    pub image_base64: String,  // nuevo — bytes leídos y codificados
    pub image_name: String,    // nuevo — para mostrar en UI
}
```

Flujo:
1. `Ctrl+I` activa `image_mode`
2. Usuario escribe la ruta del archivo
3. `Enter` carga el archivo como bytes → base64
4. TUI muestra `[imagen: wireframe.png ✓]` en el formulario

#### Opción B — Flag CLI `--image path/to/image.png`

```bash
ovd-tui --image wireframe.png
```

La imagen se carga al iniciar y se adjunta automáticamente al FR.

**Recomendación:** Implementar ambas. El flag CLI es más ágil para el flujo de trabajo habitual (abrir TUI con la imagen ya indicada). El `Ctrl+I` es útil cuando ya estás en el formulario.

**Limitación de terminal:** No es posible mostrar preview visual de la imagen en terminal estándar (sin Kitty protocol). El indicador `[imagen: nombre.png ✓]` es suficiente.

---

### 5. Model Router — `src/engine/model_router.py`

Agregar constante para el modelo de visión:

```python
_VISION_MODEL = os.environ.get("OVD_VISION_MODEL", "qwen2-vl:7b")
_VISION_OLLAMA_URL = os.environ.get("OVD_VISION_OLLAMA_URL", _DEFAULT_OLLAMA_URL)
```

El nodo `describe_image` instancia el LLM de visión directamente vía `build_llm()`, sin pasar por el routing normal de agentes — es un rol fijo.

---

### 6. Variables de entorno nuevas (`.env`)

```bash
# --- Visión (S21) ---
OVD_VISION_MODEL=qwen2-vl:7b
OVD_VISION_OLLAMA_URL=http://localhost:11434
OVD_VISION_ENABLED=true          # permite desactivar sin remover el nodo
```

---

## Lo que NO cambia

| Componente | Por qué no cambia |
|---|---|
| Nodos de agentes (backend, frontend, database, devops) | Solo reciben `fr_analysis` enriquecido |
| `security_audit`, `qa_review` | Sin relación con el input visual |
| `nats_client` | Estructura de eventos sin cambios |
| Tests unitarios existentes | `image_base64` e `image_description` son `""` por defecto |
| Checkpointer / estado LangGraph | Campos nuevos son strings simples |

---

## Esfuerzo estimado por componente

| Componente | Esfuerzo | Archivos |
|---|---|---|
| Engine: campos nuevos en StartSessionRequest + OVDState | Bajo | `api.py`, `graph.py` |
| Engine: nodo `describe_image` + tests | Medio | `graph.py`, `tests/test_vision.py` |
| Engine: inyección en `analyze_fr` | Muy bajo | `graph.py` (3 líneas) |
| Engine: variables de entorno | Muy bajo | `.env`, `.env.prod.example` |
| Dashboard: drop zone + preview + envío | Medio | `FrLauncher.tsx` |
| TUI: `Ctrl+I` + flag `--image` | Medio | `session.rs`, `main.rs` |
| Migración (no requerida) | Ninguno | — |

---

## Dependencias antes de implementar

1. `ollama pull qwen2-vl:7b` — descargar el modelo (~5 GB)
2. Verificar que `qwen2-vl:7b` acepta imagen en base64 via API OpenAI-compatible de Ollama
3. Definir prompt óptimo para descripción de layouts (iterar antes de codificar)
4. Decidir si el procesamiento de imagen ocurre en el engine o en el cliente (recomendado: engine)

---

## Ideas pendientes de evaluación (Omar)

> *Sección para agregar ideas antes de iniciar el desarrollo*

<!-- Agregar aquí ideas a evaluar -->

---

## Referencias internas

- `docs/MODEL_STRATEGY.md` — estrategia de modelos del proyecto
- `docs/OSS_MODELS_ANALYSIS.md` — análisis de modelos open-source
- `src/engine/graph.py` — grafo LangGraph principal
- `src/engine/api.py` — API FastAPI del engine
- `src/dashboard/src/pages/FrLauncher.tsx` — formulario de FR en dashboard
- `src/tui/src/ui/session.rs` — formulario de FR en TUI
