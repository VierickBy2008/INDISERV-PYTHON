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

from urllib.parse import urlparse

_DEFAULT_WEB_VIEWER_URL = "https://indiserv-web3d.vercel.app"
_ALLOWED_WEB_VIEWER_HOSTS = frozenset({"indiserv-web3d.vercel.app"})


def _sanitizar_web_viewer_url(raw_url: str | None) -> str:
    """Exige esquema HTTPS y host exacto en lista blanca para prevenir redirección y fuga de #st=."""
    cand = str(raw_url or "").strip().rstrip("/")
    if not cand:
        return _DEFAULT_WEB_VIEWER_URL
    try:
        parsed = urlparse(cand)
        host = (parsed.hostname or "").lower()
        if (
            parsed.scheme != "https"
            or host not in _ALLOWED_WEB_VIEWER_HOSTS
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.port not in (None, 443)
        ):
            raise ValueError("origen no permitido")
        clean_path = parsed.path.rstrip("/")
        return f"https://{host}{clean_path}"
    except Exception:
        import warnings
        warnings.warn(
            f"[config] WEB_VIEWER_URL inválida o fuera de lista blanca ('{cand}'). "
            f"Se usa el origen oficial: {_DEFAULT_WEB_VIEWER_URL}",
            stacklevel=2,
        )
        return _DEFAULT_WEB_VIEWER_URL


WEB_VIEWER_URL: str = _sanitizar_web_viewer_url(
    os.getenv("WEB_VIEWER_URL", _DEFAULT_WEB_VIEWER_URL)
)

for _canary_var in ("INDISERV_ADMIN_MASTER_KEY", "SUPABASE_SERVICE_ROLE_CANARY"):
    _val = os.getenv(_canary_var, "").strip()
    if _val and ("canary" in _val.lower() or _val.startswith("ag_canary_")):
        try:
            from core.security import trigger_honeytoken_alert
            trigger_honeytoken_alert("LLAVE_ENV_CANARIO_USADA", f"Variable señuelo {_canary_var} cargada en entorno")
        except Exception:
            pass
