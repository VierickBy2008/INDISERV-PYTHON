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

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_ENV_FILE, override=False)
except ImportError:
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

_DEFAULT_WEB_VIEWER_URL = "https://indiserv-web3d.vercel.app"

WEB_VIEWER_URL: str = os.getenv(
    "WEB_VIEWER_URL", _DEFAULT_WEB_VIEWER_URL
).rstrip("/")

if "localhost" in WEB_VIEWER_URL or "127.0.0.1" in WEB_VIEWER_URL:
    import warnings
    warnings.warn(
        f"[config] WEB_VIEWER_URL apunta a '{WEB_VIEWER_URL}' (local). "
        f"Se reemplaza por la URL de producción: {_DEFAULT_WEB_VIEWER_URL}",
        stacklevel=1,
    )
    WEB_VIEWER_URL = _DEFAULT_WEB_VIEWER_URL

for _canary_var in ("INDISERV_ADMIN_MASTER_KEY", "SUPABASE_SERVICE_ROLE_CANARY"):
    _val = os.getenv(_canary_var, "").strip()
    if _val and ("canary" in _val.lower() or _val.startswith("ag_canary_")):
        try:
            from core.security import trigger_honeytoken_alert
            trigger_honeytoken_alert("LLAVE_ENV_CANARIO_USADA", f"Variable señuelo {_canary_var} cargada en entorno")
        except Exception:
            pass
