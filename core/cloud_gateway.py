"""
core/cloud_gateway.py — Capa de Persistencia en Supabase (Fase 3 + Auditoría)
==============================================================================
Usa supabase-py 2.x (PostgREST via httpx) en lugar de requests puro.
Logging explícito en consola para depuración de errores HTTP.
"""

from __future__ import annotations

import base64
import hashlib
import http.client
import ssl
import traceback
import threading
import json as _json
import urllib.request
import urllib.error
from typing import Any

SUPABASE_URL  = "https://pvrfnvrxaxulcxacdino.supabase.co"
SUPABASE_HOST = "pvrfnvrxaxulcxacdino.supabase.co"
SUPABASE_KEY  = "sb_publishable_G7D4dhh3Q2LWzgRnzRRa9A_4ngZ5FiW"

# Pines SPKI SHA-256 reales de Google Trust Services / GlobalSign (sincronizados con Android network_security_config.xml)
SUPABASE_SPKI_PINS: frozenset[str] = frozenset({
    "kIdp6NNEd8wsugYyyIYFsi1ylMCED3hZbSR8ZFsa/A4=",  # GTS WE1 (intermedia Supabase)
    "yDu9og255NN5GEf+Bwa9rTrqFQ0EydZ0r1FCh9TdAW4=",  # GTS WR1 (intermedia Vercel)
    "mEflZT5enoR1FuXLgYYGqnVEoZvmf9c2bVBpiOjYQ0c=",  # GTS Root R4
    "hxqRlPTu1bMS/0DITB1SSu0vd4u/8l8TjPgfaAp63Gc=",  # GTS Root R1
    "K87oWBWM9UZfyddvDfoxL+8lpNyoUB2ptGtn0fv6G2Q=",  # GlobalSign Root CA
})

TABLA_TICKETS = "reportes_diagnostico"
TABLA_PADRON  = "padron_oficial"
TABLA_USUARIOS = "usuarios_app"

_CLIENT_LOCK = threading.Lock()
_PINNED_OPENER: urllib.request.OpenerDirector | None = None
_WARMUP_STARTED: bool = False


