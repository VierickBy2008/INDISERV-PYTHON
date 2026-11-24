"""
ui/modales.py — Modales flotantes (Gemelo 3D, Reporte Final, Privacidad, Flota/Tickets y Sugerencias).
"""

from __future__ import annotations

import json
import os
import random
import sys
import threading
import webbrowser
import customtkinter as ctk

from core.cloud_gateway import CloudGateway
from core.diagnostico import obtener_dictamen
from core.gemelo_digital import abrir_gemelo_digital
from core.legal import POLITICA_PRIVACIDAD_TEXTO, VERSION_POLITICA
from core.ui_theme import (
    P,
    F_H2, F_H3, F_SMALL, F_CAPTION,
    Badge,
    boton,
    tarjeta,
    entrada,
    estilo_combo,
    estilo_textbox,
    estilizar_toplevel,
    toast,
)

COLOR_OK = P["primario"]
COLOR_ERR = P["rojo"]


def _obtener_carpeta_reportes() -> str:
    """Devuelve y crea la carpeta dedicada para reportes locales sin ensuciar la raíz del código."""
    if getattr(sys, "frozen", False):
        carpeta = os.path.join(os.path.expanduser("~"), "Documents", "IndiServ_Reportes")
    else:
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        carpeta = os.path.join(raiz, "reportes")
    try:
        os.makedirs(carpeta, exist_ok=True)
    except OSError:
        carpeta = os.path.join(os.getcwd(), "reportes")
        os.makedirs(carpeta, exist_ok=True)
    return carpeta


