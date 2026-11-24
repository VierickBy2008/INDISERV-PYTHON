"""
core/security.py — Criptografía de Contraseñas, Rate-Limiting y Motor de Honeytokens
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import platform
import secrets
import tempfile
import threading
import time
from typing import Any

HASH_PREFIX = "indiserv_v1$"
HASH_SALT_NAMESPACE = "INDISERV_SALT_2026"

HONEY_DNIS = {"00000000", "99999999", "12345678", "87654321", "11111111", "admin", "root"}
HONEY_EMAILS = {
    "admin@indiserv.pe",
    "root@indiserv.pe",
    "soporte@indiserv.pe",
    "security@indiserv.pe",
    " administrator@indiserv.pe",
    "admin@unmsm.edu.pe",
}
HONEY_TICKETS = {
    "0000-ADMIN-ROOT",
    "TKT-ADMIN-MASTER",
    "TKT-BACKUP-DB",
    "9999-TICKET-0000",
}
CANARY_ENV_TOKENS = {
    "ag_canary_9f8e7d6c5b4a3f2e1d0c",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.canary_trap_indiserv",
}

_failed_attempts: list[float] = []
_LOCKOUT_WINDOW_SEC = 300.0
_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_DURATION_SEC = 60.0
_lockout_until: float = 0.0
_AUTH_GUARD_PATH = os.path.join(tempfile.gettempdir(), ".indiserv_auth_guard_v1.json")


def _load_auth_guard_state() -> None:
    """Carga el estado de bloqueo antibruteforce desde disco para resistir reinicios del proceso."""
    global _lockout_until
    try:
        if not os.path.exists(_AUTH_GUARD_PATH):
            return
        with open(_AUTH_GUARD_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data.get("attempts"), list):
            _failed_attempts[:] = [float(x) for x in data["attempts"] if isinstance(x, (int, float))]
        if isinstance(data.get("lockout_until"), (int, float)):
            _lockout_until = float(data["lockout_until"])
    except Exception:
        pass


def _save_auth_guard_state() -> None:
    """Persiste el estado de bloqueo antibruteforce en disco."""
    try:
        with open(_AUTH_GUARD_PATH, "w", encoding="utf-8") as fh:
            json.dump({"attempts": _failed_attempts, "lockout_until": _lockout_until}, fh)
    except Exception:
        pass


_load_auth_guard_state()


def hash_password(dni: str, password: str) -> str:
    """Genera un hash SHA-256 determinista con sal vinculada al DNI (compatible con WebCrypto en JS)."""
    clean_dni = str(dni or "").strip()
    clean_pass = str(password or "")
    if clean_pass.startswith(HASH_PREFIX):
        return clean_pass
    raw = f"{HASH_SALT_NAMESPACE}::{clean_dni}::{clean_pass}".encode("utf-8")
    return f"{HASH_PREFIX}{hashlib.sha256(raw).hexdigest()}"


def verify_password(dni: str, plain_password: str, stored_hash: str) -> tuple[bool, bool]:
    """
    Verifica la contraseña contra stored_hash.
    Retorna (es_valida, requiere_migracion_hash).
    """
    if not stored_hash or not plain_password:
        return False, False
    expected = hash_password(dni, plain_password)
    if stored_hash.startswith(HASH_PREFIX):
        return secrets.compare_digest(stored_hash, expected), False
    is_legacy_match = secrets.compare_digest(stored_hash, plain_password)
    return is_legacy_match, is_legacy_match


def generate_secure_ticket_id(dni_or_prefix: str | None, tag: str = "TICKET") -> str:
    """Genera un ID de ticket con 32 bits de entropía criptográfica (4.29 mil millones de combinaciones)."""
    raw = str(dni_or_prefix or "").strip()
    pref = raw[:4] if len(raw) >= 4 else "USER"
    token = secrets.token_hex(4).upper()
    return f"{pref}-{tag}-{token}"


def check_login_rate_limit() -> tuple[bool, int]:
    """Verifica si el cliente está bloqueado temporalmente por exceso de intentos fallidos."""
    _load_auth_guard_state()
    now = time.time()
    if now < _lockout_until:
        return False, max(1, int(_lockout_until - now))
    return True, 0


def record_failed_login(dni: str, correo: str) -> tuple[bool, int]:
    """Registra un intento fallido y activa bloqueo de 60 s al llegar a 5 fallos."""
    global _lockout_until
    _load_auth_guard_state()
    now = time.time()
    _failed_attempts[:] = [t for t in _failed_attempts if now - t < _LOCKOUT_WINDOW_SEC]
    _failed_attempts.append(now)
    if len(_failed_attempts) >= _MAX_FAILED_ATTEMPTS:
        _lockout_until = now + _LOCKOUT_DURATION_SEC
        _failed_attempts.clear()
        _save_auth_guard_state()
        trigger_honeytoken_alert(
            tipo="FUERZA_BRUTA_LOGIN",
            detalle=f"5 intentos fallidos consecutivos sobre DNI='{dni}' correo='{correo}'",
        )
        return True, int(_LOCKOUT_DURATION_SEC)
    _save_auth_guard_state()
    return False, 0


def reset_login_rate_limit() -> None:
    """Limpia el contador de fallos tras un inicio de sesión exitoso."""
    global _lockout_until
    _failed_attempts.clear()
    _lockout_until = 0.0
    _save_auth_guard_state()


def is_honey_credential(dni: str, correo: str = "") -> bool:
    """Detecta si el DNI o correo ingresado pertenece a una cuenta señuelo (Honeytoken D3-DUC)."""
    d = str(dni or "").strip().lower()
    c = str(correo or "").strip().lower()
    if d in HONEY_DNIS or c in HONEY_EMAILS:
        return True
    if any(tok in d or tok in c for tok in ("canary", "honeypot", "' or ", "1=1", "union select")):
        return True
    return False


def is_honey_ticket(ticket_id: str) -> bool:
    """Detecta si un ID de ticket consultado es un ticket trampa o contiene payload de inyección."""
    t = str(ticket_id or "").strip().upper()
    if t in HONEY_TICKETS:
        return True
    low = t.lower()
    if any(p in low for p in ("' or ", "1=1", "union select", "<script", "../", "admin-root")):
        return True
    return False


def trigger_honeytoken_alert(tipo: str, detalle: str) -> str:
    """
    Envía una alerta silenciosa de Honeytoken a Supabase ('sugerencias_locales')
    en un hilo secundario para no revelar al intruso que activó una trampa.
    """
    alert_id = f"HONEY-{secrets.token_hex(4).upper()}"
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    host_info = f"{platform.system()} {platform.release()} ({platform.node()})"
    mensaje = f"[ALERTA-HONEYTOKEN] {tipo} | {detalle} | Host: {host_info} | Fecha: {ts}"

    def _send():
        try:
            from core.cloud_gateway import CloudGateway
            CloudGateway.subir_sugerencia(alert_id, mensaje)
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()
    return alert_id
