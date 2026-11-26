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


def abrir_gemelo_digital(id_ticket: str, root_widget=None, share_token: str | None = None) -> str:
    """
    Construye el enlace al Gemelo Digital 3D (con share_token criptográfico de 128 bits),
    lo abre en el navegador predeterminado del sistema y lo copia al portapapeles.
    """
    ticket_sanitizado = quote(str(id_ticket).strip())
    st_clean = quote(str(share_token or "").strip())

    enlace_completo = f"{WEB_VIEWER_URL}/?ticket={ticket_sanitizado}"
    if st_clean:
        enlace_completo += f"&st={st_clean}"

    print(f"\n[Gemelo Digital] Enlace Público Generado: {enlace_completo}")

    try:
        webbrowser.open(enlace_completo)
    except Exception as exc:
        print(f"[Gemelo Digital] Error al abrir el navegador: {exc}")

    copiado = False

    if root_widget is not None:
        try:
            root_widget.clipboard_clear()
            root_widget.clipboard_append(enlace_completo)
            root_widget.update()
            copiado = True
            print("[Gemelo Digital] Enlace copiado al portapapeles (GUI).")
        except Exception as exc:
            print(f"[Gemelo Digital] Error copiando con clipboard de GUI: {exc}")

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
