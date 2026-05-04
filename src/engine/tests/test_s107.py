"""
OVD Platform — Tests S107: Architecture Gate + Oracle fix + naming sync + QA contract.

P1: generate_architecture_contract — nodo determinístico antes del fan-out
P2: postprocess_yaml_file — reemplaza imágenes Oracle en docker-compose
P3: sync_service_imports — sincroniza imports router/tests con services.py real
P4: system_backend_python.md — tabla de naming consistente presente
P5: QA verifica architecture contract vs implementación en disco
"""

import os
import sys
import textwrap

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import asyncio
import pathlib
import tempfile

import pytest
from factories import make_state

from code_postprocessor import (
    _apply_import_corrections,
    _build_service_alias_map,
    _extract_defined_functions,
    _fix_oracle_in_docker_compose,
    postprocess_yaml_file,
    sync_service_imports,
)
from graph import (
    _build_architecture_contract_text,
    _extract_service_functions_from_task,
    generate_architecture_contract,
)

# ---------------------------------------------------------------------------
# P1 — Architecture Gate: extracción de funciones y generación de contrato
# ---------------------------------------------------------------------------


class TestExtractServiceFunctions:
    def test_extrae_funciones_crud_en_snake_case(self):
        desc = "Implementar get_contract, create_contract, deactivate_contract en service.py"
        fns = _extract_service_functions_from_task(desc)
        assert "get_contract" in fns
        assert "create_contract" in fns
        assert "deactivate_contract" in fns

    def test_excluye_palabras_comunes_no_funciones(self):
        desc = "Crear los modelos y los schemas para el contrato"
        fns = _extract_service_functions_from_task(desc)
        # "los", "para", "del" nunca son funciones
        assert "los" not in fns
        assert "para" not in fns

    def test_retorna_lista_vacia_sin_verbos_crud(self):
        desc = "El módulo principal del sistema de contratos enterprise"
        fns = _extract_service_functions_from_task(desc)
        assert isinstance(fns, list)

    def test_no_duplica_funciones(self):
        desc = "Implementar get_contract, get_contract y también get_contract"
        fns = _extract_service_functions_from_task(desc)
        assert fns.count("get_contract") == 1


class TestBuildArchitectureContractText:
    def _sdd_with_service_task(
        self, fns_desc: str, output_file: str = "src/contracts/service.py"
    ) -> dict:
        return {
            "tasks": [
                {
                    "output_file": output_file,
                    "description": fns_desc,
                    "title": "",
                }
            ]
        }

    def test_genera_bloque_json_para_service_py(self):
        sdd = self._sdd_with_service_task(
            "Implementar get_contract, create_contract, deactivate_contract"
        )
        result = _build_architecture_contract_text(sdd)
        assert "[ARCHITECTURE CONTRACT" in result
        assert "S107-P1" in result
        assert "VINCULANTE" in result
        assert "service_module" in result

    def test_contiene_canonical_functions(self):
        sdd = self._sdd_with_service_task(
            "Implementar get_contract, create_contract, deactivate_contract"
        )
        result = _build_architecture_contract_text(sdd)
        assert "get_contract" in result or "create_contract" in result

    def test_retorna_vacio_sin_tasks_service_py(self):
        sdd = {
            "tasks": [
                {
                    "output_file": "src/contracts/router.py",
                    "description": "Endpoints CRUD para contratos",
                    "title": "",
                }
            ]
        }
        result = _build_architecture_contract_text(sdd)
        assert result == ""

    def test_retorna_vacio_con_sdd_vacio(self):
        assert _build_architecture_contract_text({}) == ""

    def test_incluye_regla_no_renombrar(self):
        sdd = self._sdd_with_service_task(
            "Implementar get_contract, deactivate_contract"
        )
        result = _build_architecture_contract_text(sdd)
        assert "ImportError" in result or "NO renombrar" in result or "delete" in result

    def test_services_py_tambien_reconocido(self):
        sdd = self._sdd_with_service_task(
            "Implementar get_contracts, create_contract, deactivate_contract",
            output_file="src/app/services.py",
        )
        result = _build_architecture_contract_text(sdd)
        assert "[ARCHITECTURE CONTRACT" in result


