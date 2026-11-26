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
import sys
import tempfile
import threading
import time
import uuid
from typing import Any

HASH_PREFIX = "indiserv_v1$"
HASH_SALT_NAMESPACE = "INDISERV_SALT_2026"

HONEY_DNIS = {"00000000", "99999999", "12345678", "87654321", "11111111", "admin", "root"}
HONEY_EMAILS = {
    "admin@indiserv.pe",
    "root@indiserv.pe",
    "soporte@indiserv.pe",
    "security@indiserv.pe",
    "administrator@indiserv.pe",
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
    """Genera un ID de ticket con 64 bits de entropía criptográfica (1.84 × 10^19 combinaciones)."""
    raw = str(dni_or_prefix or "").strip()
    pref = raw[:4] if len(raw) >= 4 else "USER"
    token = secrets.token_hex(8).upper()
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
            CloudGateway.enviar_alerta_honeytoken(tipo, mensaje)
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()
    return alert_id


_SESSION_FILE_PATH = os.path.join(os.path.expanduser("~"), ".indiserv_session_v1.json")


def _dpapi_protect(raw_bytes: bytes) -> bytes | None:
    """Cifra bytes usando Windows DPAPI ligado al usuario local actual."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        buf = ctypes.create_string_buffer(raw_bytes, len(raw_bytes))
        blob_in = DATA_BLOB(len(raw_bytes), buf)
        blob_out = DATA_BLOB()
        if not crypt32.CryptProtectData(
            ctypes.byref(blob_in), "IndiServSession", None, None, None, 0x01, ctypes.byref(blob_out)
        ):
            return None
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(blob_out.pbData)
    except Exception:
        return None


def _dpapi_unprotect(enc_bytes: bytes) -> bytes | None:
    """Descifra bytes protegidos con Windows DPAPI para el usuario local actual."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        buf = ctypes.create_string_buffer(enc_bytes, len(enc_bytes))
        blob_in = DATA_BLOB(len(enc_bytes), buf)
        blob_out = DATA_BLOB()
        if not crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0x01, ctypes.byref(blob_out)
        ):
            return None
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(blob_out.pbData)
    except Exception:
        return None


def _read_machine_guid() -> str:
    """Obtiene un identificador estable del sistema operativo sin requerir privilegios elevados."""
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                val, _ = winreg.QueryValueEx(key, "MachineGuid")
                if val:
                    return str(val).strip()
        except Exception:
            pass
    else:
        for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                if os.path.exists(path):
                    val = open(path, "r", encoding="utf-8").read().strip()
                    if val:
                        return val
            except Exception:
                pass
    return f"node-{uuid.getnode()}"


def get_device_fingerprint() -> tuple[str, str]:
    """Retorna (device_hash_sha256, device_label) estable para vincular sesiones y dispositivos confiables."""
    guid = _read_machine_guid()
    host = platform.node() or "host"
    arch = platform.machine() or "x64"
    os_name = platform.system() or "Desktop"
    raw = f"INDISERV_DEV_V1::{os_name}::{arch}::{guid}".encode("utf-8")
    device_hash = hashlib.sha256(raw).hexdigest()
    device_label = f"{os_name} · {host[:36]}"
    return device_hash, device_label


def _posix_aesgcm_encrypt(raw_bytes: bytes) -> dict | None:
    """Cifra la sesión con AES-256-GCM derivado de machine-id + UID + sal aleatoria en POSIX."""
    try:
        import base64
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.hashes import SHA256
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

        salt = secrets.token_bytes(16)
        nonce = secrets.token_bytes(12)
        uid = os.getuid() if hasattr(os, "getuid") else 0
        ikm = f"INDISERV_POSIX_SESS_V1::{_read_machine_guid()}::{uid}".encode("utf-8")
        key = PBKDF2HMAC(algorithm=SHA256(), length=32, salt=salt, iterations=200_000).derive(ikm)
        ct = AESGCM(key).encrypt(nonce, raw_bytes, b"indiserv-session-v1")
        return {
            "aesgcm_v1": {
                "salt": base64.b64encode(salt).decode("ascii"),
                "nonce": base64.b64encode(nonce).decode("ascii"),
                "ct": base64.b64encode(ct).decode("ascii"),
            }
        }
    except Exception:
        return None


def _posix_aesgcm_decrypt(box: dict) -> bytes | None:
    """Descifra una sesión cifrada con _posix_aesgcm_encrypt en el mismo host y usuario."""
    try:
        import base64
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.hashes import SHA256
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

        salt = base64.b64decode(str(box["salt"]))
        nonce = base64.b64decode(str(box["nonce"]))
        ct = base64.b64decode(str(box["ct"]))
        uid = os.getuid() if hasattr(os, "getuid") else 0
        ikm = f"INDISERV_POSIX_SESS_V1::{_read_machine_guid()}::{uid}".encode("utf-8")
        key = PBKDF2HMAC(algorithm=SHA256(), length=32, salt=salt, iterations=200_000).derive(ikm)
        return AESGCM(key).decrypt(nonce, ct, b"indiserv-session-v1")
    except Exception:
        return None


