"""
core/cloud_gateway.py — Capa de Persistencia en Supabase (Fase 3 + Auditoría)
==============================================================================
Usa supabase-py 2.x (PostgREST via httpx) en lugar de requests puro.
Logging explícito en consola para depuración de errores HTTP.
"""

from __future__ import annotations

import base64
import hashlib
import html as _html
import http.client
import http.server
import os
import secrets
import ssl
import subprocess
import sys
import time
import traceback
import threading
import json as _json
import urllib.parse
import urllib.request
import urllib.error
import webbrowser
from typing import Any

SUPABASE_URL  = "https://pvrfnvrxaxulcxacdino.supabase.co"
SUPABASE_HOST = "pvrfnvrxaxulcxacdino.supabase.co"
SUPABASE_KEY  = "sb_publishable_G7D4dhh3Q2LWzgRnzRRa9A_4ngZ5FiW"

OAUTH_PROVIDERS: tuple[str, ...] = ("google", "github")
OAUTH_DEFAULT_PORT: int = 54321
OAUTH_CALLBACK_PATH: str = "/auth/callback"
OAUTH_CALLBACK_URL_DEFAULT: str = f"http://localhost:{OAUTH_DEFAULT_PORT}{OAUTH_CALLBACK_PATH}"

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


def _abrir_navegador_multiplataforma(url: str) -> bool:
    """
    Abre una URL HTTPS en el navegador predeterminado en Windows, Linux y macOS.
    En binarios Linux PyInstaller (--onefile) restaura LD_LIBRARY_PATH_ORIG para
    evitar conflictos de librerías compartidas (.so) con xdg-open / Firefox / Chrome.
    """
    clean_url = str(url or "").strip()
    if not clean_url.startswith("https://"):
        return False

    if sys.platform.startswith("linux") and getattr(sys, "frozen", False):
        env = dict(os.environ)
        orig_ld = env.get("LD_LIBRARY_PATH_ORIG")
        if orig_ld is not None:
            env["LD_LIBRARY_PATH"] = orig_ld
        else:
            env.pop("LD_LIBRARY_PATH", None)
        xdg = "/usr/bin/xdg-open" if os.path.isfile("/usr/bin/xdg-open") else "xdg-open"
        try:
            subprocess.Popen(
                [xdg, clean_url],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            pass
    elif sys.platform == "darwin" and os.path.isfile("/usr/bin/open"):
        try:
            subprocess.Popen(
                ["/usr/bin/open", clean_url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            pass

    return bool(webbrowser.open(clean_url))


class _ReusableLoopbackHTTPServer(http.server.HTTPServer):
    """Servidor HTTP loopback con SO_REUSEADDR habilitado para reintentos rápidos en Linux y macOS."""

    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], handler_cls: Any, oauth_state: dict, oauth_nonce: str):
        self.oauth_state = oauth_state
        self.oauth_nonce = oauth_nonce
        super().__init__(server_address, handler_cls)


class _OAuthCallbackRequestHandler(http.server.BaseHTTPRequestHandler):
    """Manejador HTTP loopback compatible con compilación C nativa (Cython) en Windows/Linux/macOS."""

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def _send_bytes(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        srv: Any = self.server
        state: dict = srv.oauth_state
        nonce: str = srv.oauth_nonce

        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/favicon.ico":
            self._send_bytes(204, "text/plain", b"")
            return
        if not parsed.path.startswith(OAUTH_CALLBACK_PATH):
            self._send_bytes(404, "text/plain; charset=utf-8", b"Ruta no encontrada.")
            return

        qs = urllib.parse.parse_qs(parsed.query)
        code = (qs.get("code") or [""])[0].strip()
        acc = (qs.get("access_token") or [""])[0].strip()
        err = (qs.get("error") or [""])[0].strip()
        err_desc = (qs.get("error_description") or [""])[0].strip()

        if err:
            state["error"] = err
            state["error_description"] = err_desc or err
            state["done"] = True
            body = CloudGateway._render_oauth_callback_html(
                "Autorización cancelada o denegada",
                err_desc or "El proveedor OAuth rechazó la solicitud. Vuelva a la aplicación.",
                es_error=True,
            )
            self._send_bytes(200, "text/html; charset=utf-8", body)
        elif code or acc:
            state["code"] = code
            state["access_token"] = acc
            state["refresh_token"] = (qs.get("refresh_token") or [""])[0].strip()
            state["done"] = True
            body = CloudGateway._render_oauth_callback_html(
                "Autenticación recibida",
                "Ya puede cerrar esta pestaña del navegador y volver a IndiServ Analytica.",
                es_error=False,
            )
            self._send_bytes(200, "text/html; charset=utf-8", body)
        else:
            body = CloudGateway._render_oauth_callback_html(
                "Sincronizando sesión…",
                "Procesando credenciales seguras con IndiServ Analytica…",
                es_error=False,
                nonce=nonce,
            )
            self._send_bytes(200, "text/html; charset=utf-8", body)

    def do_POST(self) -> None:  # noqa: N802
        srv: Any = self.server
        state: dict = srv.oauth_state
        nonce: str = srv.oauth_nonce

        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != f"{OAUTH_CALLBACK_PATH}/fragment":
            self._send_bytes(404, "application/json", b'{"ok":false}')
            return
        if self.headers.get("X-OAuth-Nonce", "") != nonce:
            self._send_bytes(403, "application/json", b'{"ok":false}')
            return
        try:
            length = min(16384, max(0, int(self.headers.get("Content-Length", "0"))))
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            data = _json.loads(raw) if raw else {}
        except Exception:
            data = {}

        state["access_token"] = str(data.get("access_token") or "").strip()
        state["refresh_token"] = str(data.get("refresh_token") or "").strip()
        state["code"] = str(data.get("code") or "").strip()
        state["error"] = str(data.get("error") or "").strip()
        state["error_description"] = str(data.get("error_description") or "").strip()
        state["done"] = True
        self._send_bytes(200, "application/json", b'{"ok":true}')


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

    # =========================================================================
    # AUTENTICACIÓN OAUTH 2.0 EN ESCRITORIO (PKCE + IMPLICIT — GOOGLE / GITHUB)
    # =========================================================================

    @staticmethod
    def obtener_callback_url_configuracion(port: int = OAUTH_DEFAULT_PORT) -> str:
        """Devuelve la URL de redirección local recomendada para Supabase Auth."""
        return f"http://localhost:{int(port)}{OAUTH_CALLBACK_PATH}"

    @staticmethod
    def generar_pkce_pair() -> tuple[str, str]:
        """Genera (code_verifier, code_challenge) conforme a RFC 7636 (S256)."""
        verifier = secrets.token_urlsafe(48)
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return verifier, challenge

    @staticmethod
    def construir_url_oauth(
        provider: str,
        redirect_uri: str | None = None,
        code_challenge: str | None = None,
    ) -> str:
        """Construye la URL oficial de autorización OAuth de Supabase para Google o GitHub."""
        prov = str(provider or "").strip().lower()
        if prov not in OAUTH_PROVIDERS:
            raise ValueError(f"Proveedor OAuth no soportado: {provider!r}. Use 'google' o 'github'.")

        destino = str(redirect_uri or OAUTH_CALLBACK_URL_DEFAULT).strip()
        params: dict[str, str] = {
            "provider": prov,
            "redirect_to": destino,
        }
        if code_challenge:
            params["code_challenge"] = str(code_challenge).strip()
            params["code_challenge_method"] = "s256"
        if prov == "google":
            params["prompt"] = "select_account"

        qs = urllib.parse.urlencode(params)
        return f"{SUPABASE_URL.rstrip('/')}/auth/v1/authorize?{qs}"

    @staticmethod
    def _render_oauth_callback_html(titulo: str, detalle: str, es_error: bool = False, nonce: str = "") -> bytes:
        """Genera la página HTML dark-tech servida localmente al navegador tras el callback OAuth."""
        acento = "#ef4444" if es_error else "#10b981"
        simbolo = "✖" if es_error else "✔"
        t_safe = _html.escape(titulo)
        d_safe = _html.escape(detalle)
        script_fragment = ""
        if nonce:
            script_fragment = f"""
<script>
(function() {{
  var h = window.location.hash ? window.location.hash.substring(1) : "";
  var st = document.getElementById("status-msg");
  var ti = document.getElementById("status-title");
  if (!h) {{
    ti.textContent = "✖ No se recibieron credenciales OAuth";
    ti.style.color = "#ef4444";
    st.textContent = "Vuelva a IndiServ Analytica e intente iniciar sesión nuevamente.";
    fetch("{OAUTH_CALLBACK_PATH}/fragment", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json", "X-OAuth-Nonce": "{nonce}" }},
      body: JSON.stringify({{ error: "missing_credentials", error_description: "El proveedor no devolvió código ni token de sesión." }})
    }}).catch(function(){{}});
    return;
  }}
  var p = new URLSearchParams(h);
  var payload = {{
    access_token: p.get("access_token") || "",
    refresh_token: p.get("refresh_token") || "",
    code: p.get("code") || "",
    error: p.get("error") || "",
    error_description: p.get("error_description") || ""
  }};
  fetch("{OAUTH_CALLBACK_PATH}/fragment", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json", "X-OAuth-Nonce": "{nonce}" }},
    body: JSON.stringify(payload)
  }}).then(function() {{
    if (payload.error) {{
      ti.textContent = "✖ Autorización denegada";
      ti.style.color = "#ef4444";
      st.textContent = payload.error_description || payload.error;
    }} else {{
      ti.textContent = "✔ Autenticación completada";
      ti.style.color = "#10b981";
      st.textContent = "Sesión sincronizada con IndiServ Analytica. Ya puede cerrar esta pestaña.";
      if (window.history && window.history.replaceState) {{
        window.history.replaceState(null, "", window.location.pathname);
      }}
    }}
  }}).catch(function() {{
    st.textContent = "No se pudo contactar con la instancia local de IndiServ Analytica.";
  }});
}})();
</script>"""
        doc = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>IndiServ Analytica — Autenticación OAuth</title>
<style>
  body {{ margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
         background:#090c12; color:#f1f5f9; font-family:'Segoe UI',system-ui,sans-serif; }}
  .card {{ max-width:440px; padding:28px 30px; background:#141b2a; border:1px solid #334361;
          border-radius:14px; box-shadow:0 20px 50px rgba(0,0,0,.55); text-align:center; }}
  .brand {{ color:#22d3ee; font-size:12px; font-weight:600; letter-spacing:1.2px; margin-bottom:12px; }}
  h1 {{ font-size:19px; margin:0 0 10px; color:{acento}; }}
  p {{ font-size:13.5px; line-height:1.55; color:#94a3b8; margin:0; }}
</style>
</head>
<body>
  <div class="card">
    <div class="brand">◈ INDISERV ANALYTICA · DESKTOP OAUTH</div>
    <h1 id="status-title">{simbolo} {t_safe}</h1>
    <p id="status-msg">{d_safe}</p>
  </div>
  {script_fragment}
</body>
</html>"""
        return doc.encode("utf-8")

    @staticmethod
    def iniciar_servidor_callback_oauth(preferred_port: int = OAUTH_DEFAULT_PORT) -> tuple[http.server.HTTPServer, str, dict]:
        """
        Levanta un servidor HTTP local temporal en 127.0.0.1 (prefiere puerto 54321;
        si está ocupado, toma cualquier puerto libre del SO) listo para capturar el callback.
        """
        nonce = secrets.token_urlsafe(24)
        state: dict[str, Any] = {
            "done": False,
            "code": "",
            "access_token": "",
            "refresh_token": "",
            "error": "",
            "error_description": "",
        }

        httpd: http.server.HTTPServer | None = None
        if preferred_port > 0:
            try:
                httpd = _ReusableLoopbackHTTPServer(
                    ("127.0.0.1", int(preferred_port)), _OAuthCallbackRequestHandler, state, nonce
                )
            except OSError:
                httpd = None
        if httpd is None:
            httpd = _ReusableLoopbackHTTPServer(
                ("127.0.0.1", 0), _OAuthCallbackRequestHandler, state, nonce
            )

        httpd.timeout = 0.25
        actual_port = int(httpd.server_address[1])
        redirect_uri = f"http://localhost:{actual_port}{OAUTH_CALLBACK_PATH}"
        return httpd, redirect_uri, state

    @staticmethod
    def esperar_callback_oauth(
        httpd: http.server.HTTPServer,
        state: dict,
        cancel_event: threading.Event | None = None,
        timeout_sec: float = 180.0,
    ) -> dict:
        """Espera respuesta del navegador sin bloquear la GUI y cierra el servidor automáticamente."""
        deadline = time.monotonic() + max(5.0, float(timeout_sec))
        try:
            while not state.get("done"):
                if cancel_event is not None and cancel_event.is_set():
                    return {"ok": False, "cancelado": True, "error": "Autenticación cancelada por el operador."}
                if time.monotonic() >= deadline:
                    return {
                        "ok": False,
                        "timeout": True,
                        "error": "Tiempo de espera agotado esperando autorización en el navegador.",
                    }
                httpd.handle_request()
        finally:
            try:
                httpd.server_close()
            except Exception:
                pass

        if state.get("error"):
            return {
                "ok": False,
                "error": state.get("error_description") or state.get("error") or "Autorización OAuth rechazada.",
            }
        if state.get("code") or state.get("access_token"):
            return {
                "ok": True,
                "code": state.get("code", ""),
                "access_token": state.get("access_token", ""),
                "refresh_token": state.get("refresh_token", ""),
            }
        return {"ok": False, "error": "No se recibió código ni token de autorización."}

    @staticmethod
    def intercambiar_codigo_oauth_pkce(auth_code: str, code_verifier: str) -> dict:
        """Intercambia el authorization code PKCE por access_token + perfil verificado en Supabase Auth."""
        url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=pkce"
        body = _json.dumps(
            {"auth_code": str(auth_code or "").strip(), "code_verifier": str(code_verifier or "").strip()}
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "apikey": SUPABASE_KEY},
        )
        try:
            with _get_pinned_opener().open(req, timeout=12) as resp:
                parsed = _json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
                tok = str(parsed.get("access_token") or "").strip()
                if tok:
                    return {
                        "ok": True,
                        "access_token": tok,
                        "refresh_token": str(parsed.get("refresh_token") or "").strip(),
                        "user": parsed.get("user") or {},
                    }
                return {"ok": False, "error": "Supabase no devolvió un token de acceso válido."}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            try:
                err_obj = _json.loads(raw) if raw else {}
            except Exception:
                err_obj = {}
            msg = err_obj.get("msg") or err_obj.get("error_description") or err_obj.get("error") or f"HTTP {exc.code}"
            return {"ok": False, "error": f"Error al canjear código OAuth: {msg}"}
        except Exception as exc:
            return {"ok": False, "error_conexion": f"Error de conexión segura en canje OAuth: {str(exc)[:90]}"}

    @staticmethod
    def obtener_usuario_oauth_token(access_token: str) -> dict:
        """Verifica un access_token OAuth directamente contra GET /auth/v1/user (con pinning SPKI)."""
        url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/user"
        req = urllib.request.Request(
            url,
            method="GET",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {str(access_token or '').strip()}",
            },
        )
        try:
            with _get_pinned_opener().open(req, timeout=12) as resp:
                user = _json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
                if isinstance(user, dict) and (user.get("id") or user.get("email")):
                    return {"ok": True, "user": user}
                return {"ok": False, "error": "Perfil OAuth inválido o expirado."}
        except urllib.error.HTTPError as exc:
            return {"ok": False, "error": f"Token OAuth rechazado por Supabase (HTTP {exc.code})."}
        except Exception as exc:
            return {"ok": False, "error_conexion": f"Error de red verificando identidad OAuth: {str(exc)[:90]}"}

    @staticmethod
    def extraer_perfil_oauth(user_obj: dict, provider_hint: str = "") -> dict:
        """Extrae correo electrónico y nombre/alias normalizado del objeto user de Google o GitHub."""
        u = user_obj if isinstance(user_obj, dict) else {}
        meta = u.get("user_metadata") if isinstance(u.get("user_metadata"), dict) else {}
        app_meta = u.get("app_metadata") if isinstance(u.get("app_metadata"), dict) else {}
        identities = u.get("identities") if isinstance(u.get("identities"), list) else []
        id_data = (
            identities[0].get("identity_data")
            if identities and isinstance(identities[0], dict) and isinstance(identities[0].get("identity_data"), dict)
            else {}
        )

        correo = (
            str(u.get("email") or meta.get("email") or id_data.get("email") or "").strip().lower()
        )
        raw_alias = (
            meta.get("full_name")
            or meta.get("name")
            or meta.get("preferred_username")
            or meta.get("user_name")
            or id_data.get("full_name")
            or id_data.get("name")
            or id_data.get("user_name")
            or (correo.split("@", 1)[0] if "@" in correo else "Operador")
        )
        nickname = str(raw_alias).strip()[:40] or "Operador"
        provider = str(app_meta.get("provider") or provider_hint or "oauth").strip().lower()
        return {
            "correo": correo,
            "nickname": nickname,
            "provider": provider,
            "oauth_user_id": str(u.get("id") or ""),
        }

    @staticmethod
    def _rest_oauth_request(
        path_and_query: str,
        access_token: str,
        method: str = "GET",
        payload: dict | None = None,
        prefer: str = "",
    ) -> tuple[int, Any]:
        """Ejecuta una llamada PostgREST/RPC autenticada con el JWT OAuth de Supabase y pinning SPKI."""
        url = f"{SUPABASE_URL.rstrip('/')}{path_and_query}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = _json.dumps(payload).encode("utf-8")
        if prefer:
            headers["Prefer"] = prefer
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with _get_pinned_opener().open(req, timeout=12) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return resp.status, (_json.loads(raw) if raw else None)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            try:
                return exc.code, (_json.loads(raw) if raw else {})
            except Exception:
                return exc.code, {"message": raw or f"HTTP {exc.code}"}
        except Exception as exc:
            return 0, {"error_conexion": f"Error de conexión segura: {str(exc)[:90]}"}

    @staticmethod
    def autenticar_operador_oauth(
        access_token: str,
        correo: str,
        nickname: str,
        provider: str,
        device_hash: str,
        device_label: str,
    ) -> dict:
        """
        Verifica si el correo autenticado por Google/GitHub ya figura en 'usuarios_app'.
        Si existe, retorna autenticado=True + datos + session_token.
        Si es nuevo, retorna requiere_dni=True para abrir el modal estilizado de DNI.
        """
        from core.security import is_honey_credential, trigger_honeytoken_alert

        clean_correo = str(correo or "").strip().lower()
        clean_nick = str(nickname or "Operador").strip() or "Operador"
        if not clean_correo or "@" not in clean_correo:
            return {
                "ok": False,
                "error": "Tu cuenta social no expuso un correo electrónico público/verificado.",
            }

        if is_honey_credential("", clean_correo):
            trigger_honeytoken_alert(
                tipo="CREDENCIAL_SENUELO_OAUTH_DESKTOP",
                detalle=f"Intento OAuth ({provider}) con correo señuelo '{clean_correo}'",
            )
            return {"ok": False, "error": "Cuenta no autorizada en el sistema."}

        # 1) Vía primaria: Edge Function 'auth-otp' (emite session_token de 15 min si está desplegada)
        otp_res = CloudGateway._auth_otp_post(
            {
                "action": "oauth_login",
                "oauth_access_token": access_token,
                "correo": clean_correo,
                "nickname": clean_nick,
                "provider": provider,
                "device_hash": device_hash,
                "device_label": device_label,
                "plataforma": "desktop",
            }
        )
        if otp_res.get("ok"):
            if otp_res.get("requires_dni") or otp_res.get("status") == "needs_dni":
                return {
                    "ok": True,
                    "autenticado": False,
                    "requiere_dni": True,
                    "correo": clean_correo,
                    "nickname": clean_nick,
                    "provider": provider,
                }
            user = otp_res.get("user") or {}
            return {
                "ok": True,
                "autenticado": True,
                "requiere_dni": False,
                "session_token": otp_res.get("session_token"),
                "dni": user.get("dni"),
                "correo": user.get("correo") or clean_correo,
                "nickname": user.get("nickname") or clean_nick,
                "avatar_data": user.get("avatar_data"),
                "rol": user.get("rol") or "operator",
            }

        # 2) Vía RPC SECURITY DEFINER 'oauth_sync_operador' (autenticada con JWT de Supabase Auth)
        status_rpc, rpc_data = CloudGateway._rest_oauth_request(
            "/rest/v1/rpc/oauth_sync_operador",
            access_token=access_token,
            method="POST",
            payload={
                "p_dni": None,
                "p_nickname": clean_nick,
                "p_device_hash": device_hash,
                "p_device_label": device_label,
            },
        )
        if status_rpc == 200 and isinstance(rpc_data, dict):
            if rpc_data.get("ok") and rpc_data.get("status") == "needs_dni":
                return {
                    "ok": True,
                    "autenticado": False,
                    "requiere_dni": True,
                    "correo": clean_correo,
                    "nickname": clean_nick,
                    "provider": provider,
                }
            if rpc_data.get("ok") and rpc_data.get("status") == "authenticated":
                u = rpc_data.get("user") or {}
                return {
                    "ok": True,
                    "autenticado": True,
                    "requiere_dni": False,
                    "session_token": rpc_data.get("session_token"),
                    "dni": u.get("dni") or rpc_data.get("dni"),
                    "correo": u.get("correo") or clean_correo,
                    "nickname": u.get("nickname") or clean_nick,
                    "avatar_data": u.get("avatar_data"),
                    "rol": u.get("rol") or "operator",
                }
            if rpc_data.get("error"):
                return {"ok": False, "error": str(rpc_data["error"])}

        # 3) Respaldo PostgREST sobre 'usuarios_app' autenticado con Bearer JWT
        q_mail = urllib.parse.quote(clean_correo, safe="")
        st_tbl, rows = CloudGateway._rest_oauth_request(
            f"/rest/v1/{TABLA_USUARIOS}?select=dni,correo,nickname,avatar_data&correo=ilike.{q_mail}&limit=1",
            access_token=access_token,
            method="GET",
        )
        if st_tbl == 200 and isinstance(rows, list):
            if rows:
                row = rows[0]
                return {
                    "ok": True,
                    "autenticado": True,
                    "requiere_dni": False,
                    "session_token": None,
                    "dni": row.get("dni"),
                    "correo": row.get("correo") or clean_correo,
                    "nickname": row.get("nickname") or clean_nick,
                    "avatar_data": row.get("avatar_data"),
                    "rol": "operator",
                }
            return {
                "ok": True,
                "autenticado": False,
                "requiere_dni": True,
                "correo": clean_correo,
                "nickname": clean_nick,
                "provider": provider,
            }

        if st_tbl == 0 and isinstance(rows, dict) and rows.get("error_conexion"):
            return {"ok": False, "error_conexion": rows["error_conexion"]}

        return {
            "ok": False,
            "error": (
                "Falta habilitar la función SQL 'oauth_sync_operador' en Supabase "
                "(ejecute supabase_oauth_setup.sql en SQL Editor)."
            ),
        }

    @staticmethod
    def completar_registro_oauth_dni(
        access_token: str,
        dni: str,
        correo: str,
        nickname: str,
        provider: str,
        device_hash: str,
        device_label: str,
    ) -> dict:
        """
        Valida el DNI de 8 dígitos contra 'padron_oficial' y vincula/crea la cuenta
        del operador autenticado con Google o GitHub en 'usuarios_app'.
        """
        from core.security import is_honey_credential, trigger_honeytoken_alert

        clean_dni = str(dni or "").strip()
        clean_correo = str(correo or "").strip().lower()
        clean_nick = str(nickname or "Operador").strip()[:40] or "Operador"

        if len(clean_dni) != 8 or not clean_dni.isdigit():
            return {"ok": False, "error": "Ingrese un DNI válido de exactamente 8 dígitos numéricos."}

        if is_honey_credential(clean_dni, clean_correo):
            trigger_honeytoken_alert(
                tipo="CREDENCIAL_SENUELO_OAUTH_DNI",
                detalle=f"Intento de vincular DNI señuelo '{clean_dni}' con OAuth '{clean_correo}'",
            )
            return {"ok": False, "error": "El DNI ingresado no figura en el padrón oficial autorizado."}

        # 1) Vía primaria: Edge Function 'auth-otp'
        otp_res = CloudGateway._auth_otp_post(
            {
                "action": "oauth_register_dni",
                "oauth_access_token": access_token,
                "dni": clean_dni,
                "correo": clean_correo,
                "nickname": clean_nick,
                "provider": provider,
                "device_hash": device_hash,
                "device_label": device_label,
                "plataforma": "desktop",
            }
        )
        if otp_res.get("ok"):
            u = otp_res.get("user") or {}
            return {
                "ok": True,
                "autenticado": True,
                "session_token": otp_res.get("session_token"),
                "dni": u.get("dni") or clean_dni,
                "correo": u.get("correo") or clean_correo,
                "nickname": u.get("nickname") or clean_nick,
                "avatar_data": u.get("avatar_data"),
                "rol": u.get("rol") or "operator",
            }
        if otp_res.get("error") and "Acción no soportada" not in str(otp_res.get("error", "")) and not otp_res.get("_missing_function"):
            return {"ok": False, "error": str(otp_res["error"])}

        # 2) Vía RPC SECURITY DEFINER 'oauth_sync_operador'
        status_rpc, rpc_data = CloudGateway._rest_oauth_request(
            "/rest/v1/rpc/oauth_sync_operador",
            access_token=access_token,
            method="POST",
            payload={
                "p_dni": clean_dni,
                "p_nickname": clean_nick,
                "p_device_hash": device_hash,
                "p_device_label": device_label,
            },
        )
        if status_rpc == 200 and isinstance(rpc_data, dict):
            if rpc_data.get("ok") and rpc_data.get("status") == "authenticated":
                u = rpc_data.get("user") or {}
                return {
                    "ok": True,
                    "autenticado": True,
                    "session_token": rpc_data.get("session_token"),
                    "dni": u.get("dni") or rpc_data.get("dni") or clean_dni,
                    "correo": u.get("correo") or clean_correo,
                    "nickname": u.get("nickname") or clean_nick,
                    "avatar_data": u.get("avatar_data"),
                    "rol": u.get("rol") or "operator",
                }
            return {
                "ok": False,
                "error": str(rpc_data.get("error") or "No se pudo validar el DNI en el padrón oficial."),
            }

        # 3) Respaldo PostgREST directo autenticado con JWT
        q_dni = urllib.parse.quote(clean_dni, safe="")
        st_pad, pad_rows = CloudGateway._rest_oauth_request(
            f"/rest/v1/{TABLA_PADRON}?select=dni&dni=eq.{q_dni}&limit=1",
            access_token=access_token,
            method="GET",
        )
        if st_pad == 200 and isinstance(pad_rows, list):
            if not pad_rows:
                return {"ok": False, "error": "El DNI ingresado no figura en el padrón oficial público."}
            oauth_hash_tag = f"indiserv_oauth${provider}${secrets.token_hex(16)}"
            st_ins, ins_res = CloudGateway._rest_oauth_request(
                f"/rest/v1/{TABLA_USUARIOS}",
                access_token=access_token,
                method="POST",
                payload={
                    "dni": clean_dni,
                    "nickname": clean_nick,
                    "correo": clean_correo,
                    "password_hash": oauth_hash_tag,
                },
                prefer="return=representation",
            )
            if st_ins in (200, 201):
                return {
                    "ok": True,
                    "autenticado": True,
                    "session_token": None,
                    "dni": clean_dni,
                    "correo": clean_correo,
                    "nickname": clean_nick,
                    "avatar_data": None,
                    "rol": "operator",
                }
            err_msg = ins_res.get("message") if isinstance(ins_res, dict) else ""
            if "duplicate" in str(err_msg).lower() or st_ins == 409:
                return {"ok": False, "error": "Este DNI ya se encuentra vinculado a otra cuenta registrada."}
            return {"ok": False, "error": f"No se pudo completar el registro ({err_msg or st_ins})."}

        return {
            "ok": False,
            "error": (
                "Falta habilitar 'supabase_oauth_setup.sql' en Supabase SQL Editor para validar el padrón vía OAuth."
            ),
        }

    @staticmethod
    def verificar_proveedor_oauth_habilitado(provider: str) -> dict:
        """
        Consulta GET /auth/v1/settings antes de abrir el navegador para evitar la
        pantalla cruda '{"code":400,"msg":"Unsupported provider: provider is not enabled"}'
        cuando Google o GitHub están desactivados en el panel de Supabase.
        """
        prov = str(provider or "").strip().lower()
        nombre = "Google" if prov == "google" else ("GitHub" if prov == "github" else prov)
        if prov not in OAUTH_PROVIDERS:
            return {"ok": False, "habilitado": False, "error": f"Proveedor no soportado: {provider!r}"}

        url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/settings"
        req = urllib.request.Request(
            url,
            method="GET",
            headers={"apikey": SUPABASE_KEY, "Accept": "application/json"},
        )
        try:
            with _get_pinned_opener().open(req, timeout=8) as resp:
                data = _json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
                ext = data.get("external") if isinstance(data, dict) else None
                if isinstance(ext, dict) and ext.get(prov) is False:
                    return {
                        "ok": False,
                        "habilitado": False,
                        "error": (
                            f"El proveedor {nombre} no está habilitado en Supabase. "
                            f"Actívelo en Supabase → Authentication → Sign In / Providers → {nombre}."
                        ),
                    }
                return {"ok": True, "habilitado": True}
        except Exception as exc:
            return {
                "ok": False,
                "error_conexion": f"No se pudo verificar estado OAuth en Supabase: {str(exc)[:85]}",
            }

    @staticmethod
    def verificar_dni_pre_oauth(dni: str, origen: str = "login") -> dict:
        """
        Verifica en Supabase que el DNI de 8 dígitos exista en la base de datos
        ('padron_oficial' / 'usuarios_app') ANTES de iniciar sesión o continuar con Google/GitHub.
        """
        from core.security import is_honey_credential, trigger_honeytoken_alert

        clean_dni = str(dni or "").strip()
        if len(clean_dni) != 8 or not clean_dni.isdigit():
            return {
                "ok": False,
                "existe": False,
                "error": "Ingrese primero su DNI de 8 dígitos numéricos antes de continuar.",
            }

        if is_honey_credential(clean_dni):
            trigger_honeytoken_alert(
                tipo="CREDENCIAL_SENUELO_PRE_OAUTH_DNI",
                detalle=f"Intento pre-OAuth ({origen}) con DNI señuelo '{clean_dni}'",
            )
            return {
                "ok": False,
                "existe": False,
                "error": "El DNI ingresado no se encuentra registrado en Supabase.",
            }

        # 1) Intento vía Edge Function 'auth-otp' si soporta 'oauth_check_dni'
        otp_chk = CloudGateway._auth_otp_post(
            {"action": "oauth_check_dni", "dni": clean_dni, "origen": origen}
        )
        if otp_chk.get("ok"):
            existe = bool(otp_chk.get("existe") or otp_chk.get("en_padron") or otp_chk.get("ya_registrado"))
            if not existe:
                return {
                    "ok": False,
                    "existe": False,
                    "error": f"El DNI {clean_dni} no está registrado en la base de datos de Supabase.",
                }
            return {
                "ok": True,
                "existe": True,
                "en_padron": bool(otp_chk.get("en_padron", True)),
                "ya_registrado": bool(otp_chk.get("ya_registrado", False)),
            }

        # 2) Intento vía RPC SECURITY DEFINER 'verificar_dni_pre_oauth' (y respaldo 'verificar_padron_dni')
        for rpc_name in ("verificar_dni_pre_oauth", "verificar_padron_dni"):
            st_rpc, rpc_res = CloudGateway._rest_oauth_request(
                f"/rest/v1/rpc/{rpc_name}",
                access_token=SUPABASE_KEY,
                method="POST",
                payload={"p_dni": clean_dni},
            )
            if st_rpc == 200 and isinstance(rpc_res, dict):
                existe = bool(
                    rpc_res.get("existe")
                    or rpc_res.get("en_padron")
                    or rpc_res.get("ya_registrado")
                )
                if not existe:
                    return {
                        "ok": False,
                        "existe": False,
                        "error": f"El DNI {clean_dni} no figura en la base de datos de Supabase (padrón oficial).",
                    }
                return {
                    "ok": True,
                    "existe": True,
                    "en_padron": bool(rpc_res.get("en_padron", rpc_res.get("existe", True))),
                    "ya_registrado": bool(rpc_res.get("ya_registrado", False)),
                }
            if st_rpc == 0 and isinstance(rpc_res, dict) and rpc_res.get("error_conexion"):
                return {"ok": False, "error_conexion": rpc_res["error_conexion"]}

        return {
            "ok": False,
            "falta_sql": True,
            "error": (
                "Falta habilitar 'verificar_dni_pre_oauth' en Supabase: ejecute "
                "supabase_oauth_setup.sql en Supabase → SQL Editor."
            ),
        }

    @staticmethod
    def iniciar_sesion_oauth_escritorio(
        provider: str,
        device_hash: str,
        device_label: str,
        dni: str = "",
        origen: str = "login",
        on_esperando_navegador: Any = None,
        cancel_event: threading.Event | None = None,
        abrir_navegador_fn: Any = None,
        timeout_sec: float = 180.0,
        preferred_port: int = OAUTH_DEFAULT_PORT,
    ) -> dict:
        """
        Orquesta el flujo completo OAuth 2.0 en escritorio (PKCE + Implicit):
        1. Verifica en Supabase que el DNI de 8 dígitos exista ANTES de continuar.
        2. Verifica en Supabase (/auth/v1/settings) que Google o GitHub esté habilitado.
        3. Levanta servidor HTTP local temporal en puerto libre (prefiriendo 54321).
        4. Abre la URL de autorización en el navegador y espera callback cancelable.
        5. Canjea el código PKCE y vincula/autentica la sesión contra el DNI verificado.
        """
        prov = str(provider or "").strip().lower()
        if prov not in OAUTH_PROVIDERS:
            return {"ok": False, "error": f"Proveedor OAuth inválido: {provider!r}"}

        clean_dni = str(dni or "").strip()
        dni_chk = CloudGateway.verificar_dni_pre_oauth(clean_dni, origen=origen)
        if not dni_chk.get("ok"):
            return dni_chk

        if cancel_event is not None and cancel_event.is_set():
            return {"ok": False, "cancelado": True, "error": "Autenticación cancelada por el operador."}

        prov_chk = CloudGateway.verificar_proveedor_oauth_habilitado(prov)
        if not prov_chk.get("ok"):
            return prov_chk

        if cancel_event is not None and cancel_event.is_set():
            return {"ok": False, "cancelado": True, "error": "Autenticación cancelada por el operador."}

        verifier, challenge = CloudGateway.generar_pkce_pair()
        try:
            httpd, redirect_uri, state = CloudGateway.iniciar_servidor_callback_oauth(
                preferred_port=preferred_port
            )
        except Exception as exc:
            return {"ok": False, "error": f"No se pudo abrir el puerto local de callback OAuth: {exc}"}

        if callable(on_esperando_navegador):
            try:
                on_esperando_navegador()
            except Exception:
                pass

        auth_url = CloudGateway.construir_url_oauth(
            prov, redirect_uri=redirect_uri, code_challenge=challenge
        )
        launcher = abrir_navegador_fn or _abrir_navegador_multiplataforma
        try:
            opened = launcher(auth_url)
            if opened is False:
                try:
                    httpd.server_close()
                except Exception:
                    pass
                return {"ok": False, "error": "No se pudo abrir el navegador predeterminado del sistema."}
        except Exception as exc:
            try:
                httpd.server_close()
            except Exception:
                pass
            return {"ok": False, "error": f"Error al lanzar el navegador para OAuth: {exc}"}

        cb_res = CloudGateway.esperar_callback_oauth(
            httpd, state, cancel_event=cancel_event, timeout_sec=timeout_sec
        )
        if not cb_res.get("ok"):
            return cb_res

        access_token = str(cb_res.get("access_token") or "").strip()
        user_obj: dict = {}
        if cb_res.get("code"):
            ex = CloudGateway.intercambiar_codigo_oauth_pkce(str(cb_res["code"]), verifier)
            if not ex.get("ok"):
                return ex
            access_token = str(ex["access_token"])
            user_obj = ex.get("user") if isinstance(ex.get("user"), dict) else {}

        if not user_obj:
            u_res = CloudGateway.obtener_usuario_oauth_token(access_token)
            if not u_res.get("ok"):
                return u_res
            user_obj = u_res.get("user") or {}

        perfil = CloudGateway.extraer_perfil_oauth(user_obj, provider_hint=prov)
        if clean_dni:
            return CloudGateway.completar_registro_oauth_dni(
                access_token=access_token,
                dni=clean_dni,
                correo=perfil["correo"],
                nickname=perfil["nickname"],
                provider=prov,
                device_hash=device_hash,
                device_label=device_label,
            )

        op_res = CloudGateway.autenticar_operador_oauth(
            access_token=access_token,
            correo=perfil["correo"],
            nickname=perfil["nickname"],
            provider=prov,
            device_hash=device_hash,
            device_label=device_label,
        )
        if op_res.get("ok") and op_res.get("requiere_dni"):
            op_res["oauth_access_token"] = access_token
        return op_res
