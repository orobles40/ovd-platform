"""
OVD Platform — Tests: pending_store (Bloque A)
Cubre: add, remove, list_by_org, get, aislamiento multi-org.
No requiere BD ni infraestructura.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
import pytest
import pending_store


# ---------------------------------------------------------------------------
# Fixture: limpia el store antes de cada test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_store():
    """Vacía el _store singleton antes y después de cada test."""
    pending_store._store.clear()
    yield
    pending_store._store.clear()


def _item(thread_id: str, org_id: str, **extra) -> dict:
    return {
        "thread_id":      thread_id,
        "session_id":     f"sess-{thread_id}",
        "org_id":         org_id,
        "feature_request": "Implementar autenticación JWT",
        "sdd_summary":    "SDD: módulo de auth con JWT + refresh tokens",
        "sdd":            {"summary": "auth module", "requirements": [], "tasks": []},
        "revision_count": 0,
        **extra,
    }


# ---------------------------------------------------------------------------
# TestAdd
# ---------------------------------------------------------------------------

class TestAdd:
    def test_add_registra_item(self):
        pending_store.add("T1", _item("T1", "ORG_A"))
        assert pending_store.get("T1") is not None

    def test_add_incluye_stored_at(self):
        before = time.time()
        pending_store.add("T1", _item("T1", "ORG_A"))
        item = pending_store.get("T1")
        assert item["stored_at"] >= before

    def test_add_sobreescribe_si_mismo_thread_id(self):
        pending_store.add("T1", _item("T1", "ORG_A", revision_count=0))
        pending_store.add("T1", _item("T1", "ORG_A", revision_count=1))
        assert pending_store.get("T1")["revision_count"] == 1

    def test_add_multiples_threads(self):
        pending_store.add("T1", _item("T1", "ORG_A"))
        pending_store.add("T2", _item("T2", "ORG_A"))
        pending_store.add("T3", _item("T3", "ORG_B"))
        assert len(pending_store._store) == 3


# ---------------------------------------------------------------------------
# TestRemove
# ---------------------------------------------------------------------------

class TestRemove:
    def test_remove_elimina_existente(self):
        pending_store.add("T1", _item("T1", "ORG_A"))
        pending_store.remove("T1")
        assert pending_store.get("T1") is None

    def test_remove_no_existente_no_lanza(self):
        # No debe lanzar KeyError
        pending_store.remove("INEXISTENTE")

    def test_remove_solo_elimina_el_thread_indicado(self):
        pending_store.add("T1", _item("T1", "ORG_A"))
        pending_store.add("T2", _item("T2", "ORG_A"))
        pending_store.remove("T1")
        assert pending_store.get("T1") is None
        assert pending_store.get("T2") is not None


# ---------------------------------------------------------------------------
# TestListByOrg
# ---------------------------------------------------------------------------

class TestListByOrg:
    def test_lista_vacia_si_no_hay_items(self):
        assert pending_store.list_by_org("ORG_A") == []

    def test_lista_solo_items_del_org(self):
        pending_store.add("T1", _item("T1", "ORG_A"))
        pending_store.add("T2", _item("T2", "ORG_A"))
        pending_store.add("T3", _item("T3", "ORG_B"))

        result = pending_store.list_by_org("ORG_A")
        assert len(result) == 2
        thread_ids = {r["thread_id"] for r in result}
        assert thread_ids == {"T1", "T2"}

    def test_lista_org_distinto_no_ve_items_ajenos(self):
        pending_store.add("T1", _item("T1", "ORG_A"))
        result = pending_store.list_by_org("ORG_B")
        assert result == []

    def test_lista_retorna_copia_no_referencia(self):
        pending_store.add("T1", _item("T1", "ORG_A"))
        result = pending_store.list_by_org("ORG_A")
        # Modificar el resultado no debe alterar el store
        result.clear()
        assert pending_store.get("T1") is not None

    def test_lista_org_inexistente_retorna_lista_vacia(self):
        pending_store.add("T1", _item("T1", "ORG_A"))
        assert pending_store.list_by_org("ORG_FANTASMA") == []


# ---------------------------------------------------------------------------
# TestGet
# ---------------------------------------------------------------------------

class TestGet:
    def test_get_retorna_none_si_no_existe(self):
        assert pending_store.get("NOEXISTE") is None

    def test_get_retorna_datos_correctos(self):
        pending_store.add("T1", _item("T1", "ORG_A"))
        item = pending_store.get("T1")
        assert item["org_id"] == "ORG_A"
        assert item["thread_id"] == "T1"
        assert "stored_at" in item

    def test_get_incluye_campos_originales(self):
        pending_store.add("T1", _item("T1", "ORG_A", revision_count=3))
        item = pending_store.get("T1")
        assert item["revision_count"] == 3
        assert item["sdd"]["summary"] == "auth module"


# ---------------------------------------------------------------------------
# TestAislamientoMultiOrg (regresión SEC-01 inspired)
# ---------------------------------------------------------------------------

class TestAislamientoMultiOrg:
    def test_org_a_no_ve_threads_de_org_b(self):
        for i in range(5):
            pending_store.add(f"ORG_A_T{i}", _item(f"ORG_A_T{i}", "ORG_A"))
        for i in range(3):
            pending_store.add(f"ORG_B_T{i}", _item(f"ORG_B_T{i}", "ORG_B"))

        result_a = pending_store.list_by_org("ORG_A")
        result_b = pending_store.list_by_org("ORG_B")

        assert len(result_a) == 5
        assert len(result_b) == 3
        # Sin superposición
        ids_a = {r["thread_id"] for r in result_a}
        ids_b = {r["thread_id"] for r in result_b}
        assert ids_a.isdisjoint(ids_b)

    def test_remove_un_org_no_afecta_otro(self):
        pending_store.add("T_A", _item("T_A", "ORG_A"))
        pending_store.add("T_B", _item("T_B", "ORG_B"))
        pending_store.remove("T_A")
        assert pending_store.list_by_org("ORG_B") != []
        assert pending_store.list_by_org("ORG_A") == []
