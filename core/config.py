"""
core/config.py — Configuración Global de IndiServ Analytica
============================================================
Carga variables de entorno desde .env (si existe) y expone
constantes sanitizadas para uso en todo el proyecto.

Uso:
    from core.config import WEB_VIEWER_URL
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Carga automática del archivo .env del proyecto (si python-dotenv disponible)
# ---------------------------------------------------------------------------
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_ENV_FILE, override=False)  # No sobreescribe vars ya definidas en el entorno
except ImportError:
    # python-dotenv no instalado: parseo manual mínimo del .env
    if _ENV_FILE.exists():
        with open(_ENV_FILE, encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _, _v = _line.partition("=")
                    _k = _k.strip()
                    _v = _v.strip().strip('"').strip("'")
                    if _k and _k not in os.environ:
                        os.environ[_k] = _v

# ---------------------------------------------------------------------------
# WEB_VIEWER_URL
# Valor de producción por defecto: NUNCA localhost.
# .rstrip('/') elimina barra final para evitar doble '//' al concatenar rutas.
# ---------------------------------------------------------------------------
_DEFAULT_WEB_VIEWER_URL = "https://indiserv-web3d.vercel.app"

WEB_VIEWER_URL: str = os.getenv(
    "WEB_VIEWER_URL", _DEFAULT_WEB_VIEWER_URL
).rstrip("/")

# Guardia de seguridad: si por algún motivo el entorno definió localhost, se
# fuerza el fallback a producción para evitar enlaces rotos en clientes.
if "localhost" in WEB_VIEWER_URL or "127.0.0.1" in WEB_VIEWER_URL:
    import warnings
    warnings.warn(
        f"[config] WEB_VIEWER_URL apunta a '{WEB_VIEWER_URL}' (local). "
        f"Se reemplaza por la URL de producción: {_DEFAULT_WEB_VIEWER_URL}",
        stacklevel=1,
    )
    WEB_VIEWER_URL = _DEFAULT_WEB_VIEWER_URL
