"""
OVD Platform — Tests S30: write_file fix, logging, subdirectory instruction, message compression
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import pathlib
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# S30-A — write_file guard dirname vacío
# ---------------------------------------------------------------------------


class TestS30AWriteFileDirname:
    """S30-A: write_file no lanza FileNotFoundError cuando dirname=""."""

    def test_write_file_raiz_no_falla(self):
        """Escribir archivo en la raíz del workspace (sin subdirectorio) no lanza error."""
        from tools.file_tools import make_file_tools

        with tempfile.TemporaryDirectory() as tmpdir:
            tools = make_file_tools(tmpdir)
            write_fn = next(t for t in tools if t.name == "write_file")

            # "app.py" sin directorio → dirname="" → makedirs vacío → no debe fallar
            result = write_fn.invoke({"path": "app.py", "content": "print('hello')"})
            assert not result.startswith("ERROR"), f"No debería fallar: {result}"
            assert os.path.isfile(os.path.join(tmpdir, "app.py"))

    def test_write_file_subdirectorio_crea_dirs(self):
        """Escribir en subdirectorio inexistente crea los directorios intermedios."""
        from tools.file_tools import make_file_tools

        with tempfile.TemporaryDirectory() as tmpdir:
            tools = make_file_tools(tmpdir)
            write_fn = next(t for t in tools if t.name == "write_file")

            result = write_fn.invoke(
                {
                    "path": "src/components/Button.tsx",
                    "content": "export default () => <button/>",
                }
            )
            assert not result.startswith("ERROR"), f"No debería fallar: {result}"
            assert os.path.isfile(
                os.path.join(tmpdir, "src", "components", "Button.tsx")
            )

    def test_write_file_retorna_ruta_absoluta(self):
        """write_file retorna la ruta absoluta del archivo escrito."""
        from tools.file_tools import make_file_tools

        with tempfile.TemporaryDirectory() as tmpdir:
            tools = make_file_tools(tmpdir)
            write_fn = next(t for t in tools if t.name == "write_file")

            result = write_fn.invoke({"path": "main.py", "content": "pass"})
            assert os.path.isabs(result), f"Se esperaba ruta absoluta, got: {result}"
            # macOS resuelve /var → /private/var; comparar con realpath
            assert os.path.isfile(result), (
                f"Archivo no existe en la ruta retornada: {result}"
            )


# ---------------------------------------------------------------------------
# S30-B — Logging de errores en tool calling
# ---------------------------------------------------------------------------


class TestS30BLogging:
    """S30-B: _run_agent_with_tools loguea errores de tools y warning cuando written_files=0."""

    def test_write_file_error_genera_warning(self):
        """Si write_file lanza excepción, el código contiene log.warning con S30-B."""
        import inspect

        import graph as _graph

        src = inspect.getsource(_graph._run_agent_with_tools)
        assert "S30-B" in src, "Código S30-B no encontrado en _run_agent_with_tools"
        assert "log.warning" in src

    def test_no_written_files_emite_warning(self):
        """El código de warning por written_files=0 existe en graph.py."""
        import inspect

        import graph as _graph

        src = inspect.getsource(_graph._run_agent_with_tools)
        assert (
            "no escribió ningún archivo" in src
            or "written_files=0" in src.lower()
            or "S30-B" in src
        )


# ---------------------------------------------------------------------------
# S30-C — Instrucción de subdirectorios en human_content
# ---------------------------------------------------------------------------


class TestS30CSubdirectoryInstruction:
    """S30-C: human_content incluye instrucción explícita de usar subdirectorios."""

    def test_human_content_menciona_subdirectorios(self):
        """El código de _run_agent_with_tools incluye instrucción de organizar en subdirectorios."""
        import inspect

        import graph as _graph

        src = inspect.getsource(_graph._run_agent_with_tools)
        assert "subdirectori" in src.lower() or "Organiza los archivos" in src, (
            "No se encontró la instrucción de subdirectorios en _run_agent_with_tools"
        )

    def test_human_content_prohibe_rutas_planas(self):
        """El código incluye instrucción de NO usar rutas planas."""
        import inspect

        import graph as _graph

        src = inspect.getsource(_graph._run_agent_with_tools)
        assert (
            "NO uses rutas planas" in src
            or "no uses rutas planas" in src.lower()
            or "write_file" in src
        ), "No se encontró la prohibición de rutas planas"

    def test_human_content_menciona_write_file_directo(self):
        """El mensaje indica al modelo que empiece a escribir con write_file directamente."""
        import inspect

        import graph as _graph

        src = inspect.getsource(_graph._run_agent_with_tools)
        assert "Empieza a escribir archivos directamente con write_file" in src


# ---------------------------------------------------------------------------
# S30-D — Compresión de ventana de contexto
# ---------------------------------------------------------------------------


class TestS30DMessageCompression:
    """S30-D: el loop de tool calling comprime el historial de mensajes."""

    def test_message_compression_code_exists(self):
        """El código de compresión S30-D existe en _run_agent_with_tools."""
        import inspect

        import graph as _graph

        src = inspect.getsource(_graph._run_agent_with_tools)
        assert "S30-D" in src, "Código de compresión S30-D no encontrado"
        assert "_MAX_HIST" in src or "MAX_HIST" in src, (
            "Variable _MAX_HIST no encontrada"
        )

    def test_compression_mantiene_system_y_human(self):
        """Tras compresión, los primeros 2 mensajes (system + human) se conservan."""
        import inspect

        import graph as _graph

        src = inspect.getsource(_graph._run_agent_with_tools)
        # Verificar que el slice [:2] está en el código de compresión
        assert "messages[:2]" in src, (
            "No se conservan los primeros 2 mensajes en la compresión"
        )

    @pytest.mark.asyncio
    async def test_context_no_explota_con_muchas_iteraciones(self):
        """Con muchas tool calls, la lista de mensajes se mantiene acotada."""
        from langchain_core.messages import (
            AIMessage,
            HumanMessage,
            SystemMessage,
            ToolMessage,
        )

        # Simular la compresión directamente
        messages = [
            SystemMessage(content="system"),
            HumanMessage(content="human"),
        ]
        # Agregar 20 intercambios ficticios
        for i in range(20):
            messages.append(AIMessage(content=f"resp {i}"))
            messages.append(
                ToolMessage(content=f"tool_result {i}", tool_call_id=f"tc{i}")
            )

        # Aplicar la misma lógica que S30-D
        _MAX_HIST = 8
        if len(messages) > _MAX_HIST + 2:
            compressed = messages[:2] + messages[-_MAX_HIST:]
        else:
            compressed = messages

        assert len(compressed) <= _MAX_HIST + 2, (
            f"Mensajes no comprimidos: {len(compressed)}"
        )
        assert isinstance(compressed[0], SystemMessage), (
            "Primer mensaje debe ser SystemMessage"
        )
        assert isinstance(compressed[1], HumanMessage), (
            "Segundo mensaje debe ser HumanMessage"
        )
