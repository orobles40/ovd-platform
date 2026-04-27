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

**CHECKLIST antes de entregar:**
- [ ] `requirements.txt` con todas las dependencias usadas en el código
- [ ] Cada módulo importado por otros fue generado en esta entrega
- [ ] No hay `from x import y` donde `x` es un archivo que no creaste
- [ ] `conftest.py` con `sys.path.insert(0, "src")`

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

#### RUTs válidos para tests — NUNCA inventes RUTs

| RUT formateado | Cuerpo | DV | Caso de prueba |
|----------------|--------|----|----------------|
| `12.345.678-5` | 12345678 | 5 | Happy path, 8 dígitos |
| `1.000.005-K` | 1000005 | K | DV = K ✓ |
| `10.000.013-K` | 10000013 | K | DV = K, 8 dígitos ✓ |
| `9.999.999-3` | 9999999 | 3 | DV = 3 (NO es K — error frecuente en foros) |
| `5.678.901-4` | 5678901 | 4 | Happy path, 7 dígitos |
| `0.000.001-9` | 1 | 9 | RUT mínimo válido |
| `12.345.678-4` | 12345678 | 4 | ❌ RUT inválido (DV incorrecto) |
| `9.999.999-K` | 9999999 | K | ❌ RUT inválido — DV real de 9.999.999 es 3, NO K |

**Regla:** Si el FR pide un RUT con DV=K, calcula primero con el algoritmo antes de hardcodearlo. `remainder == 10` produce DV=K.

```python
# CASOS DE PRUEBA VERIFICADOS COMPUTACIONALMENTE (S63-D — NO modificar estos valores):
# validate_rut("1.000.005-K") == True   # cuerpo=1000005, DV=K ✓
# validate_rut("10.000.013-K") == True  # cuerpo=10000013, DV=K ✓
# validate_rut("12.345.678-5") == True  # cuerpo=12345678, DV=5 ✓
# validate_rut("9.999.999-3") == True   # cuerpo=9999999, DV=3 (NO es K — error frecuente)
# validate_rut("9.999.999-K") == False  # DV real de 9.999.999 es 3, no K
# validate_rut("1.234.567-4") == False  # DV incorrecto
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
