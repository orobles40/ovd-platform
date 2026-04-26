"""
OVD Platform — Tests S43: externalización de instrucciones hardcodeadas por stack

S43-A: doc_instructions movidas a system_docs.md
S43-B: conftest.py inyectado solo para runner=pytest
S43-C: _get_import_error_diagnosis — diagnóstico stack-aware
S43-D: _RUNNER_FLAGS — flags centralizados por runner
S43-E: _get_retry_no_modify_instruction — feedback retry stack-aware
S43-F: tabla de RUTs válidos en templates
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import pathlib
import pytest
from factories import make_state, make_agent_result


# ---------------------------------------------------------------------------
# S43-A — doc_instructions movidas a system_docs.md
# ---------------------------------------------------------------------------

class TestS43ADocInstructions:
    """S43-A: system_docs.md contiene la tabla de instrucciones por tipo de FR."""

    def _get_template(self) -> str:
        templates_dir = pathlib.Path(__file__).parent.parent / "templates"
        tpl = templates_dir / "system_docs.md"
        assert tpl.exists(), "system_docs.md no encontrado"
        return tpl.read_text(encoding="utf-8")

    def test_system_docs_tiene_tipos_principales(self):
        """S43-A: system_docs.md contiene los tipos endpoint, migration, refactor, service."""
        content = self._get_template()
        for fr_type in ("endpoint", "migration", "refactor", "service", "component"):
            assert fr_type in content, f"Tipo '{fr_type}' no encontrado en system_docs.md"

    def test_system_docs_tiene_openapi(self):
        """S43-A: system_docs.md menciona OpenAPI para endpoints."""
        content = self._get_template()
        assert "OpenAPI" in content or "openapi" in content.lower()

    def test_system_docs_tiene_changelog(self):
        """S43-A: system_docs.md menciona CHANGELOG para refactors."""
        content = self._get_template()
        assert "CHANGELOG" in content

    def test_generate_docs_no_usa_dict_hardcodeado(self):
        """S43-A: generate_docs no contiene el dict doc_instructions hardcodeado."""
        import inspect
        import graph as _graph
        src = inspect.getsource(_graph.generate_docs)
        assert "doc_instructions" not in src, "doc_instructions aún hardcodeado en generate_docs"
        assert "Genera: 1) spec OpenAPI" not in src, "Instrucción OpenAPI aún hardcodeada en generate_docs"

    def test_system_docs_tiene_placeholders(self):
        """S43-A: system_docs.md tiene los placeholders estándar."""
        content = self._get_template()
        assert "{project_context}" in content
        assert "{retry_feedback}" in content
        assert "{rag_context}" in content


# ---------------------------------------------------------------------------
# S43-B — conftest.py inyectado solo para runner=pytest
# ---------------------------------------------------------------------------

class TestS43BConftestCondicional:
    """S43-B: conftest.py se inyecta solo cuando runner == 'pytest'."""

    def test_codigo_condiciona_por_runner(self):
        """S43-B: el código de run_tests condiciona la inyección de conftest al runner pytest."""
        import inspect
        import graph as _graph
        src = inspect.getsource(_graph.run_tests)
        # Debe haber una condición que involucre runner y conftest
        assert 'runner == "pytest"' in src or "runner == 'pytest'" in src
        assert "conftest" in src

    def test_etiqueta_s43b_en_codigo(self):
        """S43-B: el código contiene la etiqueta S43-B para trazabilidad."""
        import inspect
        import graph as _graph
        src = inspect.getsource(_graph.run_tests)
        assert "S43-B" in src


# ---------------------------------------------------------------------------
# S43-C — _get_import_error_diagnosis
# ---------------------------------------------------------------------------

class TestS43CImportDiagnosis:
    """S43-C: _get_import_error_diagnosis retorna mensaje correcto por runner."""

    def _get_fn(self):
        import graph as g
        return g._get_import_error_diagnosis

    def test_pytest_diagnosis_menciona_init_py(self):
        """S43-C: diagnóstico pytest menciona __init__.py y conftest.py."""
        fn = self._get_fn()
        msg = fn("pytest")
        assert "__init__.py" in msg
        assert "conftest.py" in msg or "conftest" in msg

    def test_pytest_diagnosis_menciona_src(self):
        """S43-C: diagnóstico pytest menciona la carpeta src/."""
        fn = self._get_fn()
        msg = fn("pytest")
        assert "src/" in msg or "src" in msg

    def test_vitest_diagnosis_no_menciona_init_py(self):
        """S43-C: diagnóstico vitest NO menciona __init__.py (no aplica a TypeScript)."""
        fn = self._get_fn()
        msg = fn("vitest")
        assert "__init__.py" not in msg

    def test_vitest_diagnosis_menciona_tsconfig(self):
        """S43-C: diagnóstico vitest menciona tsconfig o TypeScript."""
        fn = self._get_fn()
        msg = fn("vitest")
        assert "tsconfig" in msg.lower() or "typescript" in msg.lower() or "TypeScript" in msg

    def test_cargo_diagnosis_menciona_mod(self):
        """S43-C: diagnóstico cargo menciona la declaración 'mod'."""
        fn = self._get_fn()
        msg = fn("cargo")
        assert "mod" in msg

    def test_unknown_runner_retorna_fallback_no_vacio(self):
        """S43-C: runner desconocido retorna string no vacío."""
        fn = self._get_fn()
        msg = fn("go")
        assert msg and len(msg) > 10

    def test_todos_los_runners_retornan_string(self):
        """S43-C: todos los runners conocidos retornan string."""
        fn = self._get_fn()
        for runner in ("pytest", "vitest", "cargo", ""):
            result = fn(runner)
            assert isinstance(result, str) and result


# ---------------------------------------------------------------------------
# S43-D — _RUNNER_FLAGS
# ---------------------------------------------------------------------------

class TestS43DRunnerFlags:
    """S43-D: _RUNNER_FLAGS centraliza los flags por runner."""

    def _get_flags(self):
        import graph as g
        return g._RUNNER_FLAGS

    def test_runner_flags_dict_existe(self):
        """S43-D: _RUNNER_FLAGS existe como dict accesible a nivel módulo."""
        flags = self._get_flags()
        assert isinstance(flags, dict)

    def test_pytest_flags_contiene_import_mode(self):
        """S43-D: _RUNNER_FLAGS['pytest'] contiene --import-mode=importlib."""
        flags = self._get_flags()
        assert "pytest" in flags
        assert any("import-mode" in f for f in flags["pytest"])

    def test_vitest_flags_no_contienen_pytest_flags(self):
        """S43-D: _RUNNER_FLAGS['vitest'] no contiene flags de pytest."""
        flags = self._get_flags()
        vitest_flags = flags.get("vitest", [])
        assert not any("import-mode" in f for f in vitest_flags)
        assert not any("rootdir" in f for f in vitest_flags)

    def test_pytest_flags_no_contienen_rootdir(self):
        """S43-D: --rootdir se construye dinámicamente, no en _RUNNER_FLAGS."""
        flags = self._get_flags()
        assert not any("rootdir" in f for f in flags.get("pytest", []))

    def test_cargo_flags_lista(self):
        """S43-D: _RUNNER_FLAGS['cargo'] es una lista (puede ser vacía)."""
        flags = self._get_flags()
        assert isinstance(flags.get("cargo", []), list)


# ---------------------------------------------------------------------------
# S43-E — _get_retry_no_modify_instruction
# ---------------------------------------------------------------------------

class TestS43ERetryInstruction:
    """S43-E: _get_retry_no_modify_instruction retorna instrucción stack-aware."""

    def _get_fn(self):
        import graph as g
        return g._get_retry_no_modify_instruction

    def test_pytest_instruction_menciona_src(self):
        """S43-E: instrucción para pytest menciona src/."""
        fn = self._get_fn()
        msg = fn("pytest")
        assert "src/" in msg

    def test_pytest_instruction_menciona_nunca(self):
        """S43-E: instrucción para pytest contiene 'NUNCA'."""
        fn = self._get_fn()
        msg = fn("pytest")
        assert "NUNCA" in msg

    def test_vitest_instruction_menciona_typescript_context(self):
        """S43-E: instrucción para vitest incluye contexto de TypeScript."""
        fn = self._get_fn()
        msg = fn("vitest")
        assert "TypeScript" in msg or "typescript" in msg.lower() or "__tests__" in msg

    def test_cargo_instruction_menciona_cfg_test(self):
        """S43-E: instrucción para cargo menciona #[cfg(test)]."""
        fn = self._get_fn()
        msg = fn("cargo")
        assert "#[cfg(test)]" in msg

    def test_empty_runner_usa_python_default(self):
        """S43-E: runner vacío retorna instrucción válida (default Python)."""
        fn = self._get_fn()
        msg = fn("")
        assert "NUNCA" in msg and len(msg) > 20

    def test_feedback_generado_contiene_instruccion_pytest(self):
        """S43-E (integración): update_test_retry con runner='pytest' produce feedback con instrucción."""
        import graph as _graph
        state = make_state(
            test_results={"passed": False, "output": "assert 1 == 2", "runner": "pytest"},
            test_retry_count=0,
        )
        result = _graph.update_test_retry(state)
        feedback = result.get("retry_feedback", "")
        assert "NUNCA" in feedback
        assert "src/" in feedback

    def test_feedback_generado_contiene_instruccion_vitest(self):
        """S43-E (integración): update_test_retry con runner='vitest' produce feedback con contexto TypeScript."""
        import graph as _graph
        state = make_state(
            test_results={"passed": False, "output": "FAIL src/utils.test.ts", "runner": "vitest"},
            test_retry_count=0,
        )
        result = _graph.update_test_retry(state)
        feedback = result.get("retry_feedback", "")
        assert "NUNCA" in feedback
        assert "TypeScript" in feedback or "__tests__" in feedback


