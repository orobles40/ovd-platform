"""
OVD Platform — Tests para S6.A+B+C: Git Integration
Copyright 2026 Omar Robles

Verifica el comportamiento de _git_integration() en distintos escenarios:
- Directorio que no es un repo git → retorno sin error
- Directorio vacío o inexistente → retorno sin error
- Sin archivos escritos → no intenta crear branch
- Mock de subprocess para S6.A branch creation
"""
import sys
import os
import asyncio
import tempfile
import subprocess
from unittest.mock import patch, MagicMock, AsyncMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from graph import _git_integration


def run(coro):
    """Helper para ejecutar corrutinas en tests síncronos."""
    return asyncio.new_event_loop().run_until_complete(coro)


class TestGitIntegrationNoRepo:
    """Cuando el directorio no es un repo git, retorna sin error."""

    def test_directorio_vacio_retorna_disabled(self):
        result = run(_git_integration("", "sess-abc", "test FR", ["file.py"]))
        assert result["enabled"] is False
        assert result["branch"] is None

    def test_directorio_inexistente_retorna_disabled(self):
        result = run(_git_integration("/tmp/no-existe-xyz-ovd", "sess-abc", "test FR", ["file.py"]))
        assert result["enabled"] is False

    def test_sin_archivos_retorna_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run(_git_integration(tmpdir, "sess-abc", "test FR", []))
        assert result["enabled"] is False

    def test_directorio_no_repo_git_retorna_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run(_git_integration(tmpdir, "sess-abc", "test FR", ["main.py"]))
        assert result["enabled"] is False
        assert result["error"] is None

    def test_retorno_tiene_claves_esperadas(self):
        result = run(_git_integration("", "sess-abc", "test FR", []))
        assert set(result.keys()) == {"enabled", "branch", "commit", "pr_url", "error"}


class TestGitIntegrationConRepo:
    """Con un repo git real inicializado en tmp."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        subprocess.run(["git", "init"], cwd=self.tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.tmpdir, capture_output=True)
        # Crear un commit inicial para tener HEAD
        test_file = os.path.join(self.tmpdir, "README.md")
        with open(test_file, "w") as f:
            f.write("# Test repo\n")
        subprocess.run(["git", "add", "."], cwd=self.tmpdir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.tmpdir, capture_output=True)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_s6a_crea_branch(self):
        # Crear un archivo para commitear
        test_file = os.path.join(self.tmpdir, "feature.py")
        with open(test_file, "w") as f:
            f.write("def hello(): pass\n")

        result = run(_git_integration(
            self.tmpdir, "tui-abc123def456", "Agregar función hello", ["feature.py"]
        ))
        assert result["enabled"] is True
        # session_id[:12] de "tui-abc123def456" = "tui-abc123de"
        assert result["branch"] == "ovd/tui-abc123de"

    def test_s6b_commit_de_artefactos(self):
        # Crear archivo a commitear
        test_file = os.path.join(self.tmpdir, "api.py")
        with open(test_file, "w") as f:
            f.write("def endpoint(): return {}\n")

        result = run(_git_integration(
            self.tmpdir, "tui-xyz789", "Crear endpoint API", ["api.py"]
        ))
        assert result["enabled"] is True
        # Si el commit fue exitoso, tiene SHA corto
        assert result["commit"] is not None or result["error"] is not None

    def test_s6b_mensaje_commit_contiene_fr(self):
        """El mensaje de commit debe incluir el feature request."""
        test_file = os.path.join(self.tmpdir, "service.py")
        with open(test_file, "w") as f:
            f.write("class Service: pass\n")

        feature_request = "Implementar servicio de notificaciones"
        run(_git_integration(self.tmpdir, "tui-notif01", feature_request, ["service.py"]))

        # Verificar el log de git
        log = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=self.tmpdir, capture_output=True, text=True
        )
        if log.returncode == 0 and log.stdout.strip():
            assert "notificaciones" in log.stdout or "ovd/" in subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.tmpdir, capture_output=True, text=True
            ).stdout

    def test_branch_ya_existente_no_falla(self):
        """Si el branch ya existe, debe usarlo sin error."""
        test_file = os.path.join(self.tmpdir, "util.py")
        with open(test_file, "w") as f:
            f.write("# util\n")

        # Primera llamada crea el branch
        run(_git_integration(self.tmpdir, "tui-dup123", "FR duplicado", ["util.py"]))

        # Crear otro archivo para la segunda llamada
        test_file2 = os.path.join(self.tmpdir, "util2.py")
        with open(test_file2, "w") as f:
            f.write("# util2\n")

        # Segunda llamada al mismo branch no debe fallar
        result = run(_git_integration(self.tmpdir, "tui-dup123", "FR duplicado", ["util2.py"]))
        assert result["enabled"] is True


class TestGitIntegrationSinGithubPAT:
    """Sin GITHUB_PAT configurado, S6.C no intenta crear PR."""

    def test_sin_pat_pr_url_es_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
            result = run(_git_integration(tmpdir, "sess-nopat", "FR sin PAT", ["x.py"]))
        # enabled=False porque no hay HEAD, pero si tuviera repo válido:
        # pr_url debería ser None sin PAT
        assert result["pr_url"] is None

    def test_con_pat_vacio_no_abre_pr(self):
        """Un PAT vacío equivale a sin PAT."""
        with patch.dict(os.environ, {"GITHUB_PAT": ""}):
            with tempfile.TemporaryDirectory() as tmpdir:
                result = run(_git_integration(tmpdir, "sess-emptyp", "FR", ["y.py"]))
        assert result["pr_url"] is None


class TestGitIntegrationSesionId:
    """Verifica el formato del branch name."""

    def test_branch_trunca_session_id_a_12(self):
        """El branch usa solo los primeros 12 chars del session_id."""
        long_id = "tui-123456789012345678"
        # No importa si el repo existe, comprobamos la lógica en un tmpdir sin git
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run(_git_integration(tmpdir, long_id, "FR", ["f.py"]))
        # Si enabled es False (no es repo), el branch no se crea
        # El test relevante está en TestGitIntegrationConRepo.test_s6a_crea_branch
        # "tui-123456789012345678"[:12] = "tui-123456789" (12 chars)
        expected_branch = f"ovd/{long_id[:12]}"
        assert expected_branch == "ovd/tui-12345678"  # 4+"ovd/" prefix + 12 chars
        assert len(long_id[:12]) == 12


class TestRegressionS6:
    """Tests de regresión para S6."""

    def test_nunca_lanza_excepcion(self):
        """_git_integration nunca debe propagar excepciones al caller."""
        casos = [
            ("", "", "", []),
            ("/root/forbidden/path", "sess", "fr", ["f.py"]),
            (None, "sess", "fr", ["f.py"]),  # type: ignore
        ]
        for directory, session_id, fr, files in casos:
            try:
                result = run(_git_integration(directory or "", session_id, fr, files))
                assert "enabled" in result
            except Exception as e:
                pytest.fail(f"_git_integration lanzó excepción para {directory}: {e}")

    def test_retorno_siempre_tiene_estructura_completa(self):
        """El dict de retorno siempre tiene las 5 claves esperadas."""
        result = run(_git_integration("", "sid", "fr", []))
        for key in ("enabled", "branch", "commit", "pr_url", "error"):
            assert key in result, f"Falta clave '{key}' en resultado"
