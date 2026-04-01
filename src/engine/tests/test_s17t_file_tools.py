"""
OVD Platform — Tests para S17T: File Tools y Tool Calling
Copyright 2026 Omar Robles

Verifica que:
- make_file_tools() retorna herramientas funcionales con base_dir vinculado
- write_file, read_file, edit_file, list_files operan correctamente
- Path traversal está bloqueado en todas las operaciones de escritura/lectura
- read_project_context() filtra archivos irrelevantes
- make_file_tools() retorna [] si el directorio no existe
"""
import sys
import os
import json
import tempfile
import pathlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import pytest
from tools.file_tools import make_file_tools, read_project_context


class TestMakeFileTools:
    """Verifica la fábrica de herramientas."""

    def test_directorio_valido_retorna_4_herramientas(self):
        with tempfile.TemporaryDirectory() as d:
            tools = make_file_tools(d)
        assert len(tools) == 4

    def test_directorio_inexistente_retorna_lista_vacia(self):
        tools = make_file_tools("/ruta/que/no/existe-ovd-test")
        assert tools == []

    def test_directorio_vacio_retorna_lista_vacia(self):
        tools = make_file_tools("")
        assert tools == []

    def test_herramientas_tienen_nombre(self):
        with tempfile.TemporaryDirectory() as d:
            tools = make_file_tools(d)
        names = {t.name for t in tools}
        assert names == {"write_file", "read_file", "edit_file", "list_files"}

    def test_herramientas_tienen_descripcion(self):
        with tempfile.TemporaryDirectory() as d:
            tools = make_file_tools(d)
        for t in tools:
            assert t.description, f"'{t.name}' sin descripción"


class TestWriteFile:
    """Pruebas de write_file."""

    def _get_tool(self, base_dir: str):
        tools = make_file_tools(base_dir)
        return next(t for t in tools if t.name == "write_file")

    def test_escribe_archivo_simple(self):
        with tempfile.TemporaryDirectory() as d:
            tool = self._get_tool(d)
            result = tool.invoke({"path": "hello.py", "content": "print('hello')\n"})
            assert "hello.py" in result
            assert (pathlib.Path(d) / "hello.py").read_text() == "print('hello')\n"

    def test_crea_directorios_intermedios(self):
        with tempfile.TemporaryDirectory() as d:
            tool = self._get_tool(d)
            tool.invoke({"path": "src/api/routes.py", "content": "# routes"})
            assert (pathlib.Path(d) / "src" / "api" / "routes.py").exists()

    def test_sobreescribe_archivo_existente(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "f.py").write_text("version1")
            tool = self._get_tool(d)
            tool.invoke({"path": "f.py", "content": "version2"})
            assert (pathlib.Path(d) / "f.py").read_text() == "version2"

    def test_path_traversal_bloqueado(self):
        with tempfile.TemporaryDirectory() as d:
            tool = self._get_tool(d)
            with pytest.raises(ValueError, match="Ruta denegada"):
                tool.invoke({"path": "../../etc/passwd", "content": "mal"})

    def test_path_traversal_con_slash_absoluto(self):
        with tempfile.TemporaryDirectory() as d:
            tool = self._get_tool(d)
            with pytest.raises(ValueError, match="Ruta denegada"):
                tool.invoke({"path": "/etc/passwd", "content": "mal"})


class TestReadFile:
    """Pruebas de read_file."""

    def _get_tool(self, base_dir: str):
        tools = make_file_tools(base_dir)
        return next(t for t in tools if t.name == "read_file")

    def test_lee_archivo_existente(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "config.py").write_text("DEBUG = True\n")
            tool = self._get_tool(d)
            content = tool.invoke({"path": "config.py"})
            assert "DEBUG = True" in content

    def test_archivo_inexistente_retorna_error(self):
        with tempfile.TemporaryDirectory() as d:
            tool = self._get_tool(d)
            result = tool.invoke({"path": "no-existe.py"})
            assert "ERROR" in result

    def test_trunca_archivos_grandes(self):
        with tempfile.TemporaryDirectory() as d:
            # 40 KB de contenido
            (pathlib.Path(d) / "big.txt").write_text("X" * 40_000)
            tool = self._get_tool(d)
            content = tool.invoke({"path": "big.txt"})
            assert len(content) <= 32_768 + 10  # tolerancia mínima

    def test_path_traversal_bloqueado(self):
        with tempfile.TemporaryDirectory() as d:
            tool = self._get_tool(d)
            with pytest.raises(ValueError, match="Ruta denegada"):
                tool.invoke({"path": "../secreto.txt"})


class TestEditFile:
    """Pruebas de edit_file."""

    def _get_tool(self, base_dir: str):
        tools = make_file_tools(base_dir)
        return next(t for t in tools if t.name == "edit_file")

    def test_reemplaza_cadena_existente(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "app.py").write_text("version = 1\n")
            tool = self._get_tool(d)
            result = tool.invoke({"path": "app.py", "old_str": "version = 1", "new_str": "version = 2"})
            assert result == "OK"
            assert (pathlib.Path(d) / "app.py").read_text() == "version = 2\n"

    def test_cadena_no_encontrada_retorna_error(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "app.py").write_text("a = 1\n")
            tool = self._get_tool(d)
            result = tool.invoke({"path": "app.py", "old_str": "no_existe", "new_str": "x"})
            assert "ERROR" in result

    def test_archivo_inexistente_retorna_error(self):
        with tempfile.TemporaryDirectory() as d:
            tool = self._get_tool(d)
            result = tool.invoke({"path": "ghost.py", "old_str": "x", "new_str": "y"})
            assert "ERROR" in result

    def test_solo_reemplaza_primera_ocurrencia(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "f.py").write_text("a\na\na\n")
            tool = self._get_tool(d)
            tool.invoke({"path": "f.py", "old_str": "a", "new_str": "b"})
            content = (pathlib.Path(d) / "f.py").read_text()
            assert content == "b\na\na\n"


