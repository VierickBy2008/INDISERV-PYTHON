"""
core/cloud_gateway.py — Capa de Persistencia en Supabase (Fase 3 + Auditoría)
==============================================================================
Usa supabase-py 2.x (PostgREST via httpx) en lugar de requests puro.
Logging explícito en consola para depuración de errores HTTP.
"""

from __future__ import annotations

import traceback
import threading
import json as _json
import urllib.request
import urllib.error
from typing import Any

SUPABASE_URL  = "https://pvrfnvrxaxulcxacdino.supabase.co"
SUPABASE_KEY  = "sb_publishable_G7D4dhh3Q2LWzgRnzRRa9A_4ngZ5FiW"

TABLA_TICKETS = "reportes_diagnostico"
TABLA_PADRON  = "padron_oficial"
TABLA_USUARIOS = "usuarios_app"

_CLIENT_LOCK = threading.Lock()
_CLIENT_INSTANCE: Any = None
_WARMUP_STARTED: bool = False


def _get_client() -> Any:
    """Devuelve una instancia singleton thread-safe del cliente Supabase (importación diferida)."""
    global _CLIENT_INSTANCE
    if _CLIENT_INSTANCE is None:
        with _CLIENT_LOCK:
            if _CLIENT_INSTANCE is None:
                from supabase import create_client

                _CLIENT_INSTANCE = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _CLIENT_INSTANCE


class CloudGateway:
    """
    Todos los métodos son @staticmethod para mantener compatibilidad con el
    código existente en main.py (se invocan como CloudGateway.metodo()).
    """

    @staticmethod
    def warm_up_async() -> None:
        """Precarga supabase-py en segundo plano sin bloquear el arranque de la ventana."""
        global _WARMUP_STARTED
        if _WARMUP_STARTED or _CLIENT_INSTANCE is not None:
            return
        _WARMUP_STARTED = True

        def _bg():
            try:
                _get_client()
            except Exception:
                pass

        threading.Thread(target=_bg, daemon=True).start()

    @staticmethod
    def _auth_otp_post(payload: dict) -> dict:
        """Invoca la Supabase Edge Function 'auth-otp' por HTTPS sin dependencias externas."""
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
            with urllib.request.urlopen(req, timeout=12) as resp:
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
            return {"ok": False, "error_conexion": f"Error de conexión con servidor: {str(exc)[:90]}"}

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