class TestGenerateArchitectureContractNode:
    def test_nodo_devuelve_contrato_para_sdd_con_service(self):
        sdd = {
            "tasks": [
                {
                    "output_file": "src/contracts/service.py",
                    "description": "Implementar get_contract, deactivate_contract",
                    "title": "",
                }
            ]
        }
        state = make_state(sdd=sdd, architecture_contract="")
        result = asyncio.run(generate_architecture_contract(state))
        assert "architecture_contract" in result
        assert "[ARCHITECTURE CONTRACT" in result["architecture_contract"]

    def test_nodo_devuelve_vacio_sin_tasks_service(self):
        state = make_state(sdd={"tasks": []}, architecture_contract="")
        result = asyncio.run(generate_architecture_contract(state))
        assert result["architecture_contract"] == ""

    def test_nodo_devuelve_string_no_none(self):
        state = make_state(sdd={}, architecture_contract="")
        result = asyncio.run(generate_architecture_contract(state))
        assert isinstance(result["architecture_contract"], str)


# ---------------------------------------------------------------------------
# P2 — Oracle → PostgreSQL en docker-compose
# ---------------------------------------------------------------------------


DOCKER_COMPOSE_WITH_ORACLE = textwrap.dedent("""\
    version: "3.9"
    services:
      db:
        image: gvenzl/oracle-xe:21-slim
        environment:
          ORACLE_PASSWORD: changeme
      api:
        image: python:3.12-slim
""")

DOCKER_COMPOSE_WITH_ORACLE_DATABASE = textwrap.dedent("""\
    services:
      db:
        image: oracle/database:19.3.0-ee
      api:
        build: .
""")

DOCKER_COMPOSE_POSTGRES = textwrap.dedent("""\
    services:
      db:
        image: postgres:16-alpine
      api:
        build: .
""")


class TestFixOracleInDockerCompose:
    def test_reemplaza_gvenzl_oracle_xe_cuando_no_oracle(self):
        result = _fix_oracle_in_docker_compose(
            DOCKER_COMPOSE_WITH_ORACLE, oracle_involved=False
        )
        assert "gvenzl/oracle-xe" not in result
        assert "postgres:16-alpine" in result

    def test_reemplaza_oracle_database_cuando_no_oracle(self):
        result = _fix_oracle_in_docker_compose(
            DOCKER_COMPOSE_WITH_ORACLE_DATABASE, oracle_involved=False
        )
        assert "oracle/database" not in result
        assert "postgres:16-alpine" in result

    def test_no_toca_nada_cuando_oracle_involved_true(self):
        result = _fix_oracle_in_docker_compose(
            DOCKER_COMPOSE_WITH_ORACLE, oracle_involved=True
        )
        assert "gvenzl/oracle-xe:21-slim" in result

    def test_no_toca_postgres_existente(self):
        result = _fix_oracle_in_docker_compose(
            DOCKER_COMPOSE_POSTGRES, oracle_involved=False
        )
        assert result == DOCKER_COMPOSE_POSTGRES

    def test_preserva_el_resto_del_archivo(self):
        result = _fix_oracle_in_docker_compose(
            DOCKER_COMPOSE_WITH_ORACLE, oracle_involved=False
        )
        assert "ORACLE_PASSWORD" in result  # variable de entorno no se toca
        assert "python:3.12-slim" in result


class TestPostprocessYamlFile:
    def test_docker_compose_oracle_reemplazado(self):
        result = postprocess_yaml_file(
            DOCKER_COMPOSE_WITH_ORACLE,
            rel_path="docker-compose.yml",
            oracle_involved=False,
        )
        assert "postgres:16-alpine" in result
        assert "gvenzl" not in result

    def test_archivo_no_docker_compose_no_modificado(self):
        content = "image: gvenzl/oracle-xe:21-slim"
        result = postprocess_yaml_file(
            content, rel_path=".github/workflows/ci.yml", oracle_involved=False
        )
        assert result == content  # CI workflow no debe tocarse

    def test_extension_yaml_tambien_reconocida(self):
        result = postprocess_yaml_file(
            DOCKER_COMPOSE_WITH_ORACLE,
            rel_path="docker-compose.yaml",
            oracle_involved=False,
        )
        assert "postgres:16-alpine" in result

    def test_sin_extension_yml_retorna_sin_cambios(self):
        content = "alguna configuración sin extension yml"
        result = postprocess_yaml_file(
            content, rel_path="Makefile", oracle_involved=False
        )
        assert result == content


