"""
core/ui_theme.py — Sistema de Diseño y Motor de Animaciones a 60 FPS
====================================================================
Paleta, tipografías y componentes reutilizables con interpolación fluida
a 60 FPS (FRAME_MS = 16 ms) para que todas las vistas de `main.py`
compartan una experiencia visual de alta fluidez sin bloquear el hilo Tk.
"""

from __future__ import annotations

import math
import re
import tkinter as tk
from typing import Callable

import customtkinter as ctk

# Intervalo nativo de 60 FPS (~16.6 ms -> 16 ms en Tkinter)
FRAME_MS: int = 16

# ---------------------------------------------------------------------------
# Paleta (dark-tech, alineada con core/hardware_map.py)
# ---------------------------------------------------------------------------
P = {
    "bg":          "#0b0f19",
    "surface":     "#0f172a",
    "card":        "#131c2e",
    "card_alt":    "#172238",
    "borde":       "#1e293b",
    "borde_fuerte": "#334155",
    "texto":       "#e2e8f0",
    "texto_sec":   "#94a3b8",
    "texto_dim":   "#64748b",
    "primario":    "#10b981",
    "primario_h":  "#059669",
    "cian":        "#06b6d4",
    "azul":        "#2563eb",
    "azul_h":      "#1d4ed8",
    "violeta":     "#8b5cf6",
    "violeta_h":   "#7c3aed",
    "ambar":       "#f59e0b",
    "ambar_h":     "#d97706",
    "rojo":        "#ef4444",
    "rojo_h":      "#dc2626",
    "neutro":      "#334155",
    "neutro_h":    "#475569",
    "ok_bg":       "#052e22",
    "warn_bg":     "#3a1d04",
    "err_bg":      "#3b0a0a",
    "info_bg":     "#072a3d",
}

# Tipografías
F_H1      = ("Segoe UI Semibold", 22)
F_H2      = ("Segoe UI Semibold", 17)
F_H3      = ("Segoe UI Semibold", 13)
F_BODY    = ("Segoe UI", 12)
F_SMALL   = ("Segoe UI", 11)
F_CAPTION = ("Segoe UI", 10)
F_MONO    = ("Consolas", 11)
F_METRIC  = ("Segoe UI Semibold", 20)

# Variantes de botón → (fg, hover, texto)
_VARIANTES = {
    "primario":   (P["primario"], P["primario_h"], "#04140e"),
    "azul":       (P["azul"], P["azul_h"], "#ffffff"),
    "violeta":    (P["violeta"], P["violeta_h"], "#ffffff"),
    "ambar":      (P["ambar"], P["ambar_h"], "#1a1002"),
    "peligro":    (P["rojo"], P["rojo_h"], "#ffffff"),
    "neutro":     (P["neutro"], P["neutro_h"], P["texto"]),
    "fantasma":   ("transparent", P["card_alt"], P["texto_sec"]),
}

# Badges → (fondo, texto)
_BADGES = {
    "ok":     (P["ok_bg"], P["primario"]),
    "warn":   (P["warn_bg"], P["ambar"]),
    "err":    (P["err_bg"], P["rojo"]),
    "info":   (P["info_bg"], P["cian"]),
    "neutro": (P["card_alt"], P["texto_sec"]),
    "violeta": ("#24123f", "#c4b5fd"),
}


def _hex_to_rgb(hex_col: str) -> tuple[int, int, int]:
    h = (hex_col or "#000000").lstrip("#")
    if len(h) != 6:
        return (19, 28, 46)
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except ValueError:
        return (19, 28, 46)


