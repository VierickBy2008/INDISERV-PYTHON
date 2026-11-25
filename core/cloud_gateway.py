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

from supabase import create_client, Client

SUPABASE_URL  = "https://pvrfnvrxaxulcxacdino.supabase.co"
SUPABASE_KEY  = "sb_publishable_G7D4dhh3Q2LWzgRnzRRa9A_4ngZ5FiW"

TABLA_TICKETS = "reportes_diagnostico"
TABLA_PADRON  = "padron_oficial"
TABLA_USUARIOS = "usuarios_app"

_CLIENT_LOCK = threading.Lock()
_CLIENT_INSTANCE: Client | None = None


def _get_client() -> Client:
    """Devuelve una instancia singleton thread-safe del cliente Supabase reutilizando conexiones HTTP."""
    global _CLIENT_INSTANCE
    if _CLIENT_INSTANCE is None:
        with _CLIENT_LOCK:
            if _CLIENT_INSTANCE is None:
                _CLIENT_INSTANCE = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _CLIENT_INSTANCE


class CloudGateway:
    """
    Todos los métodos son @staticmethod para mantener compatibilidad con el
    código existente en main.py (se invocan como CloudGateway.metodo()).
    """

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
        from core.security import hash_password

        clean_dni = str(dni or "").strip()
        clean_correo = str(correo or "").strip()
        hashed_input = hash_password(clean_dni, password)
        res = CloudGateway._auth_otp_post(
            {
                "action": "login_init",
                "dni": clean_dni,
                "correo": clean_correo,
                "password_hash": hashed_input,
                "device_hash": device_hash,
                "device_label": device_label,
                "plataforma": "desktop",
            }
        )
        if res.get("_missing_function"):
            # Respaldo temporal si la Edge Function auth-otp aún no fue desplegada en Supabase
            return CloudGateway.autenticar_usuario_seguro(clean_dni, clean_correo, password)
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
        from core.security import hash_password

        clean_dni = str(dni or "").strip()
        hashed_pass = hash_password(clean_dni, password)
        res = CloudGateway._auth_otp_post(
            {
                "action": "register_init",
                "dni": clean_dni,
                "nickname": str(nickname or "").strip(),
                "correo": str(correo or "").strip(),
                "password_hash": hashed_pass,
                "device_hash": device_hash,
                "device_label": device_label,
                "plataforma": "desktop",
            }
        )
        if res.get("_missing_function"):
            ok = CloudGateway.registrar_usuario(clean_dni, correo, password, nickname)
            return {"ok": ok, "legacy_direct": True, "error": "" if ok else "No se pudo registrar la cuenta."}
        return res

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
    def consultar_padron(dni: str) -> dict:
        client = _get_client()
        clean_dni = str(dni or "").strip()
        try:
            rpc_resp = client.rpc("verificar_padron_dni", {"p_dni": clean_dni}).execute()
            if isinstance(rpc_resp.data, dict) and "existe" in rpc_resp.data:
                return rpc_resp.data
        except Exception:
            pass
        try:
            resp = (
                client.table(TABLA_PADRON)
                .select("dni, nombres_completos, carrera")
                .eq("dni", clean_dni)
                .limit(1)
                .execute()
            )
            if resp.data:
                data = resp.data[0]
                return {
                    "existe": True,
                    "nombres": data.get("nombres_completos"),
                    "carrera": data.get("carrera"),
                }
        except Exception as exc:
            print(f"[CloudGateway.consultar_padron] ERROR: {exc}")
        return {"existe": False}

    @staticmethod
    def autenticar_usuario_seguro(dni: str, correo: str, password: str) -> dict:
        """
        Autentica un operador priorizando la función RPC SECURITY DEFINER
        'autenticar_usuario' en PostgreSQL para no exponer 'password_hash' en red.
        """
        from core.security import hash_password, verify_password

        clean_dni = str(dni or "").strip()
        clean_correo = str(correo or "").strip()
        hashed_input = hash_password(clean_dni, password)
        client = _get_client()

        try:
            rpc_resp = client.rpc(
                "autenticar_usuario",
                {
                    "p_dni": clean_dni,
                    "p_correo": clean_correo,
                    "p_password_hash": hashed_input,
                },
            ).execute()
            if isinstance(rpc_resp.data, dict) and "ok" in rpc_resp.data:
                return {
                    "autenticado": bool(rpc_resp.data.get("ok")),
                    "dni": clean_dni,
                    "correo": rpc_resp.data.get("correo") or clean_correo,
                    "nickname": rpc_resp.data.get("nickname") or "Operador",
                }
        except Exception as exc:
            err_msg = str(exc)
            # Solo caer al respaldo legacy SELECT si la función RPC aún no existe en Supabase.
            is_missing_rpc = any(
                tok in err_msg.lower()
                for tok in ("pgrst202", "42883", "could not find the function", "does not exist", "404")
            )
            if not is_missing_rpc:
                print(f"[CloudGateway.autenticar_usuario_seguro] ERROR RPC: {err_msg}")
                return {
                    "autenticado": False,
                    "error_conexion": f"Error de conexión con Supabase: {err_msg[:90]}",
                }

        cuenta = CloudGateway.consultar_usuario(clean_dni)
        es_valida, _ = verify_password(clean_dni, password, str(cuenta.get("password_hash") or ""))
        ok = bool(cuenta.get("registrado") and cuenta.get("correo") == clean_correo and es_valida)
        return {
            "autenticado": ok,
            "dni": clean_dni,
            "correo": cuenta.get("correo"),
        }

    @staticmethod
    def consultar_usuario(dni: str) -> dict:
        client = _get_client()
        try:
            resp = (
                client.table(TABLA_USUARIOS)
                .select("dni, correo, nickname, password_hash")
                .eq("dni", str(dni or "").strip())
                .limit(1)
                .execute()
            )
            if resp.data:
                data = resp.data[0]
                return {
                    "registrado": True,
                    "correo": data.get("correo"),
                    "password_hash": data.get("password_hash"),
                }
        except Exception as exc:
            print(f"[CloudGateway.consultar_usuario] ERROR: {exc}")
        return {"registrado": False}

    @staticmethod
    def registrar_usuario(dni: str, correo: str, password: str, nickname: str) -> bool:
        from core.security import hash_password

        clean_dni = str(dni or "").strip()
        clean_correo = str(correo or "").strip()
        clean_nick = str(nickname or "").strip()
        hashed_pass = hash_password(clean_dni, password)
        client = _get_client()

        try:
            rpc_resp = client.rpc(
                "registrar_usuario_seguro",
                {
                    "p_dni": clean_dni,
                    "p_nickname": clean_nick,
                    "p_correo": clean_correo,
                    "p_password_hash": hashed_pass,
                },
            ).execute()
            if isinstance(rpc_resp.data, dict) and "ok" in rpc_resp.data:
                return bool(rpc_resp.data.get("ok"))
        except Exception:
            pass

        payload = {
            "dni": clean_dni,
            "correo": clean_correo,
            "password_hash": hashed_pass,
            "nickname": clean_nick,
        }
        try:
            resp = client.table(TABLA_USUARIOS).insert(payload).execute()
            return bool(resp.data)
        except Exception as exc:
            print(f"[CloudGateway.registrar_usuario] ERROR: {exc}")
            return False

    @staticmethod
    def actualizar_hash_usuario(dni: str, nuevo_hash: str) -> bool:
        """Actualiza el hash de contraseña de una cuenta legacy a indiserv_v1$<sha256>."""
        client = _get_client()
        try:
            resp = (
                client.table(TABLA_USUARIOS)
                .update({"password_hash": nuevo_hash})
                .eq("dni", str(dni).strip())
                .execute()
            )
            return bool(resp.data)
        except Exception as exc:
            print(f"[CloudGateway.actualizar_hash_usuario] ERROR: {exc}")
            return False

    @staticmethod
    def listar_alertas_honeytoken(limite: int = 15) -> list[dict[str, Any]]:
        """Consulta las alertas disparadas por los Honeytokens en 'sugerencias_locales'."""
        try:
            client = _get_client()
            resp = (
                client.table("sugerencias_locales")
                .select("id_ticket, sugerencia")
                .like("id_ticket", "HONEY-%")
                .order("id_ticket", desc=True)
                .limit(limite)
                .execute()
            )
            return list(resp.data or [])
        except Exception as exc:
            print(f"[CloudGateway.listar_alertas_honeytoken] ERROR: {exc}")
            return []

    @staticmethod
    def subir_ticket(ticket_id: str, dni: str, hw: dict, diag: dict) -> bool:
        """
        Construye el payload expandido y lo inserta en 'reportes_diagnostico'.
        Imprime el payload y cualquier error HTTP en consola para trazabilidad.

        Parámetros
        ----------
        ticket_id : str  — identificador único del ticket (ej. "USER-TICKET-8234")
        dni       : str  — DNI del operador activo
        hw        : dict — dict completo de LectorHardware.escanear_entorno()
        diag      : dict — dictamen final del motor de diagnóstico
        """
        from core.hardware import construir_resumen_para_bd

        payload = construir_resumen_para_bd(ticket_id, hw, diag, owner_dni=dni)

        print("\n" + "=" * 60)
        print(f"[CloudGateway] Enviando ticket {ticket_id} a Supabase...")
        print(f"[CloudGateway] Tabla: {TABLA_TICKETS}")
        print("[CloudGateway] Payload:")
        payload_log = {k: (v if k != "specs_json" else "{...JSON extendido...}") for k, v in payload.items()}
        print(_json.dumps(payload_log, indent=2, ensure_ascii=False))
        print("=" * 60)
        try:
            client = _get_client()
            response = (
                client.table(TABLA_TICKETS)
                .upsert(payload, on_conflict="id_ticket")
                .execute()
            )

            if response.data:
                print(f"[CloudGateway] [OK] Ticket {ticket_id} sincronizado (upsert). Filas: {len(response.data)}")
                return True
            else:
                print(f"[CloudGateway] [WARN] Insercion sin datos devueltos. response={response}")
                return False

        except Exception as exc:
            print(f"[CloudGateway] [ERROR] Excepcion al insertar ticket {ticket_id}:")
            print(f"  Tipo   : {type(exc).__name__}")
            print(f"  Mensaje: {exc}")
            traceback.print_exc()
            return False

    @staticmethod
    def listar_tickets_usuario(dni: str | None, limite: int = 120) -> list[dict[str, Any]]:
        """
        Devuelve únicamente los tickets en 'reportes_diagnostico' cuyo
        specs_json->>owner_dni coincide exactamente con el DNI autenticado.
        Por privacidad nunca devuelve tickets globales ni de otros operadores.
        """
        clean_dni = str(dni or "").strip()
        if not clean_dni or clean_dni.upper() in ("USER", "LOCAL", "NONE"):
            return []
        try:
            client = _get_client()
            resp = (
                client.table(TABLA_TICKETS)
                .select("id_ticket, cpu, placa_base, health_score, diagnostico, fecha_creacion, specs_json")
                .eq("specs_json->>owner_dni", clean_dni)
                .order("fecha_creacion", desc=True)
                .limit(limite)
                .execute()
            )
            return list(resp.data or [])
        except Exception as exc:
            print(f"[CloudGateway.listar_tickets_usuario] ERROR: {exc}")
            return []

    @staticmethod
    def subir_ticket_legacy(ticket_id: str, dni: str, hw: dict, diag: dict) -> bool:
        """Alias para compatibilidad con código anterior que llame al gateway directamente."""
        return CloudGateway.subir_ticket(ticket_id, dni, hw, diag)

    @staticmethod
    def subir_sugerencia(ticket_id: str, sugerencia_texto: str) -> bool:
        """
        Inserta o actualiza una fila en 'sugerencias_locales'.

        Parámetros
        ----------
        ticket_id        : str — ID unico del ticket (PK de la tabla).
        sugerencia_texto : str — Texto consolidado de todas las recomendaciones.
                           Si el motor genero multiples acciones, deben llegar
                           ya concatenadas en un unico string antes de llamar aqui.

        Usa upsert para evitar el error 23505 (duplicate key) si el ticket
        ya existe en la tabla.

        Payload enviado a PostgREST (estrictamente solo estas 2 claves):
            { "id_ticket": str, "sugerencia": str }
        """
        payload_sugerencia: dict[str, str] = {
            "id_ticket":  str(ticket_id),
            "sugerencia": str(sugerencia_texto),
        }

        print("\n" + "-" * 55)
        print("[CloudGateway.subir_sugerencia] Tabla: sugerencias_locales")
        print("[CloudGateway.subir_sugerencia] Payload:")
        print(_json.dumps(payload_sugerencia, indent=2, ensure_ascii=False))
        print("-" * 55)

        try:
            client = _get_client()
            response = (
                client.table("sugerencias_locales")
                .upsert(payload_sugerencia, on_conflict="id_ticket")
                .execute()
            )

            if response.data:
                print(f"[CloudGateway.subir_sugerencia] [OK] Sugerencia '{ticket_id}' persistida.")
                return True
            else:
                print(f"[CloudGateway.subir_sugerencia] [WARN] Upsert sin datos devueltos. response={response}")
                return False

        except Exception as exc:
            print(f"[CloudGateway.subir_sugerencia] [ERROR] {type(exc).__name__}: {exc}")
            traceback.print_exc()
            return False
