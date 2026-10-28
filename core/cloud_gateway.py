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

# ---------------------------------------------------------------------------
# Credenciales (hardcoded — mover a .env en producción)
# ---------------------------------------------------------------------------
SUPABASE_URL  = "https://pvrfnvrxaxulcxacdino.supabase.co"
SUPABASE_KEY  = "sb_publishable_G7D4dhh3Q2LWzgRnzRRa9A_4ngZ5FiW"

# Tabla principal de tickets de diagnóstico
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

    # ------------------------------------------------------------------
    # AUTH / USUARIOS (sin cambios funcionales, preservados)
    # ------------------------------------------------------------------
    @staticmethod
    def consultar_padron(dni: str) -> dict:
        client = _get_client()
        try:
            resp = client.table(TABLA_PADRON).select("*").eq("dni", dni).execute()
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
    def consultar_usuario(dni: str) -> dict:
        client = _get_client()
        try:
            resp = client.table(TABLA_USUARIOS).select("*").eq("dni", dni).execute()
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
        client = _get_client()
        payload = {
            "dni": dni,
            "correo": correo,
            "password_hash": password,
            "nickname": nickname,
        }
        try:
            resp = client.table(TABLA_USUARIOS).insert(payload).execute()
            return bool(resp.data)
        except Exception as exc:
            print(f"[CloudGateway.registrar_usuario] ERROR: {exc}")
            return False

    # ------------------------------------------------------------------
    # TICKETS DE DIAGNÓSTICO (Fase 3 — tabla 'reportes_diagnostico')
    # ------------------------------------------------------------------
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
        from core.hardware import construir_resumen_para_bd  # import local para evitar circular

        payload = construir_resumen_para_bd(ticket_id, hw, diag)

        print("\n" + "=" * 60)
        print(f"[CloudGateway] Enviando ticket {ticket_id} a Supabase...")
        print(f"[CloudGateway] Tabla: {TABLA_TICKETS}")
        print("[CloudGateway] Payload:")
        # specs_json puede ser grande — se serializa y se muestra resumido
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

    # ------------------------------------------------------------------
    # Método legacy subir_ticket con firma antigua (compatibilidad)
    # ------------------------------------------------------------------
    @staticmethod
    def subir_ticket_legacy(ticket_id: str, dni: str, hw: dict, diag: dict) -> bool:
        """Alias para compatibilidad con código anterior que llame al gateway directamente."""
        return CloudGateway.subir_ticket(ticket_id, dni, hw, diag)

    # ------------------------------------------------------------------
    # SUGERENCIAS (tabla 'sugerencias_locales')
    # Esquema exacto: id_ticket (text PK), sugerencia (text)
    # ------------------------------------------------------------------
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