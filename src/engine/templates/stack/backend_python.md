## Convenciones OVD — Python (S58-pre)

### Infraestructura obligatoria — ORDEN DE ESCRITURA (S32-B)

Escribe estos archivos PRIMERO, antes que cualquier código de negocio:

1. **`requirements.txt`** — dependencias con versiones fijas ← PRIMERO SIEMPRE
2. **`src/<paquete>/__init__.py`** — paquete del código fuente (puede estar vacío) ← SEGUNDO
3. **`tests/__init__.py`** — paquete de tests ← TERCERO
4. **`conftest.py`** (raíz del proyecto) — inserta `src/` en sys.path ← CUARTO
5. **`pytest.ini`** — configuración de pytest con `testpaths = tests` ← QUINTO
6. **Todos los módulos que importas** — si `auth_service.py` importa `schemas.py`, escribe `schemas.py` ANTES ← SEXTO
7. **`tests/test_<paquete>.py`** — tests unitarios con pytest ← OBLIGATORIO SIEMPRE (S51-B)

Solo después de estos archivos escribe el código de negocio.

**PROHIBIDO entregar sin `tests/test_<paquete>.py`.** Un entregable sin tests es un entregable incompleto.

**PROHIBIDO: NUNCA generes `__init__.py` en la RAÍZ del proyecto.** Convierte el workspace en paquete, rompiendo pytest y los imports.

**REGLA DE NAMING — módulo de servicios (S113-A):**
El archivo de lógica de negocio siempre se llama **`services.py`** (plural con 's').
❌ PROHIBIDO: `service.py` (singular sin 's')
✅ CORRECTO: `src/contratos/services.py`, `src/turnos/services.py`, `src/auth/services.py`
Los tests deben importar `from src.<paquete>.services import ...` — nunca `from src.<paquete>.service import ...`

### Orden topológico obligatorio para proyectos multi-archivo (S115-D)

Cuando el SDD incluye 4 o más archivos Python interdependientes, SIEMPRE generalos en este orden. Un archivo NO puede importar de uno que aún no aparece en tu output:

```
1. models.py          ← ORM SQLAlchemy (sin imports del propio proyecto)
2. schemas.py         ← Pydantic BaseModel (importa solo from models si usa from_attributes)
3. utils/rut.py       ← funciones puras, helpers (sin imports del proyecto)
4. services.py        ← lógica de negocio (importa models + schemas)
5. routers/<x>.py     ← endpoints FastAPI (importa services + schemas)
6. main.py            ← app FastAPI + include_router (importa routers)
7. conftest.py        ← sys.path.insert (sin imports del proyecto)
8. tests/test_*.py    ← importa main + schemas (SIEMPRE el último)
```

Al inicio de cada bloque de código, declara sus imports reales. Si un archivo importa de otro de esta entrega, ese otro debe haber aparecido ANTES en tu respuesta.

**CHECKLIST antes de entregar:**
- [ ] `requirements.txt` con todas las dependencias usadas en el código
- [ ] Cada módulo importado por otros fue generado en esta entrega
- [ ] No hay `from x import y` donde `x` es un archivo que no creaste
- [ ] `conftest.py` con `sys.path.insert(0, "src")`
- [ ] El archivo de servicios se llama `services.py` (plural), no `service.py`

### Estructura válida vs inválida

✅ **CORRECTO:**
```
proyecto/
├── conftest.py          ← sys.path.insert(0, "src")
├── pytest.ini           ← testpaths = tests
├── requirements.txt
├── src/
│   └── calculadora/
│       ├── __init__.py
│       └── imc.py
└── tests/
    ├── __init__.py
    └── test_imc.py  ← from calculadora.imc import calculate_bmi
```

❌ **INCORRECTO (rompe pytest):**
```
proyecto/
├── __init__.py          ← NUNCA crear esto en la raíz
├── imc.py               ← código suelto en raíz
└── tests/
    └── test_imc.py
```

### conftest.py obligatorio

```python:conftest.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
```

**PROHIBIDO en conftest.py (S121-B):** NUNCA importes `from src.database import ...` ni `from src.models import ...` a nivel de módulo en `conftest.py`. Esto provoca `ImportError` en colección de pytest si el engine async no puede inicializarse.

❌ **PROHIBIDO:**
```python
# conftest.py — MALO
from src.database import Base, get_session  # ← dispara create_async_engine() al importar
```

✅ **CORRECTO — conftest.py mínimo para FastAPI async:**
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
```

### pytest.ini mínimo

```ini:pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

### Una sola implementación por función

Si una función de negocio debe existir, defínela en **UN SOLO ARCHIVO**. Los tests importan desde esa única ubicación.

