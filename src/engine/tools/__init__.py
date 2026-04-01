"""
OVD Platform — Tool Calling S17T
Copyright 2026 Omar Robles

Módulo de herramientas LangChain para agentes con acceso al sistema de archivos.
"""
from .file_tools import make_file_tools, read_project_context

__all__ = ["make_file_tools", "read_project_context"]
