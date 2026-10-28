"""
core/gemelo_digital.py — Lanzador del Gemelo Digital 3D
=========================================================
Centraliza la lógica de construcción de URL, apertura del
navegador y copiado al portapapeles para el visor web en Vercel.

Uso:
    from core.gemelo_digital import abrir_gemelo_digital
    enlace = abrir_gemelo_digital(id_ticket, root_widget=self)
"""

from __future__ import annotations

import os
import webbrowser
from urllib.parse import quote

from core.config import WEB_VIEWER_URL


def abrir_gemelo_digital(id_ticket: str, root_widget=None) -> str:
    """
    Construye el enlace público al Gemelo Digital 3D, lo abre en el
    navegador predeterminado del sistema y lo copia al portapapeles.

    Parámetros
    ----------
    id_ticket   : str  — ID del ticket tal como fue insertado en Supabase.
                         Se aplica .strip() para garantizar consistencia exacta.
    root_widget : obj  — Widget raíz de CustomTkinter/Tkinter (ej. instancia
                         de CTk). Necesario para usar el portapapeles nativo
                         de la GUI. Si es None, se intenta con pyperclip.

    Retorna
    -------
    str — La URL completa generada (útil para mostrarla en la UI).
    """
    # Sanitizar ticket: eliminar espacios que podrían romper la búsqueda en BD
    ticket_sanitizado = quote(str(id_ticket).strip())

    # URL de producción (nunca localhost) + parámetro de ticket URL-encoded
    enlace_completo = f"{WEB_VIEWER_URL}/?ticket={ticket_sanitizado}"

    print(f"\n[Gemelo Digital] Enlace Público Generado: {enlace_completo}")

    # ── 1. Abrir en el navegador predeterminado del sistema ─────────────
    try:
        webbrowser.open(enlace_completo)
    except Exception as exc:
        print(f"[Gemelo Digital] Error al abrir el navegador: {exc}")

    # ── 2. Copiar al portapapeles ────────────────────────────────────────
    copiado = False

    # Intento primario: portapapeles nativo de la GUI (Tkinter/CTk)
    if root_widget is not None:
        try:
            root_widget.clipboard_clear()
            root_widget.clipboard_append(enlace_completo)
            root_widget.update()
            copiado = True
            print("[Gemelo Digital] Enlace copiado al portapapeles (GUI).")
        except Exception as exc:
            print(f"[Gemelo Digital] Error copiando con clipboard de GUI: {exc}")

    # Intento secundario: pyperclip (si está disponible)
    if not copiado:
        try:
            import pyperclip
            pyperclip.copy(enlace_completo)
            copiado = True
            print("[Gemelo Digital] Enlace copiado al portapapeles (pyperclip).")
        except ImportError:
            print("[Gemelo Digital] pyperclip no disponible; portapapeles no actualizado.")
        except Exception as exc:
            print(f"[Gemelo Digital] Error copiando con pyperclip: {exc}")

    return enlace_completo
