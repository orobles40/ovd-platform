"""
OVD Platform — Tests S46: Design Quality System
S46-A: Tailwind + shadcn/ui + app shell + paleta de colores en template frontend
S46-B: Estados de UI requeridos (formularios, listas, feedback)
S46-C: Patrones de knowledge base (forms, data-table, dashboard, auth)
S46-D: Responsive y accesibilidad
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pathlib
import pytest

TEMPLATE = pathlib.Path(__file__).parent.parent / "templates" / "system_frontend_react.md"
KNOWLEDGE_BASE = pathlib.Path(__file__).parent.parent.parent / "knowledge" / "ui-ux" / "src" / "ui-ux-pro-max" / "templates" / "base"


def _tpl() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# S46-A — Design system obligatorio
# ---------------------------------------------------------------------------

class TestS46ADesignSystem:

    def test_tailwind_obligatorio(self):
        """S46-A1: template prohíbe CSS-in-JS y exige Tailwind."""
        content = _tpl()
        assert "Tailwind" in content
        assert "PROHIBIDO" in content or "Está PROHIBIDO" in content
        assert "S46-A" in content

    def test_shadcn_ui_obligatorio(self):
        """S46-A2: template menciona shadcn/ui con ejemplos de import."""
        content = _tpl()
        assert "shadcn/ui" in content
        assert "@/components/ui/button" in content
        assert "Button" in content

    def test_shadcn_componentes_listados(self):
        """S46-A2: template lista los componentes shadcn/ui disponibles."""
        content = _tpl()
        for comp in ["Card", "Table", "Dialog", "Badge", "Skeleton", "Alert"]:
            assert comp in content, f"Componente shadcn/ui '{comp}' no mencionado en template"

    def test_app_shell_obligatorio(self):
        """S46-A3: template incluye ejemplo de AppShell con sidebar y topbar."""
        content = _tpl()
        assert "AppShell" in content
        assert "sidebar" in content.lower() or "Sidebar" in content
        assert "S46-A3" in content

    def test_paleta_colores_tailwind_config(self):
        """S46-A4: template incluye tailwind.config.ts con tokens de diseño."""
        content = _tpl()
        assert "tailwind.config.ts" in content
        assert "primary" in content
        assert "muted" in content
        assert "Inter" in content

    def test_index_css_variables(self):
        """S46-A4: template incluye src/index.css con variables CSS."""
        content = _tpl()
        assert "index.css" in content
        assert "--primary" in content
        assert "--background" in content


# ---------------------------------------------------------------------------
# S46-B — Estados de UI requeridos
# ---------------------------------------------------------------------------

class TestS46BUIStates:

    def test_formulario_estado_loading(self):
        """S46-B1: template muestra spinner en botón submit durante loading."""
        content = _tpl()
        assert "animate-spin" in content or "isLoading" in content
        assert "S46-B1" in content

    def test_formulario_estado_error(self):
        """S46-B1: template muestra error inline bajo el campo."""
        content = _tpl()
        assert "text-destructive" in content
        assert "border-destructive" in content

    def test_lista_skeleton_loading(self):
        """S46-B2: template muestra skeleton de carga para listas."""
        content = _tpl()
        assert "Skeleton" in content
        assert "S46-B2" in content

    def test_lista_estado_vacio(self):
        """S46-B2: template muestra estado vacío con icono y mensaje."""
        content = _tpl()
        assert "length === 0" in content or "Sin registros" in content or "estado vacío" in content.lower()

    def test_lista_estado_error_con_retry(self):
        """S46-B2: template muestra error con botón de retry."""
        content = _tpl()
        assert "Reintentar" in content or "retry" in content.lower()

    def test_accion_destructiva_dialog(self):
        """S46-B3: template exige confirmation dialog para acciones destructivas."""
        content = _tpl()
        assert "Dialog" in content
        assert "destructi" in content.lower()
        assert "S46-B3" in content

    def test_toast_exito_y_error(self):
        """S46-B3: template muestra toast para éxito y error de API."""
        content = _tpl()
        assert "useToast" in content
        assert "toast" in content
        assert "variant" in content


# ---------------------------------------------------------------------------
# S46-C — Patrones de knowledge base
# ---------------------------------------------------------------------------

class TestS46CKnowledgePatterns:

    def test_patterns_forms_existe(self):
        """S46-C1: existe archivo patterns-forms.md en knowledge base."""
        assert (KNOWLEDGE_BASE / "patterns-forms.md").exists()

    def test_patterns_forms_floating_label(self):
        """S46-C1: patterns-forms.md incluye floating label pattern."""
        content = (KNOWLEDGE_BASE / "patterns-forms.md").read_text(encoding="utf-8")
        assert "FloatingLabel" in content or "floating" in content.lower()

    def test_patterns_forms_validacion_inline(self):
        """S46-C1: patterns-forms.md incluye validación inline."""
        content = (KNOWLEDGE_BASE / "patterns-forms.md").read_text(encoding="utf-8")
        assert "validateRut" in content or "validación inline" in content.lower() or "handleChange" in content

    def test_patterns_data_table_existe(self):
        """S46-C2: existe archivo patterns-data-table.md en knowledge base."""
        assert (KNOWLEDGE_BASE / "patterns-data-table.md").exists()

    def test_patterns_data_table_sort_filtro_paginacion(self):
        """S46-C2: data table incluye sort, filtro y paginación."""
        content = (KNOWLEDGE_BASE / "patterns-data-table.md").read_text(encoding="utf-8")
        assert "sort" in content.lower() or "Sort" in content
        assert "search" in content.lower() or "filtro" in content.lower()
        assert "page" in content.lower() or "Paginación" in content

    def test_patterns_data_table_acciones_por_fila(self):
        """S46-C2: data table incluye acciones por fila."""
        content = (KNOWLEDGE_BASE / "patterns-data-table.md").read_text(encoding="utf-8")
        assert "DropdownMenu" in content or "actions" in content

    def test_patterns_dashboard_existe(self):
        """S46-C3: existe archivo patterns-dashboard.md en knowledge base."""
        assert (KNOWLEDGE_BASE / "patterns-dashboard.md").exists()

    def test_patterns_dashboard_stat_cards(self):
        """S46-C3: dashboard incluye stat cards con delta."""
        content = (KNOWLEDGE_BASE / "patterns-dashboard.md").read_text(encoding="utf-8")
        assert "StatCard" in content or "stat" in content.lower()
        assert "delta" in content or "TrendingUp" in content

    def test_patterns_dashboard_actividad_reciente(self):
        """S46-C3: dashboard incluye actividad reciente."""
        content = (KNOWLEDGE_BASE / "patterns-dashboard.md").read_text(encoding="utf-8")
        assert "RecentActivity" in content or "actividad reciente" in content.lower()

    def test_patterns_auth_existe(self):
        """S46-C4: existe archivo patterns-auth.md en knowledge base."""
        assert (KNOWLEDGE_BASE / "patterns-auth.md").exists()

    def test_patterns_auth_login_card(self):
        """S46-C4: auth incluye login card centrado."""
        content = (KNOWLEDGE_BASE / "patterns-auth.md").read_text(encoding="utf-8")
        assert "LoginPage" in content or "login" in content.lower()
        assert "justify-center" in content

    def test_patterns_auth_forgot_password(self):
        """S46-C4: auth incluye forgot password flow."""
        content = (KNOWLEDGE_BASE / "patterns-auth.md").read_text(encoding="utf-8")
        assert "ForgotPassword" in content or "forgot" in content.lower() or "recuperar" in content.lower()

    def test_patterns_auth_password_strength(self):
        """S46-C4: auth incluye indicador de fortaleza de contraseña."""
        content = (KNOWLEDGE_BASE / "patterns-auth.md").read_text(encoding="utf-8")
        assert "PasswordStrength" in content or "fortaleza" in content.lower()


# ---------------------------------------------------------------------------
# S46-D — Responsive y accesibilidad
# ---------------------------------------------------------------------------

class TestS46DResponsiveAccessibility:

    def test_breakpoints_obligatorios(self):
        """S46-D1: template define breakpoints mobile/tablet/desktop."""
        content = _tpl()
        assert "md:" in content
        assert "xl:" in content
        assert "S46-D1" in content

    def test_sidebar_colapsa_mobile(self):
        """S46-D1: sidebar usa Sheet/drawer en mobile."""
        content = _tpl()
        assert "Sheet" in content
        assert "hidden md:" in content or "md:flex" in content

    def test_aria_label_iconos(self):
        """S46-D2: template muestra aria-label en iconos sin texto."""
        content = _tpl()
        assert "aria-label" in content
        assert "aria-hidden" in content
        assert "S46-D2" in content

    def test_contraste_tokens_design_system(self):
        """S46-D2: template advierte usar colores del design system para contraste AA."""
        content = _tpl()
        assert "muted-foreground" in content
        assert "text-foreground" in content or "foreground" in content

    def test_role_elementos_interactivos(self):
        """S46-D2: template muestra role en elementos interactivos custom."""
        content = _tpl()
        assert 'role="button"' in content or "role=" in content
