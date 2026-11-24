"""
core/cloud_gateway.py — Capa de Persistencia en Supabase (Fase 3 + Auditoría)
==============================================================================
Usa supabase-py 2.x (PostgREST via httpx) en lugar de requests puro.
Logging explícito en consola para depuración de errores HTTP.
"""

from __future__ import annotations

import traceback
import json as _json
from typing import Any

from supabase import create_client, Client

SUPABASE_URL  = "https://pvrfnvrxaxulcxacdino.supabase.co"
SUPABASE_KEY  = "sb_publishable_G7D4dhh3Q2LWzgRnzRRa9A_4ngZ5FiW"

TABLA_TICKETS = "reportes_diagnostico"
TABLA_PADRON  = "padron_oficial"
TABLA_USUARIOS = "usuarios_app"


def _get_client() -> Client:
    """Crea y devuelve el cliente Supabase. Puede lanzar excepción si las credenciales son inválidas."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)


class CloudGateway:
    """
    Todos los métodos son @staticmethod para mantener compatibilidad con el
    código existente en main.py (se invocan como CloudGateway.metodo()).
    """

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
        except Exception:
            pass

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
    def listar_tickets_usuario(dni: str | None, limite: int = 20) -> list[dict[str, Any]]:
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
