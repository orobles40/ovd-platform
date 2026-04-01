"""
OVD Platform — Oracle connection pool manager
Copyright 2026 Omar Robles

Gestiona pools de conexion separados por sede.
CAS → Oracle 12c (PSOL7 / Casa Matriz)
CAT → Oracle 19c (PSOL8 / Catedral)
CAV → Oracle 19c (PSOL8 / Cavour)

Credenciales via variables de entorno (nunca hardcodeadas).
Oracle Wallet para autenticacion segura en produccion.
"""
from __future__ import annotations
import os
import oracledb
from typing import Literal

Sede = Literal["CAS", "CAT", "CAV"]

# ---------------------------------------------------------------------------
# Configuracion por sede
# ---------------------------------------------------------------------------

def _sede_config(sede: Sede) -> dict:
    prefix = f"ORACLE_{sede}"
    dsn = os.environ.get(f"{prefix}_DSN")
    user = os.environ.get(f"{prefix}_USER")
    password = os.environ.get(f"{prefix}_PASSWORD")
    wallet_dir = os.environ.get("ORACLE_WALLET_DIR")

    if not dsn:
        raise EnvironmentError(f"{prefix}_DSN no configurado — ver .env.example")
    if not user:
        raise EnvironmentError(f"{prefix}_USER no configurado")
    if not password:
        raise EnvironmentError(f"{prefix}_PASSWORD no configurado")

    cfg: dict = {
        "dsn": dsn,
        "user": user,
        "password": password,
        "min": int(os.environ.get("ORACLE_POOL_MIN", "2")),
        "max": int(os.environ.get("ORACLE_POOL_MAX", "10")),
        "increment": 1,
    }

    # Oracle Wallet (produccion) — si el directorio existe, usarlo
    if wallet_dir and os.path.isdir(wallet_dir):
        wallet_path = os.path.join(wallet_dir, sede)
        if os.path.isdir(wallet_path):
            cfg["wallet_location"] = wallet_path
            cfg["wallet_password"] = os.environ.get(f"{prefix}_WALLET_PASSWORD", "")

    return cfg


# ---------------------------------------------------------------------------
# Pools — creados lazy, uno por sede
# ---------------------------------------------------------------------------

_pools: dict[Sede, oracledb.ConnectionPool] = {}


def get_pool(sede: Sede) -> oracledb.ConnectionPool:
    if sede not in _pools:
        cfg = _sede_config(sede)
        _pools[sede] = oracledb.create_pool(**cfg)
    return _pools[sede]


def close_all() -> None:
    for pool in _pools.values():
        try:
            pool.close(force=True)
        except Exception:
            pass
    _pools.clear()
