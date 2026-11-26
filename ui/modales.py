"""
ui/modales.py — Modales flotantes (Gemelo 3D, Reporte Final, Privacidad, Flota/Tickets y Sugerencias).
"""

from __future__ import annotations

import base64
import io
import json
import os
import random
import sys
import threading
import webbrowser
from tkinter import filedialog
import customtkinter as ctk
from PIL import Image, ImageOps

from core.cloud_gateway import CloudGateway
from core.diagnostico import EvaluadorTelemetria, obtener_dictamen
from core.gemelo_digital import abrir_gemelo_digital
from core.legal import POLITICA_PRIVACIDAD_TEXTO, VERSION_POLITICA
from core.security import clear_session_token
from core.ui_theme import (
    P,
    F_H1, F_H2, F_H3, F_SMALL, F_CAPTION,
    Badge,
    boton,
    tarjeta,
    entrada,
    overline,
    estilo_combo,
    estilo_tabview,
    estilo_textbox,
    estilizar_toplevel,
    toast,
)

COLOR_OK = P["primario"]
COLOR_ERR = P["rojo"]


def _comprimir_imagen_avatar(ruta: str) -> str:
    """Recorta a 192×192 y comprime a WebP/JPEG (<= 60 KB) devolviendo Data URI base64."""
    img = Image.open(ruta)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = ImageOps.fit(img, (192, 192), Image.Resampling.LANCZOS)

    for fmt, mime in (("WEBP", "image/webp"), ("JPEG", "image/jpeg")):
        for q in (82, 70, 56, 44):
            buf = io.BytesIO()
            try:
                img.save(buf, format=fmt, quality=q, method=4) if fmt == "WEBP" else img.save(
                    buf, format=fmt, quality=q, optimize=True
                )
            except Exception:
                break
            raw = buf.getvalue()
            if len(raw) <= 60_000:
                b64 = base64.b64encode(raw).decode("ascii")
                return f"data:{mime};base64,{b64}"
    raise ValueError("La imagen seleccionada no pudo comprimirse por debajo de 60 KB.")


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
            f.write(f"Código Interno: #{df['codigo']}\n\n")
            ficha_cpuz = EvaluadorTelemetria.generar_ficha_cpuz_texto(hw)
            if ficha_cpuz:
                f.write(ficha_cpuz + "\n")
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

    def modal_mi_cuenta(self):
        """Sección Mi Cuenta: foto de perfil, cambio de contraseña con OTP y eliminación total."""
        v = ctk.CTkToplevel(self)
        estilizar_toplevel(v, self, "Mi Cuenta y Seguridad — IndiServ Analytica", 720, 620)

        card = tarjeta(v)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        info = getattr(self, "usuario_activo_info", {}) or {}
        dni = str(self.dni_usuario_activo or info.get("dni") or "").strip()
        tok = getattr(self, "_session_token", None)

        enc = ctk.CTkFrame(card, fg_color="transparent")
        enc.pack(fill="x", padx=16, pady=(12, 6))
        ctk.CTkLabel(
            enc, text="👤 Mi Cuenta y Seguridad", font=F_H2, text_color=P["texto"]
        ).pack(side="left")
        Badge(enc, f"DNI {dni or 'LOCAL'}", tipo="info").pack(side="left", padx=(10, 0))
        boton(
            enc, "🛡️ Política v2.0", self.modal_politica_privacidad,
            variante="util", width=122, height=28, font=F_CAPTION
        ).pack(side="right")

        if not tok or not dni:
            ctk.CTkLabel(
                card,
                text="Inicie sesión con su cuenta verificada para administrar su foto de perfil, "
                     "cambiar su contraseña o eliminar su cuenta.",
                font=F_SMALL, text_color=P["texto_sec"], wraplength=600, justify="center"
            ).pack(pady=40)
            boton(card, "Cerrar", v.destroy, variante="neutro", width=120, height=34).pack()
            return

        tabs = ctk.CTkTabview(card, **estilo_tabview())
        tabs.pack(fill="both", expand=True, padx=14, pady=(2, 12))
        for tname in ("Perfil y Foto", "Equipos Confiables", "Cambiar Contraseña", "Eliminar Cuenta"):
            tabs.add(tname)

        # ── TAB 1: PERFIL Y FOTO ───────────────────────────────────────────────
        t_perf = tabs.tab("Perfil y Foto")
        fila_av = ctk.CTkFrame(t_perf, fg_color=P["surface"], corner_radius=12, border_width=1, border_color=P["borde"])
        fila_av.pack(fill="x", padx=12, pady=(10, 8))

        lbl_av = ctk.CTkLabel(
            fila_av, text="", width=96, height=96, corner_radius=48,
            fg_color=P["card_alt"], text_color=P["cian"], font=F_H1
        )
        lbl_av.pack(side="left", padx=18, pady=16)

        col_datos = ctk.CTkFrame(fila_av, fg_color="transparent")
        col_datos.pack(side="left", fill="both", expand=True, padx=(0, 14), pady=14)

        lbl_nick = ctk.CTkLabel(
            col_datos, text=str(info.get("nickname") or "Operador"),
            font=F_H2, text_color=P["texto"], anchor="w"
        )
        lbl_nick.pack(fill="x")
        lbl_correo = ctk.CTkLabel(
            col_datos, text=str(info.get("correo") or "Cargando correo…"),
            font=F_SMALL, text_color=P["cian"], anchor="w"
        )
        lbl_correo.pack(fill="x", pady=(2, 6))
        lbl_stats = ctk.CTkLabel(
            col_datos, text="Cargando estadísticas de dispositivos y tickets…",
            font=F_CAPTION, text_color=P["texto_sec"], anchor="w"
        )
        lbl_stats.pack(fill="x")

        lbl_av_msg = ctk.CTkLabel(t_perf, text="", font=F_SMALL, text_color=P["texto_sec"])
        lbl_av_msg.pack(anchor="w", padx=16, pady=(4, 4))

        def _pintar_avatar_modal(av_data: str | None):
            if not v.winfo_exists():
                return
            img = self._decodificar_avatar_ctk(av_data, size=92, cache_key="modal_account")
            if img is not None:
                lbl_av.configure(image=img, text="", fg_color="transparent")
            else:
                nick_txt = str(self.usuario_activo_info.get("nickname") or dni or "OP").strip()
                lbl_av.configure(image=None, text=nick_txt[:2].upper(), fg_color=P["card_alt"])

        _pintar_avatar_modal(info.get("avatar_data"))

        def _cargar_perfil_bg():
            res = CloudGateway.obtener_perfil_cuenta(tok, self._device_hash)

            def _apply():
                if not v.winfo_exists():
                    return
                if res.get("ok") and res.get("user"):
                    u = res["user"]
                    self.usuario_activo_info.update({
                        "dni": u.get("dni") or dni,
                        "correo": u.get("correo") or "",
                        "nickname": u.get("nickname") or "Operador",
                        "avatar_data": u.get("avatar_data"),
                    })
                    lbl_nick.configure(text=self.usuario_activo_info["nickname"])
                    lbl_correo.configure(text=self.usuario_activo_info["correo"])
                    lbl_stats.configure(
                        text=f"Dispositivos confiables: {u.get('dispositivos_confiables', 0)}   ·   "
                             f"Tickets guardados: {u.get('tickets_count', 0)}"
                    )
                    _pintar_avatar_modal(u.get("avatar_data"))
                    self._refrescar_avatar_topbar()
                elif res.get("session_expired"):
                    lbl_stats.configure(text="⚠ Tu sesión de 15 min expiró. Vuelve a iniciar sesión.", text_color=COLOR_ERR)

            self._post_ui(_apply)

        threading.Thread(target=_cargar_perfil_bg, daemon=True).start()

        def _subir_foto():
            ruta = filedialog.askopenfilename(
                parent=v,
                title="Seleccionar foto de perfil (PNG, JPG o WebP)",
                filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.webp")],
            )
            if not ruta:
                return
            try:
                data_uri = _comprimir_imagen_avatar(ruta)
            except Exception as exc:
                lbl_av_msg.configure(text=f"✖ No se pudo procesar la imagen: {exc}", text_color=COLOR_ERR)
                return

            btn_subir_av.configure(state="disabled", text="Guardando foto…")
            lbl_av_msg.configure(text="Validando firma binaria y guardando en Supabase…", text_color=P["texto_sec"])

            def _bg():
                res = CloudGateway.actualizar_avatar(tok, self._device_hash, data_uri)

                def _apply():
                    if not v.winfo_exists():
                        return
                    btn_subir_av.configure(state="normal", text="📷 Subir / Cambiar Foto")
                    if res.get("ok"):
                        self.usuario_activo_info["avatar_data"] = res.get("avatar_data")
                        _pintar_avatar_modal(res.get("avatar_data"))
                        self._refrescar_avatar_topbar()
                        lbl_av_msg.configure(text="✔ Foto de perfil actualizada correctamente.", text_color=COLOR_OK)
                    else:
                        lbl_av_msg.configure(
                            text=f"✖ {res.get('error') or res.get('error_conexion') or 'No se pudo actualizar la foto.'}",
                            text_color=COLOR_ERR,
                        )

                self._post_ui(_apply)

            threading.Thread(target=_bg, daemon=True).start()

        def _quitar_foto():
            btn_quitar_av.configure(state="disabled")
            lbl_av_msg.configure(text="Eliminando foto de perfil…", text_color=P["texto_sec"])

            def _bg():
                res = CloudGateway.actualizar_avatar(tok, self._device_hash, None)

                def _apply():
                    if not v.winfo_exists():
                        return
                    btn_quitar_av.configure(state="normal")
                    if res.get("ok"):
                        self.usuario_activo_info["avatar_data"] = None
                        _pintar_avatar_modal(None)
                        self._refrescar_avatar_topbar()
                        lbl_av_msg.configure(text="✔ Foto de perfil retirada.", text_color=COLOR_OK)
                    else:
                        lbl_av_msg.configure(
                            text=f"✖ {res.get('error') or 'Error al retirar foto.'}", text_color=COLOR_ERR
                        )

                self._post_ui(_apply)

            threading.Thread(target=_bg, daemon=True).start()

        acc_av = ctk.CTkFrame(t_perf, fg_color="transparent")
        acc_av.pack(fill="x", padx=14, pady=6)
        btn_subir_av = boton(
            acc_av, "📷 Subir / Cambiar Foto", _subir_foto,
            variante="primario", width=210, height=36, font=F_SMALL
        )
        btn_subir_av.pack(side="left", padx=(0, 8))
        btn_quitar_av = boton(
            acc_av, "🗑 Quitar Foto", _quitar_foto,
            variante="util", width=130, height=36, font=F_SMALL
        )
        btn_quitar_av.pack(side="left")

        info_seg = ctk.CTkFrame(t_perf, fg_color=P["surface"], corner_radius=10, border_width=1, border_color=P["borde"])
        info_seg.pack(fill="x", padx=12, pady=(14, 6))
        ctk.CTkLabel(
            info_seg,
            text="🔒 Privacidad de avatar: la imagen se recorta localmente a 192×192 px (≤ 60 KB), "
                 "se valida por magic bytes en servidor y se borra al instante si la retiras o eliminas tu cuenta.",
            font=F_CAPTION, text_color=P["texto_sec"], wraplength=600, justify="left", anchor="w"
        ).pack(fill="x", padx=14, pady=10)

        # ── TAB 2: EQUIPOS CONFIABLES (VERIFICAR Y REVOCAR) ───────────────────
        t_dev = tabs.tab("Equipos Confiables")
        dev_top = ctk.CTkFrame(t_dev, fg_color="transparent")
        dev_top.pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkLabel(
            dev_top,
            text="Administra las PCs, teléfonos y navegadores verificados con tu cuenta. "
                 "Al quitar un equipo se cierran sus sesiones activas y volverá a pedir OTP.",
            font=F_CAPTION, text_color=P["texto_sec"], wraplength=500, justify="left", anchor="w"
        ).pack(side="left", fill="x", expand=True)

        lbl_dev_msg = ctk.CTkLabel(t_dev, text="", font=F_SMALL, text_color=P["texto_sec"], anchor="w")
        lbl_dev_msg.pack(fill="x", padx=14, pady=(0, 4))

        scroll_devs = ctk.CTkScrollableFrame(t_dev, fg_color=P["bg"], corner_radius=10)
        scroll_devs.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        def _render_devices(devices: list[dict]):
            if not v.winfo_exists():
                return
            for w in scroll_devs.winfo_children():
                w.destroy()
            if not devices:
                ctk.CTkLabel(
                    scroll_devs,
                    text="No hay equipos confiables registrados actualmente.",
                    font=F_SMALL, text_color=P["texto_sec"]
                ).pack(pady=28)
                return

            for d in devices:
                d_id = str(d.get("id") or "")
                d_label = str(d.get("device_label") or "Dispositivo")
                plat = str(d.get("plataforma") or "desktop").lower()
                icono = "📱" if plat == "android" else ("🌐" if plat == "web" else "🖥️")
                es_actual = bool(d.get("is_current"))
                sesion_act = bool(d.get("sesion_activa"))
                uso_raw = str(d.get("ultimo_uso") or "")
                uso_fmt = uso_raw[:16].replace("T", " ") if len(uso_raw) >= 16 else "Reciente"

                fila = ctk.CTkFrame(
                    scroll_devs, fg_color=P["surface"], corner_radius=10,
                    border_width=1, border_color=P["cian"] if es_actual else P["borde"]
                )
                fila.pack(fill="x", padx=6, pady=4)

                col_info = ctk.CTkFrame(fila, fg_color="transparent")
                col_info.pack(side="left", fill="x", expand=True, padx=12, pady=8)

                hdr_d = ctk.CTkFrame(col_info, fg_color="transparent")
                hdr_d.pack(fill="x")
                ctk.CTkLabel(
                    hdr_d, text=f"{icono}  {d_label}",
                    font=F_H3, text_color=P["texto"], anchor="w"
                ).pack(side="left")
                if es_actual:
                    Badge(hdr_d, "ESTE EQUIPO", tipo="ok").pack(side="left", padx=(8, 0))
                elif sesion_act:
                    Badge(hdr_d, "SESIÓN ACTIVA", tipo="info").pack(side="left", padx=(8, 0))

                ctk.CTkLabel(
                    col_info,
                    text=f"Plataforma: {plat.upper()}  ·  Último acceso (UTC): {uso_fmt}",
                    font=F_CAPTION, text_color=P["texto_sec"], anchor="w"
                ).pack(fill="x", pady=(2, 0))

                def _revocar(dev_id=d_id, dev_lbl=d_label):
                    lbl_dev_msg.configure(text=f"Revocando acceso de {dev_lbl}…", text_color=P["texto_sec"])

                    def _bg_rev():
                        res = CloudGateway.revocar_dispositivo_confiable(tok, self._device_hash, dev_id)

                        def _apply_rev():
                            if not self.winfo_exists():
                                return
                            if res.get("session_expired"):
                                lbl_dev_msg.configure(text="⚠ Sesión expirada.", text_color=COLOR_ERR)
                                return
                            if res.get("ok"):
                                if res.get("revoked_current"):
                                    clear_session_token()
                                    self._session_token = None
                                    self.dni_usuario_activo = None
                                    self.usuario_activo_info = {}
                                    if v.winfo_exists():
                                        v.destroy()
                                    self.pantalla_login()
                                    toast(
                                        self,
                                        "Se revocó este equipo. Deberás verificar con OTP al volver a ingresar.",
                                        tipo="warn",
                                        duracion_ms=4500,
                                    )
                                    return
                                if v.winfo_exists():
                                    lbl_dev_msg.configure(
                                        text=f"✔ Acceso revocado para {res.get('device_label', dev_lbl)}.",
                                        text_color=COLOR_OK,
                                    )
                                    _cargar_devices_bg()
                                    threading.Thread(target=_cargar_perfil_bg, daemon=True).start()
                            else:
                                if v.winfo_exists():
                                    lbl_dev_msg.configure(
                                        text=f"✖ {res.get('error') or res.get('error_conexion') or 'No se pudo revocar.'}",
                                        text_color=COLOR_ERR,
                                    )

                        self._post_ui(_apply_rev)

                    threading.Thread(target=_bg_rev, daemon=True).start()

                boton(
                    fila, "🚫 Quitar acceso", _revocar,
                    variante="peligro" if not es_actual else "ambar",
                    width=132, height=30, font=F_CAPTION
                ).pack(side="right", padx=10, pady=10)

        def _cargar_devices_bg():
            if v.winfo_exists():
                for w in scroll_devs.winfo_children():
                    w.destroy()
                ctk.CTkLabel(
                    scroll_devs, text="Consultando equipos confiables en Supabase…",
                    font=F_SMALL, text_color=P["texto_sec"]
                ).pack(pady=24)

            def _bg():
                res = CloudGateway.listar_dispositivos_confiables(tok, self._device_hash)

                def _apply():
                    if not v.winfo_exists():
                        return
                    if res.get("ok"):
                        _render_devices(res.get("devices") or [])
                    elif res.get("session_expired"):
                        lbl_dev_msg.configure(text="⚠ Tu sesión de 15 min expiró.", text_color=COLOR_ERR)
                    else:
                        for w in scroll_devs.winfo_children():
                            w.destroy()
                        ctk.CTkLabel(
                            scroll_devs,
                            text=f"⚠ {res.get('error') or res.get('error_conexion') or 'No se pudieron cargar los equipos.'}",
                            font=F_SMALL, text_color=COLOR_ERR, wraplength=540
                        ).pack(pady=24)

                self._post_ui(_apply)

            threading.Thread(target=_bg, daemon=True).start()

        boton(
            dev_top, "⟳ Actualizar", _cargar_devices_bg,
            variante="util", width=104, height=28, font=F_CAPTION
        ).pack(side="right", padx=(8, 0))
        _cargar_devices_bg()

        # ── TAB 3: CAMBIAR CONTRASEÑA (CON DOBLE FACTOR OTP) ──────────────────
        t_pwd = tabs.tab("Cambiar Contraseña")
        pwd_state = {"challenge_id": "", "busy": False}

        ctk.CTkLabel(
            t_pwd,
            text="Por seguridad, cambiar tu contraseña exige tu clave actual y un código OTP enviado a tu correo. "
                 "Al confirmar, todas tus otras sesiones activas se cerrarán automáticamente.",
            font=F_CAPTION, text_color=P["texto_sec"], wraplength=620, justify="left", anchor="w"
        ).pack(fill="x", padx=14, pady=(10, 8))

        overline(t_pwd, "Contraseña Actual").pack(anchor="w", padx=14, pady=(2, 2))
        ent_pwd_cur = entrada(t_pwd, "••••••••", show="*", width=420)
        ent_pwd_cur.pack(fill="x", padx=14, pady=(0, 6))

        overline(t_pwd, "Nueva Contraseña (mínimo 8 caracteres)").pack(anchor="w", padx=14, pady=(2, 2))
        ent_pwd_new = entrada(t_pwd, "••••••••", show="*", width=420)
        ent_pwd_new.pack(fill="x", padx=14, pady=(0, 6))

        overline(t_pwd, "Confirmar Nueva Contraseña").pack(anchor="w", padx=14, pady=(2, 2))
        ent_pwd_rep = entrada(t_pwd, "••••••••", show="*", width=420)
        ent_pwd_rep.pack(fill="x", padx=14, pady=(0, 8))

        lbl_pwd_msg = ctk.CTkLabel(t_pwd, text="", font=F_SMALL, text_color=COLOR_ERR, wraplength=610, anchor="w")
        lbl_pwd_msg.pack(fill="x", padx=14, pady=(2, 6))

        marco_pwd_otp = ctk.CTkFrame(t_pwd, fg_color=P["surface"], corner_radius=10, border_width=1, border_color=P["borde"])
        overline(marco_pwd_otp, "Paso 2 — Código OTP de 6 dígitos enviado al correo", color=P["cian"]).pack(
            anchor="w", padx=12, pady=(8, 4)
        )
        fila_pwd_otp = ctk.CTkFrame(marco_pwd_otp, fg_color="transparent")
        fila_pwd_otp.pack(fill="x", padx=12, pady=(0, 10))
        ent_pwd_otp = entrada(fila_pwd_otp, "000000", width=180)
        ent_pwd_otp.configure(font=F_H2, justify="center")
        ent_pwd_otp.pack(side="left", padx=(0, 10))

        def _confirmar_cambio_pwd():
            if pwd_state["busy"] or not pwd_state["challenge_id"]:
                return
            code = ent_pwd_otp.get().strip()
            if len(code) != 6 or not code.isdigit():
                lbl_pwd_msg.configure(text="⚠ Ingrese los 6 dígitos del código OTP.", text_color=COLOR_ERR)
                return
            pwd_state["busy"] = True
            btn_pwd_verify.configure(state="disabled", text="Verificando OTP…")

            def _bg():
                res = CloudGateway.verificar_cambio_password(
                    tok, self._device_hash, pwd_state["challenge_id"], code
                )

                def _apply():
                    pwd_state["busy"] = False
                    if not v.winfo_exists():
                        return
                    btn_pwd_verify.configure(state="normal", text="✔ Confirmar Cambio")
                    if res.get("ok"):
                        pwd_state["challenge_id"] = ""
                        ent_pwd_cur.delete(0, "end")
                        ent_pwd_new.delete(0, "end")
                        ent_pwd_rep.delete(0, "end")
                        ent_pwd_otp.delete(0, "end")
                        marco_pwd_otp.pack_forget()
                        lbl_pwd_msg.configure(
                            text="✔ Contraseña actualizada. Se cerraron las demás sesiones activas y se envió un aviso a tu correo.",
                            text_color=COLOR_OK,
                        )
                        toast(self, "Contraseña actualizada con éxito.", tipo="ok")
                    else:
                        lbl_pwd_msg.configure(
                            text=f"✖ {res.get('error') or res.get('error_conexion') or 'Código incorrecto.'}",
                            text_color=COLOR_ERR,
                        )

                self._post_ui(_apply)

            threading.Thread(target=_bg, daemon=True).start()

        btn_pwd_verify = boton(
            fila_pwd_otp, "✔ Confirmar Cambio", _confirmar_cambio_pwd,
            variante="primario", width=190, height=38, font=F_SMALL
        )
        btn_pwd_verify.pack(side="left")

        def _iniciar_cambio_pwd():
            if pwd_state["busy"]:
                return
            c_cur = ent_pwd_cur.get().strip()
            c_new = ent_pwd_new.get().strip()
            c_rep = ent_pwd_rep.get().strip()
            if not c_cur or not c_new or not c_rep:
                lbl_pwd_msg.configure(text="⚠ Complete todos los campos de contraseña.", text_color=COLOR_ERR)
                return
            if len(c_new) < 8:
                lbl_pwd_msg.configure(text="⚠ La nueva contraseña debe tener mínimo 8 caracteres.", text_color=COLOR_ERR)
                return
            if c_new != c_rep:
                lbl_pwd_msg.configure(text="⚠ La confirmación no coincide con la nueva contraseña.", text_color=COLOR_ERR)
                return
            if c_cur == c_new:
                lbl_pwd_msg.configure(text="⚠ La nueva contraseña debe ser diferente a la actual.", text_color=COLOR_ERR)
                return

            pwd_state["busy"] = True
            btn_pwd_init.configure(state="disabled", text="Validando clave y enviando OTP…")
            lbl_pwd_msg.configure(text="")

            def _bg():
                res = CloudGateway.iniciar_cambio_password(
                    tok, self._device_hash, self._device_label, dni, c_cur, c_new
                )

                def _apply():
                    pwd_state["busy"] = False
                    if not v.winfo_exists():
                        return
                    btn_pwd_init.configure(state="normal", text="Paso 1: Enviar Código OTP al Correo")
                    if res.get("ok") and res.get("challenge_id"):
                        pwd_state["challenge_id"] = res["challenge_id"]
                        marco_pwd_otp.pack(fill="x", padx=14, pady=(4, 8))
                        lbl_pwd_msg.configure(
                            text=f"✔ Código de 6 dígitos enviado a {res.get('masked_email')}. Ingrésalo abajo.",
                            text_color=P["cian"],
                        )
                        ent_pwd_otp.focus_set()
                    else:
                        lbl_pwd_msg.configure(
                            text=f"✖ {res.get('error') or res.get('error_conexion') or 'No se pudo iniciar el cambio.'}",
                            text_color=COLOR_ERR,
                        )

                self._post_ui(_apply)

            threading.Thread(target=_bg, daemon=True).start()

        btn_pwd_init = boton(
            t_pwd, "Paso 1: Enviar Código OTP al Correo", _iniciar_cambio_pwd,
            variante="azul", width=300, height=36, font=F_SMALL
        )
        btn_pwd_init.pack(anchor="w", padx=14, pady=(0, 6))

        # ── TAB 3: ZONA DE PELIGRO — ELIMINAR CUENTA Y TICKETS ────────────────
        t_del = tabs.tab("Eliminar Cuenta")
        del_state = {"challenge_id": "", "busy": False}

        aviso_del = ctk.CTkFrame(t_del, fg_color=P["err_bg"], corner_radius=10, border_width=1, border_color="#7f1d1d")
        aviso_del.pack(fill="x", padx=14, pady=(10, 8))
        ctk.CTkLabel(
            aviso_del,
            text="⚠ ZONA DE PELIGRO — ACCIÓN IRREVERSIBLE (DERECHO ARCO)\n"
                 "Eliminar tu cuenta borrará permanentemente tu perfil, foto de perfil, sesiones activas, "
                 "dispositivos confiables y TODOS los tickets de diagnóstico y sugerencias vinculados a tu DNI.",
            font=F_SMALL, text_color="#fca5a5", wraplength=600, justify="left", anchor="w"
        ).pack(fill="x", padx=12, pady=10)

        overline(t_del, "Contraseña Actual").pack(anchor="w", padx=14, pady=(2, 2))
        ent_del_pwd = entrada(t_del, "••••••••", show="*", width=420)
        ent_del_pwd.pack(fill="x", padx=14, pady=(0, 6))

        overline(t_del, "Escriba ELIMINAR para confirmar").pack(anchor="w", padx=14, pady=(2, 2))
        ent_del_txt = entrada(t_del, "ELIMINAR", width=420)
        ent_del_txt.pack(fill="x", padx=14, pady=(0, 8))

        lbl_del_msg = ctk.CTkLabel(t_del, text="", font=F_SMALL, text_color=COLOR_ERR, wraplength=610, anchor="w")
        lbl_del_msg.pack(fill="x", padx=14, pady=(2, 6))

        marco_del_otp = ctk.CTkFrame(t_del, fg_color=P["surface"], corner_radius=10, border_width=1, border_color="#7f1d1d")
        overline(marco_del_otp, "Paso 2 — Código OTP Irreversible enviado al correo", color=P["rojo"]).pack(
            anchor="w", padx=12, pady=(8, 4)
        )
        fila_del_otp = ctk.CTkFrame(marco_del_otp, fg_color="transparent")
        fila_del_otp.pack(fill="x", padx=12, pady=(0, 10))
        ent_del_otp = entrada(fila_del_otp, "000000", width=180)
        ent_del_otp.configure(font=F_H2, justify="center")
        ent_del_otp.pack(side="left", padx=(0, 10))

        def _confirmar_eliminar():
            if del_state["busy"] or not del_state["challenge_id"]:
                return
            code = ent_del_otp.get().strip()
            if len(code) != 6 or not code.isdigit():
                lbl_del_msg.configure(text="⚠ Ingrese los 6 dígitos del código OTP.", text_color=COLOR_ERR)
                return
            del_state["busy"] = True
            btn_del_verify.configure(state="disabled", text="Eliminando cuenta y tickets…")

            def _bg():
                res = CloudGateway.verificar_eliminacion_cuenta(
                    tok, self._device_hash, del_state["challenge_id"], code
                )

                def _apply():
                    del_state["busy"] = False
                    if not self.winfo_exists():
                        return
                    if res.get("ok"):
                        n_tkt = res.get("tickets_eliminados", 0)
                        clear_session_token()
                        self._session_token = None
                        self.dni_usuario_activo = None
                        self.usuario_activo_info = {}
                        if v.winfo_exists():
                            v.destroy()
                        self.pantalla_login()
                        toast(
                            self,
                            f"Cuenta eliminada permanentemente ({n_tkt} ticket(s) borrados).",
                            tipo="ok",
                            duracion_ms=5000,
                        )
                    else:
                        if v.winfo_exists():
                            btn_del_verify.configure(state="normal", text="⚠ Eliminar Permanentemente")
                            lbl_del_msg.configure(
                                text=f"✖ {res.get('error') or res.get('error_conexion') or 'Código incorrecto.'}",
                                text_color=COLOR_ERR,
                            )

                self._post_ui(_apply)

            threading.Thread(target=_bg, daemon=True).start()

        btn_del_verify = boton(
            fila_del_otp, "⚠ Eliminar Permanentemente", _confirmar_eliminar,
            variante="peligro", width=230, height=38, font=F_SMALL
        )
        btn_del_verify.pack(side="left")

        def _iniciar_eliminar():
            if del_state["busy"]:
                return
            c_pwd = ent_del_pwd.get().strip()
            c_txt = ent_del_txt.get().strip().upper()
            if not c_pwd:
                lbl_del_msg.configure(text="⚠ Ingrese su contraseña actual.", text_color=COLOR_ERR)
                return
            if c_txt not in ("ELIMINAR", "ELIMINAR MI CUENTA", dni.upper()):
                lbl_del_msg.configure(text="⚠ Escriba ELIMINAR para habilitar la solicitud.", text_color=COLOR_ERR)
                return
            del_state["busy"] = True
            btn_del_init.configure(state="disabled", text="Enviando código OTP de confirmación…")
            lbl_del_msg.configure(text="")

            def _bg():
                res = CloudGateway.iniciar_eliminacion_cuenta(
                    tok, self._device_hash, self._device_label, dni, c_pwd, c_txt
                )

                def _apply():
                    del_state["busy"] = False
                    if not v.winfo_exists():
                        return
                    btn_del_init.configure(state="normal", text="Paso 1: Solicitar Código OTP de Eliminación")
                    if res.get("ok") and res.get("challenge_id"):
                        del_state["challenge_id"] = res["challenge_id"]
                        marco_del_otp.pack(fill="x", padx=14, pady=(4, 8))
                        lbl_del_msg.configure(
                            text=f"⚠ Código irreversible enviado a {res.get('masked_email')}. Ingrésalo abajo para borrar todo.",
                            text_color=P["ambar"],
                        )
                        ent_del_otp.focus_set()
                    else:
                        lbl_del_msg.configure(
                            text=f"✖ {res.get('error') or res.get('error_conexion') or 'No se pudo iniciar la eliminación.'}",
                            text_color=COLOR_ERR,
                        )

                self._post_ui(_apply)

            threading.Thread(target=_bg, daemon=True).start()

        btn_del_init = boton(
            t_del, "Paso 1: Solicitar Código OTP de Eliminación", _iniciar_eliminar,
            variante="peligro", width=330, height=36, font=F_SMALL
        )
        btn_del_init.pack(anchor="w", padx=14, pady=(0, 6))

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
