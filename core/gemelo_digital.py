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


def abrir_gemelo_digital(
    id_ticket: str,
    root_widget=None,
    share_token: str | None = None,
    auto_copy: bool = False,
) -> str:
    """
    Construye el enlace al Gemelo Digital 3D (con share_token criptográfico de 128 bits con TTL),
    lo abre en el navegador predeterminado del sistema y solo copia al portapapeles si auto_copy=True.
    """
    ticket_sanitizado = quote(str(id_ticket).strip())
    st_clean = quote(str(share_token or "").strip())

    enlace_completo = f"{WEB_VIEWER_URL}/?ticket={ticket_sanitizado}"
    if st_clean:
        # Hash fragment (#st=...) evita que el share_token viaje al servidor en logs HTTP/Referer
        enlace_completo += f"#st={st_clean}"

    print(f"\n[Gemelo Digital] Enlace Seguro Generado para ticket: {ticket_sanitizado}")

    try:
        webbrowser.open(enlace_completo)
    except Exception as exc:
        print(f"[Gemelo Digital] Error al abrir el navegador: {exc}")

    if auto_copy:
        copiado = False
        if root_widget is not None:
            try:
                root_widget.clipboard_clear()
                root_widget.clipboard_append(enlace_completo)
                root_widget.update()
                copiado = True
            except Exception as exc:
                print(f"[Gemelo Digital] Error copiando con clipboard de GUI: {exc}")

        if not copiado:
            try:
                import pyperclip
                pyperclip.copy(enlace_completo)
            except Exception:
                pass

    return enlace_completo