❌ **PROHIBIDO:** definir `calculate_bmi` en `src/imc.py` Y en `src/utils.py` Y en `src/main.py`. Causa ImportError.

✅ **CORRECTO:** una sola definición en `src/<paquete>/<modulo>.py`.

---

### Pydantic v2 obligatorio (S50-C)

**SIEMPRE usa Pydantic v2.** El decorador `@validator` está DEPRECADO. Usa `@field_validator`.

❌ **INCORRECTO (Pydantic v1 — deprecado):**
```python
from pydantic import BaseModel, validator

class ImcRequest(BaseModel):
    peso: float

    @validator('peso')
    def peso_positivo(cls, v):
        if v <= 0:
            raise ValueError("El peso debe ser positivo")
        return v
```

✅ **CORRECTO (Pydantic v2):**
```python
from pydantic import BaseModel, field_validator

class ImcRequest(BaseModel):
    peso: float

    @field_validator('peso')
    @classmethod
    def peso_positivo(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("El peso debe ser positivo")
        return v
```

### Pydantic v2 — PROHIBIDO: @classmethod duplicado (S119-C)

El orden correcto es: `@field_validator(...)` primero, `@classmethod` debajo. NUNCA al revés ni duplicado.

❌ **PROHIBIDO — genera `TypeError: duplicate decorator` o ignora la validación:**
```python
# MALO: @classmethod antes de @field_validator
@classmethod
@field_validator('rut')
def validate_rut(cls, v): ...

# MALO: @classmethod duplicado
@field_validator('rut')
@classmethod
@classmethod
def validate_rut(cls, v): ...

# MALO: @classmethod standalone en un BaseModel (fuera de @field_validator)
class PacienteCreate(BaseModel):
    rut: str

    @classmethod
    def validate_rut(cls, v): ...  # ← no es un validator de Pydantic
```

✅ **CORRECTO — único patrón válido en Pydantic v2:**
```python
class PacienteCreate(BaseModel):
    rut: str

    @field_validator('rut')
    @classmethod
    def validate_rut(cls, v: str) -> str:
        if not v:
            raise ValueError("RUT requerido")
        return v
```

---

### Regla de valores numéricos en tests (S50-D / S53-A)

**NUNCA escribas valores float de memoria.** Los errores de redondeo hacen que el test falle aunque la implementación sea correcta.

**REGLA CRÍTICA (S53-A): NUNCA escribas un valor float literal en un `assert`. Escribe la expresión `round(...)` directamente.**

❌ PROHIBIDO:
```python
assert data["imc"] == 19.14   # ← valor calculado de memoria, probablemente incorrecto
assert result.imc == 22.86    # ← idem
```

✅ OBLIGATORIO:
```python
assert data["imc"] == round(55 / 1.70**2, 2)   # Python calcula: 19.03
assert result.imc == round(70 / 1.75**2, 2)    # Python calcula: 22.86
```

Valores de referencia verificados:
```python
round(53.4 / 1.70**2, 2)   # → 18.48  ✅  (NO 18.49)
round(65 / 1.72**2, 2)     # → 21.97  ✅  (NO 22.35)
round(70 / 1.75**2, 2)     # → 22.86  ✅
round(80 / 1.70**2, 2)     # → 27.68  ✅
```

---

### Validación de RUT chileno (S40-templates / S43-F / S45-B)

Cuando el FR involucre RUT chileno, implementa la validación en el backend.

**Regla de prioridad (S45-B):**
1. Si el `{project_context}` contiene RUTs de prueba → úsalos EXACTAMENTE
2. Si no → usa ÚNICAMENTE los de la tabla inferior

#### Algoritmo obligatorio

```python:src/<paquete>/utils/rut.py
import re

def clean_rut(rut: str) -> str:
    """Elimina puntos y guión, retorna solo dígitos + dígito verificador."""
    return re.sub(r"[.\-]", "", rut.strip().upper())

def validate_rut(rut: str) -> bool:
    """
    Valida RUT chileno. Acepta formatos: 12345678-9, 12.345.678-9, 123456789.
    Retorna True si el dígito verificador es correcto.
    """
    cleaned = clean_rut(rut)
    if not re.match(r"^\d{7,8}[0-9K]$", cleaned):
        return False
    body, dv = cleaned[:-1], cleaned[-1]
    total, factor = 0, 2
    for digit in reversed(body):
        total += int(digit) * factor
        factor = 2 if factor == 7 else factor + 1
    remainder = 11 - (total % 11)
    expected = {10: "K", 11: "0"}.get(remainder, str(remainder))
    return dv == expected

def format_rut(rut: str) -> str:
    """Formatea RUT como XX.XXX.XXX-X."""
    cleaned = clean_rut(rut)
    body, dv = cleaned[:-1], cleaned[-1]
    formatted_body = ""
    for i, digit in enumerate(reversed(body)):
        if i > 0 and i % 3 == 0:
            formatted_body = "." + formatted_body
        formatted_body = digit + formatted_body
    return f"{formatted_body}-{dv}"
```