class TestListFiles:
    """Pruebas de list_files."""

    def _get_tool(self, base_dir: str):
        tools = make_file_tools(base_dir)
        return next(t for t in tools if t.name == "list_files")

    def test_lista_archivos_existentes(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "a.py").touch()
            (pathlib.Path(d) / "b.py").touch()
            tool = self._get_tool(d)
            result = tool.invoke({"pattern": "*.py"})
            assert "a.py" in result
            assert "b.py" in result

    def test_directorio_vacio_retorna_sin_archivos(self):
        with tempfile.TemporaryDirectory() as d:
            tool = self._get_tool(d)
            result = tool.invoke({"pattern": "**/*"})
            assert "(sin archivos)" in result

    def test_respeta_patron_glob(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "main.py").touch()
            (pathlib.Path(d) / "index.ts").touch()
            tool = self._get_tool(d)
            result = tool.invoke({"pattern": "*.ts"})
            assert "index.ts" in result
            assert "main.py" not in result

    def test_retorna_string(self):
        with tempfile.TemporaryDirectory() as d:
            tool = self._get_tool(d)
            result = tool.invoke({})
            assert isinstance(result, str)


class TestReadProjectContext:
    """Pruebas de read_project_context (S17T.C)."""

    def test_directorio_inexistente_retorna_vacio(self):
        result = read_project_context("/no/existe", "backend")
        assert result == ""

    def test_directorio_vacio_retorna_vacio(self):
        result = read_project_context("", "frontend")
        assert result == ""

    def test_encuentra_archivos_python_para_backend(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "api.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")
            result = read_project_context(d, "backend")
        assert "api.py" in result
        assert "FastAPI" in result

    def test_encuentra_archivos_ts_para_frontend(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "App.tsx").write_text("export default function App() {}\n")
            result = read_project_context(d, "frontend")
        assert "App.tsx" in result

    def test_ignora_node_modules(self):
        with tempfile.TemporaryDirectory() as d:
            nm = pathlib.Path(d) / "node_modules"
            nm.mkdir()
            (nm / "react.js").write_text("// react")
            result = read_project_context(d, "frontend")
        assert "node_modules" not in result

    def test_ignora_directorio_punto(self):
        with tempfile.TemporaryDirectory() as d:
            git = pathlib.Path(d) / ".git"
            git.mkdir()
            (git / "HEAD").write_text("ref: refs/heads/main")
            result = read_project_context(d, "backend")
        assert ".git" not in result

    def test_limita_numero_de_archivos(self):
        with tempfile.TemporaryDirectory() as d:
            # Crear 10 archivos Python
            for i in range(10):
                (pathlib.Path(d) / f"module_{i}.py").write_text(f"# module {i}\n")
            result = read_project_context(d, "backend")
        # Máximo 3 archivos (separados por "---")
        sections = result.split("---")
        assert len(sections) <= 3 + 1  # 3 secciones + header/footer

    def test_retorna_header_y_footer(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "app.py").write_text("pass\n")
            result = read_project_context(d, "backend")
        assert "Archivos existentes" in result
        assert "Fin del contexto" in result

    def test_no_lanza_excepcion_con_archivo_binario(self):
        with tempfile.TemporaryDirectory() as d:
            # Escribir bytes no UTF-8
            (pathlib.Path(d) / "data.py").write_bytes(b"\xff\xfe invalido\n")
            try:
                result = read_project_context(d, "backend")
                assert isinstance(result, str)
            except Exception as e:
                pytest.fail(f"read_project_context lanzó excepción: {e}")


class TestRegressionS17T:
    """Tests de regresión para S17T."""

    def test_make_file_tools_es_determinista(self):
        """Llamar make_file_tools dos veces con el mismo dir da los mismos nombres."""
        with tempfile.TemporaryDirectory() as d:
            tools1 = make_file_tools(d)
            tools2 = make_file_tools(d)
        names1 = {t.name for t in tools1}
        names2 = {t.name for t in tools2}
        assert names1 == names2

    def test_write_y_read_roundtrip(self):
        """Escribir y leer el mismo archivo da el contenido original."""
        with tempfile.TemporaryDirectory() as d:
            tools = make_file_tools(d)
            write = next(t for t in tools if t.name == "write_file")
            read  = next(t for t in tools if t.name == "read_file")

            content = "# Este es el contenido\nprint('test')\n"
            write.invoke({"path": "roundtrip.py", "content": content})
            read_back = read.invoke({"path": "roundtrip.py"})
            assert read_back == content

    def test_write_edit_read_chain(self):
        """Escribir → editar → leer produce el resultado esperado."""
        with tempfile.TemporaryDirectory() as d:
            tools = make_file_tools(d)
            write = next(t for t in tools if t.name == "write_file")
            edit  = next(t for t in tools if t.name == "edit_file")
            read  = next(t for t in tools if t.name == "read_file")

            write.invoke({"path": "ver.txt", "content": "v1"})
            edit.invoke({"path": "ver.txt", "old_str": "v1", "new_str": "v2"})
            assert read.invoke({"path": "ver.txt"}) == "v2"
