"""
main.py — IndiServ Analytica (Sistema Experto de Diagnóstico de PC)
===================================================================
Orquestador principal de la ventana, ciclo de vida, autenticación,
escaneo de hardware en segundo plano y ensamblaje de vistas modulares:
  • ui/dashboard_tabs.py    — Dashboard y sus 5 pestañas de telemetría
  • ui/diagnostico_views.py — Diagnóstico Multisíntoma y Buscador Asistido IA
  • ui/stress_y_arbol.py    — Micro-Stress Test, Árbol Guiado y Mapa 2D
  • ui/modales.py           — Gemelo 3D, Reporte Final, Privacidad, Tickets y Sugerencias
"""

from __future__ import annotations

import os
import sys
import threading
import customtkinter as ctk
from PIL import Image


def _resource_path(relative_path: str) -> str:
    """Resuelve rutas de recursos tanto en desarrollo como dentro del .exe de PyInstaller."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


from core.hardware import LectorHardware, calcular_health_score
from core.cloud_gateway import CloudGateway
from core.diagnostico import MicroStressTest
from core.security import (
    generate_secure_ticket_id,
    check_login_rate_limit,
    record_failed_login,
    reset_login_rate_limit,
    is_honey_credential,
    trigger_honeytoken_alert,
)
from core.ui_theme import (
    P,
    F_H1, F_H2, F_H3, F_BODY, F_SMALL, F_CAPTION, F_MONO,
    Badge,
    PuntoPulso,
    boton,
    tarjeta,
    entrada,
    overline,
    estilo_checkbox,
    toast,
    animar_entrada_panel,
)
from ui import DashboardMixin, DiagnosticoMixin, StressYArbolMixin, ModalesMixin

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


class AppIndiServ(DashboardMixin, DiagnosticoMixin, StressYArbolMixin, ModalesMixin, ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("IndiServ Analytica — Sistema Experto de Diagnóstico de PC")
        self.geometry("980x700")
        self.minsize(960, 680)
        self.resizable(True, True)
        self.configure(fg_color=P["bg"])

        self._es_pantalla_completa: bool = False
        self._btn_fullscreen = None
        self._bg_pil = None
        self._bg_resize_after = None
        self._bg_last_size = (0, 0)
        self.bg_label = None
        fondo_path = _resource_path(os.path.join("assets", "fondo.jpg"))
        if os.path.exists(fondo_path):
            try:
                self._bg_pil = Image.open(fondo_path)
                self.bg_image = ctk.CTkImage(self._bg_pil, size=(980, 700))
                self.bg_label = ctk.CTkLabel(self, image=self.bg_image, text="")
                self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            except Exception:
                pass

        self.bind("<Configure>", self._al_redimensionar_ventana)
        self.bind("<F11>", lambda _e: self.alternar_pantalla_completa())
        self.bind("<Escape>", lambda _e: self.salir_pantalla_completa())
        if sys.platform == "darwin":
            self.bind("<Command-Control-f>", lambda _e: self.alternar_pantalla_completa())
            self.bind("<Command-Shift-F>", lambda _e: self.alternar_pantalla_completa())

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
        self.after(80, lambda: self._aplicar_pantalla_completa(True))

    def _al_redimensionar_ventana(self, event=None):
        """Reescala el fondo dinámicamente al cambiar entre ventana y pantalla completa."""
        if event is not None and event.widget is not self:
            return
        if not self._bg_pil or not self.bg_label:
            return
        w = max(980, self.winfo_width())
        h = max(700, self.winfo_height())
        if abs(w - self._bg_last_size[0]) < 12 and abs(h - self._bg_last_size[1]) < 12:
            return
        if self._bg_resize_after:
            try:
                self.after_cancel(self._bg_resize_after)
            except Exception:
                pass

        def _aplicar_bg():
            self._bg_resize_after = None
            try:
                if not self.winfo_exists() or not self.bg_label:
                    return
                cw = max(980, self.winfo_width())
                ch = max(700, self.winfo_height())
                self._bg_last_size = (cw, ch)
                self.bg_image = ctk.CTkImage(self._bg_pil, size=(cw, ch))
                self.bg_label.configure(image=self.bg_image)
            except Exception:
                pass

        self._bg_resize_after = self.after(60, _aplicar_bg)

    def _aplicar_pantalla_completa(self, activar: bool):
        """Activa o desactiva pantalla completa de forma segura en Windows, Linux y macOS."""
        self._es_pantalla_completa = bool(activar)
        aplicado = False
        try:
            self.attributes("-fullscreen", self._es_pantalla_completa)
            aplicado = True
        except Exception:
            aplicado = False

        if not aplicado and self._es_pantalla_completa:
            try:
                if sys.platform == "win32" or sys.platform == "darwin":
                    self.state("zoomed")
                else:
                    self.attributes("-zoomed", True)
            except Exception:
                try:
                    sw = self.winfo_screenwidth()
                    sh = self.winfo_screenheight()
                    self.geometry(f"{sw}x{sh}+0+0")
                except Exception:
                    pass
        elif not self._es_pantalla_completa:
            try:
                if sys.platform == "win32" or sys.platform == "darwin":
                    self.state("normal")
                else:
                    self.attributes("-zoomed", False)
            except Exception:
                pass
            try:
                sw = self.winfo_screenwidth()
                sh = self.winfo_screenheight()
                x = max(0, (sw - 980) // 2)
                y = max(0, (sh - 700) // 2)
                self.geometry(f"980x700+{x}+{y}")
            except Exception:
                self.geometry("980x700")

        self._actualizar_texto_btn_fullscreen()
        self.after(90, self._al_redimensionar_ventana)

    def alternar_pantalla_completa(self):
        """Alterna entre modo pantalla completa y modo ventana (F11 / botón superior)."""
        self._aplicar_pantalla_completa(not self._es_pantalla_completa)

    def salir_pantalla_completa(self):
        """Sale del modo pantalla completa al presionar Escape."""
        if self._es_pantalla_completa:
            self._aplicar_pantalla_completa(False)

    def _texto_btn_fullscreen(self) -> str:
        return "🗗 Ventana (Esc)" if self._es_pantalla_completa else "⛶ Pantalla Completa"

    def _actualizar_texto_btn_fullscreen(self):
        if self._btn_fullscreen is not None:
            try:
                if self._btn_fullscreen.winfo_exists():
                    self._btn_fullscreen.configure(text=self._texto_btn_fullscreen())
            except Exception:
                pass

    def _colocar_boton_fullscreen_flotante(self):
        """Coloca un botón discreto en la esquina superior derecha para pantallas centradas."""
        self._btn_fullscreen = boton(
            self,
            self._texto_btn_fullscreen(),
            self.alternar_pantalla_completa,
            variante="neutro",
            width=142,
            height=28,
            font=F_CAPTION,
        )
        self._btn_fullscreen.place(relx=0.985, rely=0.022, anchor="ne")

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
        self._colocar_boton_fullscreen_flotante()

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
        if auth_res.get("error_conexion"):
            if hasattr(self, "btn_ingresar"):
                self.btn_ingresar.configure(state="normal", text="Ingresar a Consola de Operaciones  →")
            self.lbl_login_error.configure(text=f"⚠ {auth_res['error_conexion']}")
        elif auth_res.get("autenticado"):
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
        self._colocar_boton_fullscreen_flotante()

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



if __name__ == "__main__":
    app = AppIndiServ()
    app.mainloop()