def _build_pinned_ssl_context() -> ssl.SSLContext:
    """Construye un SSLContext TLS >= 1.2 respaldado por certifi (inmune a CAs corporativas/MitM)."""
    cafile = None
    try:
        import certifi
        cafile = certifi.where()
    except Exception:
        cafile = None
    ctx = ssl.create_default_context(cafile=cafile) if cafile else ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def _compute_der_spki_pin(der_cert: bytes) -> str:
    """Calcula el hash SPKI SHA-256 en Base64 de un certificado X.509 DER."""
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization

    cert = x509.load_der_x509_certificate(der_cert)
    spki = cert.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return base64.b64encode(hashlib.sha256(spki).digest()).decode("ascii")


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Conexión HTTPS que exige coincidencia SPKI SHA-256 en la cadena verificada de Supabase."""

    def connect(self) -> None:
        super().connect()
        host_clean = (self.host or "").split(":", 1)[0].strip().lower()
        if host_clean != SUPABASE_HOST:
            return
        sock = self.sock
        if sock is None:
            raise ssl.SSLCertVerificationError("Socket TLS no disponible para validación SPKI.")
        get_chain = getattr(sock, "get_verified_chain", None)
        if callable(get_chain):
            chain = get_chain() or ()
            pins = {_compute_der_spki_pin(der) for der in chain}
            if SUPABASE_SPKI_PINS.isdisjoint(pins):
                try:
                    sock.close()
                except Exception:
                    pass
                raise ssl.SSLCertVerificationError(
                    "Pinning TLS SPKI rechazado: cadena de certificados no coincide con los pines autorizados."
                )


class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, context: ssl.SSLContext) -> None:
        super().__init__(context=context)

    def https_open(self, req: urllib.request.Request):
        return self.do_open(_PinnedHTTPSConnection, req, context=self._context)


def _get_pinned_opener() -> urllib.request.OpenerDirector:
    """Devuelve el opener HTTPS singleton con TLS 1.2+ certifi y SPKI pinning."""
    global _PINNED_OPENER
    if _PINNED_OPENER is None:
        with _CLIENT_LOCK:
            if _PINNED_OPENER is None:
                _PINNED_OPENER = urllib.request.build_opener(
                    _PinnedHTTPSHandler(_build_pinned_ssl_context())
                )
    return _PINNED_OPENER


class CloudGateway:
    """
    Todos los métodos son @staticmethod para mantener compatibilidad con el
    código existente en main.py (se invocan como CloudGateway.metodo()).
    """

    @staticmethod
    def warm_up_async() -> None:
        """Precalienta el contexto TLS con pinning SPKI en segundo plano sin bloquear la ventana."""
        global _WARMUP_STARTED
        if _WARMUP_STARTED or _PINNED_OPENER is not None:
            return
        _WARMUP_STARTED = True

        def _bg():
            try:
                _get_pinned_opener()
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    @staticmethod
    def _auth_otp_post(payload: dict) -> dict:
        """Invoca la Supabase Edge Function 'auth-otp' por HTTPS con pinning SPKI SHA-256."""
        url = f"{SUPABASE_URL.rstrip('/')}/functions/v1/auth-otp"
        data = _json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            },
        )
        try:
            with _get_pinned_opener().open(req, timeout=12) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                parsed = _json.loads(raw) if raw else {}
                parsed["_http_status"] = resp.status
                return parsed
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            try:
                parsed = _json.loads(raw) if raw else {}
            except Exception:
                parsed = {"ok": False, "error": f"HTTP {exc.code}"}
            parsed["_http_status"] = exc.code
            if exc.code == 404:
                parsed["_missing_function"] = True
            return parsed
        except Exception as exc:
            return {"ok": False, "error_conexion": f"Error de conexión segura con servidor: {str(exc)[:90]}"}

    @staticmethod
    def iniciar_login_otp(dni: str, correo: str, password: str, device_hash: str, device_label: str) -> dict:
        clean_dni = str(dni or "").strip()
        clean_correo = str(correo or "").strip()
        res = CloudGateway._auth_otp_post(
            {
                "action": "login_init",
                "dni": clean_dni,
                "correo": clean_correo,
                "password": str(password or ""),
                "device_hash": device_hash,
                "device_label": device_label,
                "plataforma": "desktop",
            }
        )
        if res.get("error_conexion"):
            return {"autenticado": False, "error_conexion": res["error_conexion"]}
        if res.get("ok") and res.get("requires_otp"):
            return {
                "autenticado": False,
                "requires_otp": True,
                "challenge_id": res.get("challenge_id"),
                "masked_email": res.get("masked_email"),
                "expires_in_sec": int(res.get("expires_in_sec") or 600),
                "resend_cooldown_sec": int(res.get("resend_cooldown_sec") or 60),
            }
        if res.get("ok") and res.get("session_token"):
            user = res.get("user") or {}
            return {
                "autenticado": True,
                "session_token": res["session_token"],
                "expires_at": res.get("expires_at"),
                "dni": user.get("dni") or clean_dni,
                "correo": user.get("correo") or clean_correo,
                "nickname": user.get("nickname") or "Operador",
                "avatar_data": user.get("avatar_data"),
                "rol": user.get("rol") or "operator",
            }
        return {"autenticado": False, "error": res.get("error") or "Credenciales incorrectas o cuenta inexistente."}

    @staticmethod
    def verificar_otp_login(challenge_id: str, code: str, device_hash: str, device_label: str) -> dict:
        return CloudGateway._auth_otp_post(
            {
                "action": "login_verify_otp",
                "challenge_id": challenge_id,
                "code": str(code or "").strip(),
                "device_hash": device_hash,
                "device_label": device_label,
                "plataforma": "desktop",
            }
        )

    @staticmethod
    def iniciar_registro_otp(
        dni: str, nickname: str, correo: str, password: str, device_hash: str, device_label: str
    ) -> dict:
        clean_dni = str(dni or "").strip()
        return CloudGateway._auth_otp_post(
            {
                "action": "register_init",
                "dni": clean_dni,
                "nickname": str(nickname or "").strip(),
                "correo": str(correo or "").strip(),
                "password": str(password or ""),
                "device_hash": device_hash,
                "device_label": device_label,
                "plataforma": "desktop",
            }
        )

    @staticmethod
    def verificar_otp_registro(challenge_id: str, code: str, device_hash: str, device_label: str) -> dict:
        return CloudGateway._auth_otp_post(
            {
                "action": "register_verify",
                "challenge_id": challenge_id,
                "code": str(code or "").strip(),
                "device_hash": device_hash,
                "device_label": device_label,
                "plataforma": "desktop",
            }
        )

    @staticmethod
    def validar_sesion_token(session_token: str, device_hash: str) -> dict:
        return CloudGateway._auth_otp_post(
            {
                "action": "session_validate",
                "session_token": session_token,
                "device_hash": device_hash,
            }
        )

    @staticmethod
    def revocar_sesion_token(session_token: str, device_hash: str) -> dict:
        return CloudGateway._auth_otp_post(
            {
                "action": "session_logout",
                "session_token": session_token,
                "device_hash": device_hash,
            }
        )

    @staticmethod
    def obtener_perfil_cuenta(session_token: str, device_hash: str) -> dict:
        return CloudGateway._auth_otp_post(
            {
                "action": "profile_get",
                "session_token": session_token,
                "device_hash": device_hash,
            }
        )

    @staticmethod
    def actualizar_avatar(session_token: str, device_hash: str, avatar_data: str | None) -> dict:
        return CloudGateway._auth_otp_post(
            {
                "action": "profile_update_avatar",
                "session_token": session_token,
                "device_hash": device_hash,
                "avatar_data": avatar_data,
            }
        )

    @staticmethod
    def listar_dispositivos_confiables(session_token: str, device_hash: str) -> dict:
        return CloudGateway._auth_otp_post(
            {
                "action": "devices_list",
                "session_token": session_token,
                "device_hash": device_hash,
            }
        )

    @staticmethod
    def revocar_dispositivo_confiable(
        session_token: str, device_hash: str, device_id: str
    ) -> dict:
        return CloudGateway._auth_otp_post(
            {
                "action": "device_revoke",
                "session_token": session_token,
                "device_hash": device_hash,
                "device_id": str(device_id or "").strip(),
            }
        )

    @staticmethod
    def iniciar_cambio_password(
        session_token: str,
        device_hash: str,
        device_label: str,
        dni: str,
        current_password: str,
        new_password: str,
    ) -> dict:
        return CloudGateway._auth_otp_post(
            {
                "action": "password_change_init",
                "session_token": session_token,
                "device_hash": device_hash,
                "device_label": device_label,
                "current_password": str(current_password or ""),
                "new_password": str(new_password or ""),
            }
        )

    @staticmethod
    def verificar_cambio_password(
        session_token: str, device_hash: str, challenge_id: str, code: str
    ) -> dict:
        return CloudGateway._auth_otp_post(
            {
                "action": "password_change_verify",
                "session_token": session_token,
                "device_hash": device_hash,
                "challenge_id": challenge_id,
                "code": str(code or "").strip(),
            }
        )

    @staticmethod
    def iniciar_recuperacion_password(
        dni: str, correo: str, device_hash: str, device_label: str
    ) -> dict:
        return CloudGateway._auth_otp_post(
            {
                "action": "password_reset_init",
                "dni": str(dni or "").strip(),
                "correo": str(correo or "").strip(),
                "device_hash": device_hash,
                "device_label": device_label,
            }
        )

    @staticmethod
    def verificar_recuperacion_password(
        dni: str, challenge_id: str, code: str, new_password: str, device_hash: str
    ) -> dict:
        return CloudGateway._auth_otp_post(
            {
                "action": "password_reset_verify",
                "challenge_id": challenge_id,
                "code": str(code or "").strip(),
                "new_password": str(new_password or ""),
                "device_hash": device_hash,
            }
        )

    @staticmethod
    def iniciar_eliminacion_cuenta(
        session_token: str,
        device_hash: str,
        device_label: str,
        dni: str,
        current_password: str,
        confirm_text: str,
    ) -> dict:
        return CloudGateway._auth_otp_post(
            {
                "action": "account_delete_init",
                "session_token": session_token,
                "device_hash": device_hash,
                "device_label": device_label,
                "current_password": str(current_password or ""),
                "confirm_text": str(confirm_text or "").strip(),
            }
        )

    @staticmethod
    def verificar_eliminacion_cuenta(
        session_token: str, device_hash: str, challenge_id: str, code: str
    ) -> dict:
        return CloudGateway._auth_otp_post(
            {
                "action": "account_delete_verify",
                "session_token": session_token,
                "device_hash": device_hash,
                "challenge_id": challenge_id,
                "code": str(code or "").strip(),
            }
        )

    @staticmethod
    def enviar_alerta_honeytoken(tipo: str, detalle: str) -> bool:
        """Envía una alerta silenciosa de Honeytoken vía Edge Function auth-otp."""
        res = CloudGateway._auth_otp_post(
            {
                "action": "honey_alert",
                "tipo": str(tipo or "ALERTA")[:80],
                "detalle": str(detalle or "")[:300],
            }
        )
        return bool(res.get("ok"))

    @staticmethod
    def listar_alertas_honeytoken(limite: int = 15) -> list[dict[str, Any]]:
        """Consulta alertas Honeytoken exclusivamente con sesión activa verificada en servidor."""
        from core.security import load_session_token

        sess = load_session_token()
        if not sess:
            return []
        tok, dev_hash = sess
        res = CloudGateway._auth_otp_post(
            {
                "action": "honeytokens_list",
                "session_token": tok,
                "device_hash": dev_hash,
                "limit": int(limite),
            }
        )
        if res.get("ok") and isinstance(res.get("alerts"), list):
            return list(res["alerts"])
        return []

    _share_tokens: dict[str, str] = {}

    @staticmethod
    def obtener_share_token(ticket_id: str) -> str:
        return CloudGateway._share_tokens.get(str(ticket_id or "").strip(), "")

    @staticmethod
    def rotar_share_token(ticket_id: str, ttl_hours: int = 72) -> dict:
        """Rota e invalida de inmediato el share_token (#st=) de un ticket propio en servidor."""
        from core.security import load_session_token

        sess = load_session_token()
        if not sess:
            return {"ok": False, "error": "Sesión activa requerida."}
        tok, dev_hash = sess
        tid = str(ticket_id or "").strip()
        res = CloudGateway._auth_otp_post(
            {
                "action": "ticket_rotate_share_token",
                "session_token": tok,
                "device_hash": dev_hash,
                "ticket_id": tid,
                "ttl_hours": int(ttl_hours),
            }
        )
        if res.get("ok") and res.get("share_token"):
            CloudGateway._share_tokens[tid] = str(res["share_token"]).strip()
        return res

    @staticmethod
    def subir_ticket(ticket_id: str, dni: str, hw: dict, diag: dict) -> bool:
        """Envía un ticket validado por sesión activa a través de auth-otp (sin acceso anon directo)."""
        from core.hardware import construir_resumen_para_bd
        from core.security import load_session_token

        sess = load_session_token()
        if not sess:
            print("[CloudGateway.subir_ticket] Sesión activa requerida para subir tickets.")
            return False
        tok, dev_hash = sess
        payload = construir_resumen_para_bd(ticket_id, hw, diag, owner_dni=dni)
        res = CloudGateway._auth_otp_post(
            {
                "action": "tickets_upsert",
                "session_token": tok,
                "device_hash": dev_hash,
                "ticket": payload,
            }
        )
        if res.get("ok"):
            st = str(res.get("share_token") or "").strip()
            if st:
                CloudGateway._share_tokens[str(ticket_id).strip()] = st
            print(f"[CloudGateway] [OK] Ticket {ticket_id} sincronizado de forma segura.")
            return True
        print(f"[CloudGateway.subir_ticket] [ERROR] {res.get('error') or res.get('error_conexion')}")
        return False

    @staticmethod
    def listar_tickets_usuario(dni: str | None, limite: int = 120) -> list[dict[str, Any]]:
        """Lista exclusivamente los tickets del operador autenticado (verificado en servidor por sesión)."""
        from core.security import load_session_token

        sess = load_session_token()
        if not sess:
            return []
        tok, dev_hash = sess
        res = CloudGateway._auth_otp_post(
            {
                "action": "tickets_list",
                "session_token": tok,
                "device_hash": dev_hash,
                "limit": int(limite),
            }
        )
        if res.get("ok") and isinstance(res.get("tickets"), list):
            return list(res["tickets"])
        return []

    @staticmethod
    def subir_ticket_legacy(ticket_id: str, dni: str, hw: dict, diag: dict) -> bool:
        """Alias para compatibilidad con código anterior."""
        return CloudGateway.subir_ticket(ticket_id, dni, hw, diag)

    @staticmethod
    def subir_sugerencia(ticket_id: str, sugerencia_texto: str) -> bool:
        """Persiste una sugerencia técnica validada por sesión activa a través de auth-otp."""
        from core.security import load_session_token

        sess = load_session_token()
        if not sess:
            return False
        tok, dev_hash = sess
        res = CloudGateway._auth_otp_post(
            {
                "action": "suggestion_save",
                "session_token": tok,
                "device_hash": dev_hash,
                "id_ticket": str(ticket_id),
                "sugerencia": str(sugerencia_texto),
            }
        )
        return bool(res.get("ok"))
