"""
OVD Platform — Rate Limiter compartido (LOW-03)
Copyright 2026 Omar Robles

Instancia Limiter de slowapi que se registra en api.py y se aplica
en auth_router.py para proteger los endpoints de autenticación.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