#### Reglas de uso en APIs (FastAPI)

- **Almacenamiento:** guardar siempre en formato limpio `12345678K` (sin puntos ni guión)
- **Validación en endpoint:**

```python
from fastapi import HTTPException, status

def require_valid_rut(rut: str) -> str:
    cleaned = clean_rut(rut)
    if not validate_rut(cleaned):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"RUT inválido: {rut}"
        )
    return cleaned
```

- **Unicidad:** constraint UNIQUE dentro del scope de org_id
- **Tests obligatorios:** RUT válido, RUT con DV=K, RUT con formato (puntos/guión), RUT inválido, RUT con letras

#### RUTs válidos para tests — NUNCA inventes RUTs [S64-A]

**PROHIBIDO inventar valores de DV.** Usar EXCLUSIVAMENTE la tabla siguiente, verificada
computacionalmente con `python3` (algoritmo módulo 11, factores 2-7 cíclicos de derecha a izquierda):

| RUT formateado    | Cuerpo   | DV | Estado   | Verificación (total, %11, 11-r)       |
|-------------------|----------|----|----------|---------------------------------------|
| `12.345.678-5`    | 12345678 | 5  | válido   | total=138, 138%11=6, 11-6=**5**       |
| `1.000.005-K`     | 1000005  | K  | válido   | total=12, 12%11=1, 11-1=10→**K**      |
| `9.999.999-3`     | 9999999  | 3  | válido   | total=261, 261%11=8, 11-8=**3**       |
| `11.111.111-1`    | 11111111 | 1  | válido   | total=32, 32%11=10, 11-10=**1**       |
| `10.000.013-K`    | 10000013 | K  | válido   | total=12, 12%11=1, 11-1=10→**K**      |
| `5.678.901-4`     | 5678901  | 4  | válido   | total=172, 172%11=7, 11-7=**4**       |
| `1.234.567-4`     | 1234567  | 4  | válido   | total=106, 106%11=7, 11-7=**4**       |
| `12.345.678-9`    | 12345678 | 9  | inválido | DV real=5, no 9                       |
| `9.999.999-K`     | 9999999  | K  | inválido | DV real=3, no K                       |
| `1.234.567-0`     | 1234567  | 0  | inválido | DV real=4, no 0                       |

**NOTA CRÍTICA:** `"1.234.567-4"` es **válido** (DV=4). No lo uses como caso inválido.

Verificación en línea: `python3 -c "b='12345678'; d=[int(x) for x in reversed(b)]; s=sum(d[i]*[2,3,4,5,6,7][i%6] for i in range(len(d))); r=11-(s%11); print('K' if r==10 else '0' if r==11 else str(r))"`

```python
# TABLA VERIFICADA COMPUTACIONALMENTE [S64-A] — NO modificar estos valores:
# validate_rut("12.345.678-5") == True   # total=138, DV=5
# validate_rut("1.000.005-K")  == True   # total=12,  DV=K
# validate_rut("9.999.999-3")  == True   # total=261, DV=3
# validate_rut("11.111.111-1") == True   # total=32,  DV=1
# validate_rut("10.000.013-K") == True   # total=12,  DV=K
# validate_rut("5.678.901-4")  == True   # total=172, DV=4
# validate_rut("1.234.567-4")  == True   # total=106, DV=4  ← ES VÁLIDO
# validate_rut("12.345.678-9") == False  # DV real=5, no 9
# validate_rut("9.999.999-K")  == False  # DV real=3, no K
# validate_rut("1.234.567-0")  == False  # DV real=4, no 0
```

---

### D2 — Separación ORM / Pydantic [S64-D2]

`Session.add()` requiere un modelo ORM (`DeclarativeBase`), **nunca** un `BaseModel` Pydantic. Son incompatibles.