def _os_keyring_save(raw_str: str) -> bool:
    """Guarda el secreto de sesión en macOS Keychain o Linux Secret Service sin exponerlo en argv."""
    import subprocess

    if sys.platform == "darwin" and os.path.isfile("/usr/bin/security"):
        try:
            # 'security -i' lee comandos desde stdin (nunca aparece la contraseña en ps/argv)
            escaped = raw_str.replace("\\", "\\\\").replace('"', '\\"')
            cmd_line = (
                'add-generic-password -U -a "indiserv_session" '
                f'-s "com.indiserv.analytica.session" -w "{escaped}"\n'
            )
            res = subprocess.run(
                ["/usr/bin/security", "-i"],
                input=cmd_line,
                text=True,
                capture_output=True,
                timeout=4,
            )
            return res.returncode == 0
        except Exception:
            return False
    if sys.platform.startswith("linux") and os.path.isfile("/usr/bin/secret-tool"):
        try:
            res = subprocess.run(
                [
                    "/usr/bin/secret-tool",
                    "store",
                    "--label=IndiServ Analytica Session",
                    "service",
                    "com.indiserv.analytica.session",
                    "account",
                    "indiserv_session",
                ],
                input=raw_str,
                text=True,
                capture_output=True,
                timeout=4,
            )
            return res.returncode == 0
        except Exception:
            return False
    return False


def _os_keyring_load() -> str | None:
    """Recupera el secreto de sesión desde macOS Keychain o Linux Secret Service."""
    import subprocess

    if sys.platform == "darwin" and os.path.isfile("/usr/bin/security"):
        try:
            res = subprocess.run(
                [
                    "/usr/bin/security",
                    "find-generic-password",
                    "-a",
                    "indiserv_session",
                    "-s",
                    "com.indiserv.analytica.session",
                    "-w",
                ],
                text=True,
                capture_output=True,
                timeout=4,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            return None
    if sys.platform.startswith("linux") and os.path.isfile("/usr/bin/secret-tool"):
        try:
            res = subprocess.run(
                [
                    "/usr/bin/secret-tool",
                    "lookup",
                    "service",
                    "com.indiserv.analytica.session",
                    "account",
                    "indiserv_session",
                ],
                text=True,
                capture_output=True,
                timeout=4,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            return None
    return None


def _os_keyring_delete() -> None:
    """Elimina el secreto de sesión del llavero nativo del SO en macOS/Linux."""
    import subprocess

    if sys.platform == "darwin" and os.path.isfile("/usr/bin/security"):
        try:
            subprocess.run(
                [
                    "/usr/bin/security",
                    "delete-generic-password",
                    "-a",
                    "indiserv_session",
                    "-s",
                    "com.indiserv.analytica.session",
                ],
                capture_output=True,
                timeout=4,
            )
        except Exception:
            pass
    elif sys.platform.startswith("linux") and os.path.isfile("/usr/bin/secret-tool"):
        try:
            subprocess.run(
                [
                    "/usr/bin/secret-tool",
                    "clear",
                    "service",
                    "com.indiserv.analytica.session",
                    "account",
                    "indiserv_session",
                ],
                capture_output=True,
                timeout=4,
            )
        except Exception:
            pass


def save_session_token(token: str, device_hash: str, path: str | None = None) -> None:
    """Persiste el token opaco cifrado: Windows DPAPI, macOS Keychain, Linux Secret Service o AES-256-GCM."""
    import base64

    target = path or _SESSION_FILE_PATH
    try:
        raw_str = json.dumps({"token": str(token), "device_hash": str(device_hash)})
        raw = raw_str.encode("utf-8")

        if sys.platform == "win32":
            enc = _dpapi_protect(raw)
            if enc is None:
                return
            payload = {"dpapi": base64.b64encode(enc).decode("ascii")}
        else:
            if path is None and _os_keyring_save(raw_str):
                # Limpiar archivo en disco si se guardó en el llavero nativo del SO
                try:
                    if os.path.exists(target):
                        os.remove(target)
                except Exception:
                    pass
                return
            payload = _posix_aesgcm_encrypt(raw)
            if payload is None:
                return

        if os.name != "nt":
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
            os.chmod(target, 0o600)
        else:
            with open(target, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
    except Exception:
        pass


def load_session_token(path: str | None = None) -> tuple[str, str] | None:
    """Lee el token cifrado (DPAPI en Windows, Keychain/Secret Service o AES-256-GCM en POSIX)."""
    import base64

    target = path or _SESSION_FILE_PATH
    try:
        if sys.platform != "win32" and path is None:
            kr = _os_keyring_load()
            if kr:
                data = json.loads(kr)
                tok = str(data.get("token") or "").strip()
                dh = str(data.get("device_hash") or "").strip()
                if tok and dh:
                    return tok, dh

        if not os.path.exists(target):
            return None
        with open(target, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and data.get("dpapi"):
            dec = _dpapi_unprotect(base64.b64decode(str(data["dpapi"])))
            if not dec:
                return None
            data = json.loads(dec.decode("utf-8"))
        elif isinstance(data, dict) and isinstance(data.get("aesgcm_v1"), dict):
            dec = _posix_aesgcm_decrypt(data["aesgcm_v1"])
            if not dec:
                return None
            data = json.loads(dec.decode("utf-8"))
        else:
            # Rechazar archivos en texto plano heredados y limpiarlos
            try:
                os.remove(target)
            except Exception:
                pass
            return None

        tok = str(data.get("token") or "").strip()
        dh = str(data.get("device_hash") or "").strip()
        if tok and dh:
            return tok, dh
    except Exception:
        pass
    return None


def clear_session_token(path: str | None = None) -> None:
    """Elimina el token local de sesión tanto del llavero del SO como del disco."""
    target = path or _SESSION_FILE_PATH
    if sys.platform != "win32" and path is None:
        _os_keyring_delete()
    try:
        if os.path.exists(target):
            os.remove(target)
    except Exception:
        pass
