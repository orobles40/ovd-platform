"""
S21 — Tests del nodo describe_image y la inyección en analyze_fr.
"""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_state(**kwargs) -> dict:
    """Estado mínimo para el nodo describe_image."""
    defaults = {
        "image_base64": "",
        "image_description": "",
        "feature_request": "Crear un formulario de login",
        "messages": [],
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# describe_image — no-op paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_describe_image_noop_sin_imagen():
    """Sin image_base64, retorna {} limpiando image_base64 vacío."""
    import graph as g

    state = _make_state(image_base64="")
    result = await g.describe_image(state)

    assert result == {"image_base64": ""}
    # image_description no debe haberse generado
    assert "image_description" not in result or result.get("image_description") is None


@pytest.mark.asyncio
async def test_describe_image_noop_si_ya_hay_descripcion():
    """Si image_description ya existe, no llama al modelo."""
    import graph as g

    state = _make_state(
        image_base64="abc123",
        image_description="descripción previa del layout",
    )

    with patch("graph.ChatOpenAI") as mock_llm_cls:
        result = await g.describe_image(state)

    mock_llm_cls.assert_not_called()
    assert result == {"image_base64": ""}


@pytest.mark.asyncio
async def test_describe_image_noop_si_vision_disabled():
    """Con OVD_VISION_ENABLED=false, no llama al modelo aunque haya imagen."""
    import graph as g

    state = _make_state(image_base64="abc123")

    with (
        patch.object(g, "_VISION_ENABLED", False),
        patch("graph.ChatOpenAI") as mock_llm_cls,
    ):
        result = await g.describe_image(state)

    mock_llm_cls.assert_not_called()
    assert result == {"image_base64": ""}


# ---------------------------------------------------------------------------
# describe_image — happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_describe_image_llama_modelo_y_retorna_descripcion():
    """Con imagen y visión habilitada, llama al modelo y retorna descripción."""
    import graph as g

    state = _make_state(image_base64="iVBORw0KGgoAAAANSUhEUgA=")

    mock_response = MagicMock()
    mock_response.content = "Formulario con campo email, campo password y botón azul centrado."

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with (
        patch.object(g, "_VISION_ENABLED", True),
        patch("graph.ChatOpenAI", return_value=mock_llm),
    ):
        result = await g.describe_image(state)

    assert result["image_base64"] == ""  # bytes limpios
    assert result["image_description"] == "Formulario con campo email, campo password y botón azul centrado."


@pytest.mark.asyncio
async def test_describe_image_limpia_base64_tras_procesar():
    """Después de procesar, image_base64 queda vacío en el resultado."""
    import graph as g

    state = _make_state(image_base64="datosimagenlargo==")

    mock_response = MagicMock()
    mock_response.content = "Wireframe de dashboard con sidebar y tabla."

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with (
        patch.object(g, "_VISION_ENABLED", True),
        patch("graph.ChatOpenAI", return_value=mock_llm),
    ):
        result = await g.describe_image(state)

    assert result["image_base64"] == ""


# ---------------------------------------------------------------------------
# describe_image — error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_describe_image_error_no_rompe_ciclo():
    """Si el modelo falla, retorna {} sin propagar la excepción."""
    import graph as g

    state = _make_state(image_base64="abc123")

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("qwen2.5vl timeout"))

    with (
        patch.object(g, "_VISION_ENABLED", True),
        patch("graph.ChatOpenAI", return_value=mock_llm),
    ):
        result = await g.describe_image(state)  # no debe lanzar

    assert result == {"image_base64": ""}
    assert "image_description" not in result or not result.get("image_description")


# ---------------------------------------------------------------------------
# _build_fr_content — inyección en analyze_fr
# ---------------------------------------------------------------------------

def test_build_fr_content_sin_imagen():
    """Sin imagen, retorna solo el Feature Request."""
    import graph as g

    state = _make_state(feature_request="Agregar autenticación OAuth")
    content = g._build_fr_content(state)

    assert content == "Feature Request:\nAgregar autenticación OAuth"
    assert "Descripción visual" not in content


def test_build_fr_content_con_imagen():
    """Con image_description, la inyecta después del Feature Request."""
    import graph as g

    state = _make_state(
        feature_request="Crear pantalla de login",
        image_description="Panel centrado con logo, dos inputs y botón primario azul.",
    )
    content = g._build_fr_content(state)

    assert "Feature Request:\nCrear pantalla de login" in content
    assert "Descripción visual del diseño adjunto:" in content
    assert "Panel centrado con logo" in content


def test_build_fr_content_imagen_vacia_no_agrega_seccion():
    """image_description vacío no agrega la sección visual."""
    import graph as g

    state = _make_state(
        feature_request="Refactorizar el módulo de pagos",
        image_description="",
    )
    content = g._build_fr_content(state)

    assert "Descripción visual" not in content
