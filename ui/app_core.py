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

import base64
import io
import os
import sys
import threading
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageOps


def _resource_path(relative_path: str) -> str:
    """Resuelve rutas de recursos tanto en desarrollo como dentro del .exe de PyInstaller."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
    get_device_fingerprint,
    save_session_token,
    load_session_token,
    clear_session_token,
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
        self._bg_visible: bool = False
        self.bg_label = None
        fondo_path = _resource_path(os.path.join("assets", "fondo.jpg"))
        if os.path.exists(fondo_path):
            try:
                pil_img = Image.open(fondo_path)
                if pil_img.width > 1920 or pil_img.height > 1080:
                    pil_img.thumbnail((1920, 1080), Image.Resampling.BILINEAR)
                self._bg_pil = pil_img
                init_w = max(980, self.winfo_screenwidth())
                init_h = max(700, self.winfo_screenheight())
                self._bg_last_size = (init_w, init_h)
                self.bg_image = ctk.CTkImage(self._bg_pil, size=(init_w, init_h))
                self.bg_label = ctk.CTkLabel(self, image=self.bg_image, text="")
                self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
                self._bg_visible = True
            except Exception:
                pass

        self.bind("<Configure>", self._al_redimensionar_ventana)
        self.bind("<F11>", lambda _e: self.alternar_pantalla_completa())
        self.bind("<Escape>", lambda _e: self.salir_pantalla_completa())
        if sys.platform == "darwin":
            self.bind("<Command-Control-f>", lambda _e: self.alternar_pantalla_completa())
            self.bind("<Command-Shift-F>", lambda _e: self.alternar_pantalla_completa())

        self.dni_usuario_activo: str | None = None
        self.usuario_activo_info: dict = {}
        self.hardware_detectado: dict | None = None
        self._device_hash, self._device_label = get_device_fingerprint()
        self._session_token: str | None = None
        self._otp_timer_after: str | None = None
        self._avatar_img_refs: dict[str, ctk.CTkImage] = {}
        self._avatar_cache_sig: dict[str, tuple[int, str]] = {}
        self._dashboard_frame: ctk.CTkFrame | None = None
        self._dashboard_cache_key: tuple | None = None

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
        self._iniciar_con_sesion_o_login()
        self.after(80, lambda: self._aplicar_pantalla_completa(True))
        self.after(1200, CloudGateway.warm_up_async)

    def _post_ui(self, fn):
        """Encola un callback en el hilo principal Tk ignorando cierres de ventana en curso."""
        try:
            self.after(0, fn)
        except Exception:
            pass

    def _iniciar_con_sesion_o_login(self):
        """Si existe un token local, valida en servidor si sigue dentro de los 15 minutos."""
        saved = load_session_token()
        if not saved:
            self.pantalla_login()
            return
        tok, dh = saved
        if dh != self._device_hash:
            clear_session_token()
            self.pantalla_login()
            return

        self.limpiar_panel(mostrar_fondo=True)
        frame = ctk.CTkFrame(
            self, width=420, height=175, corner_radius=0,
            fg_color=P["card"], border_width=1, border_color=P["borde_fuerte"]
        )
        animar_entrada_panel(frame)
        frame.pack_propagate(False)
        ctk.CTkLabel(
            frame, text="Verificando Sesión Segura (15 min)…",
            font=F_H2, text_color=P["texto"]
        ).pack(pady=(34, 10))
        barra = ctk.CTkProgressBar(
            frame, width=320, height=8, mode="indeterminate",
            fg_color=P["surface"], progress_color=P["primario"]
        )
        barra.pack(pady=8)
        barra.start()
        ctk.CTkLabel(
            frame, text="Validando token y huella de dispositivo en Supabase…",
            font=F_SMALL, text_color=P["texto_sec"]
        ).pack(pady=4)

        def _bg_validate():
            res = CloudGateway.validar_sesion_token(tok, self._device_hash)

            def _apply():
                if not self.winfo_exists():
                    return
                if res.get("ok") and res.get("user"):
                    user = res["user"]
                    self._session_token = tok
                    self.dni_usuario_activo = user.get("dni")
                    self.usuario_activo_info = {
                        "dni": user.get("dni"),
                        "correo": user.get("correo"),
                        "nickname": user.get("nickname") or "Operador",
                        "avatar_data": user.get("avatar_data"),
                        "rol": user.get("rol") or "operator",
                    }
                    self._mostrar_splash_carga()
                else:
                    clear_session_token()
                    self._session_token = None
                    self.usuario_activo_info = {}
                    self.pantalla_login()

            self._post_ui(_apply)

        threading.Thread(target=_bg_validate, daemon=True).start()

    def cerrar_sesion(self):
        """Revoca la sesión de 15 min inmediatamente en Supabase y limpia el token local."""
        tok = self._session_token
        if not tok:
            saved = load_session_token()
            if saved:
                tok = saved[0]
        clear_session_token()
        self._session_token = None
        self.dni_usuario_activo = None
        self.usuario_activo_info = {}
        if tok:
            threading.Thread(
                target=lambda: CloudGateway.revocar_sesion_token(tok, self._device_hash),
                daemon=True,
            ).start()
        self.pantalla_login()

    def _decodificar_avatar_ctk(
        self, avatar_data: str | None, size: int = 32, cache_key: str = "topbar"
    ) -> ctk.CTkImage | None:
        """Decodifica un Data URI base64 en un CTkImage circular seguro con memoización."""
        raw = str(avatar_data or "").strip()
        if not raw.startswith("data:image/") or ";base64," not in raw:
            self._avatar_img_refs.pop(cache_key, None)
            self._avatar_cache_sig.pop(cache_key, None)
            return None
        sig = (size, raw)
        if self._avatar_cache_sig.get(cache_key) == sig and cache_key in self._avatar_img_refs:
            return self._avatar_img_refs[cache_key]
        try:
            b64 = raw.split(";base64,", 1)[1]
            img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGBA")
            img = ImageOps.fit(img, (size * 2, size * 2), Image.Resampling.LANCZOS)
            mask = Image.new("L", img.size, 0)
            ImageDraw.Draw(mask).ellipse((0, 0, img.size[0] - 1, img.size[1] - 1), fill=255)
            img.putalpha(mask)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
            self._avatar_img_refs[cache_key] = ctk_img
            self._avatar_cache_sig[cache_key] = sig
            return ctk_img
        except Exception:
            return None

    def _mostrar_fondo(self, visible: bool):
        """Muestra el fondo fotográfico solo en pantallas de acceso; lo oculta en Dashboard/vistas."""
        if not self.bg_label:
            self._bg_visible = False
            return
        if visible:
            if not self._bg_visible:
                self._bg_visible = True
                try:
                    self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
                    self.bg_label.lower()
                except Exception:
                    pass
                self._al_redimensionar_ventana()
        else:
            if self._bg_visible:
                self._bg_visible = False
                if self._bg_resize_after:
                    try:
                        self.after_cancel(self._bg_resize_after)
                    except Exception:
                        pass
                    self._bg_resize_after = None
                try:
                    self.bg_label.place_forget()
                except Exception:
                    pass

    def _al_redimensionar_ventana(self, event=None):
        """Reescala el fondo dinámicamente solo cuando está visible en pantallas de autenticación."""
        if event is not None and event.widget is not self:
            return
        if not self._bg_visible or not self._bg_pil or not self.bg_label:
            return
        w = max(980, self.winfo_width())
        h = max(700, self.winfo_height())
        if abs(w - self._bg_last_size[0]) < 16 and abs(h - self._bg_last_size[1]) < 16:
            return
        if self._bg_resize_after:
            try:
                self.after_cancel(self._bg_resize_after)
            except Exception:
                pass

        def _aplicar_bg():
            self._bg_resize_after = None
            try:
                if not self.winfo_exists() or not self._bg_visible or not self.bg_label:
                    return
                cw = max(980, self.winfo_width())
                ch = max(700, self.winfo_height())
                self._bg_last_size = (cw, ch)
                self.bg_image = ctk.CTkImage(self._bg_pil, size=(cw, ch))
                self.bg_label.configure(image=self.bg_image)
            except Exception:
                pass

        self._bg_resize_after = self.after(100, _aplicar_bg)

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

    def limpiar_panel(self, mostrar_fondo: bool = False, destruir_dashboard: bool = False):
        """
        Elimina vistas transitorias y controla el fondo. Preserva el Dashboard en caché
        (place_forget) para volver en <15 ms, salvo que se pida destruir_dashboard=True.
        """
        if self._stress_actual and self._stress_actual.activo:
            try:
                self._stress_actual.cancelar()
            except Exception:
                pass
        self._mostrar_fondo(mostrar_fondo)
        dash = getattr(self, "_dashboard_frame", None)
        for widget in self.winfo_children():
            if widget == self.bg_label:
                continue
            if not destruir_dashboard and dash is not None and widget == dash:
                try:
                    widget.place_forget()
                except Exception:
                    pass
                continue
            widget.destroy()
        if destruir_dashboard:
            self._dashboard_frame = None
            self._dashboard_cache_key = None

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
        self.limpiar_panel(mostrar_fondo=True, destruir_dashboard=True)
        self._colocar_boton_fullscreen_flotante()

        card = ctk.CTkFrame(
            self, width=440, height=535, corner_radius=0,
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
        ).pack(fill="x", pady=(0, 6))

        boton(
            acciones, "🔑 ¿Olvidaste tu contraseña?",
            self.pantalla_recuperar_password, variante="util", width=388, height=30,
            font=F_CAPTION, hover_border_color=P["ambar"]
        ).pack(fill="x")

    def pantalla_recuperar_password(self):
        """Flujo seguro de recuperación de contraseña desde Login (DNI + Correo + OTP Brevo)."""
        if self._otp_timer_after:
            try:
                self.after_cancel(self._otp_timer_after)
            except Exception:
                pass
            self._otp_timer_after = None

        self.limpiar_panel(mostrar_fondo=True)
        self._colocar_boton_fullscreen_flotante()

        state = {
            "step": 1,
            "dni": "",
            "correo": "",
            "challenge_id": "",
            "masked_email": "",
            "exp_left": 0,
            "resend_left": 0,
            "busy": False,
        }

        card = ctk.CTkFrame(
            self, width=460, height=540, corner_radius=0,
            fg_color=P["card"], border_width=1, border_color=P["borde_fuerte"]
        )
        animar_entrada_panel(card)
        card.pack_propagate(False)

        top = ctk.CTkFrame(card, fg_color=P["surface"], corner_radius=12)
        top.pack(fill="x", padx=18, pady=(16, 8))
        ctk.CTkLabel(
            top, text="🔑 Recuperar Contraseña", font=F_H2, text_color=P["ambar"], anchor="w"
        ).pack(fill="x", padx=14, pady=(12, 2))
        lbl_sub = ctk.CTkLabel(
            top,
            text="Ingrese su DNI y correo registrado. Enviaremos un código de 6 dígitos para restablecer su clave.",
            font=F_CAPTION, text_color=P["texto_sec"], anchor="w", wraplength=400, justify="left"
        )
        lbl_sub.pack(fill="x", padx=14, pady=(0, 12))

        contenedor = ctk.CTkFrame(card, fg_color="transparent")
        contenedor.pack(fill="both", expand=True, padx=26, pady=4)

        lbl_msg = ctk.CTkLabel(card, text="", text_color=COLOR_ERR, font=F_SMALL, wraplength=400)
        lbl_msg.pack(pady=(2, 4))

        def _render_step1():
            for w in contenedor.winfo_children():
                w.destroy()
            lbl_msg.configure(text="")
            lbl_sub.configure(
                text="Ingrese su DNI y correo registrado. Enviaremos un código de 6 dígitos para restablecer su clave."
            )

            overline(contenedor, "DNI del Operador (8 dígitos)").pack(anchor="w", pady=(6, 2))
            ent_dni = entrada(contenedor, "Ej. 75509123", width=390)
            if state["dni"]:
                ent_dni.insert(0, state["dni"])
            ent_dni.pack(fill="x", pady=(0, 8))

            overline(contenedor, "Correo Registrado").pack(anchor="w", pady=(4, 2))
            ent_cor = entrada(contenedor, "operador@indiserv.pe", width=390)
            if state["correo"]:
                ent_cor.insert(0, state["correo"])
            ent_cor.pack(fill="x", pady=(0, 12))

            def _solicitar():
                if state["busy"]:
                    return
                d = ent_dni.get().strip()
                c = ent_cor.get().strip()
                if len(d) < 8 or "@" not in c:
                    lbl_msg.configure(text="⚠ Ingrese un DNI válido (8 dígitos) y su correo.", text_color=COLOR_ERR)
                    return
                state["busy"] = True
                btn_env.configure(state="disabled", text="Enviando código de recuperación…")
                lbl_msg.configure(text="")

                def _bg():
                    res = CloudGateway.iniciar_recuperacion_password(
                        d, c, self._device_hash, self._device_label
                    )

                    def _apply():
                        state["busy"] = False
                        if not card.winfo_exists():
                            return
                        if res.get("ok") and res.get("challenge_id"):
                            state.update({
                                "step": 2,
                                "dni": d,
                                "correo": c,
                                "challenge_id": res["challenge_id"],
                                "masked_email": res.get("masked_email") or c,
                                "exp_left": int(res.get("expires_in_sec") or 600),
                                "resend_left": int(res.get("resend_cooldown_sec") or 60),
                            })
                            _render_step2()
                        else:
                            btn_env.configure(state="normal", text="Enviar Código de Recuperación  →")
                            lbl_msg.configure(
                                text=f"✖ {res.get('error') or res.get('error_conexion') or 'No se pudo iniciar la recuperación.'}",
                                text_color=COLOR_ERR,
                            )

                    self._post_ui(_apply)

                threading.Thread(target=_bg, daemon=True).start()

            btn_env = boton(
                contenedor, "Enviar Código de Recuperación  →", _solicitar,
                variante="ambar", width=390, height=40
            )
            btn_env.pack(fill="x", pady=(4, 8))
            boton(
                contenedor, "← Volver al Inicio de Sesión", self.pantalla_login,
                variante="fantasma", width=390, height=34
            ).pack(fill="x")
            ent_cor.bind("<Return>", lambda _e: _solicitar())

        def _render_step2():
            for w in contenedor.winfo_children():
                w.destroy()
            lbl_msg.configure(text="")
            lbl_sub.configure(
                text=f"Si los datos coinciden con una cuenta activa, enviamos un código de 6 dígitos a {state['masked_email']}."
            )

            overline(contenedor, "Código de Seguridad (6 dígitos)").pack(anchor="w", pady=(2, 2))
            ent_code = entrada(contenedor, "000000", width=390)
            ent_code.configure(font=F_H2, justify="center")
            ent_code.pack(fill="x", pady=(0, 4))

            lbl_tmr = ctk.CTkLabel(contenedor, text="", font=F_CAPTION, text_color=P["texto_sec"])
            lbl_tmr.pack(anchor="w", pady=(0, 6))

            overline(contenedor, "Nueva Contraseña (mín. 8 caracteres)").pack(anchor="w", pady=(2, 2))
            ent_p1 = entrada(contenedor, "••••••••", show="*", width=390)
            ent_p1.pack(fill="x", pady=(0, 6))

            overline(contenedor, "Confirmar Nueva Contraseña").pack(anchor="w", pady=(2, 2))
            ent_p2 = entrada(contenedor, "••••••••", show="*", width=390)
            ent_p2.pack(fill="x", pady=(0, 10))

            def _confirmar():
                if state["busy"]:
                    return
                code = ent_code.get().strip()
                p1 = ent_p1.get().strip()
                p2 = ent_p2.get().strip()
                if len(code) != 6 or not code.isdigit():
                    lbl_msg.configure(text="⚠ Ingrese exactamente 6 dígitos numéricos.", text_color=COLOR_ERR)
                    return
                if len(p1) < 8:
                    lbl_msg.configure(text="⚠ La nueva contraseña debe tener al menos 8 caracteres.", text_color=COLOR_ERR)
                    return
                if p1 != p2:
                    lbl_msg.configure(text="⚠ Las contraseñas no coinciden.", text_color=COLOR_ERR)
                    return

                state["busy"] = True
                btn_ok.configure(state="disabled", text="Restableciendo contraseña…")
                lbl_msg.configure(text="")
                cid = state["challenge_id"]

                def _bg():
                    res = CloudGateway.verificar_recuperacion_password(
                        state["dni"], cid, code, p1, self._device_hash
                    )

                    def _apply():
                        state["busy"] = False
                        if not card.winfo_exists():
                            return
                        if res.get("ok"):
                            if self._otp_timer_after:
                                try:
                                    self.after_cancel(self._otp_timer_after)
                                except Exception:
                                    pass
                                self._otp_timer_after = None
                            self.pantalla_login()
                            toast(
                                self,
                                "Contraseña restablecida. Todas las sesiones anteriores fueron cerradas.",
                                tipo="ok",
                            )
                        else:
                            btn_ok.configure(state="normal", text="Restablecer Contraseña  →")
                            lbl_msg.configure(
                                text=f"✖ {res.get('error') or res.get('error_conexion') or 'Código incorrecto o expirado.'}",
                                text_color=COLOR_ERR,
                            )

                    self._post_ui(_apply)

                threading.Thread(target=_bg, daemon=True).start()

            def _reenviar():
                if state["busy"] or state["resend_left"] > 0:
                    return
                state["busy"] = True
                btn_res.configure(state="disabled", text="Reenviando…")

                def _bg():
                    res = CloudGateway.iniciar_recuperacion_password(
                        state["dni"], state["correo"], self._device_hash, self._device_label
                    )

                    def _apply():
                        state["busy"] = False
                        if not card.winfo_exists():
                            return
                        if res.get("ok") and res.get("challenge_id"):
                            state["challenge_id"] = res["challenge_id"]
                            state["exp_left"] = int(res.get("expires_in_sec") or 600)
                            state["resend_left"] = int(res.get("resend_cooldown_sec") or 60)
                            lbl_msg.configure(text="✔ Nuevo código enviado si la cuenta existe.", text_color=COLOR_OK)
                        else:
                            state["resend_left"] = int(res.get("wait_sec") or 30)
                            lbl_msg.configure(
                                text=f"⚠ {res.get('error') or 'No se pudo reenviar el código.'}",
                                text_color=COLOR_ERR,
                            )

                    self._post_ui(_apply)

                threading.Thread(target=_bg, daemon=True).start()

            btn_ok = boton(
                contenedor, "Restablecer Contraseña  →", _confirmar,
                variante="primario", width=390, height=40
            )
            btn_ok.pack(fill="x", pady=(0, 6))

            btn_res = boton(
                contenedor, f"Reenviar código ({state['resend_left']} s)", _reenviar,
                variante="util", width=390, height=32, font=F_SMALL
            )
            btn_res.pack(fill="x", pady=(0, 6))

            boton(
                contenedor, "← Volver al Login", self.pantalla_login,
                variante="fantasma", width=390, height=30, font=F_SMALL
            ).pack(fill="x")

            ent_p2.bind("<Return>", lambda _e: _confirmar())

            def _tick():
                if not card.winfo_exists() or state["step"] != 2:
                    return
                if state["exp_left"] > 0:
                    state["exp_left"] -= 1
                mm, ss = divmod(state["exp_left"], 60)
                lbl_tmr.configure(
                    text=f"Expira en: {mm:02d}:{ss:02d}  ·  Máx. 5 intentos"
                    if state["exp_left"] > 0
                    else "Código expirado. Solicite un nuevo código."
                )
                if not state["busy"]:
                    if state["resend_left"] > 0:
                        state["resend_left"] -= 1
                        btn_res.configure(state="disabled", text=f"Reenviar código ({state['resend_left']} s)")
                    else:
                        btn_res.configure(state="normal", text="↻ Reenviar código")
                self._otp_timer_after = self.after(1000, _tick)

            _tick()

        _render_step1()

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

        if hasattr(self, "btn_ingresar") and self.btn_ingresar.winfo_exists():
            self.btn_ingresar.configure(state="disabled", text="Verificando credenciales…")
        if hasattr(self, "lbl_login_error") and self.lbl_login_error.winfo_exists():
            self.lbl_login_error.configure(text="")

        def _bg_login():
            auth_res = CloudGateway.iniciar_login_otp(
                dni, correo, password, self._device_hash, self._device_label
            )

            def _apply_login():
                if not self.winfo_exists():
                    return
                if auth_res.get("error_conexion"):
                    if hasattr(self, "btn_ingresar") and self.btn_ingresar.winfo_exists():
                        self.btn_ingresar.configure(
                            state="normal", text="Ingresar a Consola de Operaciones  →"
                        )
                    if hasattr(self, "lbl_login_error") and self.lbl_login_error.winfo_exists():
                        self.lbl_login_error.configure(text=f"⚠ {auth_res['error_conexion']}")
                elif auth_res.get("requires_otp") and auth_res.get("challenge_id"):
                    reset_login_rate_limit()
                    self.pantalla_verificacion_otp(
                        challenge_id=auth_res["challenge_id"],
                        masked_email=auth_res.get("masked_email") or correo,
                        proposito="new_device",
                        expires_in_sec=int(auth_res.get("expires_in_sec") or 600),
                        resend_cooldown_sec=int(auth_res.get("resend_cooldown_sec") or 60),
                        reenvio_cb=lambda: CloudGateway.iniciar_login_otp(
                            dni, correo, password, self._device_hash, self._device_label
                        ),
                    )
                elif auth_res.get("autenticado"):
                    reset_login_rate_limit()
                    if auth_res.get("session_token"):
                        self._session_token = auth_res["session_token"]
                        save_session_token(self._session_token, self._device_hash)
                    self.dni_usuario_activo = auth_res.get("dni") or dni
                    self.usuario_activo_info = {
                        "dni": self.dni_usuario_activo,
                        "correo": auth_res.get("correo") or correo,
                        "nickname": auth_res.get("nickname") or "Operador",
                        "avatar_data": auth_res.get("avatar_data"),
                        "rol": auth_res.get("rol") or "operator",
                    }
                    self._mostrar_splash_carga()
                else:
                    bloqueado, seg_lock = record_failed_login(dni, correo)
                    if hasattr(self, "btn_ingresar") and self.btn_ingresar.winfo_exists():
                        self.btn_ingresar.configure(
                            state="normal", text="Ingresar a Consola de Operaciones  →"
                        )
                    if hasattr(self, "lbl_login_error") and self.lbl_login_error.winfo_exists():
                        if bloqueado:
                            self.lbl_login_error.configure(
                                text=f"⏳ Cuenta protegida contra fuerza bruta. Espere {seg_lock} s."
                            )
                        else:
                            self.lbl_login_error.configure(
                                text=f"✖ {auth_res.get('error') or 'Credenciales incorrectas o cuenta inexistente.'}"
                            )

            self._post_ui(_apply_login)

        threading.Thread(target=_bg_login, daemon=True).start()

    def pantalla_verificacion_otp(
        self,
        challenge_id: str,
        masked_email: str,
        proposito: str,
        expires_in_sec: int = 600,
        resend_cooldown_sec: int = 60,
        reenvio_cb=None,
    ):
        """Pantalla de verificación por código OTP de 6 dígitos (Registro o Nuevo Dispositivo)."""
        if self._otp_timer_after:
            try:
                self.after_cancel(self._otp_timer_after)
            except Exception:
                pass
            self._otp_timer_after = None

        self.limpiar_panel(mostrar_fondo=True)
        self._colocar_boton_fullscreen_flotante()

        state = {
            "challenge_id": challenge_id,
            "exp_left": max(60, int(expires_in_sec)),
            "resend_left": max(0, int(resend_cooldown_sec)),
            "busy": False,
        }

        card = ctk.CTkFrame(
            self, width=460, height=440, corner_radius=0,
            fg_color=P["card"], border_width=1, border_color=P["borde_fuerte"]
        )
        animar_entrada_panel(card)
        card.pack_propagate(False)

        top = ctk.CTkFrame(card, fg_color=P["surface"], corner_radius=12)
        top.pack(fill="x", padx=18, pady=(18, 10))
        titulo = (
            "Verificación de Registro" if proposito == "register" else "Nuevo Dispositivo Detectado"
        )
        ctk.CTkLabel(top, text=f"🔐 {titulo}", font=F_H2, text_color=P["texto"], anchor="w").pack(
            fill="x", padx=14, pady=(12, 2)
        )
        ctk.CTkLabel(
            top,
            text=f"Enviamos un código de 6 dígitos a: {masked_email}",
            font=F_SMALL, text_color=P["cian"], anchor="w", wraplength=400, justify="left"
        ).pack(fill="x", padx=14, pady=(0, 12))

        cuerpo = ctk.CTkFrame(card, fg_color="transparent")
        cuerpo.pack(fill="x", padx=26, pady=6)

        overline(cuerpo, "Código de Seguridad (6 dígitos)").pack(anchor="w", pady=(4, 4))
        entry_otp = entrada(cuerpo, "000000", width=390)
        entry_otp.configure(font=F_H1, justify="center")
        entry_otp.pack(fill="x", pady=(0, 6))
        entry_otp.focus_set()

        lbl_timer = ctk.CTkLabel(cuerpo, text="", font=F_CAPTION, text_color=P["texto_sec"])
        lbl_timer.pack(anchor="w", pady=(0, 4))

        lbl_err = ctk.CTkLabel(card, text="", text_color=COLOR_ERR, font=F_SMALL, wraplength=400)
        lbl_err.pack(pady=4)

        def _verificar():
            if state["busy"]:
                return
            code = entry_otp.get().strip()
            if len(code) != 6 or not code.isdigit():
                lbl_err.configure(text="⚠ Ingrese exactamente 6 dígitos numéricos.")
                return
            state["busy"] = True
            btn_ok.configure(state="disabled", text="Verificando código…")
            lbl_err.configure(text="")
            cid = state["challenge_id"]

            def _bg_verify():
                if proposito == "register":
                    res = CloudGateway.verificar_otp_registro(
                        cid, code, self._device_hash, self._device_label
                    )
                else:
                    res = CloudGateway.verificar_otp_login(
                        cid, code, self._device_hash, self._device_label
                    )

                def _apply_verify():
                    state["busy"] = False
                    if not card.winfo_exists():
                        return
                    if res.get("ok") and res.get("session_token"):
                        if self._otp_timer_after:
                            try:
                                self.after_cancel(self._otp_timer_after)
                            except Exception:
                                pass
                            self._otp_timer_after = None
                        self._session_token = res["session_token"]
                        save_session_token(self._session_token, self._device_hash)
                        user = res.get("user") or {}
                        self.dni_usuario_activo = user.get("dni")
                        self.usuario_activo_info = {
                            "dni": user.get("dni"),
                            "correo": user.get("correo"),
                            "nickname": user.get("nickname") or "Operador",
                            "avatar_data": user.get("avatar_data"),
                            "rol": user.get("rol") or "operator",
                        }
                        self._mostrar_splash_carga()
                        toast(
                            self,
                            "Dispositivo verificado. Sesión segura activa por 15 minutos.",
                            tipo="ok",
                        )
                    else:
                        btn_ok.configure(state="normal", text="Verificar Código y Entrar  →")
                        lbl_err.configure(
                            text=f"✖ {res.get('error') or res.get('error_conexion') or 'Código incorrecto o expirado.'}"
                        )

                self._post_ui(_apply_verify)

            threading.Thread(target=_bg_verify, daemon=True).start()

        def _reenviar():
            if not reenvio_cb or state["resend_left"] > 0 or state["busy"]:
                return
            state["busy"] = True
            btn_resend.configure(state="disabled", text="Reenviando…")

            def _bg_resend():
                res = reenvio_cb()

                def _apply_resend():
                    state["busy"] = False
                    if not card.winfo_exists():
                        return
                    if res.get("challenge_id"):
                        state["challenge_id"] = res["challenge_id"]
                        state["exp_left"] = int(res.get("expires_in_sec") or 600)
                        state["resend_left"] = int(res.get("resend_cooldown_sec") or 60)
                        lbl_err.configure(text="")
                        toast(self, f"Nuevo código enviado a {masked_email}.", tipo="info")
                    else:
                        state["resend_left"] = int(res.get("wait_sec") or 30)
                        lbl_err.configure(
                            text=f"⚠ {res.get('error') or res.get('error_conexion') or 'No se pudo reenviar el código.'}"
                        )

                self._post_ui(_apply_resend)

            threading.Thread(target=_bg_resend, daemon=True).start()

        acciones = ctk.CTkFrame(card, fg_color="transparent")
        acciones.pack(fill="x", padx=26, pady=6)
        btn_ok = boton(
            acciones, "Verificar Código y Entrar  →", _verificar,
            variante="primario", width=390, height=40
        )
        btn_ok.pack(fill="x", pady=(0, 8))
        btn_resend = boton(
            acciones, f"Reenviar código ({state['resend_left']} s)", _reenviar,
            variante="util", width=390, height=34, font=F_SMALL
        )
        btn_resend.pack(fill="x", pady=(0, 6))
        boton(
            acciones, "← Cancelar y volver al Login", self.pantalla_login,
            variante="fantasma", width=390, height=32, font=F_SMALL
        ).pack(fill="x")

        entry_otp.bind("<Return>", lambda _e: _verificar())

        def _tick():
            if not card.winfo_exists():
                return
            if state["exp_left"] > 0:
                state["exp_left"] -= 1
            mm, ss = divmod(state["exp_left"], 60)
            lbl_timer.configure(
                text=f"Expira en: {mm:02d}:{ss:02d}  ·  Máximo 5 intentos"
                if state["exp_left"] > 0
                else "Código expirado. Solicite uno nuevo."
            )
            if not state["busy"]:
                if state["resend_left"] > 0:
                    state["resend_left"] -= 1
                    btn_resend.configure(state="disabled", text=f"Reenviar código ({state['resend_left']} s)")
                else:
                    btn_resend.configure(state="normal", text="↻ Reenviar código al correo")
            self._otp_timer_after = self.after(1000, _tick)

        _tick()

    def _mostrar_splash_carga(self):
        """Reemplaza el login por un indicador de carga mientras el hilo trabaja."""
        self.limpiar_panel(mostrar_fondo=True)

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
        """Ejecutado en hilo secundario: escanea hardware sin autoguardar tickets en la nube."""
        try:
            self.hardware_detectado = LectorHardware.escanear_entorno()
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
        self._post_ui(self.pantalla_dashboard)

    def pantalla_registro(self):
        self.limpiar_panel(mostrar_fondo=True)
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
        self.btn_registrar = boton(acciones, "Registrar Cuenta en la Nube", self.procesar_registro,
              variante="primario", width=390, height=38)
        self.btn_registrar.pack(fill="x", pady=(0, 6))
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

        if hasattr(self, "btn_registrar") and self.btn_registrar.winfo_exists():
            self.btn_registrar.configure(state="disabled", text="Enviando código de verificación…")
        if hasattr(self, "lbl_reg_error") and self.lbl_reg_error.winfo_exists():
            self.lbl_reg_error.configure(text="")

        def _bg_reg():
            res = CloudGateway.iniciar_registro_otp(
                dni, nick, correo, password, self._device_hash, self._device_label
            )

            def _apply_reg():
                if not self.winfo_exists():
                    return
                if res.get("legacy_direct"):
                    if res.get("ok"):
                        self.pantalla_login()
                        toast(self, "Cuenta registrada exitosamente. Ya puede iniciar sesión.", tipo="ok")
                    else:
                        if hasattr(self, "btn_registrar") and self.btn_registrar.winfo_exists():
                            self.btn_registrar.configure(state="normal", text="Registrar Cuenta en la Nube")
                        if hasattr(self, "lbl_reg_error") and self.lbl_reg_error.winfo_exists():
                            self.lbl_reg_error.configure(text="✖ Error de conexión al registrar. Intente luego.")
                    return

                if res.get("ok") and res.get("challenge_id"):
                    self.pantalla_verificacion_otp(
                        challenge_id=res["challenge_id"],
                        masked_email=res.get("masked_email") or correo,
                        proposito="register",
                        expires_in_sec=int(res.get("expires_in_sec") or 600),
                        resend_cooldown_sec=int(res.get("resend_cooldown_sec") or 60),
                        reenvio_cb=lambda: CloudGateway.iniciar_registro_otp(
                            dni, nick, correo, password, self._device_hash, self._device_label
                        ),
                    )
                else:
                    if hasattr(self, "btn_registrar") and self.btn_registrar.winfo_exists():
                        self.btn_registrar.configure(state="normal", text="Registrar Cuenta en la Nube")
                    if hasattr(self, "lbl_reg_error") and self.lbl_reg_error.winfo_exists():
                        self.lbl_reg_error.configure(
                            text=f"✖ {res.get('error') or res.get('error_conexion') or 'No se pudo iniciar la verificación.'}"
                        )

            self._post_ui(_apply_reg)

        threading.Thread(target=_bg_reg, daemon=True).start()



def run_app() -> None:
    app = AppIndiServ()
    app.mainloop()


if __name__ == "__main__":
    run_app()
