"""
main.py — IndiServ Analytica (Sistema Experto de Diagnóstico de PC)
===================================================================
El escaneo de hardware y las operaciones de red/benchmark se ejecutan en
hilos secundarios (threading.Thread) para que CustomTkinter nunca se congele.

Dashboard organizado en pestañas didácticas:
  • General      — Motherboard / BIOS / SO / Uptime / Score de Salud
  • CPU / RAM    — Frecuencias, barras por núcleo, módulos de memoria
  • Gráficos     — GPU(s) detectadas, VRAM, versión de driver
  • Discos       — Unidades físicas y particiones con alertas de saturación
  • Red          — Adaptador activo, IP local, latencia DNS y estado
"""

from __future__ import annotations

import json
import os
import sys
import random
import threading
import webbrowser
import customtkinter as ctk
import psutil
from PIL import Image


def _resource_path(relative_path: str) -> str:
    """Resuelve rutas de recursos tanto en desarrollo como dentro del .exe de PyInstaller."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

from core.hardware import LectorHardware, calcular_health_score, _inferir_refrigeracion
from core.cloud_gateway import CloudGateway
from core.security import (
    hash_password,
    verify_password,
    generate_secure_ticket_id,
    check_login_rate_limit,
    record_failed_login,
    reset_login_rate_limit,
    is_honey_credential,
    trigger_honeytoken_alert,
)
from core.diagnostico import (
    MotorDiagnostico,
    MatrizSintomas,
    BuscadorAsistido,
    MicroStressTest,
    CATALOGO_DICTAMENES,
    RAMAS_ARBOL,
    obtener_dictamen,
    rama_de_codigo,
    acciones_para,
    EvaluadorTelemetria,
)
from core.gemelo_digital import abrir_gemelo_digital
from core.hardware_map import MotherboardMapView
from core.legal import POLITICA_PRIVACIDAD_TEXTO, VERSION_POLITICA
from core.ui_theme import (
    P,
    F_H1, F_H2, F_H3, F_BODY, F_SMALL, F_CAPTION, F_MONO,
    Badge,
    BarraMetrica,
    TarjetaMetrica,
    PuntoPulso,
    Sparkline,
    boton,
    tarjeta,
    entrada,
    etiqueta,
    overline,
    estilo_checkbox,
    estilo_combo,
    estilo_segmentado,
    estilo_tabview,
    estilo_textbox,
    estilizar_toplevel,
    toast,
    nivel_por_umbral,
    color_por_umbral,
    animar_entrada_panel,
)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")


FONT_TITLE  = ("Segoe UI Semibold", 16)
FONT_LABEL  = ("Segoe UI", 13)
FONT_SMALL  = ("Segoe UI", 11)
FONT_MONO   = ("Consolas", 11)
COLOR_OK    = P["primario"]
COLOR_ERR   = P["rojo"]
COLOR_DIM   = P["neutro"]
COLOR_CYAN  = P["cian"]


class AppIndiServ(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("IndiServ Analytica — Sistema Experto de Diagnóstico de PC")
        self.geometry("980x700")
        self.resizable(False, False)
        self.configure(fg_color=P["bg"])

        self.bg_label = None
        fondo_path = _resource_path(os.path.join("assets", "fondo.jpg"))
        if os.path.exists(fondo_path):
            try:
                self.bg_image = ctk.CTkImage(Image.open(fondo_path), size=(980, 700))
                self.bg_label = ctk.CTkLabel(self, image=self.bg_image, text="")
                self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            except Exception:
                pass

        self.dni_usuario_activo: str | None = None
        self.hardware_detectado: dict | None = None

        self.arbol_fase = 0
        self.arbol_rama = -1
        self.arbol_paso = 0
        self.temp_gira_ventilador = False
        self.dictamen_final: dict | None = None
        self.ticket_id_actual: str | None = None
        self.ticket_sincronizado: bool = False
        self._vista_retorno_mapa = None

        self._stress_actual: MicroStressTest | None = None
        self._ultimo_resultado_stress: dict | None = None

        self.protocol("WM_DELETE_WINDOW", self._al_cerrar_ventana)
        self.pantalla_login()

    def _al_cerrar_ventana(self):
        if self._stress_actual and self._stress_actual.activo:
            try:
                self._stress_actual.cancelar()
            except Exception:
                pass
        self.destroy()

    def limpiar_panel(self):
        """Elimina todos los widgets excepto el fondo y detiene benchmarks en curso."""
        if self._stress_actual and self._stress_actual.activo:
            try:
                self._stress_actual.cancelar()
            except Exception:
                pass
        for widget in self.winfo_children():
            if widget != self.bg_label:
                widget.destroy()

    def _hw(self, clave: str, fallback: str = "N/A") -> str:
        """Acceso seguro al dict de hardware."""
        if not self.hardware_detectado:
            return fallback
        val = self.hardware_detectado.get(clave, fallback)
        return str(val) if val is not None else fallback

    @staticmethod
    def _num(val, default: float = 0.0) -> float:
        try:
            return float(str(val).replace("%", "").split()[0])
        except (TypeError, ValueError, IndexError):
            return default

    def _asegurar_ticket(self) -> str:
        if not getattr(self, "ticket_id_actual", None):
            self.ticket_id_actual = generate_secure_ticket_id(self.dni_usuario_activo, "TICKET")
        return str(self.ticket_id_actual).strip()

    def _registrar_evento_nube(
        self,
        tipo_evento: str,
        categoria: str,
        subcategoria: str,
        solucion: str,
        codigo: str | int = 0,
        prefijo_evento: str = "EVT",
        ticket_id_fijo: str | None = None,
    ) -> str | None:
        """
        Registra automáticamente un reporte en Supabase ('reportes_diagnostico')
        vinculado exclusivamente a self.dni_usuario_activo, en segundo plano.
        """
        dni = (self.dni_usuario_activo or "").strip()
        if not dni:
            return None
        hw = self.hardware_detectado or {}
        t_id = (ticket_id_fijo or generate_secure_ticket_id(dni, prefijo_evento)).strip()
        diag_payload = {
            "codigo": codigo,
            "tipo_evento": tipo_evento,
            "categoria": categoria,
            "subcategoria": subcategoria,
            "solucion": solucion,
        }

        def _bg_sync():
            try:
                CloudGateway.subir_ticket(t_id, dni, hw, diag_payload)
                CloudGateway.subir_sugerencia(t_id, str(solucion).strip() or "Registro automático.")
            except Exception as exc:
                print(f"[HistorialAuto] Error registrando {t_id}: {exc}")

        threading.Thread(target=_bg_sync, daemon=True).start()
        return t_id

    def _crear_encabezado_vista(
        self,
        parent,
        titulo: str,
        subtitulo: str,
        badge_texto: str = "",
        badge_tipo: str = "info",
        cmd_volver=None,
        texto_volver: str = "← Dashboard",
    ) -> ctk.CTkFrame:
        """Barra superior unificada para vistas internas."""
        header = ctk.CTkFrame(
            parent, fg_color=P["surface"], corner_radius=10,
            border_width=1, border_color=P["borde"]
        )
        header.pack(fill="x", padx=14, pady=(12, 6))

        izq = ctk.CTkFrame(header, fg_color="transparent")
        izq.pack(side="left", padx=14, pady=10, fill="x", expand=True)

        fila_t = ctk.CTkFrame(izq, fg_color="transparent")
        fila_t.pack(anchor="w")
        ctk.CTkLabel(fila_t, text=titulo, font=F_H2, text_color=P["texto"]).pack(side="left")
        if badge_texto:
            Badge(fila_t, badge_texto, tipo=badge_tipo).pack(side="left", padx=(10, 0))

        ctk.CTkLabel(
            izq, text=subtitulo, font=F_SMALL, text_color=P["texto_sec"],
            anchor="w", justify="left"
        ).pack(anchor="w", pady=(2, 0))

        der = ctk.CTkFrame(header, fg_color="transparent")
        der.pack(side="right", padx=14, pady=10)
        if cmd_volver:
            boton(der, texto_volver, cmd_volver, variante="neutro", width=140, height=32).pack(side="right")

        return header

    def pantalla_login(self):
        self.limpiar_panel()

        card = ctk.CTkFrame(
            self, width=440, height=495, corner_radius=0,
            fg_color=P["card"], border_width=1, border_color=P["borde_fuerte"]
        )
        animar_entrada_panel(card)
        card.pack_propagate(False)

        top = ctk.CTkFrame(card, fg_color=P["surface"], corner_radius=12)
        top.pack(fill="x", padx=18, pady=(18, 10))

        fila_brand = ctk.CTkFrame(top, fg_color="transparent")
        fila_brand.pack(fill="x", padx=14, pady=(12, 2))
        ctk.CTkLabel(
            fila_brand, text="◈  INDISERV ANALYTICA",
            font=("Segoe UI Semibold", 13), text_color=P["cian"]
        ).pack(side="left")
        Badge(fila_brand, "v3.0 · Cloud BaaS", tipo="info").pack(side="right")

        ctk.CTkLabel(
            top, text="Portal de Seguridad Técnica",
            font=F_H2, text_color=P["texto"], anchor="w"
        ).pack(fill="x", padx=14)
        ctk.CTkLabel(
            top, text="Autenticación de operador para telemetría y diagnóstico experto.",
            font=F_CAPTION, text_color=P["texto_sec"], anchor="w"
        ).pack(fill="x", padx=14, pady=(0, 12))

        cuerpo = ctk.CTkFrame(card, fg_color="transparent")
        cuerpo.pack(fill="x", padx=26, pady=4)

        overline(cuerpo, "DNI del Operador").pack(anchor="w", pady=(4, 2))
        self.entry_dni = entrada(cuerpo, "Ej. 75509123", width=388)
        self.entry_dni.pack(fill="x", pady=(0, 6))

        overline(cuerpo, "Correo Corporativo / Institucional").pack(anchor="w", pady=(4, 2))
        self.entry_correo = entrada(cuerpo, "operador@indiserv.pe", width=388)
        self.entry_correo.pack(fill="x", pady=(0, 6))

        overline(cuerpo, "Contraseña de Acceso").pack(anchor="w", pady=(4, 2))
        fila_pass = ctk.CTkFrame(cuerpo, fg_color="transparent")
        fila_pass.pack(fill="x")
        self.entry_pass = entrada(fila_pass, "••••••••", show="*", width=342)
        self.entry_pass.pack(side="left", fill="x", expand=True)
        self._ver_pass = False

        def _toggle_pass():
            self._ver_pass = not self._ver_pass
            self.entry_pass.configure(show="" if self._ver_pass else "*")
            btn_ojo.configure(text="Ocultar" if self._ver_pass else "Ver")

        btn_ojo = boton(fila_pass, "Ver", _toggle_pass, variante="neutro", width=56, height=38, font=F_CAPTION)
        btn_ojo.pack(side="left", padx=(6, 0))

        self.entry_pass.bind("<Return>", lambda e: self._iniciar_login_async())

        self.lbl_login_error = ctk.CTkLabel(
            card, text="", text_color=COLOR_ERR, font=F_SMALL, wraplength=380
        )
        self.lbl_login_error.pack(pady=(6, 2))

        acciones = ctk.CTkFrame(card, fg_color="transparent")
        acciones.pack(fill="x", padx=26, pady=(4, 8))

        self.btn_ingresar = boton(
            acciones, "Ingresar a Consola de Operaciones  →",
            self._iniciar_login_async, variante="primario", width=388, height=40
        )
        self.btn_ingresar.pack(fill="x", pady=(0, 8))

        boton(
            acciones, "Crear Nueva Cuenta de Operador",
            self.pantalla_registro, variante="fantasma", width=388, height=34
        ).pack(fill="x")

    def _iniciar_login_async(self):
        """
        Valida credenciales y, si son correctas, lanza el escaneo de hardware
        en un hilo secundario para no bloquear la GUI.
        """
        dni      = self.entry_dni.get().strip()
        correo   = self.entry_correo.get().strip()
        password = self.entry_pass.get().strip()

        if not dni or not correo or not password:
            self.lbl_login_error.configure(text="⚠ Complete DNI, correo electrónico y contraseña.")
            return

        permitido, espera_s = check_login_rate_limit()
        if not permitido:
            self.lbl_login_error.configure(
                text=f"⏳ Demasiados intentos fallidos. Intente nuevamente en {espera_s} s."
            )
            return

        if is_honey_credential(dni, correo):
            trigger_honeytoken_alert(
                tipo="CREDENCIAL_SENUELO_LOGIN_DESKTOP",
                detalle=f"Intento de acceso a cuenta trampa DNI='{dni}' correo='{correo}'",
            )
            self.lbl_login_error.configure(text="✖ Credenciales incorrectas o cuenta inexistente.")
            return

        if hasattr(self, "btn_ingresar"):
            self.btn_ingresar.configure(state="disabled", text="Verificando credenciales…")
        self.update_idletasks()

        auth_res = CloudGateway.autenticar_usuario_seguro(dni, correo, password)
        if auth_res.get("autenticado"):
            reset_login_rate_limit()
            self.dni_usuario_activo = dni
            self._mostrar_splash_carga()
        else:
            bloqueado, seg_lock = record_failed_login(dni, correo)
            if hasattr(self, "btn_ingresar"):
                self.btn_ingresar.configure(state="normal", text="Ingresar a Consola de Operaciones  →")
            if bloqueado:
                self.lbl_login_error.configure(
                    text=f"⏳ Cuenta protegida contra fuerza bruta. Espere {seg_lock} s."
                )
            else:
                self.lbl_login_error.configure(text="✖ Credenciales incorrectas o cuenta inexistente.")

    def _mostrar_splash_carga(self):
        """Reemplaza el login por un indicador de carga mientras el hilo trabaja."""
        self.limpiar_panel()

        frame = ctk.CTkFrame(
            self, width=420, height=220, corner_radius=0,
            fg_color=P["card"], border_width=1, border_color=P["borde_fuerte"]
        )
        animar_entrada_panel(frame)
        frame.pack_propagate(False)

        fila = ctk.CTkFrame(frame, fg_color="transparent")
        fila.pack(pady=(28, 6))
        self._pulso_splash = PuntoPulso(fila, color=P["cian"])
        self._pulso_splash.pack(side="left", padx=(0, 8))
        self._pulso_splash.iniciar()
        ctk.CTkLabel(
            fila, text="Escaneando Hardware del Equipo…", font=F_H2, text_color=P["texto"]
        ).pack(side="left")

        self._barra_carga = ctk.CTkProgressBar(
            frame, width=330, height=10, mode="indeterminate",
            fg_color=P["surface"], progress_color=P["primario"]
        )
        self._barra_carga.pack(pady=12)
        self._barra_carga.start()

        self._lbl_estado_carga = ctk.CTkLabel(
            frame,
            text="Consultando sensores WMI / psutil: CPU, RAM, GPU, Discos y Red…",
            font=F_SMALL, text_color=P["texto_sec"], wraplength=360
        )
        self._lbl_estado_carga.pack(pady=6)

        Badge(frame, f"Operador autenticado: {self.dni_usuario_activo}", tipo="ok").pack(pady=(4, 0))

        hilo = threading.Thread(target=self._hilo_escaneo_hardware, daemon=True)
        hilo.start()

    def _hilo_escaneo_hardware(self):
        """Ejecutado en hilo secundario: escanea hardware y luego notifica a la GUI."""
        try:
            self.hardware_detectado = LectorHardware.escanear_entorno()
            hw = self.hardware_detectado or {}
            score = calcular_health_score(hw)
            self._registrar_evento_nube(
                tipo_evento="Escaneo Inicial",
                categoria="Escaneo de Hardware",
                subcategoria=f"Telemetría inicial ({hw.get('so', 'OS')} · Salud {score}/100)",
                solucion="Escaneo automático inicial de CPU, RAM, GPU, discos y red completado.",
                prefijo_evento="SCAN",
            )
        except Exception as exc:
            self.hardware_detectado = {
                "nombre_cpu": "Error en escaneo",
                "nucleos": 1,
                "ram_total_mb": "? MB",
                "ram_disponible_mb": "? MB",
                "so": "Desconocido",
                "alerta_ram": False,
                "alerta_cpu": False,
                "_error": str(exc),
            }
        self.after(0, self.pantalla_dashboard)

    def pantalla_registro(self):
        self.limpiar_panel()

        frame = ctk.CTkFrame(
            self, width=460, height=605, corner_radius=0,
            fg_color=P["card"], border_width=1, border_color=P["borde_fuerte"]
        )
        animar_entrada_panel(frame)
        frame.pack_propagate(False)

        top = ctk.CTkFrame(frame, fg_color=P["surface"], corner_radius=12)
        top.pack(fill="x", padx=18, pady=(16, 8))
        ctk.CTkLabel(
            top, text="Registro de Operador Autorizado", font=F_H2, text_color=P["texto"], anchor="w"
        ).pack(fill="x", padx=14, pady=(10, 2))
        ctk.CTkLabel(
            top, text="Validación contra padrón oficial público UNMSM en Supabase.",
            font=F_CAPTION, text_color=P["texto_sec"], anchor="w"
        ).pack(fill="x", padx=14, pady=(0, 10))

        cuerpo = ctk.CTkFrame(frame, fg_color="transparent")
        cuerpo.pack(fill="x", padx=26)

        overline(cuerpo, "DNI (8 dígitos)").pack(anchor="w", pady=(4, 1))
        self.reg_dni = entrada(cuerpo, "DNI registrado en el padrón", width=390)
        self.reg_dni.pack(fill="x", pady=(0, 4))

        overline(cuerpo, "Alias / Nickname Técnico").pack(anchor="w", pady=(4, 1))
        self.reg_nick = entrada(cuerpo, "Ej. op_sistemas", width=390)
        self.reg_nick.pack(fill="x", pady=(0, 4))

        overline(cuerpo, "Correo Electrónico").pack(anchor="w", pady=(4, 1))
        self.reg_correo = entrada(cuerpo, "correo@dominio.com", width=390)
        self.reg_correo.pack(fill="x", pady=(0, 4))

        overline(cuerpo, "Contraseña").pack(anchor="w", pady=(4, 1))
        self.reg_pass = entrada(cuerpo, "Contraseña segura", show="*", width=390)
        self.reg_pass.pack(fill="x", pady=(0, 4))

        fila_legal_reg = ctk.CTkFrame(cuerpo, fg_color="transparent")
        fila_legal_reg.pack(fill="x", pady=(8, 2))
        self.reg_acepta_terminos = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            fila_legal_reg,
            text="Acepto la Política de Privacidad y Términos",
            variable=self.reg_acepta_terminos,
            **estilo_checkbox(),
        ).pack(side="left")
        boton(
            fila_legal_reg, "Leer Política",
            lambda: self.modal_politica_privacidad(var_aceptar=self.reg_acepta_terminos),
            variante="fantasma", width=96, height=26, font=F_CAPTION
        ).pack(side="right")

        self.lbl_reg_error = ctk.CTkLabel(
            frame, text="", text_color=COLOR_ERR, font=F_SMALL, wraplength=400
        )
        self.lbl_reg_error.pack(pady=4)

        acciones = ctk.CTkFrame(frame, fg_color="transparent")
        acciones.pack(fill="x", padx=26, pady=4)
        boton(acciones, "Registrar Cuenta en la Nube", self.procesar_registro,
              variante="primario", width=390, height=38).pack(fill="x", pady=(0, 6))
        boton(acciones, "← Volver al Login", self.pantalla_login,
              variante="fantasma", width=390, height=34).pack(fill="x")

    def procesar_registro(self):
        dni      = self.reg_dni.get().strip()
        nick     = self.reg_nick.get().strip()
        correo   = self.reg_correo.get().strip()
        password = self.reg_pass.get().strip()

        if not dni or not nick or not correo or not password:
            self.lbl_reg_error.configure(text="⚠ Llene todos los campos requeridos.")
            return

        if hasattr(self, "reg_acepta_terminos") and not self.reg_acepta_terminos.get():
            self.lbl_reg_error.configure(
                text="⚠ Debe leer y aceptar la Política de Privacidad y Términos antes de registrarse."
            )
            return

        if is_honey_credential(dni, correo):
            trigger_honeytoken_alert(
                tipo="CREDENCIAL_SENUELO_REGISTRO_DESKTOP",
                detalle=f"Intento de registro con identidad trampa DNI='{dni}' correo='{correo}'",
            )
            self.lbl_reg_error.configure(text="✖ El DNI no figura en el padrón oficial.")
            return

        padron = CloudGateway.consultar_padron(dni)
        if not padron.get("existe"):
            self.lbl_reg_error.configure(text="✖ El DNI no figura en el padrón oficial.")
            return

        if padron.get("ya_registrado") or CloudGateway.consultar_usuario(dni).get("registrado"):
            self.lbl_reg_error.configure(text="⚠ Este DNI ya tiene una cuenta registrada.")
            return

        exito = CloudGateway.registrar_usuario(dni, correo, password, nick)
        if exito:
            self.pantalla_login()
            toast(self, "Cuenta registrada exitosamente. Ya puede iniciar sesión.", tipo="ok")
        else:
            self.lbl_reg_error.configure(text="✖ Error de conexión al registrar. Intente luego.")

    def pantalla_dashboard(self):
        self.limpiar_panel()
        hw = self.hardware_detectado or {}
        score = calcular_health_score(hw)
        if score >= 80:
            t_score, lbl_score = "ok", f"Salud Global: {score}/100 · Óptimo"
        elif score >= 55:
            t_score, lbl_score = "warn", f"Salud Global: {score}/100 · Atención"
        else:
            t_score, lbl_score = "err", f"Salud Global: {score}/100 · Crítico"

        frame = ctk.CTkFrame(
            self, width=948, height=668, corner_radius=0,
            fg_color=P["bg"], border_width=1, border_color=P["borde"]
        )
        animar_entrada_panel(frame)
        frame.pack_propagate(False)

        topbar = ctk.CTkFrame(
            frame, fg_color=P["surface"], corner_radius=10,
            border_width=1, border_color=P["borde"]
        )
        topbar.pack(fill="x", padx=12, pady=(10, 6))

        izq = ctk.CTkFrame(topbar, fg_color="transparent")
        izq.pack(side="left", padx=14, pady=8)
        fila_tit = ctk.CTkFrame(izq, fg_color="transparent")
        fila_tit.pack(anchor="w")
        p_dot = PuntoPulso(fila_tit, color=P["primario"])
        p_dot.pack(side="left", padx=(0, 6))
        p_dot.iniciar()
        ctk.CTkLabel(
            fila_tit, text="Consola Central de Operaciones",
            font=F_H2, text_color=P["texto"]
        ).pack(side="left")
        Badge(fila_tit, f"Operador: {self.dni_usuario_activo or 'LOCAL'}", tipo="info").pack(
            side="left", padx=(10, 0)
        )
        Badge(fila_tit, lbl_score, tipo=t_score).pack(side="left", padx=(8, 0))

        der = ctk.CTkFrame(topbar, fg_color="transparent")
        der.pack(side="right", padx=12, pady=8)
        boton(der, "⟳ Re-escanear", self._reescanear_rapido,
              variante="neutro", width=118, height=30, font=F_SMALL).pack(side="left", padx=(0, 6))
        boton(der, "Cerrar Sesión", self.pantalla_login,
              variante="peligro", width=118, height=30, font=F_SMALL).pack(side="left")

        self.tabs_dashboard = ctk.CTkTabview(
            frame, width=922, height=455, **estilo_tabview()
        )
        self.tabs_dashboard.pack(pady=(0, 6), padx=12)

        for nombre in ("General", "CPU / RAM", "Gráficos", "Discos", "Red"):
            self.tabs_dashboard.add(nombre)

        self._tab_general(self.tabs_dashboard.tab("General"), hw)
        self._tab_cpu_ram(self.tabs_dashboard.tab("CPU / RAM"), hw)
        self._tab_graficos(self.tabs_dashboard.tab("Gráficos"), hw)
        self._tab_discos(self.tabs_dashboard.tab("Discos"), hw)
        self._tab_red(self.tabs_dashboard.tab("Red"), hw)

        dock = ctk.CTkFrame(
            frame, fg_color=P["surface"], corner_radius=10,
            border_width=1, border_color=P["borde"]
        )
        dock.pack(fill="x", padx=12, pady=(0, 10))

        fila1 = ctk.CTkFrame(dock, fg_color="transparent")
        fila1.pack(pady=(8, 4))

        boton(fila1, "1. Árbol de Diagnóstico", self.iniciar_diagnostico,
              variante="primario", width=215, height=36).grid(row=0, column=0, padx=5)
        boton(fila1, "2. Diagnóstico Multisíntoma", self.pantalla_multisintoma,
              variante="azul", width=225, height=36).grid(row=0, column=1, padx=5)
        boton(fila1, "3. Buscador Asistido IA", self.pantalla_buscador,
              variante="azul", width=215, height=36).grid(row=0, column=2, padx=5)
        boton(fila1, "4. Micro-Stress Test CPU", self.pantalla_stress_test,
              variante="violeta", width=215, height=36).grid(row=0, column=3, padx=5)

        fila2 = ctk.CTkFrame(dock, fg_color="transparent")
        fila2.pack(pady=(2, 8))

        boton(fila2, "🗺️ Mapa 2D de Hardware",
              lambda: self._abrir_mapa_desde_vista("", self.pantalla_dashboard),
              variante="ambar", width=175, height=32, font=F_SMALL).grid(row=0, column=0, padx=4)
        boton(fila2, "🌐 Visor Gemelo 3D", self.abrir_visor_3d,
              variante="neutro", width=165, height=32, font=F_SMALL).grid(row=0, column=1, padx=4)
        boton(fila2, "🔒 Mis Tickets", self.modal_mis_tickets,
              variante="azul", width=155, height=32, font=F_SMALL).grid(row=0, column=2, padx=4)
        boton(fila2, "5. Sugerencias", self.modal_sugerencias,
              variante="neutro", width=150, height=32, font=F_SMALL).grid(row=0, column=3, padx=4)
        boton(fila2, "🛡️ Privacidad", self.modal_politica_privacidad,
              variante="fantasma", width=140, height=32, font=F_SMALL).grid(row=0, column=4, padx=4)

    def _reescanear_rapido(self):
        toast(self, "Actualizando telemetría del equipo en segundo plano…", tipo="info", duracion_ms=1800)

        def _bg():
            try:
                self.hardware_detectado = LectorHardware.escanear_entorno()
                hw = self.hardware_detectado or {}
                score = calcular_health_score(hw)
                self._registrar_evento_nube(
                    tipo_evento="Re-escaneo Hardware",
                    categoria="Re-escaneo de Telemetría",
                    subcategoria=f"Actualización manual ({hw.get('so', 'OS')} · Salud {score}/100)",
                    solucion="Re-escaneo de sensores y estado de hardware registrado en el historial.",
                    prefijo_evento="SCAN",
                )
            except Exception:
                pass
            self.after(0, self.pantalla_dashboard)

        threading.Thread(target=_bg, daemon=True).start()

    def _textbox(self, parent, height=360) -> ctk.CTkTextbox:
        """Crea y retorna un CTkTextbox estilizado."""
        tb = ctk.CTkTextbox(parent, width=820, height=height, **estilo_textbox())
        tb.pack(padx=8, pady=6, fill="both", expand=True)
        return tb

    def _insertar_y_bloquear(self, tb: ctk.CTkTextbox, texto: str):
        tb.configure(state="normal")
        tb.delete("0.0", "end")
        tb.insert("0.0", texto)
        tb.configure(state="disabled")

    def _fila_dato(self, parent, clave: str, valor: str, badge: tuple[str, str] | None = None):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=12, pady=3)
        ctk.CTkLabel(
            f, text=clave, font=F_SMALL, text_color=P["texto_dim"], width=155, anchor="w"
        ).pack(side="left")
        ctk.CTkLabel(
            f, text=str(valor), font=("Segoe UI Semibold", 12),
            text_color=P["texto"], anchor="w"
        ).pack(side="left", fill="x", expand=True)
        if badge:
            Badge(f, badge[0], tipo=badge[1]).pack(side="right")

    def _tab_general(self, tab, hw: dict):
        score = calcular_health_score(hw)
        refrig = _inferir_refrigeracion(hw)
        evidencias = EvaluadorTelemetria.evaluar(hw)

        kpis = ctk.CTkFrame(tab, fg_color="transparent")
        kpis.pack(fill="x", padx=8, pady=(6, 6))
        for col in range(4):
            kpis.grid_columnconfigure(col, weight=1, uniform="kpi")

        TarjetaMetrica(
            kpis, "SCORE DE SALUD", f"{score}/100",
            "Auditoría automática de subsistemas",
            color=color_por_umbral(100 - score, warn=20, err=45)
        ).grid(row=0, column=0, padx=4, sticky="nsew")

        TarjetaMetrica(
            kpis, "SISTEMA OPERATIVO", str(hw.get("so", "Desconocido")),
            f"Build {hw.get('so_build', 'N/A')} · Uptime {hw.get('uptime', 'N/A')}",
            color=P["cian"]
        ).grid(row=0, column=1, padx=4, sticky="nsew")

        TarjetaMetrica(
            kpis, "PERFIL TÉRMICO", refrig[:24],
            f"CPU uso actual: {hw.get('uso_cpu_total', 0)}%",
            color=P["primario"]
        ).grid(row=0, column=2, padx=4, sticky="nsew")

        n_ev = len(evidencias)
        TarjetaMetrica(
            kpis, "ALERTAS ACTIVAS",
            "0 anomalías" if n_ev == 0 else f"{n_ev} detectada(s)",
            "Telemetría en rango nominal" if n_ev == 0 else "Revise recomendaciones abajo",
            color=P["primario"] if n_ev == 0 else P["ambar"]
        ).grid(row=0, column=3, padx=4, sticky="nsew")

        cuerpo = ctk.CTkFrame(tab, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=8, pady=4)
        cuerpo.grid_columnconfigure(0, weight=3)
        cuerpo.grid_columnconfigure(1, weight=2)
        cuerpo.grid_rowconfigure(0, weight=1)

        c_mb = tarjeta(cuerpo)
        c_mb.grid(row=0, column=0, padx=(0, 6), sticky="nsew")
        overline(c_mb, "Placa Base, Firmware BIOS y Entorno", color=P["cian"]).pack(
            anchor="w", padx=12, pady=(10, 6)
        )
        es_laptop = hw.get("tipo_equipo") == "laptop"
        self._fila_dato(
            c_mb,
            "Tipo de Equipo",
            "Laptop / Portátil" if es_laptop else "PC de Escritorio",
            ("PORTÁTIL", "info") if es_laptop else ("ESCRITORIO", "info"),
        )
        modelo_eq_txt = hw.get("equipo_modelo_comercial") or f"{hw.get('mb_fabricante', '?')} {hw.get('mb_modelo', '?')}"
        es_oem = bool(hw.get("equipo_es_oem"))
        badge_modelo = (
            ("LAPTOP OEM", "info")
            if (es_laptop and es_oem)
            else (("EQUIPO OEM", "info") if es_oem else ("PERSONALIZADO", "neutro"))
        )
        self._fila_dato(c_mb, "Modelo del Equipo", modelo_eq_txt, badge_modelo)
        self._fila_dato(c_mb, "Fabricante Placa", hw.get("mb_fabricante", "N/A"))
        self._fila_dato(
            c_mb,
            "Modelo de Placa",
            hw.get("mb_modelo", "N/A"),
            ("PCB PORTÁTIL" if es_laptop else "PCB ATX", "info"),
        )
        self._fila_dato(c_mb, "Proveedor BIOS", hw.get("bios_fabricante", "N/A"))
        self._fila_dato(
            c_mb, "Versión / Fecha BIOS",
            f"v{hw.get('bios_version', '?')}  [{hw.get('bios_fecha', '?')}]"
        )
        self._fila_dato(c_mb, "Refrigeración Inferida", refrig)
        self._fila_dato(
            c_mb, "Procesador Principal", hw.get("nombre_cpu", "N/A")
        )
        self._fila_dato(c_mb, "Gráficos Primarios", hw.get("gpu_principal", "N/A"))

        lic = hw.get("licencia_windows") if isinstance(hw.get("licencia_windows"), dict) else {}
        if sys.platform == "win32" or lic.get("aplicable"):
            est_lic = str(lic.get("estado") or "No verificada")
            pk = str(lic.get("partial_key") or "").strip()
            dias = lic.get("dias_restantes")
            if lic.get("sospecha_kms") and dias:
                val_lic = f"KMS No Oficial · Vence en {dias} días" + (f" · …{pk}" if pk else "")
            else:
                uefi_tag = " (UEFI)" if lic.get("tiene_llave_uefi") and lic.get("canal", "").startswith("OEM") else ""
                val_lic = f"{est_lic}{uefi_tag}" + (f" · …{pk}" if pk else "")
            self._fila_dato(
                c_mb,
                "Licencia Windows",
                val_lic,
                (lic.get("etiqueta_badge", "INFO"), lic.get("tipo_badge", "info")),
            )
            detalle_lic = str(lic.get("detalle") or "").strip()
            if detalle_lic:
                ctk.CTkLabel(
                    c_mb,
                    text=f"ℹ {detalle_lic}",
                    font=F_CAPTION,
                    text_color=P["texto_dim"],
                    anchor="w",
                    wraplength=470,
                    justify="left",
                ).pack(fill="x", padx=12, pady=(0, 6))

        c_ev = tarjeta(cuerpo)
        c_ev.grid(row=0, column=1, padx=(6, 0), sticky="nsew")
        overline(c_ev, "Observaciones Didácticas en Vivo", color=P["ambar"]).pack(
            anchor="w", padx=12, pady=(10, 6)
        )

        BarraMetrica(
            c_ev, "Índice de Salud del Sistema", score,
            f"{score}%", warn=101, err=101
        ).pack(fill="x", padx=12, pady=(2, 8))

        if not evidencias:
            Badge(c_ev, "✔ Todos los indicadores dentro de parámetros normales", tipo="ok").pack(
                anchor="w", padx=12, pady=6
            )
            ctk.CTkLabel(
                c_ev,
                text="Puede usar el Buscador Asistido si experimenta fallas intermitentes "
                     "o lanzar el Micro-Stress Test para validar estabilidad térmica bajo carga.",
                font=F_SMALL, text_color=P["texto_sec"], wraplength=320, justify="left"
            ).pack(anchor="w", padx=12, pady=4)
        else:
            for e in evidencias[:3]:
                fila_e = ctk.CTkFrame(c_ev, fg_color=P["surface"], corner_radius=8)
                fila_e.pack(fill="x", padx=12, pady=3)
                Badge(fila_e, "ALERTA", tipo=e["nivel"]).pack(side="left", padx=8, pady=6)
                ctk.CTkLabel(
                    fila_e, text=e["texto"], font=F_SMALL, text_color=P["texto"],
                    wraplength=235, justify="left"
                ).pack(side="left", padx=(0, 8), pady=6)
                cod = e["codigos"][0]
                boton(
                    fila_e, "Diagnosticar",
                    lambda c=cod: self.ejecutar_diagnostico_directo(c),
                    variante="ambar", width=92, height=26, font=F_CAPTION
                ).pack(side="right", padx=6)

    def _tab_cpu_ram(self, tab, hw: dict):
        cont = ctk.CTkFrame(tab, fg_color="transparent")
        cont.pack(fill="both", expand=True, padx=6, pady=4)
        cont.grid_columnconfigure(0, weight=1, uniform="cr")
        cont.grid_columnconfigure(1, weight=1, uniform="cr")
        cont.grid_rowconfigure(0, weight=1)

        c_cpu = tarjeta(cont)
        c_cpu.grid(row=0, column=0, padx=(0, 5), sticky="nsew")

        enc_cpu = ctk.CTkFrame(c_cpu, fg_color="transparent")
        enc_cpu.pack(fill="x", padx=12, pady=(10, 2))
        overline(enc_cpu, "Unidad Central de Procesamiento (CPU)", color=P["cian"]).pack(side="left")
        uso_cpu = self._num(hw.get("uso_cpu_total", 0))
        Badge(
            enc_cpu, f"{hw.get('nucleos_fisicos', '?')}C / {hw.get('nucleos', '?')}T",
            tipo="info"
        ).pack(side="right")

        ctk.CTkLabel(
            c_cpu, text=str(hw.get("nombre_cpu", "Procesador no identificado")),
            font=F_H3, text_color=P["texto"], anchor="w", wraplength=410
        ).pack(fill="x", padx=12, pady=(0, 4))

        ctk.CTkLabel(
            c_cpu,
            text=f"Frecuencia base: {hw.get('frecuencia_base_ghz', '?')} GHz   ·   "
                 f"Frecuencia actual: {hw.get('frecuencia_actual_ghz', '?')} GHz",
            font=F_SMALL, text_color=P["texto_sec"], anchor="w"
        ).pack(fill="x", padx=12, pady=(0, 6))

        BarraMetrica(
            c_cpu, "Carga Global de CPU", uso_cpu, f"{uso_cpu:.1f}%", warn=70, err=90
        ).pack(fill="x", padx=12, pady=(0, 8))

        overline(c_cpu, "Distribución por Hilo Lógico").pack(anchor="w", padx=12)
        scroll_cores = ctk.CTkScrollableFrame(
            c_cpu, fg_color=P["surface"], corner_radius=8, height=210
        )
        scroll_cores.pack(fill="both", expand=True, padx=12, pady=(4, 10))
        scroll_cores.grid_columnconfigure(0, weight=1)
        scroll_cores.grid_columnconfigure(1, weight=1)

        usos = hw.get("uso_por_nucleo", []) or []
        for idx, pct in enumerate(usos):
            celda = ctk.CTkFrame(scroll_cores, fg_color="transparent")
            celda.grid(row=idx // 2, column=idx % 2, padx=6, pady=3, sticky="ew")
            BarraMetrica(
                celda, f"Core #{idx}", float(pct), f"{ float(pct):.0f}%",
                warn=75, err=92, alto_barra=6
            ).pack(fill="x")

        c_ram = tarjeta(cont)
        c_ram.grid(row=0, column=1, padx=(5, 0), sticky="nsew")

        enc_ram = ctk.CTkFrame(c_ram, fg_color="transparent")
        enc_ram.pack(fill="x", padx=12, pady=(10, 2))
        overline(enc_ram, "Subsistema de Memoria Principal (RAM)", color=P["primario"]).pack(side="left")
        Badge(
            enc_ram,
            f"{hw.get('ram_tipo', 'DDR')} @ {hw.get('ram_velocidad_mhz', '?')} MHz",
            tipo="ok"
        ).pack(side="right")

        ctk.CTkLabel(
            c_ram,
            text=f"Total: {hw.get('ram_total_mb', '?')}   ·   Disponible: {hw.get('ram_disponible_mb', '?')}",
            font=F_H3, text_color=P["texto"], anchor="w"
        ).pack(fill="x", padx=12, pady=(0, 4))

        ctk.CTkLabel(
            c_ram,
            text=f"Ranuras DIMM ocupadas: {hw.get('ram_ranuras_ocupadas', '?')}   ·   "
                 f"Canal dual activo: {'Sí' if (hw.get('ram_ranuras_ocupadas') or 0) >= 2 else 'Simple'}",
            font=F_SMALL, text_color=P["texto_sec"], anchor="w"
        ).pack(fill="x", padx=12, pady=(0, 6))

        uso_ram = self._num(hw.get("ram_uso_pct", 0))
        BarraMetrica(
            c_ram, "Uso de Memoria Física", uso_ram, f"{uso_ram:.1f}%", warn=75, err=90
        ).pack(fill="x", padx=12, pady=(0, 8))

        overline(c_ram, "Módulos Físicos Detectados (SMBIOS)").pack(anchor="w", padx=12)
        scroll_ram = ctk.CTkScrollableFrame(
            c_ram, fg_color=P["surface"], corner_radius=8, height=210
        )
        scroll_ram.pack(fill="both", expand=True, padx=12, pady=(4, 10))

        modulos = hw.get("ram_modulos", []) or []
        if not modulos:
            ctk.CTkLabel(
                scroll_ram, text="Sin detalle individual de slots vía WMI.",
                font=F_SMALL, text_color=P["texto_dim"]
            ).pack(anchor="w", padx=8, pady=8)
        for i, m in enumerate(modulos, 1):
            item = ctk.CTkFrame(
                scroll_ram, fg_color=P["card_alt"], corner_radius=8,
                border_width=1, border_color=P["borde"]
            )
            item.pack(fill="x", padx=4, pady=4)
            f1 = ctk.CTkFrame(item, fg_color="transparent")
            f1.pack(fill="x", padx=10, pady=(6, 2))
            ctk.CTkLabel(
                f1, text=f"Slot #{i} · {m.get('ranura', 'DIMM')}",
                font=F_H3, text_color=P["texto"]
            ).pack(side="left")
            Badge(f1, f"{m.get('capacidad_gb', '?')} GB", tipo="info").pack(side="right")
            ctk.CTkLabel(
                item,
                text=f"Tipo: {m.get('tipo', '?')}   ·   Frecuencia: {m.get('velocidad_mhz', '?')} MHz   ·   "
                     f"Banco: {m.get('banco', 'N/A')}",
                font=F_CAPTION, text_color=P["texto_sec"], anchor="w"
            ).pack(fill="x", padx=10, pady=(0, 6))

    def _tab_graficos(self, tab, hw: dict):
        gpus = hw.get("gpus", []) or []
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=6, pady=4)

        if not gpus:
            c = tarjeta(scroll)
            c.pack(fill="x", padx=6, pady=6)
            Badge(c, "⚠ No se detectaron adaptadores gráficos dedicados/integrados", tipo="warn").pack(
                anchor="w", padx=14, pady=14
            )
            return

        for i, g in enumerate(gpus, 1):
            c = tarjeta(scroll)
            c.pack(fill="x", padx=6, pady=6)
            enc = ctk.CTkFrame(c, fg_color="transparent")
            enc.pack(fill="x", padx=14, pady=(12, 4))
            overline(enc, f"Adaptador Gráfico #{i}", color=P["cian"]).pack(side="left")
            vram = self._num(g.get("vram_mb", 0))
            Badge(
                enc, f"VRAM: {g.get('vram_mb', '?')} MB",
                tipo="ok" if vram >= 2048 else "info"
            ).pack(side="right")

            ctk.CTkLabel(
                c, text=str(g.get("nombre", "GPU Desconocida")),
                font=F_H2, text_color=P["texto"], anchor="w"
            ).pack(fill="x", padx=14, pady=(0, 6))

            self._fila_dato(c, "Procesador de Video", g.get("procesador", "N/A"))
            self._fila_dato(c, "Memoria Dedicada", f"{g.get('vram_mb', '?')} MB")
            self._fila_dato(
                c, "Versión de Driver", g.get("driver_version", "N/A"),
                ("WDDM Activo", "ok")
            )
            BarraMetrica(
                c, "Capacidad de VRAM (referencia 16 GB)",
                min(100.0, (vram / 16384.0) * 100.0 if vram > 0 else 25.0),
                f"{vram:.0f} MB", warn=101, err=101
            ).pack(fill="x", padx=14, pady=(6, 12))

    def _tab_discos(self, tab, hw: dict):
        fisicos = hw.get("discos_fisicos", []) or []
        partics = hw.get("particiones", []) or []

        cont = ctk.CTkFrame(tab, fg_color="transparent")
        cont.pack(fill="both", expand=True, padx=6, pady=4)
        cont.grid_columnconfigure(0, weight=2)
        cont.grid_columnconfigure(1, weight=3)
        cont.grid_rowconfigure(0, weight=1)

        c_fis = tarjeta(cont)
        c_fis.grid(row=0, column=0, padx=(0, 5), sticky="nsew")
        overline(c_fis, "Unidades Físicas Detectadas", color=P["cian"]).pack(
            anchor="w", padx=12, pady=(10, 6)
        )
        sf = ctk.CTkScrollableFrame(c_fis, fg_color=P["surface"], corner_radius=8)
        sf.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        if not fisicos:
            ctk.CTkLabel(
                sf, text="Sin unidades reportadas vía WMI.", font=F_SMALL, text_color=P["texto_dim"]
            ).pack(anchor="w", padx=8, pady=8)
        for d in fisicos:
            tipo = str(d.get("tipo", "Disco"))
            es_ssd = "SSD" in tipo.upper() or "NVME" in tipo.upper()
            item = ctk.CTkFrame(
                sf, fg_color=P["card_alt"], corner_radius=8,
                border_width=1, border_color=P["borde"]
            )
            item.pack(fill="x", padx=4, pady=4)
            f1 = ctk.CTkFrame(item, fg_color="transparent")
            f1.pack(fill="x", padx=10, pady=(8, 2))
            ctk.CTkLabel(f1, text=str(d.get("modelo", "Unidad")), font=F_H3, text_color=P["texto"]).pack(side="left")
            Badge(f1, tipo, tipo="ok" if es_ssd else "warn").pack(side="right")
            ctk.CTkLabel(
                item,
                text=f"Interfaz: {d.get('interfaz', '?')}   ·   Capacidad: {d.get('capacidad_gb', '?')} GB",
                font=F_CAPTION, text_color=P["texto_sec"], anchor="w"
            ).pack(fill="x", padx=10, pady=(0, 8))

        c_par = tarjeta(cont)
        c_par.grid(row=0, column=1, padx=(5, 0), sticky="nsew")
        overline(c_par, "Particiones Lógicas y Nivel de Ocupación", color=P["primario"]).pack(
            anchor="w", padx=12, pady=(10, 6)
        )
        sp = ctk.CTkScrollableFrame(c_par, fg_color=P["surface"], corner_radius=8)
        sp.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        if not partics:
            ctk.CTkLabel(sp, text="No se detectaron particiones.", font=F_SMALL).pack(padx=8, pady=8)
        for p in partics:
            uso = float(p.get("uso_pct", 0) or 0)
            niv = nivel_por_umbral(uso, warn=80, err=90)
            txt_estado = "SATURADO (≥90%)" if uso >= 90 else ("Carga Alta" if uso >= 80 else "Saludable")
            item = ctk.CTkFrame(
                sp, fg_color=P["card_alt"], corner_radius=8,
                border_width=1, border_color=P["borde"]
            )
            item.pack(fill="x", padx=4, pady=5)
            top_p = ctk.CTkFrame(item, fg_color="transparent")
            top_p.pack(fill="x", padx=10, pady=(8, 2))
            ctk.CTkLabel(
                top_p,
                text=f"Volumen {p.get('letra', '?')}  ({p.get('fs', 'NTFS')})",
                font=F_H3, text_color=P["texto"]
            ).pack(side="left")
            Badge(top_p, txt_estado, tipo=niv).pack(side="right")

            BarraMetrica(
                item,
                f"Usado: {p.get('usado_gb', 0)} GB de {p.get('total_gb', 0)} GB",
                uso,
                f"Libre: {p.get('libre_gb', 0)} GB ({uso:.1f}%)",
                warn=80, err=90
            ).pack(fill="x", padx=10, pady=(2, 8))

    def _tab_red(self, tab, hw: dict):
        adaptador = str(hw.get("adaptador_activo", "Ninguno"))
        ip = str(hw.get("ip_local", "N/A"))
        lat = str(hw.get("latencia_ms", "N/A"))
        lat_ms = self._num(lat, default=-1.0)
        conectado = adaptador not in ("", "Ninguno") and not lat.upper().startswith("N/A")

        kpis = ctk.CTkFrame(tab, fg_color="transparent")
        kpis.pack(fill="x", padx=8, pady=(6, 8))
        for c in range(3):
            kpis.grid_columnconfigure(c, weight=1, uniform="red")

        TarjetaMetrica(
            kpis, "ADAPTADOR DE RED ACTIVO", adaptador,
            "Interfaz principal de salida",
            color=P["primario"] if conectado else P["rojo"]
        ).grid(row=0, column=0, padx=4, sticky="nsew")

        TarjetaMetrica(
            kpis, "DIRECCIÓN IPv4 LOCAL", ip,
            "Asignación de pila TCP/IP",
            color=P["cian"]
        ).grid(row=0, column=1, padx=4, sticky="nsew")

        TarjetaMetrica(
            kpis, "LATENCIA DNS (PING)", lat,
            "Óptima (<60 ms)" if 0 <= lat_ms < 60 else ("Elevada" if lat_ms >= 60 else "Sin respuesta ICMP"),
            color=P["primario"] if 0 <= lat_ms < 100 else P["ambar"]
        ).grid(row=0, column=2, padx=4, sticky="nsew")

        card = tarjeta(tab)
        card.pack(fill="both", expand=True, padx=12, pady=4)
        overline(card, "Diagnóstico Rápido de Conectividad y Entorno", color=P["cian"]).pack(
            anchor="w", padx=14, pady=(12, 6)
        )
        self._fila_dato(
            card, "Estado de Enlace",
            "Conectado y con salida DNS" if conectado else "Enlace limitado o sin respuesta",
            ("ONLINE" if conectado else "REVISAR", "ok" if conectado else "warn")
        )
        self._fila_dato(card, "Sistema Operativo", f"{hw.get('so', '?')} (Build {hw.get('so_build', '?')})")
        self._fila_dato(card, "Tiempo Activo (Uptime)", hw.get("uptime", "?"))

        if lat_ms >= 0:
            calidad = max(5.0, min(100.0, 100.0 - (lat_ms / 2.5)))
            BarraMetrica(
                card, "Calidad de Respuesta de Red",
                calidad, f"{lat} (índice {calidad:.0f}/100)", warn=101, err=101
            ).pack(fill="x", padx=14, pady=(10, 8))

        fila_acc = ctk.CTkFrame(card, fg_color="transparent")
        fila_acc.pack(fill="x", padx=14, pady=(6, 10))
        boton(
            fila_acc, "🌐 Diagnosticar Red en Árbol (Rama #8)",
            lambda: self.seleccionar_sintoma(7),
            variante="azul", width=260, height=32, font=F_SMALL
        ).pack(side="left", padx=(0, 8))
        boton(
            fila_acc, "🗺️ Ver Panel I/O en Mapa 2D",
            lambda: self._abrir_mapa_desde_vista("Adaptador de Red", self.pantalla_dashboard),
            variante="neutro", width=220, height=32, font=F_SMALL
        ).pack(side="left")

    def pantalla_multisintoma(self):
        """Selector de síntomas múltiples con filtro y ranking interactivo."""
        self.limpiar_panel()

        frame = ctk.CTkFrame(
            self, width=948, height=668, corner_radius=0,
            fg_color=P["bg"], border_width=1, border_color=P["borde"]
        )
        animar_entrada_panel(frame)
        frame.pack_propagate(False)

        self._crear_encabezado_vista(
            frame,
            "Diagnóstico Multisíntoma — Correlación Ponderada",
            "Marque los síntomas observados. El motor bayesiano calcula la probabilidad de cada causa raíz.",
            badge_texto="15 Síntomas · 8 Subsistemas",
            badge_tipo="info",
            cmd_volver=self.pantalla_dashboard,
        )

        cuerpo = ctk.CTkFrame(frame, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=14, pady=4)
        cuerpo.grid_columnconfigure(0, weight=5)
        cuerpo.grid_columnconfigure(1, weight=6)
        cuerpo.grid_rowconfigure(0, weight=1)

        col_izq = tarjeta(cuerpo)
        col_izq.grid(row=0, column=0, padx=(0, 6), sticky="nsew")

        barra_f = ctk.CTkFrame(col_izq, fg_color="transparent")
        barra_f.pack(fill="x", padx=12, pady=(10, 4))
        overline(barra_f, "1. Seleccione Síntomas Observables", color=P["cian"]).pack(side="left")
        self._badge_conteo_sint = Badge(barra_f, "0 seleccionados", tipo="neutro")
        self._badge_conteo_sint.pack(side="right")

        self._entry_filtro_sint = entrada(
            col_izq, "Filtrar síntomas por palabra clave (ej. pantalla, disco, red)…", height=32
        )
        self._entry_filtro_sint.pack(fill="x", padx=12, pady=(0, 6))
        self._entry_filtro_sint.bind("<KeyRelease>", lambda e: self._filtrar_checkboxes_sintomas())

        scroll = ctk.CTkScrollableFrame(col_izq, fg_color=P["surface"], corner_radius=8)
        scroll.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self._check_vars: list[ctk.BooleanVar] = []
        self._check_widgets: list[tuple[str, ctk.CTkCheckBox]] = []
        est_chk = estilo_checkbox()
        for i, texto in enumerate(MatrizSintomas.SINTOMAS):
            var = ctk.BooleanVar(value=False)
            self._check_vars.append(var)
            chk = ctk.CTkCheckBox(
                scroll, text=f"{i + 1:02d}. {texto}", variable=var,
                font=F_SMALL, command=self._actualizar_conteo_sintomas, **est_chk
            )
            chk.pack(anchor="w", pady=4, padx=8, fill="x")
            self._check_widgets.append((texto.lower(), chk))

        fila_btn_izq = ctk.CTkFrame(col_izq, fg_color="transparent")
        fila_btn_izq.pack(fill="x", padx=12, pady=(0, 10))
        boton(
            fila_btn_izq, "Calcular Probabilidades",
            self._calcular_multisintoma, variante="primario", width=210, height=36
        ).pack(side="left", padx=(0, 6))
        boton(
            fila_btn_izq, "Limpiar",
            self._limpiar_checks, variante="neutro", width=110, height=36
        ).pack(side="left")

        col_der = tarjeta(cuerpo)
        col_der.grid(row=0, column=1, padx=(6, 0), sticky="nsew")
        overline(col_der, "2. Ranking de Causas Probables y Acción Directa", color=P["primario"]).pack(
            anchor="w", padx=12, pady=(10, 4)
        )

        self._cards_multisintoma = ctk.CTkScrollableFrame(
            col_der, fg_color=P["surface"], corner_radius=8, height=265
        )
        self._cards_multisintoma.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        self._res_multisintoma = ctk.CTkTextbox(col_der, height=145, **estilo_textbox())
        self._res_multisintoma.pack(fill="x", padx=12, pady=(0, 10))
        self._insertar_y_bloquear(
            self._res_multisintoma,
            "Seleccione uno o más síntomas a la izquierda y presione 'Calcular Probabilidades'."
        )

    def _actualizar_conteo_sintomas(self):
        n = sum(1 for v in getattr(self, "_check_vars", []) if v.get())
        if hasattr(self, "_badge_conteo_sint"):
            self._badge_conteo_sint.set(
                f"{n} seleccionado(s)", tipo="ok" if n > 0 else "neutro"
            )

    def _filtrar_checkboxes_sintomas(self):
        q = self._entry_filtro_sint.get().strip().lower()
        for texto, chk in getattr(self, "_check_widgets", []):
            if not q or q in texto:
                chk.pack(anchor="w", pady=4, padx=8, fill="x")
            else:
                chk.pack_forget()

    def _limpiar_checks(self):
        for var in self._check_vars:
            var.set(False)
        self._actualizar_conteo_sintomas()
        if hasattr(self, "_cards_multisintoma"):
            for w in self._cards_multisintoma.winfo_children():
                w.destroy()
        self._insertar_y_bloquear(
            self._res_multisintoma,
            "Selección limpiada. Elija síntomas y calcule nuevamente."
        )

    def _calcular_multisintoma(self):
        indices_sel = [i for i, v in enumerate(self._check_vars) if v.get()]
        if hasattr(self, "_cards_multisintoma"):
            for w in self._cards_multisintoma.winfo_children():
                w.destroy()

        if not indices_sel:
            self._insertar_y_bloquear(
                self._res_multisintoma, "⚠  Seleccione al menos un síntoma para calcular."
            )
            return

        resultados = MatrizSintomas.calcular_probabilidades(indices_sel)

        if hasattr(self, "_cards_multisintoma"):
            for idx, r in enumerate(resultados[:5], 1):
                card_r = ctk.CTkFrame(
                    self._cards_multisintoma, fg_color=P["card_alt"], corner_radius=8,
                    border_width=1, border_color=P["primario"] if idx == 1 else P["borde"]
                )
                card_r.pack(fill="x", padx=4, pady=4)
                BarraMetrica(
                    card_r, f"#{idx}  {r['causa']}",
                    r["probabilidad"], f"{r['probabilidad']:.1f}%",
                    warn=50, err=75
                ).pack(fill="x", padx=10, pady=(8, 4))

                f_acc = ctk.CTkFrame(card_r, fg_color="transparent")
                f_acc.pack(fill="x", padx=10, pady=(0, 8))
                ctk.CTkLabel(
                    f_acc, text=r["descripcion"], font=F_CAPTION,
                    text_color=P["texto_sec"], wraplength=280, justify="left"
                ).pack(side="left", fill="x", expand=True)

                dictamen_ms = {
                    "categoria": r["causa"],
                    "subcategoria": "Correlación Multisíntoma",
                    "descripcion": r["descripcion"],
                    "solucion": r["solucion"],
                    "codigo": r["codigo"],
                }
                boton(
                    f_acc, "Abrir Dictamen →",
                    lambda d=dictamen_ms: self.finalizar_diagnostico(d),
                    variante="primario" if idx == 1 else "neutro",
                    width=130, height=28, font=F_CAPTION
                ).pack(side="right", padx=(6, 0))

        lineas = [
            f"  Síntomas seleccionados: {len(indices_sel)}",
            "  ─────────────────────────────────────────────────────────────",
            "  RANKING DE CAUSAS PROBABLES:",
        ]
        for idx, r in enumerate(resultados[:6], 1):
            barra = self._mini_barra(r["probabilidad"])
            lineas.append(f"  #{idx}  {r['causa']:<32s}  {barra}  {r['probabilidad']:5.1f}%")
        if resultados:
            top = resultados[0]
            lineas += [
                "",
                f"  CAUSA MÁS PROBABLE: {top['causa']} ({top['probabilidad']}%)",
                f"  GUÍA DE ACCIÓN:\n{top['solucion']}",
            ]
        self._insertar_y_bloquear(self._res_multisintoma, "\n".join(lineas))

    @staticmethod
    def _mini_barra(pct: float, ancho: int = 15) -> str:
        relleno = int((pct / 100) * ancho)
        return "[" + "█" * relleno + "░" * (ancho - relleno) + "]"

    def pantalla_buscador(self):
        """
        Buscador en lenguaje natural con:
          • Chips de consulta rápida y selector directo de las 26 hojas del catálogo.
          • Tarjetas de coincidencias con barra de confianza y botones para
            ejecutar diagnóstico directo o abrir la rama guiada del árbol.
          • Panel activo de dictamen con acceso inmediato a Mapa 2D,
            Gemelo Digital 3D, Árbol Guiado, Stress Test y Guardado de Reporte.
        """
        self.limpiar_panel()

        frame = ctk.CTkFrame(
            self, width=948, height=668, corner_radius=0,
            fg_color=P["bg"], border_width=1, border_color=P["borde"]
        )
        animar_entrada_panel(frame)
        frame.pack_propagate(False)

        self._crear_encabezado_vista(
            frame,
            "Buscador Asistido Inteligente — Diagnóstico y Ejecución Directa",
            "Describa el síntoma o elija un caso del catálogo: puede ejecutar el diagnóstico y sus acciones sin pasos manuales.",
            badge_texto=f"{len(CATALOGO_DICTAMENES)} Casos Cubiertos",
            badge_tipo="ok",
            cmd_volver=self.pantalla_dashboard,
        )

        barra_busq = tarjeta(frame)
        barra_busq.pack(fill="x", padx=14, pady=(0, 6))

        fila_in = ctk.CTkFrame(barra_busq, fg_color="transparent")
        fila_in.pack(fill="x", padx=12, pady=(10, 4))

        self._entry_busqueda = entrada(
            fila_in,
            "Describa el problema (ej: 'pantalla azul jugando con xmp', 'disco al 100 lento', 'no tengo internet')…",
            width=520, height=38,
        )
        self._entry_busqueda.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._entry_busqueda.bind("<Return>", lambda e: self._ejecutar_busqueda())

        boton(
            fila_in, "🔎 Buscar Causas",
            self._ejecutar_busqueda, variante="azul", width=150, height=38
        ).pack(side="left", padx=(0, 6))

        boton(
            fila_in, "⚡ Diagnosticar Directo",
            self._diagnosticar_directo_desde_entrada, variante="primario", width=180, height=38
        ).pack(side="left")

        fila_chips = ctk.CTkFrame(barra_busq, fg_color="transparent")
        fila_chips.pack(fill="x", padx=12, pady=(2, 10))

        ctk.CTkLabel(
            fila_chips, text="Ejemplos rápidos:", font=F_CAPTION, text_color=P["texto_dim"]
        ).pack(side="left", padx=(0, 6))

        ejemplos = [
            ("No enciende", "la pc no prende sin luces ni ventiladores"),
            ("Pitidos RAM", "pitidos cortos repetitivos al encender"),
            ("Pantalla negra", "no hay señal de video monitor negro hdmi"),
            ("CPU caliente", "sobrecalentamiento cpu pasta termica seca"),
            ("SSD NVMe", "el ssd nvme desaparece cuando se calienta"),
            ("Disco 100%", "pc muy lenta disco al 100"),
            ("BSOD / XMP", "pantalla azul con error de memoria xmp"),
            ("Sin Internet", "no tengo internet wifi desconectado"),
        ]
        for etiqueta_corta, query_ej in ejemplos:
            boton(
                fila_chips, etiqueta_corta,
                lambda q=query_ej: self._usar_ejemplo_busqueda(q),
                variante="fantasma", width=78, height=24, font=F_CAPTION
            ).pack(side="left", padx=2)

        opciones_catalogo = [
            f"#{cod} · {d['categoria']} — {d['subcategoria']}"
            for cod, d in sorted(CATALOGO_DICTAMENES.items())
        ]
        self._combo_catalogo = ctk.CTkComboBox(
            fila_chips,
            values=opciones_catalogo,
            width=225, height=26,
            command=self._al_elegir_combo_catalogo,
            state="readonly",
            **estilo_combo(),
        )
        self._combo_catalogo.set("Catálogo directo (26 casos)…")
        self._combo_catalogo.pack(side="right", padx=(6, 0))

        cuerpo = ctk.CTkFrame(frame, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        cuerpo.grid_columnconfigure(0, weight=5)
        cuerpo.grid_columnconfigure(1, weight=6)
        cuerpo.grid_rowconfigure(0, weight=1)

        col_izq = tarjeta(cuerpo)
        col_izq.grid(row=0, column=0, padx=(0, 6), sticky="nsew")

        enc_izq = ctk.CTkFrame(col_izq, fg_color="transparent")
        enc_izq.pack(fill="x", padx=12, pady=(10, 4))
        overline(enc_izq, "Coincidencias y Ramas del Árbol", color=P["cian"]).pack(side="left")
        self._badge_resultados_busq = Badge(enc_izq, "Listo para buscar", tipo="neutro")
        self._badge_resultados_busq.pack(side="right")

        self._scroll_resultados_busq = ctk.CTkScrollableFrame(
            col_izq, fg_color=P["surface"], corner_radius=8, height=250
        )
        self._scroll_resultados_busq.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        self._res_busqueda = ctk.CTkTextbox(col_izq, height=115, **estilo_textbox())
        self._res_busqueda.pack(fill="x", padx=12, pady=(0, 10))
        self._insertar_y_bloquear(
            self._res_busqueda,
            "Escriba un síntoma arriba o pulse un ejemplo rápido.\n"
            "El buscador evalúa las 26 hojas del árbol y la telemetría actual."
        )

        col_der = tarjeta(cuerpo)
        col_der.grid(row=0, column=1, padx=(6, 0), sticky="nsew")

        enc_der = ctk.CTkFrame(col_der, fg_color="transparent")
        enc_der.pack(fill="x", padx=12, pady=(10, 4))
        overline(enc_der, "Resultado del Diagnóstico y Acciones Directas", color=P["primario"]).pack(side="left")
        self._badge_dictamen_busq = Badge(enc_der, "Sin dictamen activo", tipo="neutro")
        self._badge_dictamen_busq.pack(side="right")

        self._panel_dictamen_busq = ctk.CTkFrame(
            col_der, fg_color=P["surface"], corner_radius=10,
            border_width=1, border_color=P["borde"]
        )
        self._panel_dictamen_busq.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self._render_dictamen_en_buscador(self.dictamen_final)

    def _usar_ejemplo_busqueda(self, query: str):
        self._entry_busqueda.delete(0, "end")
        self._entry_busqueda.insert(0, query)
        self._ejecutar_busqueda()

    def _al_elegir_combo_catalogo(self, seleccion: str):
        if not seleccion or not seleccion.startswith("#"):
            return
        try:
            codigo = int(seleccion.split()[0].lstrip("#"))
        except (ValueError, IndexError):
            return
        self.ejecutar_diagnostico_directo(codigo, permanecer_en_buscador=True)

    def _diagnosticar_directo_desde_entrada(self):
        texto = self._entry_busqueda.get().strip()
        if len(texto) >= 3:
            self._ejecutar_busqueda(auto_ejecutar=True)
        else:
            toast(self, "Ingrese al menos 3 caracteres o elija un caso del catálogo.", tipo="warn")

    def _ejecutar_busqueda(self, auto_ejecutar: bool = True):
        texto = self._entry_busqueda.get().strip()
        for w in getattr(self, "_scroll_resultados_busq", []).winfo_children() if hasattr(self, "_scroll_resultados_busq") else []:
            w.destroy()

        if len(texto) < 3:
            self._insertar_y_bloquear(
                self._res_busqueda, "⚠  Ingrese al menos 3 caracteres para buscar."
            )
            if hasattr(self, "_badge_resultados_busq"):
                self._badge_resultados_busq.set("Consulta muy corta", tipo="warn")
            return

        resultados = BuscadorAsistido.buscar(texto, top_n=5, hw=self.hardware_detectado)

        if hasattr(self, "_badge_resultados_busq"):
            self._badge_resultados_busq.set(
                f"{len(resultados)} coincidencia(s)",
                tipo="ok" if resultados else "warn"
            )

        lineas = [
            f"  Búsqueda: \"{texto}\"  ({len(resultados)} coincidencias)",
            "  ──────────────────────────────────────────────────────────────",
        ]

        if not resultados:
            lineas.append("  Sin coincidencias. Intente con otras palabras clave o use el catálogo directo.")
            self._insertar_y_bloquear(self._res_busqueda, "\n".join(lineas))
            return

        if hasattr(self, "_scroll_resultados_busq"):
            for i, r in enumerate(resultados, 1):
                cod = r["codigo"]
                rama_id = r["rama_id"]
                info_rama = RAMAS_ARBOL[rama_id]
                card_item = ctk.CTkFrame(
                    self._scroll_resultados_busq,
                    fg_color=P["card_alt"],
                    corner_radius=8,
                    border_width=1,
                    border_color=P["primario"] if i == 1 else P["borde"],
                )
                card_item.pack(fill="x", padx=4, pady=4)

                top_row = ctk.CTkFrame(card_item, fg_color="transparent")
                top_row.pack(fill="x", padx=10, pady=(6, 2))
                ctk.CTkLabel(
                    top_row,
                    text=f"#{i} · {r['causa']}  (Código #{cod})",
                    font=F_H3, text_color=P["texto"]
                ).pack(side="left")
                if r.get("respaldo_telemetria"):
                    Badge(top_row, "Respaldado por telemetría", tipo="warn").pack(side="right", padx=(4, 0))

                BarraMetrica(
                    card_item,
                    f"Rama #{rama_id + 1}: {info_rama['titulo']}",
                    r["confianza_pct"],
                    f"{r['confianza_pct']:.1f}%",
                    warn=55, err=80, alto_barra=6,
                ).pack(fill="x", padx=10, pady=(2, 6))

                btn_bar = ctk.CTkFrame(card_item, fg_color="transparent")
                btn_bar.pack(fill="x", padx=10, pady=(0, 8))

                boton(
                    btn_bar, "⚡ Diagnosticar Ahora",
                    lambda c=cod: self.ejecutar_diagnostico_directo(c, permanecer_en_buscador=True),
                    variante="primario" if i == 1 else "azul",
                    width=155, height=28, font=F_CAPTION
                ).pack(side="left", padx=(0, 6))

                boton(
                    btn_bar, f"🌳 Abrir Árbol (Rama #{rama_id + 1})",
                    lambda rid=rama_id: self.lanzar_rama_desde_buscador(rid),
                    variante="neutro", width=165, height=28, font=F_CAPTION
                ).pack(side="left")

        for i, r in enumerate(resultados, 1):
            barra = self._mini_barra(r["confianza_pct"])
            lineas.append(
                f"  #{i} [{r['codigo']}] {r['causa']} — {barra} {r['confianza_pct']}% "
                f"(Rama #{r['rama_id'] + 1})"
            )

        self._insertar_y_bloquear(self._res_busqueda, "\n".join(lineas))

        if auto_ejecutar and resultados:
            self.ejecutar_diagnostico_directo(
                resultados[0]["codigo"], permanecer_en_buscador=True
            )

    def lanzar_rama_desde_buscador(self, rama_id: int):
        """Abre directamente la rama indicada en el asistente inferencial guiado."""
        self.arbol_fase = 1
        self.arbol_rama = int(rama_id)
        self.arbol_paso = 0
        self.temp_gira_ventilador = False
        self.dictamen_final = None
        self.pantalla_diagnostico()

    def ejecutar_diagnostico_directo(
        self, codigo: int, permanecer_en_buscador: bool = False
    ) -> dict:
        """
        Ejecuta directamente el diagnóstico para cualquier código del catálogo,
        genera su ticket y habilita las acciones (Mapa 2D, Gemelo 3D, Reporte).
        """
        dictamen = obtener_dictamen(int(codigo))
        self.dictamen_final = dictamen
        self.arbol_rama = rama_de_codigo(int(codigo))
        self.arbol_fase = 2
        prefijo = (
            self.dni_usuario_activo[:4]
            if self.dni_usuario_activo and len(self.dni_usuario_activo) >= 4
            else "USER"
        )
        self.ticket_id_actual = f"{prefijo}-TICKET-{random.randint(1000, 9999)}".strip()
        self.ticket_sincronizado = False

        if permanecer_en_buscador and hasattr(self, "_panel_dictamen_busq") and self._panel_dictamen_busq.winfo_exists():
            self._render_dictamen_en_buscador(dictamen)
        else:
            self.pantalla_diagnostico()
        return dictamen

    def _render_dictamen_en_buscador(self, df: dict | None):
        if not hasattr(self, "_panel_dictamen_busq") or not self._panel_dictamen_busq.winfo_exists():
            return
        for w in self._panel_dictamen_busq.winfo_children():
            w.destroy()

        if not df:
            ctk.CTkLabel(
                self._panel_dictamen_busq,
                text="Realice una búsqueda o seleccione un caso del catálogo.\n\n"
                     "Aquí verá el dictamen completo con sus pasos de solución y podrá:\n"
                     "  • Abrir el Mapa 2D con el componente afectado resaltado\n"
                     "  • Lanzar el Gemelo Digital 3D en la nube\n"
                     "  • Guardar el reporte dual (TXT + JSON + Supabase)\n"
                     "  • Iniciar el Árbol Guiado o el Micro-Stress Test de CPU",
                font=F_SMALL, text_color=P["texto_sec"], justify="left", wraplength=430
            ).pack(padx=16, pady=24, anchor="w")
            return

        ticket = self._asegurar_ticket()
        if hasattr(self, "_badge_dictamen_busq"):
            self._badge_dictamen_busq.set(f"Código #{df['codigo']} · {ticket}", tipo="ok")

        top = ctk.CTkFrame(self._panel_dictamen_busq, fg_color=P["card_alt"], corner_radius=8)
        top.pack(fill="x", padx=10, pady=(10, 6))

        f_cat = ctk.CTkFrame(top, fg_color="transparent")
        f_cat.pack(fill="x", padx=12, pady=(8, 2))
        Badge(f_cat, df["categoria"], tipo="err").pack(side="left")
        Badge(f_cat, df["subcategoria"], tipo="info").pack(side="left", padx=6)
        Badge(f_cat, f"Rama #{rama_de_codigo(df['codigo']) + 1}", tipo="neutro").pack(side="right")

        ctk.CTkLabel(
            top, text=df["descripcion"], font=F_H3, text_color=P["texto"],
            anchor="w", wraplength=430, justify="left"
        ).pack(fill="x", padx=12, pady=(2, 8))

        overline(self._panel_dictamen_busq, "Guía de Solución Paso a Paso", color=P["cian"]).pack(
            anchor="w", padx=12, pady=(2, 2)
        )
        tb_sol = ctk.CTkTextbox(self._panel_dictamen_busq, height=135, **estilo_textbox())
        tb_sol.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        self._insertar_y_bloquear(
            tb_sol,
            f"{df['solucion']}\n\nTicket activo: {ticket}  ·  Código Interno: #{df['codigo']}"
        )

        overline(self._panel_dictamen_busq, "Acciones Directas Disponibles").pack(
            anchor="w", padx=12, pady=(0, 4)
        )
        fila_a1 = ctk.CTkFrame(self._panel_dictamen_busq, fg_color="transparent")
        fila_a1.pack(fill="x", padx=10, pady=(0, 4))

        boton(
            fila_a1, "🗺️ Ver Mapa 2D",
            lambda: self._abrir_mapa_desde_vista(df["categoria"], self.pantalla_buscador),
            variante="ambar", width=142, height=34, font=F_SMALL
        ).pack(side="left", padx=(0, 6))

        boton(
            fila_a1, "🌐 Gemelo Digital 3D",
            self.abrir_visor_3d,
            variante="azul", width=165, height=34, font=F_SMALL
        ).pack(side="left", padx=(0, 6))

        boton(
            fila_a1, "💾 Guardar Reporte",
            lambda: self.guardar_reporte_final(permanecer=True),
            variante="primario", width=155, height=34, font=F_SMALL
        ).pack(side="left")

        fila_a2 = ctk.CTkFrame(self._panel_dictamen_busq, fg_color="transparent")
        fila_a2.pack(fill="x", padx=10, pady=(0, 10))

        rama_id = rama_de_codigo(df["codigo"])
        boton(
            fila_a2, f"🌳 Recorrer Árbol Guiado (Rama #{rama_id + 1})",
            lambda: self.lanzar_rama_desde_buscador(rama_id),
            variante="neutro", width=235, height=30, font=F_CAPTION
        ).pack(side="left", padx=(0, 6))

        if "stress_test" in acciones_para(df["codigo"]):
            boton(
                fila_a2, "⚡ Validar con Stress Test CPU",
                self.pantalla_stress_test,
                variante="violeta", width=220, height=30, font=F_CAPTION
            ).pack(side="left")

    def pantalla_stress_test(self):
        """Benchmark CPU multihilo con progreso animado, sparkline y cancelación segura."""
        self.limpiar_panel()

        frame = ctk.CTkFrame(
            self, width=948, height=668, corner_radius=0,
            fg_color=P["bg"], border_width=1, border_color=P["borde"]
        )
        animar_entrada_panel(frame)
        frame.pack_propagate(False)

        n_logicos = psutil.cpu_count(logical=True) or 2
        n_workers = max(1, min(n_logicos, MicroStressTest.MAX_WORKERS))
        cpu_modelo = str(self._hw("nombre_cpu", "Procesador Universal Detectado"))

        self._crear_encabezado_vista(
            frame,
            "Micro-Stress Test — Benchmark Universal de CPU (~90%)",
            f"CPU: {cpu_modelo} ({n_workers}/{n_logicos} hilos activos al ~{int(MicroStressTest.DUTY_CYCLE * 100)}% "
            "con kernel C sin GIL). Verificación de potencia real y estabilidad térmica.",
            badge_texto=f"Umbral ≥ {MicroStressTest.THROTTLE_UMBRAL_PCT}%",
            badge_tipo="violeta",
            cmd_volver=self.pantalla_dashboard,
        )

        kpis = ctk.CTkFrame(frame, fg_color="transparent")
        kpis.pack(fill="x", padx=14, pady=(0, 6))
        for c in range(4):
            kpis.grid_columnconfigure(c, weight=1, uniform="st")

        self._kpi_freq = TarjetaMetrica(
            kpis, "FRECUENCIA CPU", f"{self._hw('frecuencia_actual_ghz', '0.00')} GHz",
            "Reloj instantáneo", color=P["cian"]
        )
        self._kpi_freq.grid(row=0, column=0, padx=4, sticky="nsew")

        self._kpi_uso = TarjetaMetrica(
            kpis, "CARGA DE CPU", f"{self._hw('uso_cpu_total', '0')}%",
            f"{n_workers} workers activos al iniciar", color=P["violeta"]
        )
        self._kpi_uso.grid(row=0, column=1, padx=4, sticky="nsew")

        self._kpi_mops = TarjetaMetrica(
            kpis, "RENDIMIENTO REAL", "— Mops/s",
            "Millones de ops float/seg", color=P["primario"]
        )
        self._kpi_mops.grid(row=0, column=2, padx=4, sticky="nsew")

        self._kpi_estado_st = TarjetaMetrica(
            kpis, "ESTADO / SEGURIDAD", "EN ESPERA",
            f"Guardia RAM > {MicroStressTest.RAM_MIN_LIBRE_PCT}% libre", color=P["texto"]
        )
        self._kpi_estado_st.grid(row=0, column=3, padx=4, sticky="nsew")

        ctrl_card = tarjeta(frame)
        ctrl_card.pack(fill="x", padx=14, pady=(0, 6))

        fila_p = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        fila_p.pack(fill="x", padx=14, pady=(10, 4))

        self._pulso_stress = PuntoPulso(fila_p, color=P["violeta"])
        self._pulso_stress.pack(side="left", padx=(0, 6))
        self._lbl_fase_stress = ctk.CTkLabel(
            fila_p, text="Listo para iniciar prueba controlada.",
            font=F_H3, text_color=P["texto"]
        )
        self._lbl_fase_stress.pack(side="left")

        self._seg_duracion = ctk.CTkSegmentedButton(
            fila_p, values=["5 s", "10 s (Estándar)", "15 s"],
            **estilo_segmentado()
        )
        self._seg_duracion.set("10 s (Estándar)")
        self._seg_duracion.pack(side="right")
        ctk.CTkLabel(
            fila_p, text="Duración:", font=F_CAPTION, text_color=P["texto_dim"]
        ).pack(side="right", padx=(0, 6))

        self._barra_stress = BarraMetrica(
            ctrl_card, "Progreso del Benchmark", 0.0, "0.0 s / 10.0 s",
            warn=101, err=101, alto_barra=10
        )
        self._barra_stress.pack(fill="x", padx=14, pady=(2, 10))

        cuerpo = ctk.CTkFrame(frame, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=14, pady=(0, 6))
        cuerpo.grid_columnconfigure(0, weight=4)
        cuerpo.grid_columnconfigure(1, weight=5)
        cuerpo.grid_rowconfigure(0, weight=1)

        c_graf = tarjeta(cuerpo)
        c_graf.grid(row=0, column=0, padx=(0, 6), sticky="nsew")
        overline(c_graf, "Curva en Tiempo Real (Mops/s y % Uso CPU)", color=P["cian"]).pack(
            anchor="w", padx=12, pady=(10, 4)
        )
        self._spark_stress = Sparkline(c_graf, ancho=380, alto=155, max_puntos=32)
        self._spark_stress.pack(padx=12, pady=4, fill="x")
        self._spark_stress.agregar_serie("uso", P["violeta"], maximo=100.0)
        self._spark_stress.agregar_serie("mops", P["cian"], maximo=None)

        ley = ctk.CTkFrame(c_graf, fg_color="transparent")
        ley.pack(fill="x", padx=12, pady=(2, 6))
        Badge(ley, "━ Rendimiento (Mops/s)", tipo="info").pack(side="left", padx=(0, 6))
        Badge(ley, "━ Uso CPU (%)", tipo="violeta").pack(side="left")

        self._lbl_resumen_stress = ctk.CTkLabel(
            c_graf,
            text="Garantías de seguridad y potencia activas:\n"
                 " • Kernel C SHA256+FPU sin GIL compatible con cualquier CPU (~90% carga)\n"
                 f" • Guardia real: RAM libre > {MicroStressTest.RAM_MIN_LIBRE_PCT}% y línea base suavizada\n"
                 " • Cancelación inmediata en memoria sin procesos huérfanos",
            font=F_CAPTION, text_color=P["texto_sec"], justify="left", anchor="w"
        )
        self._lbl_resumen_stress.pack(fill="x", padx=12, pady=(2, 10))

        c_log = tarjeta(cuerpo)
        c_log.grid(row=0, column=1, padx=(6, 0), sticky="nsew")
        overline(c_log, "Bitácora de Muestreo (0.5 s) y Dictamen Térmico", color=P["primario"]).pack(
            anchor="w", padx=12, pady=(10, 4)
        )
        self._stress_log = ctk.CTkTextbox(c_log, height=230, **estilo_textbox())
        self._stress_log.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self._insertar_y_bloquear(
            self._stress_log,
            "Presione '▶ Iniciar Test' para comenzar el benchmark de potencia.\n\n"
            f"  Procesador detectado  : {cpu_modelo}\n"
            f"  Hilos lógicos activos : {n_workers} de {n_logicos} (objetivo ~{int(MicroStressTest.DUTY_CYCLE * 100)}% uso total)\n"
            f"  Duración estándar     : {MicroStressTest.DURACION_SEG} segundos\n"
            f"  Umbral de throttling  : ≥ {MicroStressTest.THROTTLE_UMBRAL_PCT}% de caída sostenida\n\n"
            "La interfaz permanecerá 100% responsiva y puede cancelar en cualquier momento."
        )

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(pady=(2, 10))

        self._btn_stress = boton(
            btn_row, "▶  Iniciar Test",
            self._iniciar_stress, variante="violeta", width=190, height=38
        )
        self._btn_stress.pack(side="left", padx=6)

        self._btn_cancelar_stress = boton(
            btn_row, "⏹  Cancelar Test",
            self._cancelar_stress, variante="peligro", width=170, height=38, state="disabled"
        )
        self._btn_cancelar_stress.pack(side="left", padx=6)

        self._btn_accion_termica = boton(
            btn_row, "🩺 Diagnosticar Enfriamiento CPU",
            lambda: self.ejecutar_diagnostico_directo(302),
            variante="neutro", width=230, height=38
        )
        self._btn_accion_termica.pack(side="left", padx=6)

    def _obtener_duracion_stress(self) -> float:
        if hasattr(self, "_seg_duracion"):
            val = self._seg_duracion.get()
            if val.startswith("5"):
                return 5.0
            if val.startswith("15"):
                return 15.0
        return float(MicroStressTest.DURACION_SEG)

    def _iniciar_stress(self):
        """Lanza el stress test en segundo plano y habilita el botón de cancelación."""
        if self._stress_actual and self._stress_actual.activo:
            return
        dur = self._obtener_duracion_stress()

        self._btn_stress.configure(state="disabled", text="⏳ Ejecutando…")
        if hasattr(self, "_btn_cancelar_stress"):
            self._btn_cancelar_stress.configure(state="normal")
        if hasattr(self, "_pulso_stress"):
            self._pulso_stress.iniciar(P["violeta"])
        if hasattr(self, "_lbl_fase_stress"):
            self._lbl_fase_stress.configure(text=f"Aplicando carga controlada durante {dur:.0f} s…")
        if hasattr(self, "_spark_stress"):
            self._spark_stress.limpiar()
        if hasattr(self, "_barra_stress"):
            self._barra_stress.set(0.0, f"0.0 s / {dur:.1f} s", animar=False)

        self._stress_log.configure(state="normal")
        self._stress_log.delete("0.0", "end")
        self._stress_log.configure(state="disabled")

        self._stress_actual = MicroStressTest(
            callback_progreso=self._stress_append,
            callback_resultado=self._stress_finalizado,
            callback_muestra=self._stress_muestra,
            duracion_seg=dur,
            cpu_nombre=str(self._hw("nombre_cpu", "Procesador Detectado")),
        )
        self._stress_actual.iniciar()

    def _cancelar_stress(self):
        """Detiene de forma segura el benchmark en ejecución."""
        if self._stress_actual and self._stress_actual.activo:
            if hasattr(self, "_lbl_fase_stress"):
                self._lbl_fase_stress.configure(text="Cancelando workers de forma segura…")
            self._stress_actual.cancelar()

    def _stress_muestra(self, muestra: dict):
        self.after(0, lambda m=muestra: self._stress_muestra_main(m))

    def _stress_muestra_main(self, m: dict):
        if not hasattr(self, "_kpi_freq") or not self._kpi_freq.winfo_exists():
            return
        f_ghz = (m.get("freq_mhz", 0.0) or 0.0) / 1000.0
        uso = float(m.get("uso_pct", 0.0) or 0.0)
        mops = float(m.get("mops", 0.0) or 0.0)
        est = str(m.get("estado", "ESTABLE")).upper()
        ram_l = float(m.get("ram_libre_pct", 0.0) or 0.0)
        caida = float(m.get("caida_pct", 0.0) or 0.0)

        self._kpi_freq.set(f"{f_ghz:.2f} GHz", f"Hilos activos: {m.get('workers', 0)}")
        self._kpi_uso.set(f"{uso:.1f}%", f"RAM libre: {ram_l:.1f}%", color=P["primario"] if uso >= 82 else P["violeta"])
        self._kpi_mops.set(f"{mops:.2f} Mops/s", "Potencia C SHA256+FPU")
        if "THROTTLING" in est:
            col_est = P["rojo"]
            sub_est = f"Caída sostenida −{caida:.1f}%"
        elif "CARGANDO" in est:
            col_est = P["cian"]
            sub_est = "Elevando carga al ~90%"
        else:
            col_est = P["primario"]
            sub_est = f"Sin riesgo · RAM libre {ram_l:.0f}%"
        self._kpi_estado_st.set(est, sub_est, color=col_est)

        if hasattr(self, "_barra_stress") and self._stress_actual:
            dur = self._stress_actual.duracion
            pct = float(m.get("progreso", 0.0)) * 100.0
            self._barra_stress.set(pct, f"{m.get('t', 0.0):.1f} s / {dur:.1f} s", animar=True)
        if hasattr(self, "_spark_stress"):
            self._spark_stress.push("uso", uso)
            self._spark_stress.push("mops", mops)

    def _stress_append(self, mensaje: str):
        """Llamado desde el hilo de stress — usa self.after() para ser thread-safe."""
        self.after(0, lambda m=mensaje: self._stress_append_main(m))

    def _stress_append_main(self, mensaje: str):
        if not hasattr(self, "_stress_log") or not self._stress_log.winfo_exists():
            return
        self._stress_log.configure(state="normal")
        self._stress_log.insert("end", mensaje)
        self._stress_log.see("end")
        self._stress_log.configure(state="disabled")

    def _stress_finalizado(self, resultado: dict):
        """Llamado desde el hilo al terminar — usa self.after() para ser thread-safe."""
        self.after(0, lambda r=resultado: self._mostrar_resultado_stress(r))

    def _mostrar_resultado_stress(self, resultado: dict):
        self._ultimo_resultado_stress = resultado
        if hasattr(self, "_pulso_stress") and self._pulso_stress.winfo_exists():
            self._pulso_stress.detener(
                P["ambar"] if resultado.get("throttling") else P["primario"]
            )
        if hasattr(self, "_btn_cancelar_stress") and self._btn_cancelar_stress.winfo_exists():
            self._btn_cancelar_stress.configure(state="disabled")

        if "error" in resultado:
            self._stress_append_main(f"\n[ERROR] {resultado['error']}\n")
            if hasattr(self, "_lbl_fase_stress") and self._lbl_fase_stress.winfo_exists():
                self._lbl_fase_stress.configure(text="Benchmark finalizado con error controlado.")
        else:
            self._stress_append_main("\n" + "─" * 58 + "\n")
            self._stress_append_main("ANÁLISIS FINAL:\n\n")
            self._stress_append_main(resultado["diagnostico"] + "\n\n")
            self._stress_append_main(
                f"Muestras tomadas : {resultado['n_muestras']}  (modo: {resultado.get('modo', 'auto')})\n"
                f"Freq. máx / mín  : {resultado['freq_max_ghz']} GHz / {resultado['freq_min_ghz']} GHz\n"
                f"Freq. promedio   : {resultado['freq_avg_ghz']} GHz\n"
                f"Rendimiento prom.: {resultado.get('rendimiento_avg_mops', 0)} Mops/s "
                f"(índice {resultado.get('indice_rendimiento', 0)})\n"
                f"Uso CPU máx.     : {resultado['uso_max_pct']}%\n"
            )
            if hasattr(self, "_kpi_estado_st") and self._kpi_estado_st.winfo_exists():
                if resultado.get("cancelado"):
                    self._kpi_estado_st.set("CANCELADO", "Detenido por el operador", color=P["ambar"])
                elif resultado.get("throttling"):
                    self._kpi_estado_st.set("THROTTLING", f"Caída {resultado.get('caida_rendimiento_pct', 0)}%", color=P["rojo"])
                else:
                    self._kpi_estado_st.set("ESTABLE", f"Índice {resultado.get('indice_rendimiento', 0)} pts", color=P["primario"])
            if hasattr(self, "_lbl_fase_stress") and self._lbl_fase_stress.winfo_exists():
                self._lbl_fase_stress.configure(
                    text="Benchmark cancelado." if resultado.get("cancelado")
                    else ("⚠ Se detectó caída térmica/potencia." if resultado.get("throttling")
                          else "✔ Prueba completada: CPU térmicamente estable.")
                )
            if hasattr(self, "_barra_stress") and self._barra_stress.winfo_exists() and not resultado.get("cancelado"):
                dur = resultado.get("duracion_objetivo_s", 10.0)
                self._barra_stress.set(100.0, f"{dur:.1f} s / {dur:.1f} s (100%)", animar=True)

            if not resultado.get("cancelado"):
                estado_txt = "THROTTLING DETECTADO" if resultado.get("throttling") else "ESTABLE"
                t_stress = self._registrar_evento_nube(
                    tipo_evento="Micro-Stress CPU",
                    categoria=f"Micro-Stress CPU ({estado_txt})",
                    subcategoria=(
                        f"{resultado.get('rendimiento_avg_mops', 0)} Mops/s · "
                        f"Freq prom. {resultado.get('freq_avg_ghz', 0)} GHz · "
                        f"Uso máx. {resultado.get('uso_max_pct', 0)}%"
                    ),
                    solucion=str(resultado.get("diagnostico", "Benchmark completado.")),
                    prefijo_evento="STRESS",
                )
                if t_stress:
                    self._stress_append_main(f"\n✔ Reporte guardado en tu historial privado: {t_stress}\n")

        if hasattr(self, "_btn_stress") and self._btn_stress.winfo_exists():
            self._btn_stress.configure(state="normal", text="▶  Reiniciar Test")

    def iniciar_diagnostico(self):
        self.arbol_fase = 0
        self.arbol_rama = -1
        self.arbol_paso = 0
        self.temp_gira_ventilador = False
        self.dictamen_final = None
        self.ticket_id_actual = None
        self.ticket_sincronizado = False
        self.pantalla_diagnostico()

    def pantalla_diagnostico(self):
        self.limpiar_panel()

        frame = ctk.CTkFrame(
            self, width=920, height=640, corner_radius=0,
            fg_color=P["bg"], border_width=1, border_color=P["borde"]
        )
        animar_entrada_panel(frame)
        frame.pack_propagate(False)

        etiquetas_fase = {
            0: ("Fase 1 / 3 · Selección de Rama", "info"),
            1: (f"Fase 2 / 3 · Inferencia Guiada (Rama #{self.arbol_rama + 1})", "warn"),
            2: ("Fase 3 / 3 · Dictamen Técnico", "ok"),
        }
        txt_b, tipo_b = etiquetas_fase.get(self.arbol_fase, ("Diagnóstico", "info"))

        self._crear_encabezado_vista(
            frame,
            "Asistente Inferencial Avanzado — Árbol de Decisión",
            "Encadenamiento hacia adelante (Forward-Chaining) con generación de ticket y gemelo digital.",
            badge_texto=txt_b,
            badge_tipo=tipo_b,
            cmd_volver=self.pantalla_dashboard,
            texto_volver="← Dashboard",
        )

        if self.arbol_fase == 0:
            sub = tarjeta(frame)
            sub.pack(fill="both", expand=True, padx=14, pady=(2, 12))

            overline(sub, "Identifique el síntoma principal observable en el equipo", color=P["cian"]).pack(
                anchor="w", padx=16, pady=(12, 8)
            )

            grid = ctk.CTkFrame(sub, fg_color="transparent")
            grid.pack(fill="both", expand=True, padx=12, pady=4)
            grid.grid_columnconfigure(0, weight=1, uniform="rama")
            grid.grid_columnconfigure(1, weight=1, uniform="rama")

            for info in RAMAS_ARBOL:
                r_id = info["id"]
                c_rama = ctk.CTkFrame(
                    grid, fg_color=P["card_alt"], corner_radius=10,
                    border_width=1, border_color=P["borde"]
                )
                c_rama.grid(row=r_id // 2, column=r_id % 2, padx=6, pady=6, sticky="nsew")

                top_r = ctk.CTkFrame(c_rama, fg_color="transparent")
                top_r.pack(fill="x", padx=12, pady=(10, 2))
                Badge(top_r, f"Rama #{r_id + 1}", tipo="info").pack(side="left")
                ctk.CTkLabel(
                    top_r, text=f"{info['icono']}  {info['titulo']}",
                    font=F_H3, text_color=P["texto"]
                ).pack(side="left", padx=8)

                ctk.CTkLabel(
                    c_rama, text=info["detalle"], font=F_SMALL,
                    text_color=P["texto_sec"], anchor="w", justify="left", wraplength=390
                ).pack(fill="x", padx=12, pady=(2, 8))

                boton(
                    c_rama, "Iniciar Diagnóstico de esta Rama  →",
                    lambda r=r_id: self.seleccionar_sintoma(r),
                    variante="primario", height=32, font=F_SMALL
                ).pack(fill="x", padx=12, pady=(0, 10))

        elif self.arbol_fase == 1:
            cuerpo = tarjeta(frame)
            cuerpo.pack(fill="both", expand=True, padx=14, pady=(2, 12))
            self.renderizar_paso_rama(cuerpo)

        elif self.arbol_fase == 2:
            df = self.dictamen_final or obtener_dictamen(101)
            ticket = self._asegurar_ticket()

            cuerpo = tarjeta(frame)
            cuerpo.pack(fill="both", expand=True, padx=14, pady=(2, 12))

            banner = ctk.CTkFrame(cuerpo, fg_color=P["card_alt"], corner_radius=10)
            banner.pack(fill="x", padx=16, pady=(14, 8))

            f_badges = ctk.CTkFrame(banner, fg_color="transparent")
            f_badges.pack(fill="x", padx=14, pady=(10, 4))
            Badge(f_badges, "✔ DIAGNÓSTICO COMPLETADO", tipo="ok").pack(side="left")
            Badge(f_badges, f"Categoría: {df['categoria']}", tipo="err").pack(side="left", padx=8)
            Badge(f_badges, f"Subcategoría: {df['subcategoria']}", tipo="info").pack(side="left")
            Badge(f_badges, f"Ticket: {ticket} · Código #{df['codigo']}", tipo="neutro").pack(side="right")

            ctk.CTkLabel(
                banner, text=df["descripcion"], font=F_H2,
                text_color=P["texto"], anchor="w", justify="left", wraplength=830
            ).pack(fill="x", padx=14, pady=(2, 10))

            overline(cuerpo, "Guía de Solución Técnica Paso a Paso", color=P["cian"]).pack(
                anchor="w", padx=18, pady=(4, 2)
            )

            resultado_txt = (
                f"Categoría: {df['categoria']}   |   Subcategoría: {df['subcategoria']}\n"
                f"Descripción: {df['descripcion']}\n"
                f"────────────────────────────────────────────────────────────────────\n"
                f"GUÍA DE SOLUCIÓN PASO A PASO:\n{df['solucion']}\n\n"
                f"Ticket Generado: {ticket}   |   Código Interno de Soporte: #{df['codigo']}"
            )
            res_box = ctk.CTkTextbox(cuerpo, width=850, height=235, **estilo_textbox())
            res_box.pack(padx=16, pady=6, fill="both", expand=True)
            self._insertar_y_bloquear(res_box, resultado_txt)

            btn_frame = ctk.CTkFrame(cuerpo, fg_color="transparent")
            btn_frame.pack(pady=(6, 14))

            boton(
                btn_frame, "🌐 Ver Gemelo Digital 3D",
                self.abrir_visor_3d, variante="azul", width=220, height=40
            ).pack(side="left", padx=6)

            boton(
                btn_frame, "🗺️ Ver Mapa de Hardware 2D",
                lambda: self._abrir_mapa_desde_vista(df["categoria"], self.pantalla_diagnostico),
                variante="ambar", width=230, height=40
            ).pack(side="left", padx=6)

            boton(
                btn_frame, "💾 Guardar Reporte y Finalizar",
                self.guardar_reporte_final, variante="primario", width=240, height=40
            ).pack(side="left", padx=6)

            boton(
                btn_frame, "Nueva Consulta",
                self.iniciar_diagnostico, variante="neutro", width=140, height=40
            ).pack(side="left", padx=6)

    def seleccionar_sintoma(self, rama_id):
        self.arbol_rama = rama_id
        self.arbol_fase = 1
        self.arbol_paso = 0
        self.pantalla_diagnostico()

    def renderizar_paso_rama(self, frame):
        """Renderiza preguntas binarias o de opción múltiple según la rama activa."""
        r = self.arbol_rama
        p = self.arbol_paso

        if 0 <= r < len(RAMAS_ARBOL):
            info = RAMAS_ARBOL[r]
            enc = ctk.CTkFrame(frame, fg_color=P["surface"], corner_radius=8)
            enc.pack(fill="x", padx=18, pady=(14, 8))
            ctk.CTkLabel(
                enc, text=f"{info['icono']}  Rama #{r + 1}: {info['titulo']}   —   Paso #{p + 1}",
                font=F_H3, text_color=P["cian"]
            ).pack(side="left", padx=12, pady=8)
            boton(
                enc, "Cambiar Rama", self.iniciar_diagnostico,
                variante="fantasma", width=120, height=28, font=F_CAPTION
            ).pack(side="right", padx=12, pady=8)

        if r == 0:
            if p == 0:
                self.crear_pregunta_binaria(
                    frame, "¿El cable de energía está firmemente conectado al tomacorriente?",
                    al_si=lambda: self.avanzar_paso(1),
                    al_no=lambda: self.finalizar_diagnostico(obtener_dictamen(101)))
            elif p == 1:
                self.crear_pregunta_binaria(
                    frame, "¿El interruptor trasero de la fuente está en posición ON / 'I'?",
                    al_si=lambda: self.avanzar_paso(2),
                    al_no=lambda: self.finalizar_diagnostico(obtener_dictamen(102)))
            elif p == 2:
                self.crear_pregunta_binaria(
                    frame, "¿Al intentar encender, el ventilador de la fuente gira aunque sea un instante?",
                    al_si=lambda: self.guardar_temporal_y_avanzar(True, 3),
                    al_no=lambda: self.guardar_temporal_y_avanzar(False, 3))
            elif p == 3:
                self.crear_pregunta_binaria(
                    frame, "¿El equipo enciende aleatoriamente (a veces sí y a veces no)?",
                    al_si=lambda: self.evaluar_rama_energia_final(True),
                    al_no=lambda: self.evaluar_rama_energia_final(False))

        elif r == 1:
            ctk.CTkLabel(
                frame, text="Seleccione el patrón de pitidos o comportamiento de video al arrancar:",
                font=F_H3, text_color=P["texto"]
            ).pack(pady=(12, 10))
            opciones = [
                ("1. Pitidos cortos repetitivos (fallo de inicialización de memoria RAM)", obtener_dictamen(201)),
                ("2. 1 pitido largo + 2 o 3 cortos (falla en tarjeta gráfica / PCIe)", obtener_dictamen(202)),
                ("3. Tono continuo ininterrumpido (cortocircuito o falla eléctrica en placa)", obtener_dictamen(203)),
                ("4. Sin pitidos, pero el monitor permanece negro sin señal de video", obtener_dictamen(204)),
            ]
            for texto, dictamen in opciones:
                boton(
                    frame, texto, lambda d=dictamen: self.finalizar_diagnostico(d),
                    variante="neutro", width=720, height=42, anchor="w"
                ).pack(pady=5, padx=24)

        elif r == 2:
            if p == 0:
                self.crear_pregunta_binaria(
                    frame, "¿El ventilador del procesador gira al intentar arrancar?",
                    al_si=lambda: self.avanzar_paso(1),
                    al_no=lambda: self.finalizar_diagnostico(obtener_dictamen(301)))
            elif p == 1:
                self.crear_pregunta_binaria(
                    frame, "¿Se ha cambiado la pasta térmica en los últimos 2 años?",
                    al_si=lambda: self.finalizar_diagnostico(obtener_dictamen(303)),
                    al_no=lambda: self.finalizar_diagnostico(obtener_dictamen(302)))

        elif r == 3:
            if p == 0:
                self.crear_pregunta_binaria(
                    frame, "¿El equipo se reinicia ANTES de mostrar el logo de la marca (BIOS)?",
                    al_si=lambda: self.finalizar_diagnostico(obtener_dictamen(401)),
                    al_no=lambda: self.avanzar_paso(1))
            elif p == 1:
                self.crear_pregunta_binaria(
                    frame, "¿Llega a mostrar el logo de Windows antes de reiniciarse?",
                    al_si=lambda: self.finalizar_diagnostico(obtener_dictamen(403)),
                    al_no=lambda: self.finalizar_diagnostico(obtener_dictamen(402)))

        elif r == 4:
            self.crear_pregunta_binaria(
                frame, "¿El SSD NVMe desaparece del sistema tras un rato de uso intensivo?",
                al_si=lambda: self.finalizar_diagnostico(obtener_dictamen(501)),
                al_no=lambda: self.finalizar_diagnostico(obtener_dictamen(502)))

        elif r == 5:
            if p == 0:
                self.crear_pregunta_binaria(
                    frame, "¿El uso de CPU en reposo supera el 40% en el Administrador de Tareas?",
                    al_si=lambda: self.finalizar_diagnostico(obtener_dictamen(601)),
                    al_no=lambda: self.avanzar_paso(1))
            elif p == 1:
                self.crear_pregunta_binaria(
                    frame, "¿El disco de almacenamiento se mantiene al 100% de uso constante?",
                    al_si=lambda: self.finalizar_diagnostico(obtener_dictamen(602)),
                    al_no=lambda: self.finalizar_diagnostico(obtener_dictamen(603)))

        elif r == 6:
            self.crear_pregunta_binaria(
                frame, "¿Ocurren pantallazos azules (BSOD) durante juegos o tareas pesadas?",
                al_si=lambda: self.finalizar_diagnostico(obtener_dictamen(702)),
                al_no=lambda: self.finalizar_diagnostico(obtener_dictamen(701)))

        elif r == 7:
            if p == 0:
                self.crear_pregunta_binaria(
                    frame, "¿El adaptador de red aparece conectado (icono de Wi-Fi o Ethernet activo)?",
                    al_si=lambda: self.avanzar_paso(1),
                    al_no=lambda: self.finalizar_diagnostico(obtener_dictamen(801)))
            elif p == 1:
                self.crear_pregunta_binaria(
                    frame, "¿Puede navegar pero sufre ping alto, cortes o pérdida de paquetes?",
                    al_si=lambda: self.finalizar_diagnostico(obtener_dictamen(802)),
                    al_no=lambda: self.finalizar_diagnostico(obtener_dictamen(803)))

    def crear_pregunta_binaria(self, frame, texto_pregunta, al_si, al_no):
        caja = ctk.CTkFrame(
            frame, fg_color=P["card_alt"], corner_radius=12,
            border_width=1, border_color=P["borde_fuerte"]
        )
        caja.pack(padx=36, pady=(28, 16), fill="x")

        overline(caja, "Pregunta de Verificación Técnica", color=P["ambar"]).pack(
            anchor="w", padx=20, pady=(14, 4)
        )
        ctk.CTkLabel(
            caja, text=texto_pregunta, font=F_H2, text_color=P["texto"],
            wraplength=760, justify="left", anchor="w"
        ).pack(fill="x", padx=20, pady=(2, 18))

        btn_box = ctk.CTkFrame(frame, fg_color="transparent")
        btn_box.pack(pady=14)
        boton(btn_box, "✔  SÍ, SE CUMPLE", al_si, variante="primario", width=210, height=44).pack(
            side="left", padx=12
        )
        boton(btn_box, "✖  NO SE CUMPLE", al_no, variante="neutro", width=210, height=44).pack(
            side="left", padx=12
        )

    def avanzar_paso(self, siguiente_paso):
        self.arbol_paso = siguiente_paso
        self.pantalla_diagnostico()

    def guardar_temporal_y_avanzar(self, valor, siguiente_paso):
        self.temp_gira_ventilador = valor
        self.avanzar_paso(siguiente_paso)

    def evaluar_rama_energia_final(self, intermitente):
        d = MotorDiagnostico.evaluar_energia(
            cable_ok=True, switch_ok=True,
            ventilador_gira=self.temp_gira_ventilador,
            intermitente=intermitente,
        )
        self.finalizar_diagnostico(d)

    def finalizar_diagnostico(self, dictamen):
        self.dictamen_final = dictamen
        self.arbol_fase = 2
        self.ticket_id_actual = generate_secure_ticket_id(self.dni_usuario_activo, "TICKET")
        self.ticket_sincronizado = True
        self._registrar_evento_nube(
            tipo_evento="Árbol Diagnóstico",
            categoria=str(dictamen.get("categoria", "Diagnóstico")),
            subcategoria=str(dictamen.get("subcategoria", "Dictamen")),
            solucion=str(dictamen.get("solucion", "")),
            codigo=dictamen.get("codigo", 0),
            ticket_id_fijo=self.ticket_id_actual,
        )
        self.pantalla_diagnostico()

    def _abrir_mapa_desde_vista(self, categoria_afectada: str, vista_retorno):
        self._vista_retorno_mapa = vista_retorno
        self.pantalla_hardware_map(categoria_afectada)

    def pantalla_hardware_map(self, categoria_afectada: str):
        """
        Vista del Mapa de Componentes del Sistema.
        Delega el renderizado completo a MotherboardMapView (dark-tech, alta fidelidad).
        """
        self.limpiar_panel()

        frame = ctk.CTkFrame(
            self,
            width=940, height=668,
            corner_radius=0,
            fg_color="#0b0f19",
            border_width=1,
            border_color="#1e293b",
        )
        animar_entrada_panel(frame)
        frame.grid_propagate(False)

        header = ctk.CTkFrame(frame, fg_color="#0f172a", corner_radius=0)
        header.pack(fill="x")

        ctk.CTkLabel(
            header,
            text="🖥  Mapa Esquemático 2D de Componentes del Sistema",
            font=("Segoe UI Semibold", 15),
            text_color="#06b6d4",
        ).pack(side="left", padx=18, pady=10)

        if categoria_afectada:
            Badge(header, f"⚠ {categoria_afectada}", tipo="err").pack(side="left", padx=6)

        ctk.CTkLabel(
            header,
            text=f"Operador: {self.dni_usuario_activo or 'LOCAL'}",
            font=("Consolas", 10),
            text_color="#94a3b8",
        ).pack(side="right", padx=18)

        cmd_volver = self._vista_retorno_mapa or (
            self.pantalla_diagnostico if self.dictamen_final else self.pantalla_dashboard
        )
        self._vista_retorno_mapa = None

        self.mapa_actual = MotherboardMapView(
            parent=frame,
            hw_data=self.hardware_detectado or {},
            categoria_diag=categoria_afectada,
            cmd_volver=cmd_volver,
            cmd_visor_3d=self.abrir_visor_3d,
        )

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

        nombre_txt = f"Reporte_Diagnostico_{ticket_id}.txt"
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

        nombre_json = f"Reporte_Diagnostico_{ticket_id}.json"
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
            f"Reporte {ticket_id} exportado (TXT + JSON) y sincronizando con Supabase.",
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
        estilizar_toplevel(v, self, "Mis Tickets Privados en la Nube", 660, 460)

        card = tarjeta(v)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        dni = (self.dni_usuario_activo or "").strip()
        dni_mask = f"••••{dni[-4:]}" if len(dni) >= 4 else (dni or "SIN SESIÓN")

        enc = ctk.CTkFrame(card, fg_color="transparent")
        enc.pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkLabel(
            enc, text="🔒 Mis Tickets Privados en la Nube",
            font=F_H2, text_color=P["texto"]
        ).pack(side="left")
        Badge(enc, f"Cuenta DNI {dni_mask}", tipo="ok" if dni else "warn").pack(side="right")

        ctk.CTkLabel(
            card,
            text="Por seguridad y privacidad, solo se muestran los reportes generados con tu cuenta.",
            font=F_SMALL, text_color=P["texto_sec"], anchor="w"
        ).pack(fill="x", padx=14, pady=(0, 8))

        scroll = ctk.CTkScrollableFrame(card, fg_color=P["bg"], corner_radius=8)
        scroll.pack(fill="both", expand=True, padx=14, pady=4)

        lbl_estado = ctk.CTkLabel(
            scroll, text="Consultando tus reportes privados en Supabase…",
            font=F_SMALL, text_color=P["texto_sec"]
        )
        lbl_estado.pack(pady=24)

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

            for item in filas:
                t_id = item.get("id_ticket", "?")
                specs = item.get("specs_json") or {}
                tipo = specs.get("tipo_equipo", "desktop")
                evento = specs.get("tipo_evento") or "Diagnóstico"
                etiqueta_tipo = "Teléfono" if tipo == "phone" else ("Laptop" if tipo == "laptop" else "PC")
                score = item.get("health_score", 100)
                equipo = item.get("placa_base") or item.get("cpu") or "Equipo diagnosticado"
                diag_txt = (item.get("diagnostico") or "").strip()
                fecha_raw = str(item.get("fecha_creacion") or "")
                fecha_fmt = fecha_raw[:16].replace("T", " ") if len(fecha_raw) >= 16 else ""

                fila = ctk.CTkFrame(
                    scroll, fg_color=P["surface"], corner_radius=8,
                    border_width=1, border_color=P["borde"]
                )
                fila.pack(fill="x", padx=6, pady=4)

                info_box = ctk.CTkFrame(fila, fg_color="transparent")
                info_box.pack(side="left", fill="x", expand=True, padx=10, pady=8)

                meta_line = f"[{evento}]  {t_id}  ·  {etiqueta_tipo}  ·  Salud {score}/100"
                if fecha_fmt:
                    meta_line += f"  ·  {fecha_fmt}"
                ctk.CTkLabel(
                    info_box, text=meta_line,
                    font=("Segoe UI Semibold", 11), text_color=P["texto"], anchor="w"
                ).pack(fill="x")
                detalle = diag_txt if diag_txt else str(equipo)
                ctk.CTkLabel(
                    info_box, text=f"{str(equipo)[:42]} — {detalle}"[:92],
                    font=F_CAPTION, text_color=P["texto_sec"], anchor="w"
                ).pack(fill="x")

                boton(
                    fila, "Abrir 3D",
                    lambda tid=t_id: webbrowser.open(f"https://indiserv-web3d.vercel.app/?ticket={tid}"),
                    variante="primario", width=92, height=28, font=F_SMALL
                ).pack(side="right", padx=10, pady=8)

        def _cargar_en_hilo():
            filas = CloudGateway.listar_tickets_usuario(dni)
            try:
                self.after(0, lambda f=filas: _render_tickets(f))
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
            fila_b, "Cerrar", v.destroy,
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

            with open("sugerencias_locales.txt", "a", encoding="utf-8") as s:
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


if __name__ == "__main__":
    app = AppIndiServ()
    app.mainloop()