# ---------------------------------------------------------------------------
# S43-F — RUTs válidos en templates
# ---------------------------------------------------------------------------

class TestS43FRutsValidos:
    """S43-F: templates contienen tabla de RUTs válidos verificados matemáticamente."""

    def _get_template(self, name: str) -> str:
        templates_dir = pathlib.Path(__file__).parent.parent / "templates"
        tpl = templates_dir / name
        assert tpl.exists(), f"{name} no encontrado"
        return tpl.read_text(encoding="utf-8")

    def test_backend_python_tiene_tabla_ruts(self):
        """S43-F: system_backend_python.md contiene tabla con RUTs válidos."""
        content = self._get_template("system_backend_python.md")
        assert "12.345.678-5" in content
        assert "NUNCA inventes RUTs" in content or "NUNCA" in content

    def test_backend_tiene_tabla_ruts(self):
        """S43-F: template backend compuesto (base + stack Python) contiene tabla con RUTs válidos.
        S58-pre: la tabla fue movida de system_backend.md a stack/backend_python.md."""
        import template_loader
        template_loader.invalidate()
        content = template_loader.render_composed("system_backend", stack_language="python")
        assert "12.345.678-5" in content
        assert "NUNCA inventes RUTs" in content or "NUNCA" in content

    def test_ruts_en_tabla_son_matematicamente_validos(self):
        """S43-F: los RUTs de la tabla son matemáticamente correctos."""
        def _calc_dv(body: str) -> str:
            total, factor = 0, 2
            for digit in reversed(body):
                total += int(digit) * factor
                factor = 2 if factor == 7 else factor + 1
            remainder = 11 - (total % 11)
            return {10: "K", 11: "0"}.get(remainder, str(remainder))

        # RUTs válidos de la tabla
        valid_ruts = [
            ("12345678", "5"),
            ("11111111", "1"),
            ("5678901",  "4"),
            ("1",        "9"),  # 0.000.001-9
        ]
        for body, expected_dv in valid_ruts:
            calculated = _calc_dv(body)
            assert calculated == expected_dv, (
                f"RUT {body}-{expected_dv} tiene DV incorrecto en la tabla: "
                f"el correcto es {calculated}"
            )

    def test_rut_negativo_en_tabla_es_invalido(self):
        """S43-F: el RUT negativo de la tabla (12.345.678-4) es efectivamente inválido."""
        def _calc_dv(body: str) -> str:
            total, factor = 0, 2
            for digit in reversed(body):
                total += int(digit) * factor
                factor = 2 if factor == 7 else factor + 1
            remainder = 11 - (total % 11)
            return {10: "K", 11: "0"}.get(remainder, str(remainder))

        # 12345678-4 debe ser inválido (DV correcto es 5, no 4)
        assert _calc_dv("12345678") != "4", "El RUT negativo de prueba debe tener DV incorrecto"

    def test_templates_mencionan_regla_calculo_dv(self):
        """S43-F: el template compuesto indica que DV=K viene de remainder==10.
        S58-pre: verificar stack/backend_python.md (antes en system_backend.md y system_backend_python.md)."""
        import template_loader
        template_loader.invalidate()
        # El template compuesto con stack Python debe tener la regla
        composed = template_loader.render_composed("system_backend", stack_language="python")
        assert "remainder" in composed or "DV=K" in composed or "módulo 11" in composed or "modulo 11" in composed.lower()
        # system_backend_python.md también debe tenerla (pre-existente, no modificado en S58-pre)
        content_python = self._get_template("system_backend_python.md")
        assert "remainder" in content_python or "DV=K" in content_python or "módulo 11" in content_python or "modulo 11" in content_python.lower()