class ModalesMixin:
    """Mixin con los modales secundarios y visor Gemelo 3D."""

    def abrir_visor_3d(self, id_ticket: str | None = None):
        """
        Dispara el Gemelo Digital 3D en el navegador web pasando el id_ticket real.
        Funciona directamente desde el Dashboard sin necesidad de haber recorrido
        el Árbol de Diagnóstico, y espera la confirmación del upsert en Supabase
        para evitar condiciones de carrera donde el visor muestre el modelo demo.
        """
        if not id_ticket:
            id_ticket = self._asegurar_ticket()
        id_ticket = str(id_ticket).strip()

        hw = self.hardware_detectado or {}
        es_laptop = hw.get("tipo_equipo") == "laptop"
        df = self.dictamen_final or {
            "codigo": 0,
            "categoria": "Inspección General 3D",
            "subcategoria": f"Gemelo Digital ({'Laptop / Portátil' if es_laptop else 'PC de Escritorio'})",
            "solucion": "Auditoría visual 3D y perfil de telemetría generados directamente desde el Dashboard.",
        }

        def _sync_inmediato():
            exito = CloudGateway.subir_ticket(id_ticket, self.dni_usuario_activo or "USER", hw, df)
            if exito:
                self.ticket_sincronizado = bool(self.dictamen_final)
                print(f"[NUBE-3D] Ticket {id_ticket} sincronizado para Gemelo Digital 3D.")
            solucion_texto = str(df.get("solucion", "Sin recomendacion especifica.")).strip()
            CloudGateway.subir_sugerencia(id_ticket, solucion_texto)

        hilo_sync = threading.Thread(target=_sync_inmediato, daemon=True)
        hilo_sync.start()
        hilo_sync.join(timeout=4.0)

        enlace_completo = abrir_gemelo_digital(id_ticket, root_widget=self)
        self.modal_gemelo_digital(id_ticket, enlace_completo)
        return enlace_completo

    def modal_gemelo_digital(self, id_ticket: str, url: str):
        """Ventana emergente informativa de lanzamiento del Gemelo Digital 3D."""
        v = ctk.CTkToplevel(self)
        estilizar_toplevel(v, self, "Gemelo Digital 3D — IndiServ Analytica", 580, 340)

        card = tarjeta(v)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        enc = ctk.CTkFrame(card, fg_color="transparent")
        enc.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(
            enc, text="🌐 Gemelo Digital 3D en la Nube",
            font=F_H2, text_color=P["cian"]
        ).pack(side="left")
        Badge(enc, f"Ticket: {id_ticket}", tipo="info").pack(side="right")

        ctk.CTkLabel(
            card,
            text="El visor interactivo 3D se abrió en su navegador predeterminado y el enlace "
                 "público quedó copiado en el portapapeles.",
            font=F_SMALL, text_color=P["texto_sec"], wraplength=510, justify="left", anchor="w"
        ).pack(fill="x", padx=16, pady=(2, 8))

        entry_url = entrada(card, "", width=510)
        entry_url.insert(0, url)
        entry_url.configure(state="readonly")
        entry_url.pack(padx=16, pady=6, fill="x")

        lbl_copiado = ctk.CTkLabel(
            card,
            text=f"✔ Enlace público activo y copiado al portapapeles",
            font=F_SMALL, text_color=COLOR_OK
        )
        lbl_copiado.pack(pady=(2, 6))

        def copiar_portapapeles():
            try:
                self.clipboard_clear()
                self.clipboard_append(url)
                self.update()
                lbl_copiado.configure(text="✔ Enlace copiado nuevamente al portapapeles", text_color=COLOR_OK)
            except Exception as e:
                lbl_copiado.configure(text=f"Error al copiar: {e}", text_color=COLOR_ERR)

        btn_box = ctk.CTkFrame(card, fg_color="transparent")
        btn_box.pack(pady=10)

        boton(btn_box, "📋 Copiar Enlace", copiar_portapapeles,
              variante="azul", width=155, height=34, font=F_SMALL).pack(side="left", padx=6)
        boton(btn_box, "🌐 Reabrir Navegador", lambda: webbrowser.open(url),
              variante="primario", width=170, height=34, font=F_SMALL).pack(side="left", padx=6)
        boton(btn_box, "Cerrar", v.destroy,
              variante="neutro", width=100, height=34, font=F_SMALL).pack(side="left", padx=6)

    def guardar_reporte_final(self, permanecer: bool = False) -> tuple[str, str]:
        """Exporta el reporte en TXT y JSON, registra bitácora y sincroniza en la nube."""
        df = self.dictamen_final or obtener_dictamen(101)
        hw = self.hardware_detectado or {}
        ticket_id = self._asegurar_ticket()
        carpeta_reportes = _obtener_carpeta_reportes()

        nombre_txt = os.path.join(carpeta_reportes, f"Reporte_Diagnostico_{ticket_id}.txt")
        with open(nombre_txt, "w", encoding="utf-8") as f:
            f.write("================================================================\n")
            f.write("          REPORTE TÉCNICO DE DIAGNÓSTICO DE PC                  \n")
            f.write("================================================================\n")
            f.write(f"TICKET ID: {ticket_id}\n")
            f.write(f"OPERADOR DNI: {self.dni_usuario_activo}\n")
            f.write("----------------------------------------------------------------\n")
            f.write(f"CPU: {hw.get('nombre_cpu','?')}\n")
            f.write(f"Núcleos: {hw.get('nucleos_fisicos','?')} físicos / {hw.get('nucleos','?')} lógicos\n")
            f.write(f"Frecuencia: Base {hw.get('frecuencia_base_ghz','?')} GHz | Actual {hw.get('frecuencia_actual_ghz','?')} GHz\n")
            f.write(f"RAM Total: {hw.get('ram_total_mb','?')} | Tipo: {hw.get('ram_tipo','?')} @ {hw.get('ram_velocidad_mhz','?')} MHz\n")
            f.write(f"GPU: {hw.get('gpu_principal','?')}\n")
            f.write(f"Placa Base: {hw.get('mb_fabricante','?')} {hw.get('mb_modelo','?')}\n")
            f.write(f"BIOS: v{hw.get('bios_version','?')} [{hw.get('bios_fecha','?')}]\n")
            f.write(f"Sistema Operativo: {hw.get('so','?')} (Build {hw.get('so_build','?')})\n")
            f.write(f"Uptime: {hw.get('uptime','?')}\n")
            f.write("----------------------------------------------------------------\n")
            f.write(f"Categoría: {df['categoria']}\n")
            f.write(f"Subcategoría: {df['subcategoria']}\n")
            f.write(f"Falla detectada: {df['descripcion']}\n\n")
            f.write("GUÍA DE SOLUCIÓN:\n")
            f.write(f"{df['solucion']}\n")
            f.write(f"Código Interno: #{df['codigo']}\n")
            f.write("================================================================\n")

        nombre_json = os.path.join(carpeta_reportes, f"Reporte_Diagnostico_{ticket_id}.json")
        datos_json = {
            "ticket_id": ticket_id,
            "operador_dni": self.dni_usuario_activo,
            "telemetria": hw,
            "diagnostico": df,
        }
        with open(nombre_json, "w", encoding="utf-8") as f:
            json.dump(datos_json, f, indent=4, ensure_ascii=False)

        def tarea_nube():
            exito_ticket = CloudGateway.subir_ticket(ticket_id, self.dni_usuario_activo, hw, df)
            if exito_ticket:
                print(f"[NUBE] Ticket {ticket_id} sincronizado a Supabase.")
            else:
                print(f"[NUBE] Error al sincronizar ticket {ticket_id}.")

            solucion_texto = str(df.get("solucion", "Sin recomendacion especifica.")).strip()
            if not solucion_texto:
                solucion_texto = "Sin recomendacion especifica."
            CloudGateway.subir_sugerencia(ticket_id, solucion_texto)

        threading.Thread(target=tarea_nube, daemon=True).start()

        if not permanecer:
            self.pantalla_dashboard()
        toast(
            self,
            f"Reporte {ticket_id} guardado en {os.path.basename(carpeta_reportes)}/ (TXT + JSON) y sincronizando con Supabase.",
            tipo="ok",
        )
        return nombre_txt, nombre_json

    def modal_politica_privacidad(self, var_aceptar: ctk.BooleanVar | None = None):
        """Muestra la Política de Privacidad y Términos y Condiciones completos."""
        v = ctk.CTkToplevel(self)
        estilizar_toplevel(v, self, "Política de Privacidad y Términos — IndiServ Analytica", 680, 520)

        card = tarjeta(v)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        enc = ctk.CTkFrame(card, fg_color="transparent")
        enc.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(
            enc, text="🛡️ Política de Privacidad y Términos de Uso",
            font=F_H2, text_color=P["cian"]
        ).pack(side="left")
        Badge(enc, VERSION_POLITICA, tipo="info").pack(side="right")

        box = ctk.CTkTextbox(card, width=620, height=360, **estilo_textbox())
        box.pack(padx=14, pady=6, fill="both", expand=True)
        self._insertar_y_bloquear(box, POLITICA_PRIVACIDAD_TEXTO)

        fila_btn = ctk.CTkFrame(card, fg_color="transparent")
        fila_btn.pack(pady=(6, 12))

        if var_aceptar is not None:
            def _aceptar_y_cerrar():
                var_aceptar.set(True)
                v.destroy()
                toast(self, "Política de Privacidad y Términos aceptados.", tipo="ok", duracion_ms=2200)

            boton(
                fila_btn, "✔ He leído y Acepto los Términos",
                _aceptar_y_cerrar, variante="primario", width=250, height=34, font=F_SMALL
            ).pack(side="left", padx=6)

        boton(
            fila_btn, "Cerrar", v.destroy,
            variante="neutro", width=120, height=34, font=F_SMALL
        ).pack(side="left", padx=6)

    def modal_mis_tickets(self):
        v = ctk.CTkToplevel(self)
        estilizar_toplevel(v, self, "Centro de Flota y Reportes Privados", 820, 580)

        card = tarjeta(v)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        dni = (self.dni_usuario_activo or "").strip()
        dni_mask = f"••••{dni[-4:]}" if len(dni) >= 4 else (dni or "SIN SESIÓN")

        enc = ctk.CTkFrame(card, fg_color="transparent")
        enc.pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkLabel(
            enc, text="🔒 Centro de Flota y Reportes Privados",
            font=F_H2, text_color=P["texto"]
        ).pack(side="left")
        Badge(enc, f"Cuenta DNI {dni_mask}", tipo="ok" if dni else "warn").pack(side="right")

        lbl_resumen = ctk.CTkLabel(
            card,
            text="Organiza los reportes de todas tus PCs, Laptops y Teléfonos por fecha, dispositivo o salud.",
            font=F_SMALL, text_color=P["texto_sec"], anchor="w"
        )
        lbl_resumen.pack(fill="x", padx=14, pady=(0, 6))

        # Barra de controles de filtrado, agrupación y ordenamiento elegibles por el usuario
        controles = ctk.CTkFrame(card, fg_color=P["surface"], corner_radius=9, border_width=1, border_color=P["borde"])
        controles.pack(fill="x", padx=14, pady=(0, 6))

        fila_ctrl = ctk.CTkFrame(controles, fg_color="transparent")
        fila_ctrl.pack(fill="x", padx=10, pady=8)

        ent_filtro = entrada(fila_ctrl, "Filtrar por modelo, ID o error…", width=210, height=30, font=F_SMALL)
        ent_filtro.pack(side="left", padx=(0, 8))

        var_tipo = ctk.StringVar(value="Todos")
        var_agrupar = ctk.StringVar(value="Por Fecha")
        var_orden = ctk.StringVar(value="Más recientes")

        filas_cache: list[dict] = []

        def _tipo_item(item: dict) -> str:
            specs = item.get("specs_json") or {}
            t = str(specs.get("tipo_equipo") or "").lower()
            if t in ("phone", "smartphone", "tablet", "mobile"):
                return "Teléfono"
            if t == "laptop" or any(k in f"{item.get('placa_base', '')} {item.get('cpu', '')}".lower() for k in ("laptop", "lnvnb", "loq", "tuf", "victus")):
                return "Laptop"
            return "PC"

        def _modelo_item(item: dict) -> str:
            specs = item.get("specs_json") or {}
            m = str(specs.get("modelo_comercial") or "").strip()
            if m:
                return m
            return str(item.get("placa_base") or item.get("cpu") or "Equipo").strip()

        def _render_tickets(filas: list[dict]):
            if not v.winfo_exists():
                return
            for w in scroll.winfo_children():
                w.destroy()
            if not dni:
                ctk.CTkLabel(
                    scroll,
                    text="Inicie sesión con su cuenta para ver sus reportes privados.",
                    font=F_SMALL, text_color=P["texto_sec"]
                ).pack(pady=24)
                return
            if not filas:
                ctk.CTkLabel(
                    scroll,
                    text=f"Aún no tienes tickets guardados con tu cuenta ({dni_mask}).\n"
                         "Genera un diagnóstico o abre el Visor 3D para registrar tu primer reporte.",
                    font=F_SMALL, text_color=P["texto_sec"], justify="center"
                ).pack(pady=28)
                return

            kw = ent_filtro.get().strip().lower()
            f_tipo = var_tipo.get()
            f_agrupar = var_agrupar.get()
            f_orden = var_orden.get()

            filtradas = []
            for item in filas:
                t_lbl = _tipo_item(item)
                score = int(item.get("health_score", 100) or 0)
                errs = (item.get("specs_json") or {}).get("errores_detectados") or []
                if f_tipo == "Laptops" and t_lbl != "Laptop":
                    continue
                if f_tipo == "PCs" and t_lbl != "PC":
                    continue
                if f_tipo == "Teléfonos" and t_lbl != "Teléfono":
                    continue
                if f_tipo == "Con Alertas" and score >= 80 and not errs:
                    continue
                if kw:
                    hay = f"{item.get('id_ticket', '')} {_modelo_item(item)} {item.get('diagnostico', '')} {item.get('fecha_creacion', '')}".lower()
                    if kw not in hay:
                        continue
                filtradas.append(item)

            if f_orden == "Más antiguos":
                filtradas.sort(key=lambda x: str(x.get("fecha_creacion") or ""))
            elif f_orden == "Peor salud":
                filtradas.sort(key=lambda x: (int(x.get("health_score", 100) or 0), str(x.get("fecha_creacion") or "")))
            elif f_orden == "Mejor salud":
                filtradas.sort(key=lambda x: (-int(x.get("health_score", 100) or 0), str(x.get("fecha_creacion") or "")))
            elif f_orden == "Modelo (A-Z)":
                filtradas.sort(key=lambda x: _modelo_item(x).lower())
            else:
                filtradas.sort(key=lambda x: str(x.get("fecha_creacion") or ""), reverse=True)

            unicos = {f"{_tipo_item(x)}::{_modelo_item(x).lower()}" for x in filas}
            alertas_tot = sum(1 for x in filas if int(x.get("health_score", 100) or 0) < 80 or bool((x.get("specs_json") or {}).get("errores_detectados")))
            lbl_resumen.configure(
                text=f"Flota: {len(filas)} reportes · {len(unicos)} equipos distintos · {alertas_tot} con alertas  |  Mostrando {len(filtradas)}"
            )

            if not filtradas:
                ctk.CTkLabel(
                    scroll, text="No hay reportes que coincidan con el filtro aplicado.",
                    font=F_SMALL, text_color=P["texto_sec"]
                ).pack(pady=24)
                return

            grupos: list[tuple[str | None, list[dict]]] = []
            if f_agrupar == "Lista plana":
                grupos = [(None, filtradas)]
            else:
                mapa_g: dict[str, list[dict]] = {}
                for item in filtradas:
                    if f_agrupar == "Por Fecha":
                        f_raw = str(item.get("fecha_creacion") or "")
                        clave = f"📅 {f_raw[:10]}" if len(f_raw) >= 10 else "📅 Sin fecha"
                    else:
                        clave = f"💻 {_modelo_item(item)} ({_tipo_item(item)})"
                    mapa_g.setdefault(clave, []).append(item)
                grupos = list(mapa_g.items())

            for titulo_g, items_g in grupos:
                if titulo_g:
                    hdr = ctk.CTkFrame(scroll, fg_color="transparent")
                    hdr.pack(fill="x", padx=6, pady=(8, 2))
                    ctk.CTkLabel(
                        hdr, text=f"{titulo_g}  ({len(items_g)})",
                        font=F_H3, text_color=P["cian"], anchor="w"
                    ).pack(side="left")

                for item in items_g:
                    t_id = item.get("id_ticket", "?")
                    specs = item.get("specs_json") or {}
                    evento = specs.get("tipo_evento") or "Diagnóstico"
                    etiqueta_tipo = _tipo_item(item)
                    score = int(item.get("health_score", 100) or 0)
                    equipo = _modelo_item(item)
                    errs = specs.get("errores_detectados") or []
                    diag_txt = (item.get("diagnostico") or "").strip()
                    fecha_raw = str(item.get("fecha_creacion") or "")
                    fecha_fmt = fecha_raw[:16].replace("T", " ") if len(fecha_raw) >= 16 else ""

                    borde_c = P["rojo"] if score < 55 else (P["ambar"] if score < 80 or errs else P["borde"])
                    fila = ctk.CTkFrame(
                        scroll, fg_color=P["surface"], corner_radius=9,
                        border_width=1, border_color=borde_c
                    )
                    fila.pack(fill="x", padx=6, pady=3)

                    info_box = ctk.CTkFrame(fila, fg_color="transparent")
                    info_box.pack(side="left", fill="x", expand=True, padx=10, pady=7)

                    err_tag = f"  ·  ⚠ {len(errs)} alerta(s)" if errs else ""
                    meta_line = f"[{evento}]  {t_id}  ·  {etiqueta_tipo}  ·  Salud {score}/100{err_tag}"
                    if fecha_fmt:
                        meta_line += f"  ·  {fecha_fmt}"
                    ctk.CTkLabel(
                        info_box, text=meta_line,
                        font=F_SMALL, text_color=P["texto"], anchor="w"
                    ).pack(fill="x")
                    detalle = diag_txt if diag_txt else str(equipo)
                    ctk.CTkLabel(
                        info_box, text=f"{str(equipo)[:45]} — {detalle}"[:105],
                        font=F_CAPTION, text_color=P["texto_sec"], anchor="w"
                    ).pack(fill="x")

                    boton(
                        fila, "Abrir Reporte 3D",
                        lambda tid=t_id: webbrowser.open(f"https://indiserv-web3d.vercel.app/?ticket={tid}"),
                        variante="primario", width=124, height=30, font=F_SMALL
                    ).pack(side="right", padx=10, pady=8)

        def _cerrar_modal():
            try:
                v.grab_release()
            except Exception:
                pass
            try:
                v.destroy()
            except Exception:
                pass

        v.protocol("WM_DELETE_WINDOW", _cerrar_modal)

        def _refiltrar(_val=None):
            _render_tickets(filas_cache)

        estilo_opt = {k: val for k, val in estilo_combo().items() if k != "border_color"}
        ent_filtro.bind("<KeyRelease>", _refiltrar)
        ctk.CTkOptionMenu(
            fila_ctrl, variable=var_tipo,
            values=["Todos", "Laptops", "PCs", "Teléfonos", "Con Alertas"],
            command=_refiltrar, width=118, height=30, **estilo_opt
        ).pack(side="left", padx=(0, 6))
        ctk.CTkOptionMenu(
            fila_ctrl, variable=var_agrupar,
            values=["Por Fecha", "Por Equipo", "Lista plana"],
            command=_refiltrar, width=118, height=30, **estilo_opt
        ).pack(side="left", padx=(0, 6))
        ctk.CTkOptionMenu(
            fila_ctrl, variable=var_orden,
            values=["Más recientes", "Más antiguos", "Peor salud", "Mejor salud", "Modelo (A-Z)"],
            command=_refiltrar, width=132, height=30, **estilo_opt
        ).pack(side="left")

        scroll = ctk.CTkScrollableFrame(card, fg_color=P["bg"], corner_radius=8)
        scroll.pack(fill="both", expand=True, padx=14, pady=4)

        lbl_estado = ctk.CTkLabel(
            scroll, text="Consultando tus reportes privados en Supabase…",
            font=F_SMALL, text_color=P["texto_sec"]
        )
        lbl_estado.pack(pady=24)

        def _cargar_en_hilo():
            filas = CloudGateway.listar_tickets_usuario(dni, limite=120)
            filas_cache[:] = filas
            try:
                self.after(0, lambda f=list(filas): _render_tickets(f))
            except Exception:
                pass

        threading.Thread(target=_cargar_en_hilo, daemon=True).start()

        def _cargar_alertas():
            alertas = CloudGateway.listar_alertas_honeytoken()

            def _render_alertas():
                if not v.winfo_exists():
                    return
                for w in scroll.winfo_children():
                    w.destroy()
                if not alertas:
                    ctk.CTkLabel(
                        scroll,
                        text="✔ 0 alertas de Honeytoken disparadas.\nNingún intruso ha tocado las trampas señuelo.",
                        font=F_SMALL, text_color=COLOR_OK, justify="center"
                    ).pack(pady=28)
                    return
                for al in alertas:
                    fila = ctk.CTkFrame(
                        scroll, fg_color=P["surface"], corner_radius=8,
                        border_width=1, border_color=P["rojo"]
                    )
                    fila.pack(fill="x", padx=6, pady=4)
                    ctk.CTkLabel(
                        fila,
                        text=f"🍯 {al.get('id_ticket', 'HONEY')}  ·  {al.get('sugerencia', '')}",
                        font=F_CAPTION, text_color=P["texto"], anchor="w", wraplength=580, justify="left"
                    ).pack(fill="x", padx=10, pady=8)

            try:
                self.after(0, _render_alertas)
            except Exception:
                pass

        fila_b = ctk.CTkFrame(card, fg_color="transparent")
        fila_b.pack(pady=(6, 12))
        boton(
            fila_b, "⟳ Mis Tickets",
            lambda: threading.Thread(target=_cargar_en_hilo, daemon=True).start(),
            variante="neutro", width=130, height=32, font=F_SMALL
        ).pack(side="left", padx=6)
        boton(
            fila_b, "🍯 Alertas Honeytoken",
            lambda: threading.Thread(target=_cargar_alertas, daemon=True).start(),
            variante="ambar", width=175, height=32, font=F_SMALL
        ).pack(side="left", padx=6)
        boton(
            fila_b, "Cerrar", _cerrar_modal,
            variante="neutro", width=110, height=32, font=F_SMALL
        ).pack(side="left", padx=6)

    def modal_sugerencias(self):
        v = ctk.CTkToplevel(self)
        estilizar_toplevel(v, self, "Buzón de Soporte y Sugerencias", 560, 420)

        card = tarjeta(v)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        enc = ctk.CTkFrame(card, fg_color="transparent")
        enc.pack(fill="x", padx=14, pady=(12, 2))
        ctk.CTkLabel(enc, text="💡 Buzón Técnico de Soporte y Mejoras", font=F_H2, text_color=P["texto"]).pack(
            side="left"
        )
        Badge(enc, "Sync Supabase", tipo="info").pack(side="right")

        ctk.CTkLabel(
            card, text="Describa la observación, nuevo síntoma o mejora que desea registrar:",
            font=F_SMALL, text_color=P["texto_sec"], anchor="w"
        ).pack(fill="x", padx=14, pady=(2, 6))

        txt_sug = ctk.CTkTextbox(card, width=500, height=175, **estilo_textbox())
        txt_sug.pack(padx=14, pady=4, fill="both", expand=True)

        lbl_estado = ctk.CTkLabel(card, text="", font=F_SMALL)
        lbl_estado.pack(pady=4)

        def enviar_feedback():
            texto = txt_sug.get("0.0", "end").strip()
            if not texto:
                lbl_estado.configure(text="⚠ Ingrese una descripción válida.", text_color=COLOR_ERR)
                return

            t_id = f"SUG-{random.randint(10000, 99999)}"

            ruta_sug = os.path.join(_obtener_carpeta_reportes(), "sugerencias_locales.txt")
            with open(ruta_sug, "a", encoding="utf-8") as s:
                s.write(f"[{t_id}] {texto}\n")

            def _subir():
                CloudGateway.subir_sugerencia(t_id, texto)

            threading.Thread(target=_subir, daemon=True).start()

            lbl_estado.configure(
                text=f"✔ Sugerencia registrada y sincronizada. Ticket: {t_id}",
                text_color=COLOR_OK
            )
            txt_sug.delete("0.0", "end")

        fila_b = ctk.CTkFrame(card, fg_color="transparent")
        fila_b.pack(pady=(4, 12))
        boton(fila_b, "Enviar Sugerencia", enviar_feedback, variante="primario", width=190, height=34).pack(
            side="left", padx=6
        )
        boton(fila_b, "Cerrar", v.destroy, variante="neutro", width=110, height=34).pack(
            side="left", padx=6
        )
