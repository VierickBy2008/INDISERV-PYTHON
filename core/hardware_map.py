"""
core/hardware_map.py — Mapa de Componentes del Sistema (Fase 3 Redesign)
========================================================================
Vista completamente rediseñada del diagrama esquemático de motherboard.
Usa Tkinter Canvas puro (compatible con CustomTkinter) para renderizar
un esquema 2D dark-tech de alta fidelidad con:

  • Placa base PCB con trazas de circuito, orificios de montaje y borde metálico.
  • Anatomía fiel: CPU socket + disipador, ranuras DIMM, slot PCIe x16 + GPU,
    módulo M.2 NVMe, panel I/O trasero, PSU/Shroud y bahía de almacenamiento.
  • Sistema de estados de salud por componente (óptimo / advertencia / alerta).
  • Panel superior con resumen de diagnóstico (equipo, salud global, componente en foco).
  • Hover interactivo: cambio de borde + tarjeta emergente de datos técnicos.
  • Dos botones de navegación inferiores con estética moderna.

Uso (desde main.py):
    from core.hardware_map import MotherboardMapView
    MotherboardMapView(parent_frame, hw_data, categoria_afectada,
                       cmd_volver, cmd_visor_3d)
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from typing import Callable

# ---------------------------------------------------------------------------
# Paleta de colores dark-tech
# ---------------------------------------------------------------------------
C = {
    # Fondos
    "bg_outer":     "#0b0f19",   # Fondo contenedor exterior
    "pcb":          "#1a2235",   # PCB principal de la placa
    "pcb_edge":     "#0f172a",   # Borde exterior del PCB
    "pcb_border":   "#334155",   # Borde metálico sutil
    "bg_panel":     "#0f1729",   # Panel de info lateral

    # Componentes base
    "comp_base":    "#1e3a5f",   # Relleno neutro de componentes
    "comp_border":  "#2d5a8e",   # Borde neutro

    # Estados
    "ok":           "#10b981",   # Verde esmeralda — óptimo
    "ok_dim":       "#064e3b",   # Verde oscuro — fill óptimo
    "warn":         "#f59e0b",   # Naranja ámbar — advertencia
    "warn_dim":     "#451a03",   # Fill advertencia
    "alert":        "#ef4444",   # Rojo — alerta crítica
    "alert_dim":    "#450a0a",   # Fill alerta

    # Pistas PCB decorativas
    "trace":        "#1e3a5f",
    "trace_glow":   "#0e2d4e",

    # Tornillos de montaje
    "screw_ring":   "#b45309",   # Anillo dorado
    "screw_center": "#fbbf24",   # Centro dorado brillante

    # Texto
    "text_primary":  "#e2e8f0",
    "text_secondary":"#94a3b8",
    "text_dim":      "#475569",
    "text_cyan":     "#06b6d4",
    "text_ok":       "#10b981",
    "text_warn":     "#f59e0b",
    "text_alert":    "#ef4444",

    # PSU / bahía
    "psu_fill":      "#161f30",
    "psu_border":    "#4b5563",
    "bay_fill":      "#0f1a2a",

    # GPU
    "gpu_fill":      "#1a2a45",
    "gpu_fan":       "#253550",

    # CPU
    "cpu_socket":    "#1e2d42",
    "cpu_lid":       "#c0c0c0",

    # RAM slot
    "ram_slot":      "#1a3050",
    "ram_clip":      "#2563eb",

    # M.2
    "m2_fill":       "#1a2a3a",
    "m2_hs":         "#243040",

    # Botones
    "btn_primary":   "#1d4ed8",
    "btn_primary_h": "#1e40af",
    "btn_secondary": "#334155",
    "btn_secondary_h":"#475569",

    # Tooltip
    "tooltip_bg":    "#0f172a",
    "tooltip_border":"#334155",
}

# ---------------------------------------------------------------------------
# Mapeo de categorías de diagnóstico → claves de componente
# ---------------------------------------------------------------------------
DIAG_TO_COMP = {
    "Fuente de Poder":              "PSU",
    "CPU / Enfriamiento Térmico":   "CPU",
    "Enfriamiento":                 "CPU",
    "Memoria RAM":                  "RAM",
    "RAM":                          "RAM",
    "Tarjeta Gráfica":              "GPU",
    "Tarjeta Gráfica (GPU)":        "GPU",
    "Placa Base":                   "MB",
    "Almacenamiento":               "M2",
    "Almacenamiento (SSD / HDD)":   "M2",
    "Rendimiento":                  "CPU",
    "Software":                     "MB",
    "Hardware":                     "MB",
    "Video":                        "GPU",
    "Adaptador de Red":             "IO",
    "Red":                          "IO",
}


# ===========================================================================
# Clase principal
# ===========================================================================
class MotherboardMapView:
    """
    Renderiza el mapa esquemático de motherboard en un widget tk.Canvas.

    Parámetros
    ----------
    parent          : tk widget — Contenedor padre (CTkFrame u otro widget).
    hw_data         : dict     — Dict de hardware detectado por LectorHardware.
    categoria_diag  : str      — Categoría del dictamen de diagnóstico.
    cmd_volver      : callable — Acción del botón "← Volver al Diagnóstico".
    cmd_visor_3d    : callable — Acción del botón "Ver Gemelo Digital 3D".
    """

    # Dimensiones del canvas
    CW = 860   # ancho
    CH = 490   # alto

    def __init__(
        self,
        parent,
        hw_data: dict,
        categoria_diag: str,
        cmd_volver: Callable,
        cmd_visor_3d: Callable,
    ):
        self.parent         = parent
        self.hw             = hw_data or {}
        self.categoria      = categoria_diag
        self.cmd_volver     = cmd_volver
        self.cmd_visor_3d   = cmd_visor_3d

        # Componente afectado mapeado
        self.comp_afectado  = DIAG_TO_COMP.get(categoria_diag, "")

        # Estado de tooltip activo
        self._tooltip_items: list[int] = []
        self._tooltip_after: str | None = None

        self._build_ui()

    # ------------------------------------------------------------------
    # Construcción de la UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        """Construye el panel de resumen, el canvas y los botones."""
        # ── Panel de resumen superior ──────────────────────────────────
        self._build_summary_panel()

        # ── Canvas principal ───────────────────────────────────────────
        self.canvas = tk.Canvas(
            self.parent,
            width=self.CW,
            height=self.CH,
            bg=C["bg_outer"],
            highlightthickness=0,
            cursor="arrow",
        )
        self.canvas.pack(pady=(4, 0))

        # ── Renderizar el diagrama ─────────────────────────────────────
        self._draw_background()
        self._draw_pcb()
        self._draw_circuit_traces()
        self._draw_mounting_screws()
        self._draw_io_panel()
        self._draw_psu_zone()
        self._draw_storage_bay()
        self._draw_cpu_socket()
        self._draw_ram_slots()
        self._draw_m2_slot()
        self._draw_pcie_gpu()
        self._draw_legend()
        self._bind_hover_events()

        # ── Botones inferiores ─────────────────────────────────────────
        self._build_nav_buttons()

    # ------------------------------------------------------------------
    # Panel de resumen superior
    # ------------------------------------------------------------------
    def _build_summary_panel(self):
        from core.hardware import calcular_health_score
        score = calcular_health_score(self.hw)

        # Color del score
        if score >= 80:
            score_color = C["text_ok"]
            score_label = "Óptimo"
        elif score >= 55:
            score_color = C["text_warn"]
            score_label = "Requiere Atención"
        else:
            score_color = C["text_alert"]
            score_label = "Crítico"

        cpu_name  = self.hw.get("nombre_cpu", "CPU no detectada")
        gpu_name  = self.hw.get("gpu_principal", "GPU no detectada")
        mb_name   = f"{self.hw.get('mb_fabricante','?')} {self.hw.get('mb_modelo','?')}"

        # Marco del panel
        import customtkinter as ctk
        panel = ctk.CTkFrame(self.parent, fg_color="#0f1729", corner_radius=8)
        panel.pack(fill="x", padx=6, pady=(0, 4))

        # Fila de métricas
        row = ctk.CTkFrame(panel, fg_color="transparent")
        row.pack(pady=(8, 6), padx=14, fill="x")

        # — Nombre de la máquina —
        mb_frame = ctk.CTkFrame(row, fg_color="#131e30", corner_radius=6)
        mb_frame.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(mb_frame, text="PLACA BASE", font=("Consolas", 9),
                     text_color="#475569").pack(padx=10, pady=(5, 0))
        ctk.CTkLabel(mb_frame, text=mb_name, font=("Segoe UI", 11, "bold"),
                     text_color="#94a3b8").pack(padx=10, pady=(0, 5))

        # — Salud global —
        hs_frame = ctk.CTkFrame(row, fg_color="#131e30", corner_radius=6)
        hs_frame.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(hs_frame, text="SALUD GLOBAL", font=("Consolas", 9),
                     text_color="#475569").pack(padx=10, pady=(5, 0))
        ctk.CTkLabel(hs_frame, text=f"{score}/100 — {score_label}",
                     font=("Segoe UI", 11, "bold"),
                     text_color=score_color).pack(padx=10, pady=(0, 5))

        # — Componente en foco —
        if self.categoria:
            focus_frame = ctk.CTkFrame(row, fg_color="#1a0808", corner_radius=6)
            focus_frame.pack(side="left", padx=(0, 8))
            ctk.CTkLabel(focus_frame, text="COMPONENTE EN FOCO", font=("Consolas", 9),
                         text_color="#6b2222").pack(padx=10, pady=(5, 0))
            ctk.CTkLabel(focus_frame, text=f"[!]  {self.categoria}",
                         font=("Segoe UI", 11, "bold"),
                         text_color=C["text_alert"]).pack(padx=10, pady=(0, 5))

        # — CPU rápida —
        cpu_frame = ctk.CTkFrame(row, fg_color="#131e30", corner_radius=6)
        cpu_frame.pack(side="left")
        ctk.CTkLabel(cpu_frame, text="CPU", font=("Consolas", 9),
                     text_color="#475569").pack(padx=10, pady=(5, 0))
        ctk.CTkLabel(cpu_frame, text=cpu_name[:28] + ("…" if len(cpu_name) > 28 else ""),
                     font=("Segoe UI", 10),
                     text_color="#94a3b8").pack(padx=10, pady=(0, 5))

    # ------------------------------------------------------------------
    # Botones de navegación
    # ------------------------------------------------------------------
    def _build_nav_buttons(self):
        import customtkinter as ctk
        btn_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        btn_frame.pack(pady=(6, 0))

        ctk.CTkButton(
            btn_frame,
            text="← Volver al Diagnóstico",
            command=self.cmd_volver,
            width=210, height=38,
            fg_color="#334155", hover_color="#475569",
            border_width=1, border_color="#4b5563",
            font=("Segoe UI", 12),
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_frame,
            text="🌐  Ver Gemelo Digital 3D",
            command=self.cmd_visor_3d,
            width=240, height=38,
            fg_color="#1d4ed8", hover_color="#1e40af",
            border_width=1, border_color="#06b6d4",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left", padx=8)

    # ------------------------------------------------------------------
    # Helpers de dibujo
    # ------------------------------------------------------------------
    def _rr(self, x1, y1, x2, y2, r=8, **kw):
        """Rectángulo con esquinas redondeadas en tk.Canvas."""
        c = self.canvas
        pts = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
            x1 + r, y1,
        ]
        return c.create_polygon(pts, smooth=True, **kw)

    def _state_colors(self, comp_key: str) -> tuple[str, str, str]:
        """
        Retorna (fill, border, text_color) según si el componente es afectado o no.
        """
        if self.comp_afectado and comp_key == self.comp_afectado:
            return C["alert_dim"], C["alert"], C["text_alert"]
        return C["comp_base"], C["comp_border"], C["text_primary"]

    def _badge_alert(self, x: int, y: int, texto: str = "[!]"):
        """Dibuja un badge de alerta en la posición (x,y)."""
        c = self.canvas
        c.create_oval(x - 10, y - 10, x + 10, y + 10, fill=C["alert"], outline="", tags="alert_badge")
        c.create_text(x, y, text="!", fill="white", font=("Segoe UI", 9, "bold"), tags="alert_badge")

    # ------------------------------------------------------------------
    # Capas de fondo
    # ------------------------------------------------------------------
    def _draw_background(self):
        c = self.canvas
        # Gradiente simulado con dos rectángulos
        c.create_rectangle(0, 0, self.CW, self.CH, fill=C["bg_outer"], outline="")

    def _draw_pcb(self):
        """Placa base PCB con borde metálico."""
        c = self.canvas
        MX, MY = 28, 16   # margen
        x1, y1 = MX, MY
        x2, y2 = self.CW - MX, self.CH - MY

        # Sombra exterior
        self._rr(x1 + 3, y1 + 3, x2 + 3, y2 + 3, r=10,
                 fill="#05080f", outline="", tags="pcb_shadow")

        # PCB principal
        self._rr(x1, y1, x2, y2, r=10,
                 fill=C["pcb"], outline=C["pcb_border"], width=2, tags="pcb")

        # Borde metálico interior (efecto bisel)
        self._rr(x1 + 4, y1 + 4, x2 - 4, y2 - 4, r=8,
                 fill="", outline=C["pcb_edge"], width=1, tags="pcb_inner")

        # Label de la placa
        mb = f"{self.hw.get('mb_fabricante','?')} {self.hw.get('mb_modelo','?')}"
        c.create_text(
            self.CW // 2, y2 - 12,
            text=f"╟  {mb}  ╢",
            fill=C["text_dim"], font=("Consolas", 8), tags="pcb_label"
        )

    def _draw_circuit_traces(self):
        """Líneas decorativas que simulan pistas de PCB."""
        c = self.canvas
        traces = [
            # Horizontales lado izquierdo
            (46, 100, 180, 100), (46, 130, 170, 130), (46, 160, 160, 160),
            (46, 200, 150, 200), (46, 230, 140, 230),
            # Horizontales lado derecho
            (550, 75, 690, 75), (550, 110, 680, 110),
            (550, 145, 690, 145), (550, 180, 675, 180),
            # Verticales
            (190, 45, 190, 95), (200, 50, 200, 85),
            (560, 50, 560, 130), (600, 60, 600, 145),
            # Conectores medios bajo GPU
            (210, 346, 510, 346), (250, 350, 470, 350),
            (95, 346, 180, 346),
        ]
        for x1, y1, x2, y2 in traces:
            c.create_line(x1, y1, x2, y2, fill=C["trace"], width=1, tags="trace")

        # Nodos (uniones de pistas)
        nodes = [
            (190, 95), (200, 85), (560, 130), (600, 145),
            (170, 130), (150, 200), (360, 346), (410, 350),
        ]
        for nx, ny in nodes:
            c.create_oval(nx - 2, ny - 2, nx + 2, ny + 2,
                          fill=C["trace_glow"], outline="", tags="trace_node")

    def _draw_mounting_screws(self):
        """Orificios de montaje en las cuatro esquinas del PCB."""
        c = self.canvas
        positions = [(48, 32), (self.CW - 48, 32),
                     (48, self.CH - 32), (self.CW - 48, self.CH - 32)]
        for sx, sy in positions:
            # Anillo exterior dorado
            c.create_oval(sx - 8, sy - 8, sx + 8, sy + 8,
                          fill=C["screw_ring"], outline=C["screw_center"], width=1, tags="screw")
            # Centro del tornillo
            c.create_oval(sx - 4, sy - 4, sx + 4, sy + 4,
                          fill=C["screw_center"], outline=C["screw_ring"], width=1, tags="screw")
            # Cruz del tornillo
            c.create_line(sx - 2, sy, sx + 2, sy, fill=C["screw_ring"], width=1, tags="screw")
            c.create_line(sx, sy - 2, sx, sy + 2, fill=C["screw_ring"], width=1, tags="screw")

    # ------------------------------------------------------------------
    # Componentes de la placa
    # ------------------------------------------------------------------
    def _draw_io_panel(self):
        """Panel I/O trasero en borde izquierdo superior."""
        c = self.canvas
        fill, border, tcol = self._state_colors("IO")
        x1, y1, x2, y2 = 40, 42, 86, 186

        self._rr(x1, y1, x2, y2, r=4, fill=fill, outline=border, width=2, tags="io_panel")

        # Puertos estilizados
        port_configs = [
            (y1 + 10, "#e11d48"),   # USB-A
            (y1 + 28, "#e11d48"),
            (y1 + 46, "#1d4ed8"),   # USB 3.0
            (y1 + 64, "#1d4ed8"),
            (y1 + 82, "#16a34a"),   # RJ45
            (y1 + 102, "#ca8a04"),  # Audio
            (y1 + 120, "#ca8a04"),
        ]
        for py, pcol in port_configs:
            c.create_rectangle(x1 + 5, py, x2 - 5, py + 12,
                               fill=pcol, outline="#1e293b", width=1, tags="io_port")

        c.create_text((x1 + x2) // 2, y2 - 8,
                      text="I/O", fill=tcol, font=("Consolas", 7, "bold"), tags="io_panel_lbl")

        # Badge de alerta si es el afectado
        if self.comp_afectado == "IO":
            self._badge_alert(x2 - 3, y1 + 3)

        # Guardar bounds para hover
        self._io_bounds = (x1, y1, x2, y2)

    def _draw_psu_zone(self):
        """Zona PSU en la esquina inferior izquierda (separada de la GPU)."""
        c = self.canvas
        fill, border, tcol = self._state_colors("PSU")
        x1, y1, x2, y2 = 44, 360, 180, 458

        # Marco PSU
        self._rr(x1, y1, x2, y2, r=6, fill=C["psu_fill"], outline=C["psu_border"], width=2, tags="psu")

        # Rejilla de ventilación simulada
        for gx in range(x1 + 10, x2 - 5, 9):
            c.create_line(gx, y1 + 6, gx, y2 - 6, fill="#1f2d40", width=1, tags="psu_grid")
        for gy in range(y1 + 8, y2 - 5, 7):
            c.create_line(x1 + 6, gy, x2 - 6, gy, fill="#1f2d40", width=1, tags="psu_grid")

        # Conector principal 24-pin
        c.create_rectangle(x1 + 8, y1 + 10, x1 + 22, y1 + 75,
                           fill="#1a2030", outline="#374151", width=1, tags="psu_conn")
        for pi in range(6):
            py_p = y1 + 14 + pi * 9
            c.create_rectangle(x1 + 10, py_p, x1 + 20, py_p + 6,
                               fill="#374151", outline="", tags="psu_pin")

        # Etiqueta
        c.create_text((x1 + x2) // 2 + 10, (y1 + y2) // 2,
                       text="PSU\nFuente",
                       fill=C["text_secondary"], font=("Consolas", 8, "bold"),
                       justify="center", tags="psu_lbl")

        # Estado
        if self.comp_afectado == "PSU":
            self._rr(x1, y1, x2, y2, r=6, fill="", outline=C["alert"], width=3, tags="psu_alert")
            self._badge_alert(x2 - 8, y1 + 8)

        self._psu_bounds = (x1, y1, x2, y2)

    def _draw_storage_bay(self):
        """Bahía de almacenamiento secundaria (HDD/SSD SATA) inferior derecha."""
        c = self.canvas
        x1, y1, x2, y2 = 540, 360, 705, 458

        self._rr(x1, y1, x2, y2, r=6, fill=C["bay_fill"], outline=C["psu_border"], width=1, tags="bay")

        # Slots SATA visuales
        satas = ["SATA 1", "SATA 2", "SATA 3"]
        for i, lbl in enumerate(satas):
            sy = y1 + 10 + i * 26
            c.create_rectangle(x1 + 8, sy, x2 - 8, sy + 20,
                               fill="#111927", outline="#2d3748", width=1, tags="bay_slot")
            c.create_text(x1 + 45, sy + 10,
                          text=lbl, fill=C["text_dim"], font=("Consolas", 8), tags="bay_lbl")

        c.create_text((x1 + x2) // 2, y2 - 8,
                      text="STORAGE BAY",
                      fill=C["text_dim"], font=("Consolas", 7), tags="bay_main_lbl")

        self._bay_bounds = (x1, y1, x2, y2)

    def _draw_cpu_socket(self):
        """Socket CPU con marco metálico, IHS y ventilador/disipador esquemático."""
        c = self.canvas
        fill, border, tcol = self._state_colors("CPU")

        cpu_name = self.hw.get("nombre_cpu", "CPU")
        brand = ""
        if "ryzen" in cpu_name.lower():
            brand = "AMD Ryzen"
        elif "intel" in cpu_name.lower() or "core" in cpu_name.lower():
            brand = "Intel Core"
        elif "celeron" in cpu_name.lower():
            brand = "Intel Celeron"
        else:
            brand = cpu_name[:12]

        cx, cy = 265, 114   # centro del CPU
        SR = 48             # radio del disipador
        SK = 28             # mitad del socket

        # ── Disipador (fan shroud) ──
        fan_x1, fan_y1 = cx - SR - 8, cy - SR - 8
        fan_x2, fan_y2 = cx + SR + 8, cy + SR + 8
        self._rr(fan_x1, fan_y1, fan_x2, fan_y2, r=6,
                 fill="#141f30", outline="#253040", width=1, tags="cpu_fan_shroud")

        # Aspas del ventilador
        for angle_deg in range(0, 360, 45):
            import math
            ang = math.radians(angle_deg)
            bx = cx + SR * 0.55 * math.cos(ang)
            by = cy + SR * 0.55 * math.sin(ang)
            bx2 = cx + SR * 0.9 * math.cos(ang + math.radians(20))
            by2 = cy + SR * 0.9 * math.sin(ang + math.radians(20))
            c.create_line(int(bx), int(by), int(bx2), int(by2),
                          fill="#1e3a5a", width=3, tags="cpu_fan_blade")

        # Círculo central del fan
        c.create_oval(cx - 8, cy - 8, cx + 8, cy + 8,
                      fill="#111f30", outline="#253040", width=2, tags="cpu_fan_hub")

        # Aletas del disipador (radiador)
        for fi in range(-3, 4):
            fx = cx + fi * 12
            c.create_line(fx, fan_y1 + 4, fx, fan_y2 - 4,
                          fill="#1a2e45", width=2, tags="cpu_heatsink_fin")

        # ── Socket LGA/AM5 ──
        sock_x1, sock_y1 = cx - SK - 2, cy - SK - 2
        sock_x2, sock_y2 = cx + SK + 2, cy + SK + 2
        self._rr(sock_x1, sock_y1, sock_x2, sock_y2, r=4,
                 fill="#0d1520", outline="#374151", width=2, tags="cpu_socket_frame")

        # Anclajes del socket (4 esquinas)
        for ax, ay in [(sock_x1, sock_y1), (sock_x2, sock_y1),
                       (sock_x1, sock_y2), (sock_x2, sock_y2)]:
            c.create_oval(ax - 3, ay - 3, ax + 3, ay + 3,
                          fill="#374151", outline="#4b5563", width=1, tags="cpu_anchor")

        # IHS (Integrated Heat Spreader) — tapa metálica del CPU
        ihs_x1, ihs_y1 = cx - SK + 3, cy - SK + 3
        ihs_x2, ihs_y2 = cx + SK - 3, cy + SK - 3
        self._rr(ihs_x1, ihs_y1, ihs_x2, ihs_y2, r=3,
                 fill=C["cpu_lid"] if self.comp_afectado != "CPU" else C["alert_dim"],
                 outline=border if self.comp_afectado == "CPU" else "#6b7280",
                 width=2 if self.comp_afectado == "CPU" else 1,
                 tags="cpu_ihs")

        # Etiqueta dentro del IHS
        c.create_text(cx, cy - 6,
                      text="CPU", fill=C["text_dim"], font=("Consolas", 8, "bold"), tags="cpu_lbl")
        c.create_text(cx, cy + 7,
                      text=brand, fill=tcol, font=("Segoe UI", 7), tags="cpu_brand")

        # Alerta si es afectado
        if self.comp_afectado == "CPU":
            self._badge_alert(sock_x2 + 4, sock_y1 - 4)
            c.create_text(cx, fan_y2 + 9,
                          text="[!] REVISIÓN REQUERIDA",
                          fill=C["text_alert"], font=("Consolas", 7, "bold"), tags="cpu_alert_lbl")

        self._cpu_bounds = (fan_x1, fan_y1, fan_x2, fan_y2)

    def _draw_ram_slots(self):
        """Ranuras DIMM x4 con clips de retención."""
        c = self.canvas
        fill, border, tcol = self._state_colors("RAM")

        ram_info = self.hw.get("ram_modulos", [])
        ram_total = self.hw.get("ram_total_mb", "?")
        ram_tipo  = self.hw.get("ram_tipo", "DDR?")
        ram_vel   = self.hw.get("ram_velocidad_mhz", "?")

        slot_x_start = 420
        slot_w       = 18
        slot_h       = 120
        slot_gap     = 7
        slot_y_top   = 54

        for i in range(4):
            sx1 = slot_x_start + i * (slot_w + slot_gap)
            sy1 = slot_y_top
            sx2 = sx1 + slot_w
            sy2 = sy1 + slot_h

            # ¿Ranura ocupada?
            occupied = i < len(ram_info)
            s_fill   = fill if occupied else "#0d1520"
            s_border = border if occupied else "#1e293b"

            # Slot principal
            self._rr(sx1, sy1, sx2, sy2, r=2, fill=s_fill, outline=s_border, width=2, tags=f"ram_slot_{i}")

            # Chips de memoria sobre el módulo (si ocupado)
            if occupied:
                for ci in range(4):
                    cy_chip = sy1 + 12 + ci * 24
                    c.create_rectangle(sx1 + 2, cy_chip, sx2 - 2, cy_chip + 15,
                                       fill="#1a3050", outline="#2d5a8e", width=1, tags=f"ram_chip_{i}_{ci}")

            # Muesca de polaridad (keying notch)
            notch_y = sy1 + slot_h // 2 + 10
            c.create_rectangle(sx1 + 3, notch_y, sx2 - 3, notch_y + 3,
                               fill="#0d1520", outline="", tags=f"ram_notch_{i}")

            # Clips de retención (latches)
            c.create_rectangle(sx1 + 1, sy1 - 5, sx2 - 1, sy1 + 2,
                               fill=C["ram_clip"] if occupied else "#1e293b",
                               outline="", tags=f"ram_clip_top_{i}")
            c.create_rectangle(sx1 + 1, sy2 - 2, sx2 - 1, sy2 + 5,
                               fill=C["ram_clip"] if occupied else "#1e293b",
                               outline="", tags=f"ram_clip_bot_{i}")

            # Número de ranura
            c.create_text((sx1 + sx2) // 2, sy2 + 10,
                          text=f"D{i+1}", fill=C["text_dim"], font=("Consolas", 7), tags=f"ram_lbl_{i}")

        # Etiqueta resumen de RAM
        lbl_x = slot_x_start + (4 * slot_w + 3 * slot_gap) // 2
        c.create_text(lbl_x, slot_y_top + slot_h + 20,
                      text=f"{ram_total}  {ram_tipo} @{ram_vel}MHz",
                      fill=tcol, font=("Consolas", 8), tags="ram_summary_lbl")

        # Alerta
        if self.comp_afectado == "RAM":
            for i in range(4):
                sx1 = slot_x_start + i * (slot_w + slot_gap)
                c.create_rectangle(sx1, slot_y_top - 6, sx1 + slot_w, slot_y_top + slot_h + 6,
                                   fill="", outline=C["alert"], width=2, tags="ram_alert_border")
            self._badge_alert(slot_x_start + 4 * (slot_w + slot_gap) + 8, slot_y_top - 2)
            c.create_text(lbl_x, slot_y_top + slot_h + 32,
                          text="[!] Revisar XMP/EXPO",
                          fill=C["text_alert"], font=("Consolas", 7, "bold"), tags="ram_alert_lbl")

        self._ram_bounds = (slot_x_start - 4, slot_y_top - 6,
                            slot_x_start + 4 * slot_w + 3 * slot_gap + 4,
                            slot_y_top + slot_h + 6)

    def _draw_m2_slot(self):
        """Módulo M.2 NVMe 2280 con disipador térmico."""
        c = self.canvas
        fill, border, tcol = self._state_colors("M2")

        discos = self.hw.get("discos_fisicos", [])
        m2_label = "M.2 NVMe"
        for d in discos:
            if "nvme" in d.get("tipo", "").lower():
                cap = d.get("capacidad_gb", 0)
                m2_label = f"NVMe {cap:.0f}GB" if cap else "NVMe SSD"
                break

        x1, y1, x2, y2 = 180, 194, 345, 220

        # Disipador térmico (heatsink)
        hs_fill = C["m2_hs"] if self.comp_afectado != "M2" else C["alert_dim"]
        self._rr(x1 - 3, y1 - 4, x2 + 3, y2 + 4, r=3,
                 fill=hs_fill, outline=border, width=2 if self.comp_afectado == "M2" else 1,
                 tags="m2_heatsink")

        # Aletas del disipador
        for hx in range(x1 + 4, x2 - 4, 8):
            c.create_line(hx, y1 - 3, hx, y2 + 3, fill="#1a2a3a", width=2, tags="m2_hs_fin")

        # Módulo SSD debajo del heatsink
        self._rr(x1, y1, x2, y2, r=2, fill=fill, outline=border, width=1, tags="m2_module")

        # Chips del módulo (NAND flash)
        for ci in range(4):
            chip_x = x1 + 10 + ci * 36
            c.create_rectangle(chip_x, y1 + 4, chip_x + 25, y2 - 4,
                               fill="#1a3050", outline="#2d5a8e", width=1, tags=f"m2_chip_{ci}")

        # Conector M.2 (extremo derecho)
        c.create_rectangle(x2 - 3, y1 + 5, x2 + 2, y2 - 5,
                           fill="#0a1020", outline="#374151", width=1, tags="m2_connector")

        # Etiqueta
        c.create_text((x1 + x2) // 2, (y1 + y2) // 2,
                      text=m2_label, fill=tcol, font=("Consolas", 8, "bold"), tags="m2_lbl")

        # Slot de anclaje
        c.create_oval(x2 + 4, (y1 + y2) // 2 - 3, x2 + 10, (y1 + y2) // 2 + 3,
                      fill="#374151", outline="#4b5563", tags="m2_anchor")

        # Alerta
        if self.comp_afectado == "M2":
            self._badge_alert(x2 + 12, y1 - 2)

        self._m2_bounds = (x1 - 4, y1 - 5, x2 + 10, y2 + 5)

    def _draw_pcie_gpu(self):
        """Slot PCIe x16 con refuerzo metálico y tarjeta gráfica optimizada."""
        c = self.canvas
        fill, border, tcol = self._state_colors("GPU")

        gpu_name = self.hw.get("gpu_principal", "GPU")
        gpu_short = gpu_name
        for brand in ("NVIDIA GeForce ", "AMD Radeon ", "Intel Arc "):
            if brand.lower() in gpu_name.lower():
                gpu_short = gpu_name[len(brand):] if gpu_name.lower().startswith(brand.lower()) else gpu_name
                break
        if len(gpu_short) > 20:
            gpu_short = gpu_short[:20] + "…"

        # ── Slot PCIe x16 ──
        slot_x1, slot_y1 = 120, 242
        slot_x2, slot_y2 = 540, 256

        # Refuerzo metálico del slot
        self._rr(slot_x1, slot_y1, slot_x2, slot_y2, r=3,
                 fill="#0a1018", outline="#c0c0c0", width=2, tags="pcie_slot_reinforce")

        # Ranura interior
        c.create_rectangle(slot_x1 + 4, slot_y1 + 4, slot_x2 - 4, slot_y2 - 4,
                           fill="#050a10", outline="#374151", width=1, tags="pcie_slot_inner")

        # Pins del slot
        for px in range(slot_x1 + 8, slot_x2 - 8, 6):
            c.create_line(px, slot_y1 + 4, px, slot_y2 - 4,
                          fill="#1e3a5a", width=1, tags="pcie_pin")

        # Etiqueta PCIe
        c.create_text(slot_x1 - 22, (slot_y1 + slot_y2) // 2,
                      text="PCIe\nx16", fill=C["text_dim"], font=("Consolas", 7),
                      justify="center", tags="pcie_label")

        # ── Tarjeta Gráfica (GPU card) ──
        card_x1, card_y1 = slot_x1 + 10, slot_y2
        card_x2, card_y2 = 560, slot_y2 + 78

        gpu_fill = fill
        self._rr(card_x1, card_y1, card_x2, card_y2, r=6,
                 fill=gpu_fill, outline=border, width=3 if self.comp_afectado == "GPU" else 1,
                 tags="gpu_card")

        # PCB de la tarjeta
        self._rr(card_x1 + 3, card_y1 + 3, card_x2 - 3, card_y2 - 3, r=4,
                 fill=C["gpu_fill"], outline="", tags="gpu_pcb")

        # Ventiladores (x3 esquemáticos reducidos a escala)
        fan_centers = [
            (card_x1 + 68, card_y1 + 39),
            (card_x1 + 185, card_y1 + 39),
            (card_x1 + 300, card_y1 + 39),
        ]
        fan_r = 26
        for fx, fy in fan_centers:
            # Shroud del ventilador
            c.create_oval(fx - fan_r, fy - fan_r, fx + fan_r, fy + fan_r,
                          fill=C["gpu_fan"], outline=border, width=1, tags="gpu_fan_ring")
            # Aspas
            import math
            for ang_d in range(0, 360, 60):
                a = math.radians(ang_d)
                bx1 = fx + (fan_r * 0.3) * math.cos(a)
                by1 = fy + (fan_r * 0.3) * math.sin(a)
                bx2 = fx + (fan_r * 0.82) * math.cos(a + math.radians(25))
                by2 = fy + (fan_r * 0.82) * math.sin(a + math.radians(25))
                c.create_line(int(bx1), int(by1), int(bx2), int(by2),
                              fill="#1a3050", width=2, tags="gpu_fan_blade")
            # Hub central
            c.create_oval(fx - 6, fy - 6, fx + 6, fy + 6,
                          fill="#0a1525", outline="#253550", width=1, tags="gpu_fan_hub")

        # Conectores de energía PCIe 8-pin
        conn_x = card_x2 - 25
        for ci in range(2):
            cy_c = card_y1 + 10 + ci * 28
            c.create_rectangle(conn_x - 12, cy_c, conn_x + 12, cy_c + 22,
                               fill="#111927", outline="#374151", width=1, tags=f"gpu_pwr_{ci}")
            for pi in range(4):
                c.create_rectangle(conn_x - 10 + pi * 5, cy_c + 3,
                                   conn_x - 7 + pi * 5, cy_c + 18,
                                   fill="#374151", outline="", tags=f"gpu_pin_{ci}_{pi}")
            c.create_text(conn_x, cy_c - 5,
                          text="8-pin", fill=C["text_dim"], font=("Consolas", 6), tags=f"gpu_pwr_lbl_{ci}")

        # Etiqueta de la GPU
        c.create_text((card_x1 + card_x2) // 2, card_y1 + 12,
                      text=f"GPU  ·  {gpu_short}",
                      fill=tcol, font=("Segoe UI", 9, "bold"), tags="gpu_lbl")

        # VRAM chips (indicador compacto)
        gpus_data = self.hw.get("gpus", [])
        if gpus_data:
            vram_mb = gpus_data[0].get("vram_mb", 0)
            vram_str = f"{int(vram_mb/1024)} GB VRAM" if vram_mb >= 1024 else f"{int(vram_mb)} MB"
            c.create_text((card_x1 + card_x2) // 2, card_y2 - 9,
                          text=vram_str,
                          fill=C["text_secondary"], font=("Consolas", 8), tags="gpu_vram_lbl")

        # Alerta
        if self.comp_afectado == "GPU":
            self._rr(card_x1, card_y1, card_x2, card_y2, r=6,
                     fill="", outline=C["alert"], width=3, tags="gpu_alert_border")
            self._badge_alert(card_x2 - 10, card_y1 + 10)
            c.create_text((card_x1 + card_x2) // 2, card_y1 + 22,
                          text="[!] TARJETA GRÁFICA — Revisar PCIe / Alimentación",
                          fill=C["text_alert"], font=("Consolas", 7, "bold"), tags="gpu_alert_lbl")

        # Placa bracket trasero
        c.create_rectangle(card_x1, card_y1, card_x1 + 14, card_y2,
                           fill="#1a2030", outline="#374151", width=1, tags="gpu_bracket")
        # Puertos de video en el bracket
        for port_i, (port_col, port_lbl) in enumerate([
            ("#1d4ed8", "DP"), ("#1d4ed8", "DP"), ("#374151", "HD")
        ]):
            py_p = card_y1 + 10 + port_i * 20
            c.create_rectangle(card_x1 + 2, py_p, card_x1 + 12, py_p + 14,
                               fill=port_col, outline="#1e293b", width=1, tags=f"gpu_port_{port_i}")

        self._gpu_bounds = (card_x1, slot_y1, card_x2, card_y2)

    # ------------------------------------------------------------------
    # Leyenda
    # ------------------------------------------------------------------
    def _draw_legend(self):
        """Pequeña leyenda de colores en la esquina inferior derecha del canvas."""
        c = self.canvas
        lx, ly = 724, 378
        items = [
            (C["ok"],   "Óptimo / Saludable"),
            (C["warn"], "Advertencia"),
            (C["alert"],"Falla / Alerta"),
        ]
        c.create_text(lx + 40, ly - 8,
                      text="ESTADO", fill=C["text_dim"], font=("Consolas", 7, "bold"), tags="legend_hdr")
        for i, (col, lbl) in enumerate(items):
            c.create_rectangle(lx, ly + i * 18, lx + 10, ly + 10 + i * 18,
                               fill=col, outline="", tags=f"legend_{i}")
            c.create_text(lx + 15, ly + 5 + i * 18,
                          text=lbl, fill=C["text_secondary"], font=("Consolas", 7),
                          anchor="w", tags=f"legend_lbl_{i}")

    # ------------------------------------------------------------------
    # Sistema de hover y tooltips
    # ------------------------------------------------------------------
    def _bind_hover_events(self):
        """Vincula el evento de movimiento del mouse para detección de hover."""
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.bind("<Leave>", self._on_mouse_leave)
        self._current_hover: str | None = None

    def _on_mouse_leave(self, event):
        self._clear_tooltip()
        self._current_hover = None

    def _on_mouse_move(self, event):
        mx, my = event.x, event.y
        hit = self._hit_test(mx, my)
        if hit != self._current_hover:
            self._current_hover = hit
            self._clear_tooltip()
            if hit:
                self._show_tooltip(hit, mx, my)

    def _hit_test(self, mx: int, my: int) -> str | None:
        """Retorna la clave del componente bajo el cursor, o None."""
        def inside(bounds):
            x1, y1, x2, y2 = bounds
            return x1 <= mx <= x2 and y1 <= my <= y2

        if hasattr(self, "_cpu_bounds") and inside(self._cpu_bounds):
            return "CPU"
        if hasattr(self, "_ram_bounds") and inside(self._ram_bounds):
            return "RAM"
        if hasattr(self, "_gpu_bounds") and inside(self._gpu_bounds):
            return "GPU"
        if hasattr(self, "_m2_bounds") and inside(self._m2_bounds):
            return "M2"
        if hasattr(self, "_io_bounds") and inside(self._io_bounds):
            return "IO"
        if hasattr(self, "_psu_bounds") and inside(self._psu_bounds):
            return "PSU"
        return None

    def _build_tooltip_data(self, comp_key: str) -> tuple[str, str, str]:
        """
        Retorna (título, datos, estado) para la tarjeta emergente de cada componente.
        """
        hw = self.hw
        afectado = (self.comp_afectado == comp_key)

        if comp_key == "CPU":
            nombre   = hw.get("nombre_cpu", "N/A")
            nucleos  = f"{hw.get('nucleos_fisicos','?')}C / {hw.get('nucleos','?')}T"
            freq_b   = hw.get("frecuencia_base_ghz", "?")
            freq_a   = hw.get("frecuencia_actual_ghz", "?")
            uso      = hw.get("uso_cpu_total", "?")
            data = (f"Modelo:  {nombre}\n"
                    f"Núcleos: {nucleos}\n"
                    f"Freq Base:   {freq_b} GHz\n"
                    f"Freq Actual: {freq_a} GHz\n"
                    f"Uso Total:   {uso}%")
            estado = "[!] BAJO DIAGNÓSTICO" if afectado else "✔ Normal"
            return "CPU / Socket", data, estado

        if comp_key == "RAM":
            total = hw.get("ram_total_mb", "?")
            libre = hw.get("ram_disponible_mb", "?")
            tipo  = hw.get("ram_tipo", "?")
            vel   = hw.get("ram_velocidad_mhz", "?")
            uso_p = hw.get("ram_uso_pct", "?")
            slots = hw.get("ram_ranuras_ocupadas", "?")
            data = (f"Total:    {total}\n"
                    f"Libre:    {libre}\n"
                    f"Tipo:     {tipo} @ {vel} MHz\n"
                    f"Uso:      {uso_p}%\n"
                    f"Ranuras:  {slots} ocupadas")
            estado = "[!] Revisar XMP/EXPO" if afectado else "✔ Normal"
            return "Memoria RAM — DIMMs", data, estado

        if comp_key == "GPU":
            gpus = hw.get("gpus", [])
            if gpus:
                g = gpus[0]
                nombre = g.get("nombre", "?")
                vram   = g.get("vram_mb", 0)
                driver = g.get("driver_version", "?")
                data = (f"Modelo:  {nombre}\n"
                        f"VRAM:    {int(vram)} MB\n"
                        f"Driver:  {driver}")
            else:
                data = "No detectada"
            estado = "[!] Revisar slot PCIe" if afectado else "✔ Normal"
            return "Tarjeta Gráfica — GPU", data, estado

        if comp_key == "M2":
            discos = hw.get("discos_fisicos", [])
            lines = []
            for d in discos:
                lines.append(f"{d.get('tipo','?')}: {d.get('modelo','?')} — {d.get('capacidad_gb','?')} GB")
            data = "\n".join(lines) if lines else "Sin discos detectados"
            estado = "[!] Thermal Throttling" if afectado else "✔ Normal"
            return "M.2 NVMe / Almacenamiento", data, estado

        if comp_key == "IO":
            ip       = hw.get("ip_local", "?")
            adaptador= hw.get("adaptador_activo", "?")
            latencia = hw.get("latencia_ms", "?")
            data = (f"Adaptador: {adaptador}\n"
                    f"IP Local:  {ip}\n"
                    f"Latencia:  {latencia}")
            estado = "[!] Revisar adaptador" if afectado else "✔ Normal"
            return "Panel I/O — Red", data, estado

        if comp_key == "PSU":
            data = "Fuente de Poder\nRevise conexiones 24-pin\ny conectores PCIe"
            estado = "[!] Falla detectada" if afectado else "✔ Normal"
            return "PSU — Fuente de Poder", data, estado

        return comp_key, "Sin datos", "?"

    def _show_tooltip(self, comp_key: str, mx: int, my: int):
        """Dibuja la tarjeta de información emergente."""
        c = self.canvas
        title, data, estado = self._build_tooltip_data(comp_key)
        afectado = (self.comp_afectado == comp_key)

        # Calcular posición (evitar salirse del canvas)
        TW, TH = 250, 130
        tx = mx + 12
        ty = my + 12
        if tx + TW > self.CW - 10:
            tx = mx - TW - 12
        if ty + TH > self.CH - 10:
            ty = my - TH - 12

        # Fondo y borde de la tooltip
        border_col = C["alert"] if afectado else C["text_cyan"]
        tid_bg = self._rr(tx, ty, tx + TW, ty + TH, r=6,
                          fill=C["tooltip_bg"], outline=border_col, width=2)
        self._tooltip_items.append(tid_bg)

        # Barra superior de título
        tid_bar = self._rr(tx + 2, ty + 2, tx + TW - 2, ty + 22, r=4,
                           fill=C["alert_dim"] if afectado else "#0d2040", outline="")
        self._tooltip_items.append(tid_bar)

        # Título
        tid_title = c.create_text(tx + TW // 2, ty + 12,
                                  text=title,
                                  fill=C["text_alert"] if afectado else C["text_cyan"],
                                  font=("Segoe UI", 9, "bold"), anchor="center")
        self._tooltip_items.append(tid_title)

        # Datos técnicos
        tid_data = c.create_text(tx + 8, ty + 28,
                                 text=data,
                                 fill=C["text_primary"],
                                 font=("Consolas", 8),
                                 anchor="nw", justify="left")
        self._tooltip_items.append(tid_data)

        # Estado
        estado_col = C["text_alert"] if afectado else C["text_ok"]
        tid_estado = c.create_text(tx + 8, ty + TH - 12,
                                   text=f"Estado: {estado}",
                                   fill=estado_col,
                                   font=("Consolas", 8, "bold"),
                                   anchor="w")
        self._tooltip_items.append(tid_estado)

    def _clear_tooltip(self):
        """Elimina todos los elementos del tooltip del canvas."""
        c = self.canvas
        for item in self._tooltip_items:
            try:
                c.delete(item)
            except Exception:
                pass
        self._tooltip_items.clear()