```python
# ❌ PROHIBIDO — TypeError en runtime:
db.add(ContratoCreate(rut="12.345.678-5", ...))   # Pydantic, no ORM

# ✅ CORRECTO — 3 tipos de objeto distintos:
# 1. ORM model → session.add(), queries SQLAlchemy
class ContratoORM(Base):
    __tablename__ = "contratos"
    id = Column(Integer, primary_key=True)
    rut = Column(String)

# 2. Pydantic schema entrada → request body FastAPI
class ContratoCreate(BaseModel):
    rut: str

# 3. Pydantic schema respuesta → response_model FastAPI
class ContratoResponse(BaseModel):
    id: int
    rut: str
    model_config = {"from_attributes": True}  # Pydantic v2

# En endpoint — conversión explícita Pydantic → ORM:
db_obj = ContratoORM(**schema.model_dump())
db.add(db_obj)
db.commit()
db.refresh(db_obj)
return db_obj  # FastAPI serializa con ContratoResponse
```

### D3 — Datetime agnóstico al dialecto [S64-D3]

`func.sysdate()` es Oracle-specific y falla en SQLite/PostgreSQL (usados en tests).

```python
# ❌ PROHIBIDO (Oracle-only):
Column("created_at", DateTime, server_default=func.sysdate())

# ✅ CORRECTO — Python-side, todos los dialectos:
from datetime import datetime, timezone
Column("created_at", DateTime, default=lambda: datetime.now(timezone.utc))

# ✅ ALTERNATIVA — ANSI SQL (SQLite, PostgreSQL, Oracle, MySQL):
Column("created_at", DateTime, server_default=func.current_timestamp())
```

---

### Conexión a base de datos externa (S45-E)

Si el proyecto usa Oracle, PostgreSQL u otra BD externa, la URL **DEBE** tomarse de variables de entorno o del `{project_context}`. **NUNCA hardcodear** host, puerto, usuario ni contraseña.

```python
# ✅ CORRECTO — desde variable de entorno
import os
DATABASE_URL = os.environ.get("DATABASE_URL", "oracle+oracledb://user:pass@localhost:1521/?service_name=XEPDB1")
```

Si el `{project_context}` menciona `host.docker.internal` como host de la BD, úsalo en el docker-compose. Nunca uses el nombre de un servicio Docker para conectarte a una BD que corre fuera de Docker.

```yaml
# ✅ CORRECTO para Oracle externo:
environment:
  - DATABASE_URL=oracle+oracledb://user:password@host.docker.internal:1521/?service_name=XEPDB1

# ❌ INCORRECTO — asume Oracle como servicio Docker:
environment:
  - DATABASE_URL=oracle+oracledb://user:password@oracle:1521/XE
```

---

### D4 — SQLAlchemy 2.x async: transacciones ACID y SELECT FOR UPDATE (S117-E)

Cuando el FR requiera operaciones concurrentes (reservas, asignaciones de turnos, inventario), usa `async with db.begin()` + `.with_for_update()` para garantizar atomicidad y evitar race conditions.

```python
# ✅ CORRECTO — SQLAlchemy 2.x async, transacción ACID con row lock
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select
from fastapi import Depends

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def reservar_turno(turno_id: int, paciente_id: int, db: AsyncSession) -> Turno:
    async with db.begin():                          # BEGIN + COMMIT/ROLLBACK automático
        stmt = (
            select(Turno)
            .where(Turno.id == turno_id)
            .with_for_update()                      # SELECT FOR UPDATE → lock de fila
        )
        result = await db.execute(stmt)
        turno = result.scalar_one_or_none()
        if turno is None:
            raise HTTPException(404, "Turno no encontrado")
        if turno.estado != "disponible":
            raise HTTPException(409, "Turno ya reservado")
        turno.estado = "reservado"
        turno.paciente_id = paciente_id
    return turno                                    # COMMIT ya ejecutado al salir del with
```

**Reglas obligatorias:**
- **NUNCA** uses `session.execute()` sin `async with db.begin()` para operaciones de escritura
- **NUNCA** uses `db.commit()` / `db.rollback()` manual si ya usas `async with db.begin()`
- `expire_on_commit=False` es necesario para acceder a atributos después del COMMIT
- Para reads sin lock: `async with db` (sin `.begin()`) + `await db.execute(select(...))`
- Para operaciones en batch: un solo `async with db.begin()` que envuelva todas las writes

```python
# ❌ PROHIBIDO — sin transacción explícita en writes concurrentes:
result = await db.execute(select(Turno).where(Turno.id == turno_id))
turno = result.scalar_one()
turno.estado = "reservado"
await db.commit()  # race condition: otro proceso puede modificar entre select y commit
```

---

### D5 — SQLAlchemy async: PROHIBIDO engine a nivel de módulo en src/database.py (S121-A)

`create_async_engine(...)` NUNCA debe llamarse fuera de una función en `src/database.py`. Al importar el módulo (desde `tests/conftest.py` o cualquier otro archivo), Python ejecuta el cuerpo del módulo inmediatamente. Si el driver async no está disponible o la URL es inválida, se genera `ImportError` durante la colección de pytest, antes de que se ejecute ningún test.