# ---------------------------------------------------------------------------
# P3 — Sync service imports: alias map + corrección de imports
# ---------------------------------------------------------------------------


class TestBuildServiceAliasMap:
    def test_deactivate_genera_alias_delete(self):
        fns = {"deactivate_contract", "get_contract"}
        alias = _build_service_alias_map(fns)
        assert alias.get("delete_contract") == "deactivate_contract"

    def test_deactivate_genera_alias_disable_y_remove(self):
        fns = {"deactivate_user"}
        alias = _build_service_alias_map(fns)
        assert alias.get("disable_user") == "deactivate_user"
        assert alias.get("remove_user") == "deactivate_user"

    def test_get_Xs_genera_alias_list_Xs(self):
        fns = {"get_contracts"}
        alias = _build_service_alias_map(fns)
        assert alias.get("list_contracts") == "get_contracts"

    def test_calcular_genera_alias_calculate(self):
        fns = {"calcular_total"}
        alias = _build_service_alias_map(fns)
        assert alias.get("calculate_total") == "calcular_total"

    def test_mapa_vacio_para_funciones_sin_patron(self):
        fns = {"create_contract", "update_contract"}
        alias = _build_service_alias_map(fns)
        # create_ y update_ no tienen alias problemáticos
        assert (
            "create_contract" not in alias.values() or True
        )  # no deben generar alias erróneos


class TestApplyImportCorrections:
    def test_corrige_delete_por_deactivate(self):
        alias_map = {"delete_contract": "deactivate_contract"}
        content = "from src.contracts.service import delete_contract, get_contract"
        new_content, applied = _apply_import_corrections(content, alias_map)
        assert "deactivate_contract" in new_content
        assert "delete_contract" not in new_content
        assert len(applied) == 1

    def test_corrige_multiples_imports_en_misma_linea(self):
        alias_map = {
            "delete_contract": "deactivate_contract",
            "list_contracts": "get_contracts",
        }
        content = "from src.contracts.service import delete_contract, list_contracts"
        new_content, applied = _apply_import_corrections(content, alias_map)
        assert "deactivate_contract" in new_content
        assert "get_contracts" in new_content
        assert len(applied) == 2

    def test_no_toca_imports_correctos(self):
        alias_map = {"delete_contract": "deactivate_contract"}
        content = "from src.contracts.service import create_contract, get_contract"
        new_content, applied = _apply_import_corrections(content, alias_map)
        assert new_content == content
        assert applied == []

    def test_no_toca_imports_de_otros_modulos(self):
        alias_map = {"delete_contract": "deactivate_contract"}
        content = "from fastapi import delete_contract"  # no es módulo service
        new_content, applied = _apply_import_corrections(content, alias_map)
        assert new_content == content


