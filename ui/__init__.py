"""Paquete modular de vistas y modales de IndiServ Analytica."""

from ui.dashboard_tabs import DashboardMixin
from ui.diagnostico_views import DiagnosticoMixin
from ui.stress_y_arbol import StressYArbolMixin
from ui.modales import ModalesMixin

__all__ = ["DashboardMixin", "DiagnosticoMixin", "StressYArbolMixin", "ModalesMixin"]