❌ **PROHIBIDO — falla en colección de pytest:**
```python
# src/database.py — MALO
import os
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.environ.get("DATABASE_URL", "")
engine = create_async_engine(DATABASE_URL, echo=False)  # ← module-level: ImportError al importar
```

✅ **CORRECTO — inicialización lazy dentro de factory (S121-A):**
```python
# src/database.py
import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.environ.get("DATABASE_URL", "")

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(DATABASE_URL, echo=False)
    return _engine

class Base(DeclarativeBase):
    pass

async def get_session():
    async_session = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with async_session() as session:
        yield session
```

**Reglas:**
- **NUNCA** escribas `engine = create_async_engine(...)` fuera de una función en `src/database.py`
- La inicialización lazy garantiza que el engine solo se crea cuando el proceso realmente conecta a la BD, no al importar el módulo

---

### D6 — Tests: PROHIBIDO importar sesiones/engine desde src.database (S123-A)

Los archivos de test **NUNCA** deben importar sesiones, factories ni el engine desde `src.database`. Después de S121-A/S122-A, esos nombres (`AsyncSessionLocal`, `async_session_factory`, `async_session_maker`, `engine`) no existen a nivel de módulo — solo `Base` y las funciones lazy `get_engine()` / `get_session_factory()`.

❌ **PROHIBIDO en tests:**
```python
from src.database import AsyncSessionLocal       # ← no existe
from src.database import async_session_factory   # ← no existe
from src.database import async_session_maker     # ← no existe
from src.database import engine                  # ← no existe
```

✅ **CORRECTO — test autocontenido con engine propio y dependency override (S124-A):**
```python
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.main import app
from src.database import Base, get_session  # Base y get_session (función generadora) permitidos

TEST_DATABASE_URL = "sqlite+aiosqlite://"  # in-memory, sin persistencia entre tests

_test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
_TestSession = async_sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await _test_engine.dispose()

@pytest_asyncio.fixture
async def client():
    # dependency_override: la app usa el engine de test en lugar del de producción
    async def override_get_session():
        async with _TestSession() as session:
            yield session
    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

async def test_ejemplo(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
```

**Reglas:**
- Los tests crean su propio engine con SQLite in-memory (`sqlite+aiosqlite://`)
- `from src.database import Base` y `from src.database import get_session` son los únicos imports permitidos de `src.database` en tests
- `app.dependency_overrides[get_session]` conecta el engine de test con la app — SIEMPRE hacerlo en la fixture `client`
- `app.dependency_overrides.clear()` al finalizar la fixture para no contaminar otros tests
- `pytest.ini` debe incluir `asyncio_mode = auto` para fixtures async
- NUNCA crear el engine a nivel de módulo sin ponerlo en una fixture de scope="session"

---

### Formato de tests pytest — Ejemplo obligatorio (S52-B)

Cuando el SDD incluya una tarea de tests, el archivo `tests/test_<paquete>.py` DEBE seguir este patrón:

```python:tests/test_calculadora.py
import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.calculadora.imc import calculate_bmi

client = TestClient(app)

def test_calculo_valido():
    response = client.post("/imc", json={"peso": 70, "altura": 1.75})
    assert response.status_code == 200
    data = response.json()
    assert data["imc"] == round(70 / 1.75**2, 2)  # S53-A: expresión, no literal
    assert data["categoria"] == "Normal"

def test_peso_negativo():
    response = client.post("/imc", json={"peso": -70, "altura": 1.75})
    assert response.status_code == 400
    assert "positivo" in response.json()["detail"].lower()

def test_clasificacion_obesidad():
    response = client.post("/imc", json={"peso": 100, "altura": 1.60})
    assert response.status_code == 200
    data = response.json()
    assert data["imc"] == round(100 / 1.60**2, 2)  # S53-A: expresión, no literal
    assert data["categoria"] == "Obesidad"

def test_funcion_pura():
    result = calculate_bmi(peso=55, altura=1.70)
    assert result.imc == round(55 / 1.70**2, 2)   # S53-A: round(...) en el assert
    assert result.categoria == "Normal"
```

**Reglas:**
- El fence SIEMPRE incluye la ruta: ` ```python:tests/test_<paquete>.py `
- **NUNCA un float literal en `assert`** — usa `round(a / b**2, 2)` directamente (S53-A)
- Mínimo 3 casos: happy path, validación negativa, límite/categoría extrema
- Los imports usan la ruta real del módulo (`from src.calculadora.imc import ...`)