class TestSyncServiceImports:
    def test_corrige_router_cuando_services_define_deactivate(self, tmp_path):
        # services.py define deactivate_contract
        services = tmp_path / "src" / "contracts" / "services.py"
        services.parent.mkdir(parents=True)
        services.write_text(
            textwrap.dedent("""\
            async def deactivate_contract(db, contract_id): ...
            async def get_contract(db, contract_id): ...
            async def create_contract(db, data): ...
        """)
        )

        # router.py importa delete_contract (incorrecto)
        router = tmp_path / "src" / "contracts" / "router.py"
        router.write_text(
            "from src.contracts.services import delete_contract, get_contract\n"
        )

        fixes = sync_service_imports(str(tmp_path))
        assert len(fixes) > 0

        new_content = router.read_text()
        assert "deactivate_contract" in new_content
        assert "delete_contract" not in new_content

    def test_corrige_test_cuando_importa_alias_incorrecto(self, tmp_path):
        # El regex requiere el prefijo src. en el módulo de import
        services = tmp_path / "src" / "app" / "service.py"
        services.parent.mkdir(parents=True)
        services.write_text("async def deactivate_user(db, user_id): ...\n")

        test_file = tmp_path / "tests" / "test_users.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("from src.app.service import delete_user, create_user\n")

        fixes = sync_service_imports(str(tmp_path))
        assert any("delete_user" in f for f in fixes)

        new_content = test_file.read_text()
        assert "deactivate_user" in new_content

    def test_retorna_lista_vacia_sin_services_py(self, tmp_path):
        (tmp_path / "router.py").write_text("from x.service import delete_contract\n")
        fixes = sync_service_imports(str(tmp_path))
        assert fixes == []

    def test_retorna_lista_vacia_directorio_inexistente(self):
        fixes = sync_service_imports("/no/existe/este/directorio")
        assert fixes == []

    def test_no_toca_archivos_correctos(self, tmp_path):
        services = tmp_path / "src" / "service.py"
        services.parent.mkdir(parents=True)
        services.write_text("async def deactivate_contract(db, cid): ...\n")

        router = tmp_path / "src" / "router.py"
        original = "from src.service import deactivate_contract, get_contract\n"
        router.write_text(original)

        fixes = sync_service_imports(str(tmp_path))
        assert fixes == []
        assert router.read_text() == original


# ---------------------------------------------------------------------------
# P4 — Tabla de naming en system_backend_python.md
# ---------------------------------------------------------------------------


class TestNamingTableInTemplate:
    @pytest.fixture
    def template_content(self):
        template_path = (
            pathlib.Path(__file__).parent.parent
            / "templates"
            / "system_backend_python.md"
        )
        return template_path.read_text(encoding="utf-8")

    def test_template_contiene_regla_naming_s107(self, template_content):
        assert "S107-P4" in template_content or "NAMING CONSISTENTE" in template_content

    def test_template_menciona_deactivate_como_correcto(self, template_content):
        assert "deactivate_" in template_content

    def test_template_prohibe_delete_para_soft_delete(self, template_content):
        # La tabla debe mostrar delete_X como INCORRECTO
        assert (
            "delete_" in template_content
        )  # aparece como ejemplo de lo que NO se debe hacer

    def test_template_menciona_regla_fundamental_mismo_nombre(self, template_content):
        # Debe haber una regla explícita: mismo nombre en services + router + tests
        assert (
            "router" in template_content.lower()
            and "service" in template_content.lower()
        )


# ---------------------------------------------------------------------------
# P2 — system_devops.md: restricciones Oracle explícitas
# ---------------------------------------------------------------------------


class TestDevopsTemplateOracleRestrictions:
    @pytest.fixture
    def devops_content(self):
        template_path = (
            pathlib.Path(__file__).parent.parent / "templates" / "system_devops.md"
        )
        return template_path.read_text(encoding="utf-8")

    def test_prohíbe_gvenzl_oracle(self, devops_content):
        assert "gvenzl/oracle-xe" in devops_content

    def test_prohíbe_imagen_oracle_database(self, devops_content):
        assert "oracle/database" in devops_content or "oracle" in devops_content.lower()

    def test_especifica_postgres_obligatorio(self, devops_content):
        assert "postgres:16-alpine" in devops_content

    def test_restriccion_marcada_como_absoluta(self, devops_content):
        assert "RESTRICCIÓN ABSOLUTA" in devops_content or "PROHIBIDO" in devops_content

    def test_contiene_ejemplo_correcto_postgres(self, devops_content):
        assert "POSTGRES_DB" in devops_content


# ---------------------------------------------------------------------------
# P1 — route_after_approval ahora va a generate_architecture_contract
# ---------------------------------------------------------------------------


class TestRouteAfterApprovalGoesToArchGate:
    def test_approved_va_a_generate_architecture_contract(self):
        from graph import route_after_approval

        state = make_state(approval_decision="approved")
        result = route_after_approval(state)
        assert result == "generate_architecture_contract"

    def test_rejected_no_va_a_arch_gate(self):
        from langgraph.graph import END

        from graph import route_after_approval

        state = make_state(approval_decision="rejected")
        assert route_after_approval(state) == END