def _lerp_hex(c1: str, c2: str, t: float) -> str:
    """Interpolación lineal RGB entre dos colores hexadecimales (0.0 <= t <= 1.0)."""
    if c1 == "transparent":
        c1 = P["card"]
    if c2 == "transparent":
        c2 = P["card"]
    t = max(0.0, min(1.0, float(t)))
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def _ease_out_quart(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 4


def color_por_umbral(pct: float, warn: float = 70, err: float = 90) -> str:
    """Verde < warn ≤ ámbar < err ≤ rojo."""
    if pct >= err:
        return P["rojo"]
    if pct >= warn:
        return P["ambar"]
    return P["primario"]


def nivel_por_umbral(pct: float, warn: float = 70, err: float = 90) -> str:
    if pct >= err:
        return "err"
    if pct >= warn:
        return "warn"
    return "ok"


def _vivo(widget) -> bool:
    try:
        return bool(widget.winfo_exists())
    except Exception:
        return False


def animar_entrada_panel(
    panel,
    relx: float = 0.5,
    rely_final: float = 0.5,
    desplazamiento: float = 0.024,
    pasos: int = 12,
) -> None:
    """
    Desliza suavemente un contenedor principal hacia su posición central a 60 FPS (16 ms).
    Coloca el widget de inmediato para que winfo_exists() y los tests sincrónicos funcionen.
    """
    if not _vivo(panel):
        return
    rely_ini = rely_final + desplazamiento
    panel.place(relx=relx, rely=rely_ini, anchor="center")

    def _step(i: int):
        if not _vivo(panel):
            return
        t = _ease_out_quart(i / pasos)
        rely_cur = rely_ini + (rely_final - rely_ini) * t
        try:
            panel.place_configure(rely=rely_cur)
        except Exception:
            return
        if i < pasos:
            panel.after(FRAME_MS, lambda: _step(i + 1))

    panel.after(FRAME_MS, lambda: _step(1))


def _adjuntar_hover_borde_60fps(widget, color_base: str, color_hover: str, pasos: int = 8) -> None:
    """Anima el color del borde de una tarjeta o botón a 60 FPS al pasar el cursor."""
    estado = {"t": 0.0, "target": 0.0, "after": None}

    def _tick():
        if not _vivo(widget):
            return
        actual = estado["t"]
        meta = estado["target"]
        diff = meta - actual
        if abs(diff) < 0.08:
            estado["t"] = meta
            try:
                widget.configure(border_color=_lerp_hex(color_base, color_hover, meta))
            except Exception:
                pass
            estado["after"] = None
            return
        estado["t"] = actual + diff * 0.35
        try:
            widget.configure(border_color=_lerp_hex(color_base, color_hover, estado["t"]))
        except Exception:
            estado["after"] = None
            return
        estado["after"] = widget.after(FRAME_MS, _tick)

    def _on_enter(_e=None):
        estado["target"] = 1.0
        if estado["after"] is None and _vivo(widget):
            estado["after"] = widget.after(FRAME_MS, _tick)

    def _on_leave(_e=None):
        estado["target"] = 0.0
        if estado["after"] is None and _vivo(widget):
            estado["after"] = widget.after(FRAME_MS, _tick)

    try:
        widget.bind("<Enter>", _on_enter, add="+")
        widget.bind("<Leave>", _on_leave, add="+")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Fábricas con micro-interacciones a 60 FPS
# ---------------------------------------------------------------------------
def boton(parent, texto: str, comando: Callable | None = None,
          variante: str = "primario", **kw) -> ctk.CTkButton:
    fg, hover, txt = _VARIANTES.get(variante, _VARIANTES["primario"])
    opciones = dict(
        text=texto, command=comando, fg_color=fg, hover_color=hover,
        text_color=txt, corner_radius=8, height=36, font=F_H3,
    )
    if variante == "fantasma":
        opciones.update(border_width=1, border_color=P["borde_fuerte"])
    opciones.update(kw)
    btn = ctk.CTkButton(parent, **opciones)

    # Transición cromática de fondo a 60 FPS en hover (cuando el fondo no es transparente)
    if fg != "transparent":
        est = {"t": 0.0, "target": 0.0, "after": None}

        def _anim_bg():
            if not _vivo(btn):
                return
            diff = est["target"] - est["t"]
            if abs(diff) < 0.08:
                est["t"] = est["target"]
                try:
                    btn.configure(fg_color=_lerp_hex(fg, hover, est["t"]))
                except Exception:
                    pass
                est["after"] = None
                return
            est["t"] += diff * 0.38
            try:
                btn.configure(fg_color=_lerp_hex(fg, hover, est["t"]))
            except Exception:
                est["after"] = None
                return
            est["after"] = btn.after(FRAME_MS, _anim_bg)

        def _enter(_e=None):
            est["target"] = 1.0
            if est["after"] is None and _vivo(btn):
                est["after"] = btn.after(FRAME_MS, _anim_bg)

        def _leave(_e=None):
            est["target"] = 0.0
            if est["after"] is None and _vivo(btn):
                est["after"] = btn.after(FRAME_MS, _anim_bg)

        try:
            btn.bind("<Enter>", _enter, add="+")
            btn.bind("<Leave>", _leave, add="+")
        except Exception:
            pass
    else:
        _adjuntar_hover_borde_60fps(btn, P["borde_fuerte"], P["cian"])

    return btn


def tarjeta(parent, alt: bool = False, **kw) -> ctk.CTkFrame:
    borde_ini = kw.get("border_color", P["borde"])
    opciones = dict(
        fg_color=P["card_alt"] if alt else P["card"], corner_radius=12,
        border_width=1, border_color=borde_ini,
    )
    opciones.update(kw)
    frame = ctk.CTkFrame(parent, **opciones)
    _adjuntar_hover_borde_60fps(frame, borde_ini, P["borde_fuerte"])
    return frame


def entrada(parent, placeholder: str, **kw) -> ctk.CTkEntry:
    opciones = dict(
        placeholder_text=placeholder, height=38, corner_radius=8,
        fg_color=P["surface"], border_color=P["borde_fuerte"], border_width=1,
        text_color=P["texto"], placeholder_text_color=P["texto_dim"], font=F_BODY,
    )
    opciones.update(kw)
    ent = ctk.CTkEntry(parent, **opciones)
    _adjuntar_hover_borde_60fps(ent, P["borde_fuerte"], P["cian"])
    return ent


def etiqueta(parent, texto: str, estilo: str = "body", **kw) -> ctk.CTkLabel:
    mapa = {
        "h1": (F_H1, P["texto"]), "h2": (F_H2, P["texto"]), "h3": (F_H3, P["texto"]),
        "body": (F_BODY, P["texto"]), "sec": (F_SMALL, P["texto_sec"]),
        "caption": (F_CAPTION, P["texto_dim"]), "mono": (F_MONO, P["texto_sec"]),
        "metric": (F_METRIC, P["texto"]),
    }
    fuente, color = mapa.get(estilo, mapa["body"])
    opciones = dict(text=texto, font=fuente, text_color=color, anchor="w", justify="left")
    opciones.update(kw)
    return ctk.CTkLabel(parent, **opciones)


def overline(parent, texto: str, color: str | None = None) -> ctk.CTkLabel:
    """Rótulo pequeño en mayúsculas para encabezar secciones/tarjetas."""
    return ctk.CTkLabel(parent, text=texto.upper(), font=("Segoe UI Semibold", 9),
                        text_color=color or P["texto_dim"], anchor="w")


def estilo_checkbox() -> dict:
    return dict(
        fg_color=P["primario"], hover_color=P["primario_h"],
        border_color=P["borde_fuerte"], checkmark_color="#04140e",
        text_color=P["texto"], corner_radius=5, border_width=2,
    )


def estilo_combo() -> dict:
    """Estilo para CTkComboBox / CTkOptionMenu acorde al fondo oscuro."""
    return dict(
        fg_color=P["surface"], border_color=P["borde_fuerte"], button_color=P["neutro"],
        button_hover_color=P["neutro_h"], dropdown_fg_color=P["card_alt"],
        dropdown_hover_color=P["neutro"], dropdown_text_color=P["texto"],
        text_color=P["texto"], font=F_SMALL, dropdown_font=F_SMALL, corner_radius=8,
    )


def estilo_segmentado() -> dict:
    return dict(
        fg_color=P["surface"], selected_color=P["violeta"], selected_hover_color=P["violeta_h"],
        unselected_color=P["card_alt"], unselected_hover_color=P["neutro"],
        text_color=P["texto"], font=F_SMALL, corner_radius=8,
    )


def estilo_tabview() -> dict:
    return dict(
        fg_color=P["card"], border_width=1, border_color=P["borde"], corner_radius=12,
        segmented_button_fg_color=P["surface"],
        segmented_button_selected_color=P["primario"],
        segmented_button_selected_hover_color=P["primario_h"],
        segmented_button_unselected_color=P["surface"],
        segmented_button_unselected_hover_color=P["card_alt"],
        text_color=P["texto"],
    )


def estilo_textbox() -> dict:
    return dict(
        fg_color=P["surface"], border_width=1, border_color=P["borde"],
        text_color=P["texto_sec"], font=F_MONO, corner_radius=10,
        scrollbar_button_color=P["neutro"], scrollbar_button_hover_color=P["neutro_h"],
    )


# ---------------------------------------------------------------------------
# Componentes animados a 60 FPS
# ---------------------------------------------------------------------------
class Badge(ctk.CTkLabel):
    """Pastilla de estado: ok / warn / err / info / neutro / violeta."""

    def __init__(self, parent, texto: str, tipo: str = "neutro", **kw):
        bg, fg = _BADGES.get(tipo, _BADGES["neutro"])
        opciones = dict(text=f"  {texto}  ", fg_color=bg, text_color=fg,
                        corner_radius=8, font=("Segoe UI Semibold", 10), height=22)
        opciones.update(kw)
        super().__init__(parent, **opciones)
        self.tipo = tipo

    def set(self, texto: str, tipo: str | None = None):
        if tipo:
            bg, fg = _BADGES.get(tipo, _BADGES["neutro"])
            self.configure(fg_color=bg, text_color=fg)
            self.tipo = tipo
        self.configure(text=f"  {texto}  ")


class BarraMetrica(ctk.CTkFrame):
    """Etiqueta + valor + barra de progreso con interpolación fluida a 60 FPS (16 ms)."""

    def __init__(self, parent, titulo: str, valor_pct: float = 0.0, texto_valor: str = "",
                 warn: float = 70, err: float = 90, alto_barra: int = 8, **kw):
        super().__init__(parent, fg_color="transparent", **kw)
        self._warn, self._err = warn, err
        self._actual = 0.0
        self._color_actual = P["primario"]
        self._after: str | None = None

        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x")
        self.lbl_titulo = ctk.CTkLabel(fila, text=titulo, font=F_SMALL,
                                       text_color=P["texto_sec"], anchor="w")
        self.lbl_titulo.pack(side="left")
        self.lbl_valor = ctk.CTkLabel(fila, text=texto_valor, font=("Segoe UI Semibold", 11),
                                      text_color=P["texto"], anchor="e")
        self.lbl_valor.pack(side="right")

        self.barra = ctk.CTkProgressBar(self, height=alto_barra, corner_radius=4,
                                        fg_color=P["surface"], progress_color=P["primario"])
        self.barra.pack(fill="x", pady=(3, 0))
        self.barra.set(0)
        self.set(valor_pct, texto_valor, animar=True)

    def set(self, valor_pct: float, texto_valor: str | None = None, animar: bool = True):
        try:
            destino = max(0.0, min(100.0, float(valor_pct)))
        except (TypeError, ValueError):
            destino = 0.0
        if texto_valor is not None:
            self.lbl_valor.configure(text=texto_valor)
        color_dest = color_por_umbral(destino, self._warn, self._err)
        if self._after:
            try:
                self.after_cancel(self._after)
            except Exception:
                pass
            self._after = None
        if not animar:
            self._actual = destino
            self._color_actual = color_dest
            self.barra.configure(progress_color=color_dest)
            self.barra.set(destino / 100)
            return
        self._animar(self._actual, destino, self._color_actual, color_dest, paso=0, total=22)

    def _animar(self, desde: float, hasta: float, col_ini: str, col_fin: str, paso: int, total: int):
        if not _vivo(self):
            return
        t = _ease_out_quart((paso + 1) / total)
        valor = desde + (hasta - desde) * t
        col = _lerp_hex(col_ini, col_fin, t)
        self._actual = valor
        self._color_actual = col
        self.barra.configure(progress_color=col)
        self.barra.set(valor / 100)
        if paso + 1 < total:
            self._after = self.after(FRAME_MS, lambda: self._animar(desde, hasta, col_ini, col_fin, paso + 1, total))
        else:
            self._after = None

    @property
    def valor(self) -> float:
        return self._actual


class TarjetaMetrica(ctk.CTkFrame):
    """KPI compacto con realce de borde a 60 FPS en hover y al actualizar valores."""

    def __init__(self, parent, titulo: str, valor: str = "—", subtitulo: str = "",
                 color: str | None = None, **kw):
        opciones = dict(fg_color=P["card_alt"], corner_radius=10,
                        border_width=1, border_color=P["borde"])
        opciones.update(kw)
        super().__init__(parent, **opciones)
        self._acento = color or P["cian"]
        self._flash_after: str | None = None
        overline(self, titulo).pack(anchor="w", padx=12, pady=(10, 0))
        self.lbl_valor = ctk.CTkLabel(self, text=valor, font=F_METRIC,
                                      text_color=color or P["texto"], anchor="w")
        self.lbl_valor.pack(anchor="w", padx=12)
        self.lbl_sub = ctk.CTkLabel(self, text=subtitulo, font=F_CAPTION,
                                    text_color=P["texto_dim"], anchor="w")
        self.lbl_sub.pack(anchor="w", padx=12, pady=(0, 10))
        _adjuntar_hover_borde_60fps(self, P["borde"], self._acento)

    def set(self, valor: str, subtitulo: str | None = None, color: str | None = None):
        self.lbl_valor.configure(text=valor)
        if color:
            self._acento = color
            self.lbl_valor.configure(text_color=color)
        if subtitulo is not None:
            self.lbl_sub.configure(text=subtitulo)
        self._pulso_borde_60fps()

    def _pulso_borde_60fps(self, paso: int = 0, total: int = 10):
        if not _vivo(self):
            return
        if self._flash_after and paso == 0:
            try:
                self.after_cancel(self._flash_after)
            except Exception:
                pass
        t = 1.0 - (paso / total)
        try:
            self.configure(border_color=_lerp_hex(P["borde"], self._acento, t * 0.65))
        except Exception:
            return
        if paso < total:
            self._flash_after = self.after(FRAME_MS, lambda: self._pulso_borde_60fps(paso + 1, total))
        else:
            self._flash_after = None


class PuntoPulso(ctk.CTkLabel):
    """Indicador '●' con respiración sinusoidal continua a 60 FPS (16 ms)."""

    def __init__(self, parent, color: str = P["primario"], **kw):
        super().__init__(parent, text="●", font=("Segoe UI", 14), text_color=P["texto_dim"], **kw)
        self._color = color
        self._on = False
        self._fase = 0.0
        self._after: str | None = None

    def iniciar(self, color: str | None = None):
        if color:
            self._color = color
        if self._after:
            try:
                self.after_cancel(self._after)
            except Exception:
                pass
            self._after = None
        self._on = True
        self._tick()

    def detener(self, color: str | None = None):
        self._on = False
        if self._after:
            try:
                self.after_cancel(self._after)
            except Exception:
                pass
            self._after = None
        if _vivo(self):
            self.configure(text_color=color or P["texto_dim"])

    def _tick(self):
        if not self._on or not _vivo(self):
            return
        self._fase = (self._fase + 0.14) % (2.0 * math.pi)
        onda = 0.5 + 0.5 * math.sin(self._fase)
        col = _lerp_hex(P["borde_fuerte"], self._color, onda)
        self.configure(text_color=col)
        self._after = self.after(FRAME_MS, self._tick)


class Sparkline(tk.Canvas):
    """Mini-gráfico de líneas con interpolación de muestras a 60 FPS (16 ms)."""

    def __init__(self, parent, ancho: int = 400, alto: int = 90, max_puntos: int = 40, **kw):
        super().__init__(parent, width=ancho, height=alto, bg=P["surface"],
                         highlightthickness=0, **kw)
        self.W, self.H = ancho, alto
        self.max_puntos = max_puntos
        self.series: dict[str, dict] = {}
        self._fase_halo = 0.0
        self._anim_after: str | None = None
        self._dibujar_rejilla()

    def agregar_serie(self, nombre: str, color: str, maximo: float | None = None):
        self.series[nombre] = {"color": color, "datos": [], "display": [], "max": maximo}

    def limpiar(self):
        for s in self.series.values():
            s["datos"].clear()
            s["display"].clear()
        self._redibujar()

    def push(self, nombre: str, valor: float):
        s = self.series.get(nombre)
        if s is None:
            return
        v = float(valor or 0.0)
        s["datos"].append(v)
        if len(s["datos"]) > self.max_puntos:
            s["datos"].pop(0)
        prev = s["display"][-1] if s["display"] else v
        s["display"].append(prev)
        if len(s["display"]) > self.max_puntos:
            s["display"].pop(0)
        self._iniciar_interpolacion_60fps()

    def _iniciar_interpolacion_60fps(self, paso: int = 0, total: int = 10):
        if not _vivo(self):
            return
        if self._anim_after and paso == 0:
            try:
                self.after_cancel(self._anim_after)
            except Exception:
                pass
        for s in self.series.values():
            if s["datos"] and s["display"]:
                meta = s["datos"][-1]
                act = s["display"][-1]
                s["display"][-1] = act + (meta - act) * 0.42
        self._fase_halo = (self._fase_halo + 0.35) % (2.0 * math.pi)
        self._redibujar()
        if paso < total:
            self._anim_after = self.after(FRAME_MS, lambda: self._iniciar_interpolacion_60fps(paso + 1, total))
        else:
            for s in self.series.values():
                if s["datos"] and s["display"]:
                    s["display"][-1] = s["datos"][-1]
            self._redibujar()
            self._anim_after = None

    def _dibujar_rejilla(self):
        for i in range(1, 4):
            y = self.H * i / 4
            self.create_line(0, y, self.W, y, fill=P["borde"], dash=(2, 4), tags="grid")

    def _redibujar(self):
        self.delete("serie")
        pad = 6
        radio_halo = 4.5 + 1.8 * math.sin(self._fase_halo)
        for s in self.series.values():
            datos = s["display"] if s.get("display") else s["datos"]
            if len(datos) < 2:
                continue
            tope = s["max"] or max(max(datos), 1e-9) * 1.15
            paso = (self.W - 2 * pad) / (self.max_puntos - 1)
            puntos = []
            for i, v in enumerate(datos):
                x = pad + i * paso
                y = self.H - pad - (min(v, tope) / tope) * (self.H - 2 * pad)
                puntos.extend((x, y))
            self.create_line(*puntos, fill=s["color"], width=2, smooth=True, tags="serie")
            lx, ly = puntos[-2], puntos[-1]
            col_halo = _lerp_hex(P["surface"], s["color"], 0.45)
            self.create_oval(lx - radio_halo, ly - radio_halo, lx + radio_halo, ly + radio_halo,
                             outline=col_halo, width=1, tags="serie")
            self.create_oval(lx - 3, ly - 3, lx + 3, ly + 3,
                             fill=s["color"], outline="", tags="serie")


# ---------------------------------------------------------------------------
# Ventanas emergentes y notificaciones a 60 FPS
# ---------------------------------------------------------------------------
def fade_in(ventana, duracion_ms: int = 224, pasos: int = 14):
    """Aparición gradual a 60 FPS (16 ms por frame) con curva ease-out."""
    try:
        ventana.attributes("-alpha", 0.0)
    except Exception:
        return

    def _paso(i: int):
        if not _vivo(ventana):
            return
        try:
            ventana.attributes("-alpha", min(1.0, _ease_out_quart(i / pasos)))
        except Exception:
            return
        if i < pasos:
            ventana.after(FRAME_MS, lambda: _paso(i + 1))

    _paso(1)


def estilizar_toplevel(ventana, master, titulo: str, ancho: int, alto: int, modal: bool = True):
    """Fondo oscuro, centrado sobre la ventana principal, modal y con fade-in a 60 FPS."""
    ventana.title(titulo)
    ventana.configure(fg_color=P["bg"])
    ventana.resizable(False, False)
    try:
        master.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - ancho) // 2
        y = master.winfo_rooty() + (master.winfo_height() - alto) // 2
        ventana.geometry(f"{ancho}x{alto}+{max(0, x)}+{max(0, y)}")
    except Exception:
        ventana.geometry(f"{ancho}x{alto}")
    try:
        ventana.transient(master)
    except Exception:
        pass
    fade_in(ventana)
    if modal:
        def _grab():
            if _vivo(ventana):
                try:
                    ventana.grab_set()
                    ventana.focus_force()
                except Exception:
                    pass
        ventana.after(90, _grab)


