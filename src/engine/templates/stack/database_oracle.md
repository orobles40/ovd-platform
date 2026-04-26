## Convenciones OVD — Oracle Database (S58-pre)

### Conexión desde Docker — host.docker.internal (GAP-T4)

Si la API corre en Docker y Oracle está en el host:

```
# ✅ CORRECTO — Oracle externo al Docker stack
DATABASE_URL=oracle+oracledb://user:pass@host.docker.internal:1521/?service_name=XEPDB1

# ❌ INCORRECTO — Oracle como servicio Docker interno
DATABASE_URL=oracle+oracledb://user:pass@oracle:1521/XE
```

**NUNCA crees `Dockerfile.oracle` ni un contenedor Oracle.** Oracle es EXTERNO al docker-compose del proyecto. Solo referéncialo via `host.docker.internal`.

### Convenciones de nombres (Oracle 19c)

- Nombres de objetos en mayúsculas (`USUARIOS`, `CONTRATOS`)
- PKs con sequence: `<TABLA>_SEQ.NEXTVAL`
- Constraints nominados: `CONSTRAINT <TABLA>_PK PRIMARY KEY`, `CONSTRAINT <TABLA>_<COL>_UK UNIQUE`
- Scripts numerados: `001_create_table.sql`, `002_add_index.sql`, etc.

### Patrón de migración idempotente

```sql:migrations/001_create_table_usuarios.sql
-- Crear tabla USUARIOS
DECLARE
  v_count NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_count FROM user_tables WHERE table_name = 'USUARIOS';
  IF v_count = 0 THEN
    EXECUTE IMMEDIATE '
      CREATE TABLE USUARIOS (
        ID          NUMBER         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        RUT         VARCHAR2(12)   NOT NULL,
        NOMBRE      VARCHAR2(200)  NOT NULL,
        ORG_ID      VARCHAR2(50)   NOT NULL,
        ACTIVO      NUMBER(1)      DEFAULT 1 NOT NULL,
        CONSTRAINT USUARIOS_RUT_ORG_UK UNIQUE (RUT, ORG_ID)
      )
    ';
    DBMS_OUTPUT.PUT_LINE(''Tabla USUARIOS creada'');
  ELSE
    DBMS_OUTPUT.PUT_LINE(''Tabla USUARIOS ya existe'');
  END IF;
END;
/
```

### Trigger para columna calculada (valor_total)

```sql:migrations/004_trigger_valor_total.sql
-- Trigger para actualizar valor_total en CONTRATOS al modificar BENEFICIOS
CREATE OR REPLACE TRIGGER TRG_UPDATE_VALOR_TOTAL
AFTER INSERT OR UPDATE OR DELETE ON BENEFICIOS
FOR EACH ROW
DECLARE
  v_id_contrato NUMBER;
BEGIN
  v_id_contrato := CASE
    WHEN DELETING THEN :OLD.ID_CONTRATO
    ELSE :NEW.ID_CONTRATO
  END;

  UPDATE CONTRATOS
  SET VALOR_TOTAL = NVL(
    (SELECT SUM(VALOR) FROM BENEFICIOS WHERE ID_CONTRATO = v_id_contrato),
    0
  )
  WHERE ID = v_id_contrato;
END;
/
```

### SQLAlchemy + python-oracledb (thick mode)

```python
# ✅ CORRECTO — thick mode con python-oracledb
import oracledb
oracledb.init_oracle_client()  # activa thick mode

from sqlalchemy import create_engine
engine = create_engine(
    os.environ["DATABASE_URL"],
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
)
```

### Tests con mock Oracle (conftest.py)

Para tests unitarios que no requieren conexión real:

```python:conftest.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Mock de la BD para tests unitarios (no requiere Oracle levantado)
from unittest.mock import MagicMock, patch
import pytest

@pytest.fixture
def mock_db():
    """Fixture que provee un mock de la sesión SQLAlchemy."""
    with patch("src.database.get_db") as mock:
        mock_session = MagicMock()
        mock.return_value = iter([mock_session])
        yield mock_session
```