def toast(master, mensaje: str, tipo: str = "ok", duracion_ms: int = 3800):
    """Notificación flotante inferior con deslizamiento a 60 FPS (16 ms) y autocierre suave."""
    bg, fg = _BADGES.get(tipo, _BADGES["info"])
    iconos = {"ok": "✔", "warn": "⚠", "err": "✖", "info": "ℹ"}
    marco = ctk.CTkFrame(master, fg_color=bg, corner_radius=0,
                         border_width=1, border_color=fg)
    ctk.CTkLabel(marco, text=f"{iconos.get(tipo, 'ℹ')}  {mensaje}", font=F_SMALL,
                 text_color=fg, wraplength=520, justify="left").pack(padx=14, pady=8)

    def _deslizar_entrada(i: int, total: int = 16):
        if not _vivo(marco):
            return
        t = _ease_out_quart((i + 1) / total)
        rely = 1.05 - 0.09 * t
        marco.place(relx=0.5, rely=rely, anchor="s")
        marco.lift()
        if i + 1 < total:
            marco.after(FRAME_MS, lambda: _deslizar_entrada(i + 1, total))

    def _deslizar_salida(i: int = 0, total: int = 12):
        if not _vivo(marco):
            return
        t = (i + 1) / total
        rely = 0.96 + 0.10 * (t * t)
        marco.place(relx=0.5, rely=rely, anchor="s")
        if i + 1 < total:
            marco.after(FRAME_MS, lambda: _deslizar_salida(i + 1, total))
        else:
            if _vivo(marco):
                marco.destroy()

    _deslizar_entrada(0)
    marco.after(duracion_ms, lambda: _deslizar_salida(0) if _vivo(marco) else None)
    return marco
