"""
main.py — IndiServ Analytica (Fase 1: Dashboard Asíncrono + Pestañas)
=======================================================================
El escaneo de hardware se ejecuta en un hilo (threading.Thread) para que
CustomTkinter nunca se congele durante el proceso de login.

Dashboard organizado en pestañas:
  • General      — Motherboard / BIOS / SO / Red / Uptime
  • CPU / RAM    — Frecuencias, núcleos, módulos de memoria
  • Gráficos     — GPU(s) detectadas, VRAM, driver
  • Discos       — Unidades físicas y particiones lógicas
"""

import os
import random
import threading
import webbrowser
import customtkinter as ctk
from PIL import Image

from core.hardware import LectorHardware
from core.cloud_gateway import CloudGateway
from core.diagnostico import MotorDiagnostico, MatrizSintomas, BuscadorAsistido, MicroStressTest
from core.gemelo_digital import abrir_gemelo_digital
from core.hardware_map import MotherboardMapView

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")


# ---------------------------------------------------------------------------
# Constantes de estilo
# ---------------------------------------------------------------------------
FONT_TITLE  = ("Segoe UI", 16, "bold")
FONT_LABEL  = ("Segoe UI", 13)
FONT_SMALL  = ("Segoe UI", 11)
FONT_MONO   = ("Consolas", 11)
COLOR_OK    = "#29946d"
COLOR_ERR   = "#FF5555"
COLOR_DIM   = "#3A3A3C"
COLOR_CYAN  = "#00E5FF"


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------
class AppIndiServ(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("IndiServ Analytica - Sistema Experto de Diagnóstico de PC")
        self.geometry("960x680")
        self.resizable(False, False)

        # Fondo visual
        self.bg_label = None
        if os.path.exists("assets/fondo.jpg"):
            try:
                self.bg_image = ctk.CTkImage(Image.open("assets/fondo.jpg"), size=(960, 680))
                self.bg_label = ctk.CTkLabel(self, image=self.bg_image, text="")
                self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            except Exception:
                pass

        # Estado de sesión
        self.dni_usuario_activo: str | None = None
        self.hardware_detectado: dict | None = None

        # Estado del árbol de diagnóstico
        self.arbol_fase = 0
        self.arbol_rama = -1
        self.arbol_paso = 0
        self.temp_gira_ventilador = False
        self.dictamen_final = None
        self.ticket_id_actual: str | None = None
        self.ticket_sincronizado: bool = False

        self.pantalla_login()

    # =========================================================================
    # UTILIDADES GENERALES
    # =========================================================================
    def limpiar_panel(self):
        """Elimina todos los widgets excepto el fondo."""
        for widget in self.winfo_children():
            if widget != self.bg_label:
                widget.destroy()

    def _hw(self, clave: str, fallback: str = "N/A") -> str:
        """Acceso seguro al dict de hardware."""
        if not self.hardware_detectado:
            return fallback
        val = self.hardware_detectado.get(clave, fallback)
        return str(val) if val is not None else fallback

    # =========================================================================
    # PANTALLA 1: PORTAL DE SEGURIDAD (LOGIN)
    # =========================================================================
    def pantalla_login(self):
        self.limpiar_panel()

        frame = ctk.CTkFrame(self, width=380, height=390, corner_radius=10)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(frame, text="Portal de Seguridad", font=FONT_TITLE).pack(pady=(20, 6))
        ctk.CTkLabel(frame, text="Autenticación Requerida", font=FONT_SMALL, text_color="gray").pack(pady=(0, 10))

        self.entry_dni    = ctk.CTkEntry(frame, placeholder_text="DNI", width=280)
        self.entry_dni.pack(pady=6)

        self.entry_correo = ctk.CTkEntry(frame, placeholder_text="Correo Electrónico", width=280)
        self.entry_correo.pack(pady=6)

        self.entry_pass   = ctk.CTkEntry(frame, placeholder_text="Contraseña", show="*", width=280)
        self.entry_pass.pack(pady=6)

        self.lbl_login_error = ctk.CTkLabel(frame, text="", text_color=COLOR_ERR, font=FONT_SMALL)
        self.lbl_login_error.pack(pady=4)

        self.btn_ingresar = ctk.CTkButton(
            frame, text="Ingresar al Sistema",
            command=self._iniciar_login_async, width=280, height=36
        )
        self.btn_ingresar.pack(pady=6)

        ctk.CTkButton(
            frame, text="Crear Nueva Cuenta",
            fg_color="transparent", border_width=1,
            command=self.pantalla_registro, width=280, height=32
        ).pack(pady=6)

    def _iniciar_login_async(self):
        """
        Valida credenciales y, si son correctas, lanza el escaneo de hardware
        en un hilo secundario para no bloquear la GUI.
        """
        dni      = self.entry_dni.get().strip()
        correo   = self.entry_correo.get().strip()
        password = self.entry_pass.get().strip()

        if not dni or not correo or not password:
            self.lbl_login_error.configure(text="Complete todos los campos.")
            return

        cuenta = CloudGateway.consultar_usuario(dni)
        if cuenta.get("registrado") and cuenta.get("correo") == correo and cuenta.get("password_hash") == password:
            self.dni_usuario_activo = dni
            self._mostrar_splash_carga()
        else:
            self.lbl_login_error.configure(text="Credenciales incorrectas o cuenta inexistente.")

    def _mostrar_splash_carga(self):
        """Reemplaza el login por un indicador de carga mientras el hilo trabaja."""
        self.limpiar_panel()

        frame = ctk.CTkFrame(self, width=340, height=180, corner_radius=12)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(frame, text="Escaneando Hardware del Equipo…",
                     font=FONT_LABEL).pack(pady=(30, 10))

        self._barra_carga = ctk.CTkProgressBar(frame, width=260, mode="indeterminate")
        self._barra_carga.pack(pady=10)
        self._barra_carga.start()

        self._lbl_estado_carga = ctk.CTkLabel(frame, text="Leyendo CPU, RAM, GPU, Discos…",
                                               font=FONT_SMALL, text_color="gray")
        self._lbl_estado_carga.pack(pady=6)

        hilo = threading.Thread(target=self._hilo_escaneo_hardware, daemon=True)
        hilo.start()

    def _hilo_escaneo_hardware(self):
        """Ejecutado en hilo secundario: escanea hardware y luego notifica a la GUI."""
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
        # Notificar a la GUI desde el hilo de forma segura
        self.after(0, self.pantalla_dashboard)

    # =========================================================================
    # PANTALLA 1.5: REGISTRO DE CUENTA
    # =========================================================================
    def pantalla_registro(self):
        self.limpiar_panel()

        frame = ctk.CTkFrame(self, width=400, height=440, corner_radius=10)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(frame, text="Registro en el Sistema", font=FONT_TITLE).pack(pady=(15, 5))
        ctk.CTkLabel(frame, text="Ingrese sus datos autorizados", font=FONT_SMALL,
                     text_color="gray").pack(pady=(0, 10))

        self.reg_dni    = ctk.CTkEntry(frame, placeholder_text="DNI", width=280)
        self.reg_dni.pack(pady=5)
        self.reg_nick   = ctk.CTkEntry(frame, placeholder_text="Nickname", width=280)
        self.reg_nick.pack(pady=5)
        self.reg_correo = ctk.CTkEntry(frame, placeholder_text="Correo Electrónico", width=280)
        self.reg_correo.pack(pady=5)
        self.reg_pass   = ctk.CTkEntry(frame, placeholder_text="Contraseña", show="*", width=280)
        self.reg_pass.pack(pady=5)

        self.lbl_reg_error = ctk.CTkLabel(frame, text="", text_color=COLOR_ERR, font=FONT_SMALL)
        self.lbl_reg_error.pack(pady=4)

        ctk.CTkButton(frame, text="Registrar en la Nube",
                      command=self.procesar_registro, width=280, height=36).pack(pady=6)
        ctk.CTkButton(frame, text="Volver al Login", fg_color="gray",
                      command=self.pantalla_login, width=280, height=32).pack(pady=6)

    def procesar_registro(self):
        dni      = self.reg_dni.get().strip()
        nick     = self.reg_nick.get().strip()
        correo   = self.reg_correo.get().strip()
        password = self.reg_pass.get().strip()

        if not dni or not nick or not correo or not password:
            self.lbl_reg_error.configure(text="Llene todos los campos requeridos.")
            return

        padron = CloudGateway.consultar_padron(dni)
        if not padron.get("existe"):
            self.lbl_reg_error.configure(text="El DNI no figura en el padrón oficial.")
            return

        cuenta = CloudGateway.consultar_usuario(dni)
        if cuenta.get("registrado"):
            self.lbl_reg_error.configure(text="Este DNI ya tiene una cuenta registrada.")
            return

        exito = CloudGateway.registrar_usuario(dni, correo, password, nick)
        if exito:
            self.pantalla_login()
        else:
            self.lbl_reg_error.configure(text="Error de conexión al registrar. Intente luego.")

    # =========================================================================
    # PANTALLA 2: DASHBOARD TÉCNICO CON PESTAÑAS MODULARES
    # =========================================================================
    def pantalla_dashboard(self):
        self.limpiar_panel()
        hw = self.hardware_detectado or {}

        # Marco principal
        frame = ctk.CTkFrame(self, width=900, height=620, corner_radius=10)
        frame.place(relx=0.5, rely=0.5, anchor="center")
        frame.grid_propagate(False)

        # Encabezado
        ctk.CTkLabel(
            frame,
            text=f"Consola Central de Operaciones  —  Operador: {self.dni_usuario_activo}",
            font=FONT_TITLE, text_color=COLOR_OK
        ).pack(pady=(14, 4))

        # ---- TabView --------------------------------------------------------
        tabs = ctk.CTkTabview(frame, width=860, height=450)
        tabs.pack(pady=6, padx=10)

        for nombre in ("General", "CPU / RAM", "Gráficos", "Discos", "Red"):
            tabs.add(nombre)

        # -- TAB: GENERAL (Motherboard, BIOS, SO, Uptime) ---------------------
        self._tab_general(tabs.tab("General"), hw)

        # -- TAB: CPU / RAM ---------------------------------------------------
        self._tab_cpu_ram(tabs.tab("CPU / RAM"), hw)

        # -- TAB: GRÁFICOS (GPU) ----------------------------------------------
        self._tab_graficos(tabs.tab("Gráficos"), hw)

        # -- TAB: DISCOS ------------------------------------------------------
        self._tab_discos(tabs.tab("Discos"), hw)

        # -- TAB: RED ---------------------------------------------------------
        self._tab_red(tabs.tab("Red"), hw)

        # ---- Botones del dashboard — Fila 1 --------------------------------
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(pady=(6, 2))

        ctk.CTkButton(
            btn_frame, text="1. Árbol de Diagnóstico",
            command=self.iniciar_diagnostico, width=240, height=38
        ).grid(row=0, column=0, padx=6)

        ctk.CTkButton(
            btn_frame, text="2. Diagnóstico Multisíntoma",
            command=self.pantalla_multisintoma, width=240, height=38,
            fg_color="#1F6B4A"
        ).grid(row=0, column=1, padx=6)

        ctk.CTkButton(
            btn_frame, text="3. Buscador Asistido",
            command=self.pantalla_buscador, width=220, height=38,
            fg_color="#1F6B4A"
        ).grid(row=0, column=2, padx=6)

        # ---- Botones del dashboard — Fila 2 --------------------------------
        btn_frame2 = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame2.pack(pady=(2, 4))

        ctk.CTkButton(
            btn_frame2, text="4. Micro-Stress Test CPU",
            command=self.pantalla_stress_test, width=220, height=34,
            fg_color="#5A3A8A"
        ).grid(row=0, column=0, padx=6)

        ctk.CTkButton(
            btn_frame2, text="5. Bitácora Local",
            command=self.mostrar_historial_local, width=180, height=34,
            fg_color=COLOR_DIM
        ).grid(row=0, column=1, padx=6)

        ctk.CTkButton(
            btn_frame2, text="6. Sugerencias",
            command=self.modal_sugerencias, width=160, height=34,
            fg_color=COLOR_DIM
        ).grid(row=0, column=2, padx=6)

        ctk.CTkButton(
            btn_frame2, text="Cerrar Sesión", fg_color="#B22222",
            command=self.pantalla_login, width=140, height=34
        ).grid(row=0, column=3, padx=6)

    # ---- Helpers de pestañas ------------------------------------------------

    def _textbox(self, parent, height=360) -> ctk.CTkTextbox:
        """Crea y retorna un CTkTextbox de sólo lectura."""
        tb = ctk.CTkTextbox(parent, width=820, height=height, font=FONT_MONO)
        tb.pack(padx=8, pady=6, fill="both", expand=True)
        return tb

    def _insertar_y_bloquear(self, tb: ctk.CTkTextbox, texto: str):
        tb.configure(state="normal")
        tb.delete("0.0", "end")
        tb.insert("0.0", texto)
        tb.configure(state="disabled")

    def _tab_general(self, tab, hw: dict):
        tb = self._textbox(tab)
        lineas = [
            "╔══════════════════════════════════════════════════════════════╗",
            "║          INFORMACIÓN GENERAL DEL SISTEMA                    ║",
            "╚══════════════════════════════════════════════════════════════╝",
            "",
            f"  PLACA BASE     : {hw.get('mb_fabricante','?')} {hw.get('mb_modelo','?')}",
            f"  BIOS           : {hw.get('bios_fabricante','?')} v{hw.get('bios_version','?')}  [{hw.get('bios_fecha','?')}]",
            "",
            f"  SISTEMA OP.    : {hw.get('so','?')}",
            f"  BUILD WINDOWS  : {hw.get('so_build','?')}",
            f"  TIEMPO ACTIVO  : {hw.get('uptime','?')}",
        ]
        self._insertar_y_bloquear(tb, "\n".join(lineas))

    def _tab_cpu_ram(self, tab, hw: dict):
        tb = self._textbox(tab)

        # CPU
        uso_por_nucleo = hw.get("uso_por_nucleo", [])
        barras_nucleo = ""
        for i, pct in enumerate(uso_por_nucleo):
            bloques = int(pct / 10)
            barra = "█" * bloques + "░" * (10 - bloques)
            barras_nucleo += f"    Core {i:<2} [{barra}] {pct:5.1f}%\n"

        # RAM módulos
        modulos = hw.get("ram_modulos", [])
        txt_modulos = ""
        for m in modulos:
            txt_modulos += (
                f"    Ranura {m['ranura']:12s}  {m['capacidad_gb']} GB  "
                f"{m['tipo']}  @{m['velocidad_mhz']} MHz\n"
            )

        lineas = [
            "┌─── PROCESADOR ──────────────────────────────────────────────┐",
            f"  Modelo   : {hw.get('nombre_cpu','?')}",
            f"  Núcleos  : {hw.get('nucleos_fisicos','?')} físicos  /  {hw.get('nucleos','?')} hilos lógicos",
            f"  Freq.    : Base {hw.get('frecuencia_base_ghz','?')} GHz  |  Actual {hw.get('frecuencia_actual_ghz','?')} GHz",
            f"  Uso Total: {hw.get('uso_cpu_total','?')}%",
            "",
            "  Uso por núcleo:",
            barras_nucleo.rstrip(),
            "",
            "└─────────────────────────────────────────────────────────────┘",
            "",
            "┌─── MEMORIA RAM ─────────────────────────────────────────────┐",
            f"  Total    : {hw.get('ram_total_mb','?')}    Disponible: {hw.get('ram_disponible_mb','?')}",
            f"  Uso      : {hw.get('ram_uso_pct','?')}%",
            f"  Tipo     : {hw.get('ram_tipo','?')}   Velocidad: {hw.get('ram_velocidad_mhz','?')} MHz",
            f"  Ranuras  : {hw.get('ram_ranuras_ocupadas','?')} ocupadas",
            "",
            "  Módulos detectados:",
            txt_modulos.rstrip(),
            "└─────────────────────────────────────────────────────────────┘",
        ]
        self._insertar_y_bloquear(tb, "\n".join(lineas))

    def _tab_graficos(self, tab, hw: dict):
        tb = self._textbox(tab)
        gpus = hw.get("gpus", [])
        lineas = ["┌─── ADAPTADORES GRÁFICOS ───────────────────────────────────┐", ""]
        for i, g in enumerate(gpus, 1):
            lineas += [
                f"  GPU #{i}:",
                f"    Nombre   : {g.get('nombre','?')}",
                f"    Procesador: {g.get('procesador','?')}",
                f"    VRAM     : {g.get('vram_mb','?')} MB",
                f"    Driver   : {g.get('driver_version','?')}",
                "",
            ]
        if not gpus:
            lineas.append("  No se detectaron adaptadores gráficos.")
        lineas.append("└─────────────────────────────────────────────────────────────┘")
        self._insertar_y_bloquear(tb, "\n".join(lineas))

    def _tab_discos(self, tab, hw: dict):
        tb = self._textbox(tab)
        fisicos = hw.get("discos_fisicos", [])
        partics = hw.get("particiones", [])

        lineas = ["┌─── DISCOS FÍSICOS ──────────────────────────────────────────┐", ""]
        for d in fisicos:
            lineas += [
                f"  [{d.get('tipo','?')}]  {d.get('modelo','?')}",
                f"    Interfaz  : {d.get('interfaz','?')}   Capacidad: {d.get('capacidad_gb','?')} GB",
                "",
            ]
        if not fisicos:
            lineas.append("  No se detectaron discos físicos vía WMI.")

        lineas += ["", "┌─── PARTICIONES LÓGICAS ─────────────────────────────────────┐", ""]
        for p in partics:
            bloques = int(p.get("uso_pct", 0) / 10)
            barra   = "█" * bloques + "░" * (10 - bloques)
            satur   = " ⚠ SATURADO" if p.get("uso_pct", 0) >= 90 else ""
            lineas.append(
                f"  {p.get('letra','?'):10s} [{barra}] {p.get('uso_pct',0):5.1f}%"
                f"   {p.get('usado_gb',0)}/{p.get('total_gb',0)} GB   libre: {p.get('libre_gb',0)} GB{satur}"
            )
        if not partics:
            lineas.append("  No se detectaron particiones.")
        lineas.append("└─────────────────────────────────────────────────────────────┘")
        self._insertar_y_bloquear(tb, "\n".join(lineas))

    def _tab_red(self, tab, hw: dict):
        tb = self._textbox(tab, height=300)
        lineas = [
            "┌─── CONECTIVIDAD Y RED ──────────────────────────────────────┐",
            "",
            f"  Adaptador activo : {hw.get('adaptador_activo','?')}",
            f"  Dirección IP     : {hw.get('ip_local','?')}",
            f"  Latencia (DNS)   : {hw.get('latencia_ms','?')}",
            "",
            f"  Sistema Operativo: {hw.get('so','?')}",
            f"  Build Windows    : {hw.get('so_build','?')}",
            f"  Tiempo activo    : {hw.get('uptime','?')}",
            "└─────────────────────────────────────────────────────────────┘",
        ]
        self._insertar_y_bloquear(tb, "\n".join(lineas))


    # =========================================================================
    # PANTALLA 4: DIAGNÓSTICO MULTISÍNTOMA (Fase 2)
    # =========================================================================
    def pantalla_multisintoma(self):
        """Selector de síntomas múltiples con cálculo de probabilidad por causa raíz."""
        self.limpiar_panel()

        frame = ctk.CTkFrame(self, width=900, height=620, corner_radius=10)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(frame, text="Diagnóstico Multisíntoma — Correlación Ponderada",
                     font=FONT_TITLE, text_color=COLOR_OK).pack(pady=(14, 4))
        ctk.CTkLabel(frame, text="Seleccione todos los síntomas que observa en el equipo:",
                     font=FONT_SMALL, text_color="gray").pack(pady=(0, 6))

        # Checkboxes en CTkScrollableFrame
        scroll = ctk.CTkScrollableFrame(frame, width=840, height=220, corner_radius=6)
        scroll.pack(padx=10, pady=4)

        self._check_vars: list[ctk.BooleanVar] = []
        sintomas = MatrizSintomas.SINTOMAS
        for i, texto in enumerate(sintomas):
            var = ctk.BooleanVar(value=False)
            self._check_vars.append(var)
            ctk.CTkCheckBox(scroll, text=texto, variable=var, font=FONT_SMALL,
                            width=800).pack(anchor="w", pady=2, padx=6)

        # Área de resultados
        self._res_multisintoma = ctk.CTkTextbox(frame, width=840, height=230, font=FONT_MONO)
        self._res_multisintoma.pack(padx=10, pady=4)
        self._res_multisintoma.insert("0.0",
            "Seleccione síntomas arriba y presione 'Calcular' para ver el ranking de causas probables.")
        self._res_multisintoma.configure(state="disabled")

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(pady=(4, 0))

        ctk.CTkButton(btn_row, text="Calcular Probabilidades",
                      command=self._calcular_multisintoma,
                      width=240, height=36).pack(side="left", padx=10)
        ctk.CTkButton(btn_row, text="Limpiar Selección",
                      command=self._limpiar_checks,
                      fg_color=COLOR_DIM, width=180, height=36).pack(side="left", padx=10)
        ctk.CTkButton(btn_row, text="← Volver al Dashboard",
                      command=self.pantalla_dashboard,
                      fg_color="gray", width=200, height=36).pack(side="left", padx=10)

    def _limpiar_checks(self):
        for var in self._check_vars:
            var.set(False)
        self._res_multisintoma.configure(state="normal")
        self._res_multisintoma.delete("0.0", "end")
        self._res_multisintoma.insert("0.0", "Selección limpiada. Elija síntomas y calcule nuevamente.")
        self._res_multisintoma.configure(state="disabled")

    def _calcular_multisintoma(self):
        indices_sel = [i for i, v in enumerate(self._check_vars) if v.get()]
        if not indices_sel:
            self._res_multisintoma.configure(state="normal")
            self._res_multisintoma.delete("0.0", "end")
            self._res_multisintoma.insert("0.0", "⚠  Seleccione al menos un síntoma para calcular.")
            self._res_multisintoma.configure(state="disabled")
            return

        resultados = MatrizSintomas.calcular_probabilidades(indices_sel)

        lineas = [
            f"  Síntomas seleccionados: {len(indices_sel)}",
            "  ─────────────────────────────────────────────────────────────",
            "  RANKING DE CAUSAS PROBABLES:",
            "",
        ]
        medallas = ["🥇", "🥈", "🥉"] + ["  "] * 10
        for idx, r in enumerate(resultados[:6]):
            barra = self._mini_barra(r["probabilidad"])
            lineas.append(
                f"  {medallas[idx]}  {r['causa']:<35s}  {barra}  {r['probabilidad']:5.1f}%"
            )

        # Detalle de la causa más probable
        if resultados:
            top = resultados[0]
            lineas += [
                "",
                "  ─────────────────────────────────────────────────────────────",
                f"  CAUSA MÁS PROBABLE: {top['causa']}",
                f"  {top['descripcion']}",
                "",
                "  GUÍA DE ACCIÓN:",
                *[f"  {l}" for l in top["solucion"].split("\n")],
            ]

        self._res_multisintoma.configure(state="normal")
        self._res_multisintoma.delete("0.0", "end")
        self._res_multisintoma.insert("0.0", "\n".join(lineas))
        self._res_multisintoma.configure(state="disabled")

    @staticmethod
    def _mini_barra(pct: float, ancho: int = 15) -> str:
        relleno = int((pct / 100) * ancho)
        return "[" + "█" * relleno + "░" * (ancho - relleno) + "]"

    # =========================================================================
    # PANTALLA 5: BUSCADOR ASISTIDO / FUZZY (Fase 2)
    # =========================================================================
    def pantalla_buscador(self):
        """Búsqueda en lenguaje libre con sugerencias fuzzy de rama de diagnóstico."""
        self.limpiar_panel()

        frame = ctk.CTkFrame(self, width=820, height=560, corner_radius=10)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(frame, text="Buscador Asistido — Descripción Libre del Problema",
                     font=FONT_TITLE, text_color=COLOR_OK).pack(pady=(14, 4))
        ctk.CTkLabel(frame,
                     text="Describa el problema con sus palabras. El sistema identificará la causa más probable.",
                     font=FONT_SMALL, text_color="gray", wraplength=760).pack(pady=(0, 8))

        # Entrada de texto
        self._entry_busqueda = ctk.CTkEntry(
            frame, placeholder_text="Ej: la pc se reinicia sola y hace pitidos al encender…",
            width=740, height=38, font=FONT_LABEL
        )
        self._entry_busqueda.pack(pady=4)
        # Buscar también con Enter
        self._entry_busqueda.bind("<Return>", lambda e: self._ejecutar_busqueda())

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(pady=6)
        ctk.CTkButton(btn_row, text="Buscar Causa Probable",
                      command=self._ejecutar_busqueda, width=240, height=36).pack(side="left", padx=10)
        ctk.CTkButton(btn_row, text="← Volver",
                      command=self.pantalla_dashboard, fg_color="gray",
                      width=160, height=36).pack(side="left", padx=10)

        # Resultados
        self._res_busqueda = ctk.CTkTextbox(frame, width=760, height=340, font=FONT_MONO)
        self._res_busqueda.pack(padx=10, pady=6)
        self._res_busqueda.insert("0.0",
            "Los resultados aparecerán aquí.\n\n"
            "Consejo: use términos técnicos o síntomas observables.\n"
            "Ejemplos:\n"
            "  • 'pantalla azul con error de memoria'\n"
            "  • 'pc muy lenta disco al 100'\n"
            "  • 'ruido raro ventilador sobrecalentamiento'\n"
            "  • 'no hay señal de video monitor negro'"
        )
        self._res_busqueda.configure(state="disabled")

    def _ejecutar_busqueda(self):
        texto = self._entry_busqueda.get().strip()
        if len(texto) < 3:
            self._res_busqueda.configure(state="normal")
            self._res_busqueda.delete("0.0", "end")
            self._res_busqueda.insert("0.0", "⚠  Ingrese al menos 3 caracteres para buscar.")
            self._res_busqueda.configure(state="disabled")
            return

        resultados = BuscadorAsistido.buscar(texto, top_n=5)

        lineas = [
            f"  Búsqueda: \"{texto}\"",
            f"  Resultados: {len(resultados)} coincidencias",
            "  ──────────────────────────────────────────────────────────────",
            "",
        ]

        if not resultados:
            lineas.append("  Sin coincidencias. Intente con otras palabras clave.")
        else:
            for i, r in enumerate(resultados, 1):
                barra = self._mini_barra(r["confianza_pct"])
                rama_txt = (
                    f"  → Lanzar árbol de diagnóstico (Síntoma #{r['rama_id']+1})"
                    if r["rama_id"] is not None else ""
                )
                lineas += [
                    f"  #{i}  {r['causa']}",
                    f"       Confianza: {barra} {r['confianza_pct']}%",
                    f"{rama_txt}",
                    "",
                ]

            # Acción directa para el top resultado con rama conocida
            top = resultados[0]
            if top["rama_id"] is not None:
                lineas += [
                    "  ──────────────────────────────────────────────────────────────",
                    f"  ACCIÓN SUGERIDA: Abrir el árbol de diagnóstico en la rama",
                    f"  '{top['causa']}' (Síntoma #{top['rama_id']+1})",
                    "",
                    "  Presione 'Árbol de Diagnóstico' en el Dashboard y seleccione",
                    f"  la opción {top['rama_id']+1} para seguir el árbol guiado.",
                ]

        self._res_busqueda.configure(state="normal")
        self._res_busqueda.delete("0.0", "end")
        self._res_busqueda.insert("0.0", "\n".join(lineas))
        self._res_busqueda.configure(state="disabled")

    # =========================================================================
    # PANTALLA 6: MICRO-STRESS TEST CPU (Fase 2)
    # =========================================================================
    def pantalla_stress_test(self):
        """Benchmark CPU multihilo con detección de thermal throttling en tiempo real."""
        self.limpiar_panel()

        frame = ctk.CTkFrame(self, width=820, height=560, corner_radius=10)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(frame, text="Micro-Stress Test — Benchmark CPU (10 segundos)",
                     font=FONT_TITLE, text_color="#BB86FC").pack(pady=(14, 4))
        ctk.CTkLabel(frame,
                     text="Carga matemática multihilo controlada. Detecta caídas de frecuencia por throttling térmico.",
                     font=FONT_SMALL, text_color="gray", wraplength=760).pack(pady=(0, 6))

        # Log en tiempo real
        self._stress_log = ctk.CTkTextbox(frame, width=760, height=320, font=FONT_MONO)
        self._stress_log.pack(padx=10, pady=4)
        self._stress_log.insert("0.0",
            "Presione 'Iniciar Test' para comenzar el benchmark.\n\n"
            f"  Núcleos detectados : {psutil.cpu_count(logical=True)}\n"
            f"  Duración           : 10 segundos\n"
            f"  Umbral throttling  : ≥ {MicroStressTest.THROTTLE_UMBRAL_PCT}% de caída en frecuencia\n\n"
            "ADVERTENCIA: El sistema tardará ~10 segundos. La GUI permanecerá responsiva."
        )
        self._stress_log.configure(state="disabled")

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(pady=8)

        self._btn_stress = ctk.CTkButton(
            btn_row, text="▶  Iniciar Test",
            command=self._iniciar_stress,
            width=200, height=38, fg_color="#5A3A8A"
        )
        self._btn_stress.pack(side="left", padx=10)

        ctk.CTkButton(btn_row, text="← Volver al Dashboard",
                      command=self.pantalla_dashboard, fg_color="gray",
                      width=200, height=38).pack(side="left", padx=10)

    def _iniciar_stress(self):
        """Lanza el stress test. Desactiva el botón durante la ejecución."""
        self._btn_stress.configure(state="disabled", text="⏳ Ejecutando…")
        self._stress_log.configure(state="normal")
        self._stress_log.delete("0.0", "end")
        self._stress_log.configure(state="disabled")

        test = MicroStressTest(
            callback_progreso=self._stress_append,
            callback_resultado=self._stress_finalizado,
        )
        test.iniciar()

    def _stress_append(self, mensaje: str):
        """Llamado desde el hilo de stress — usa self.after() para ser thread-safe."""
        self.after(0, lambda m=mensaje: self._stress_append_main(m))

    def _stress_append_main(self, mensaje: str):
        self._stress_log.configure(state="normal")
        self._stress_log.insert("end", mensaje)
        self._stress_log.see("end")
        self._stress_log.configure(state="disabled")

    def _stress_finalizado(self, resultado: dict):
        """Llamado desde el hilo al terminar — usa self.after() para ser thread-safe."""
        self.after(0, lambda r=resultado: self._mostrar_resultado_stress(r))

    def _mostrar_resultado_stress(self, resultado: dict):
        if "error" in resultado:
            self._stress_append_main(f"\n[ERROR] {resultado['error']}\n")
        else:
            self._stress_append_main("\n" + "─" * 60 + "\n")
            self._stress_append_main("ANÁLISIS FINAL:\n\n")
            self._stress_append_main(resultado["diagnostico"] + "\n\n")
            self._stress_append_main(
                f"Muestras tomadas : {resultado['n_muestras']}\n"
                f"Freq. máx.       : {resultado['freq_max_ghz']} GHz\n"
                f"Freq. mín.       : {resultado['freq_min_ghz']} GHz\n"
                f"Freq. promedio   : {resultado['freq_avg_ghz']} GHz\n"
                f"Uso CPU máx.     : {resultado['uso_max_pct']}%\n"
            )

        # Rehabilitar botón
        if hasattr(self, "_btn_stress"):
            self._btn_stress.configure(state="normal", text="▶  Reiniciar Test")

    # =========================================================================
    # PANTALLA 3: ASISTENTE INFERENCIAL (sin cambios funcionales)
    # =========================================================================
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

        frame = ctk.CTkFrame(self, width=800, height=540, corner_radius=10)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(frame, text="Asistente Inferencial Avanzado — Diagnóstico",
                     font=FONT_TITLE, text_color=COLOR_OK).pack(pady=(15, 10))

        # FASE 0: Selección del síntoma inicial
        if self.arbol_fase == 0:
            ctk.CTkLabel(frame, text="Identifique el primer síntoma observable en el equipo:",
                         font=FONT_LABEL).pack(pady=(0, 10))

            sintomas = [
                ("1. La PC no da señales de encendido (sin luces / ventiladores)", 0),
                ("2. La PC enciende pero la pantalla está negra y emite pitidos", 1),
                ("3. Advertencia de SOBRECALENTAMIENTO del CPU al iniciar", 2),
                ("4. La PC se reinicia continuamente (Boot Loop)", 3),
                ("5. Falla térmica o desconexión de unidad SSD M.2 NVMe", 4),
                ("6. El sistema enciende pero sufre lentitud o cuellos de botella", 5),
                ("7. Inestabilidad general o pantallas azules (RAM / XMP)", 6),
            ]

            for texto, r_id in sintomas:
                ctk.CTkButton(
                    frame, text=texto, anchor="w", width=700, height=34,
                    command=lambda r=r_id: self.seleccionar_sintoma(r)
                ).pack(pady=3)

        # FASE 1: Preguntas del árbol
        elif self.arbol_fase == 1:
            self.renderizar_paso_rama(frame)

        # FASE 2: Dictamen final
        elif self.arbol_fase == 2:
            ctk.CTkLabel(frame, text="DIAGNÓSTICO COMPLETADO EXITOSAMENTE",
                         font=("Segoe UI", 15, "bold"), text_color=COLOR_CYAN).pack(pady=(5, 5))

            df = self.dictamen_final
            resultado_txt = (
                f"Categoría: {df['categoria']}\n"
                f"Subcategoría: {df['subcategoria']}\n"
                f"Descripción: {df['descripcion']}\n\n"
                f"GUÍA DE SOLUCIÓN PASO A PASO:\n"
                f"{df['solucion']}\n\n"
                f"Código Interno de Soporte: #{df['codigo']}"
            )

            res_box = ctk.CTkTextbox(frame, width=720, height=270, font=FONT_MONO)
            res_box.pack(pady=10)
            res_box.insert("0.0", resultado_txt)
            res_box.configure(state="disabled")

            btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
            btn_frame.pack(pady=6)

            ctk.CTkButton(
                btn_frame, text="🌐 Ver Gemelo Digital 3D",
                command=self.abrir_visor_3d,
                width=220, height=38,
                fg_color="#1F6AA5", hover_color="#144F7A",
                border_width=1, border_color=COLOR_CYAN
            ).pack(side="left", padx=6)

            ctk.CTkButton(
                btn_frame, text="🗺️ Ver Mapa de Hardware",
                command=lambda: self.pantalla_hardware_map(df["categoria"]),
                width=210, height=38, fg_color="#E07A5F", hover_color="#C06A4F"
            ).pack(side="left", padx=6)

            ctk.CTkButton(
                btn_frame, text="Guardar Reporte y Finalizar",
                command=self.guardar_reporte_final, width=220, height=38
            ).pack(side="left", padx=6)


        # Botón de escape
        if self.arbol_fase != 2:
            ctk.CTkButton(
                frame, text="Abortar Diagnóstico", fg_color="gray",
                command=self.pantalla_dashboard, width=180, height=30
            ).pack(pady=(15, 0))

    def seleccionar_sintoma(self, rama_id):
        self.arbol_rama = rama_id
        self.arbol_fase = 1
        self.arbol_paso = 0
        self.pantalla_diagnostico()

    def renderizar_paso_rama(self, frame):
        """Renderiza preguntas binarias o de opción múltiple según la rama activa."""
        r = self.arbol_rama
        p = self.arbol_paso

        if r == 0:
            if p == 0:
                self.crear_pregunta_binaria(
                    frame, "¿El cable de energía está firmemente conectado al tomacorriente?",
                    al_si=lambda: self.avanzar_paso(1),
                    al_no=lambda: self.finalizar_diagnostico({
                        "categoria": "Fuente de Poder", "subcategoria": "Cable desconectado",
                        "descripcion": "Falla de alimentación básica.",
                        "solucion": "1. Desconecte el cable de poder.\n2. Reconecte firmemente en ambos extremos.",
                        "codigo": 101
                    }))
            elif p == 1:
                self.crear_pregunta_binaria(
                    frame, "¿El interruptor trasero de la fuente está en posición ON / 'I'?",
                    al_si=lambda: self.avanzar_paso(2),
                    al_no=lambda: self.finalizar_diagnostico({
                        "categoria": "Fuente de Poder", "subcategoria": "Interruptor apagado",
                        "descripcion": "Interruptor principal en OFF.",
                        "solucion": "1. Posicione el switch trasero en 'I'.\n2. Pruebe encender el equipo.",
                        "codigo": 102
                    }))
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
            ctk.CTkLabel(frame, text="Seleccione el patrón de pitidos que emite la placa base:",
                         font=FONT_LABEL).pack(pady=10)
            opciones = [
                ("1. Pitidos cortos repetitivos",
                 {"categoria": "Memoria RAM", "subcategoria": "No detectada",
                  "descripcion": "Fallo de inicialización de RAM.",
                  "solucion": "1. Retire la RAM y limpie contactos.\n2. Reinserte en el slot principal.", "codigo": 201}),
                ("2. 1 pitido largo + 2 o 3 cortos",
                 {"categoria": "Tarjeta Gráfica", "subcategoria": "No inicializada",
                  "descripcion": "Falla en tarjeta gráfica o PCIe.",
                  "solucion": "1. Limpie el slot PCIe.\n2. Verifique cables PCIe de alimentación.", "codigo": 202}),
                ("3. Tono continuo",
                 {"categoria": "Placa Base", "subcategoria": "Cortocircuito",
                  "descripcion": "Falla crítica general.",
                  "solucion": "1. Inspeccione la placa buscando condensadores hinchados.", "codigo": 203}),
                ("4. Sin pitidos, pantalla negra",
                 {"categoria": "Video", "subcategoria": "Sin señal",
                  "descripcion": "Problema de cable o monitor.",
                  "solucion": "1. Verifique cables HDMI/DisplayPort.\n2. Conecte al puerto de la placa base.", "codigo": 204}),
            ]
            for texto, dictamen in opciones:
                ctk.CTkButton(frame, text=texto, width=660, height=36, anchor="w",
                              command=lambda d=dictamen: self.finalizar_diagnostico(d)).pack(pady=4)

        elif r == 2:
            if p == 0:
                self.crear_pregunta_binaria(
                    frame, "¿El ventilador del procesador gira al intentar arrancar?",
                    al_si=lambda: self.avanzar_paso(1),
                    al_no=lambda: self.finalizar_diagnostico({
                        "categoria": "Enfriamiento", "subcategoria": "Ventilador inactivo",
                        "descripcion": "Falla térmica por ventilador inoperativo.",
                        "solucion": "1. Verifique el conector CPU_FAN en la placa base.\n2. Reemplace el cooler.",
                        "codigo": 301
                    }))
            elif p == 1:
                self.crear_pregunta_binaria(
                    frame, "¿Se ha cambiado la pasta térmica en los últimos 2 años?",
                    al_si=lambda: self.finalizar_diagnostico({
                        "categoria": "Placa Base", "subcategoria": "Falla de sensor",
                        "descripcion": "Sensor reporta falso calor en BIOS.",
                        "solucion": "1. Actualice la BIOS.\n2. Verifique la telemetría térmica.", "codigo": 303
                    }),
                    al_no=lambda: self.finalizar_diagnostico({
                        "categoria": "Enfriamiento", "subcategoria": "Mantenimiento térmico",
                        "descripcion": "Pasta térmica degradada o seca.",
                        "solucion": "1. Retire el disipador.\n2. Limpie con alcohol isopropílico y aplique pasta nueva.",
                        "codigo": 302
                    }))

        elif r == 3:
            if p == 0:
                self.crear_pregunta_binaria(
                    frame, "¿El equipo se reinicia ANTES de mostrar el logo de la marca (BIOS)?",
                    al_si=lambda: self.finalizar_diagnostico({
                        "categoria": "Hardware", "subcategoria": "Falla Pre-POST",
                        "descripcion": "Inestabilidad eléctrica o de RAM grave.",
                        "solucion": "1. Realice un Clear CMOS.\n2. Pruebe con un solo módulo de RAM.", "codigo": 401
                    }),
                    al_no=lambda: self.avanzar_paso(1))
            elif p == 1:
                self.crear_pregunta_binaria(
                    frame, "¿Llega a mostrar el logo de Windows antes de reiniciarse?",
                    al_si=lambda: self.finalizar_diagnostico({
                        "categoria": "Software", "subcategoria": "Conflicto de SO",
                        "descripcion": "Falla de driver o actualización reciente.",
                        "solucion": "1. Inicie en Modo Seguro.\n2. Desinstale actualizaciones recientes.", "codigo": 403
                    }),
                    al_no=lambda: self.finalizar_diagnostico({
                        "categoria": "Software", "subcategoria": "Bootloader corrupto",
                        "descripcion": "Cargador de arranque dañado.",
                        "solucion": "1. Use USB de instalación.\n2. Ejecute bootrec /fixboot y /rebuildbcd.", "codigo": 402
                    }))

        elif r == 4:
            self.crear_pregunta_binaria(
                frame, "¿El SSD NVMe desaparece del sistema tras un rato de uso intensivo?",
                al_si=lambda: self.finalizar_diagnostico({
                    "categoria": "Almacenamiento", "subcategoria": "Thermal Throttling",
                    "descripcion": "El SSD corta conexión por sobrecalentamiento.",
                    "solucion": "1. Instale un disipador pasivo para M.2.\n2. Mejore el flujo de aire del chasis.",
                    "codigo": 501
                }),
                al_no=lambda: self.finalizar_diagnostico({
                    "categoria": "Almacenamiento", "subcategoria": "Chequeo Preventivo",
                    "descripcion": "Sin corte térmico directo detectado.",
                    "solucion": "1. Use CrystalDiskInfo para evaluar la salud S.M.A.R.T.", "codigo": 502
                }))

        elif r == 5:
            if p == 0:
                self.crear_pregunta_binaria(
                    frame, "¿El uso de CPU en reposo supera el 40% en el Administrador de Tareas?",
                    al_si=lambda: self.finalizar_diagnostico({
                        "categoria": "Rendimiento", "subcategoria": "Proceso parásito",
                        "descripcion": "Consumo anómalo de recursos en reposo.",
                        "solucion": "1. Identifique el proceso y realice un análisis antimalware.", "codigo": 601
                    }),
                    al_no=lambda: self.avanzar_paso(1))
            elif p == 1:
                self.crear_pregunta_binaria(
                    frame, "¿El disco de almacenamiento se mantiene al 100% de uso constante?",
                    al_si=lambda: self.finalizar_diagnostico({
                        "categoria": "Rendimiento", "subcategoria": "Saturación I/O",
                        "descripcion": "Cuello de botella de disco.",
                        "solucion": "1. Desactive el servicio SysMain.\n2. Considere migrar de disco mecánico a SSD.",
                        "codigo": 602
                    }),
                    al_no=lambda: self.finalizar_diagnostico({
                        "categoria": "Rendimiento", "subcategoria": "Saturación de Inicio",
                        "descripcion": "Exceso de aplicaciones en arranque.",
                        "solucion": "1. Abra el Administrador de Tareas y deshabilite apps de inicio innecesarias.",
                        "codigo": 603
                    }))

        elif r == 6:
            self.crear_pregunta_binaria(
                frame, "¿Ocurren pantallazos azules (BSOD) durante juegos o tareas pesadas?",
                al_si=lambda: self.finalizar_diagnostico({
                    "categoria": "RAM", "subcategoria": "Inestabilidad XMP/EXPO",
                    "descripcion": "Perfil de overclock inestable o memoria dañada.",
                    "solucion": "1. Ejecute MemTest86.\n2. Desactive o relaje el perfil XMP/EXPO en la BIOS.",
                    "codigo": 702
                }),
                al_no=lambda: self.finalizar_diagnostico({
                    "categoria": "RAM", "subcategoria": "Configuración Base",
                    "descripcion": "Verificación de frecuencia base.",
                    "solucion": "1. Verifique en BIOS que la velocidad coincida con la especificación de fábrica.",
                    "codigo": 701
                }))

    def crear_pregunta_binaria(self, frame, texto_pregunta, al_si, al_no):
        ctk.CTkLabel(frame, text=texto_pregunta, font=FONT_LABEL, wraplength=670).pack(pady=(30, 20))
        btn_box = ctk.CTkFrame(frame, fg_color="transparent")
        btn_box.pack(pady=10)
        ctk.CTkButton(btn_box, text="SÍ", width=140, height=40, command=al_si).pack(side="left", padx=15)
        ctk.CTkButton(btn_box, text="NO", width=140, height=40,
                      fg_color=COLOR_DIM, command=al_no).pack(side="left", padx=15)

    def avanzar_paso(self, siguiente_paso):
        self.arbol_paso = siguiente_paso
        self.pantalla_diagnostico()

    def guardar_temporal_y_avanzar(self, valor, siguiente_paso):
        self.temp_gira_ventilador = valor
        self.avanzar_paso(siguiente_paso)

    def evaluar_rama_energia_final(self, intermitente):
        gira = self.temp_gira_ventilador
        if not gira and not intermitente:
            d = {"categoria": "Fuente de Poder", "subcategoria": "Falla total de PSU",
                 "descripcion": "La fuente no entrega señal eléctrica.",
                 "solucion": "1. Desconecte el equipo.\n2. Realice la prueba del clip (puentear PS_ON y GND).\n3. Reemplace la fuente.",
                 "codigo": 103}
        elif not gira and intermitente:
            d = {"categoria": "Fuente de Poder", "subcategoria": "Ventilador trabado",
                 "descripcion": "Riesgo de sobrecalentamiento en PSU.",
                 "solucion": "1. Limpie el polvo de la fuente.\n2. Si el ventilador no gira, cambie la fuente.",
                 "codigo": 104}
        elif gira and intermitente:
            d = {"categoria": "Fuente de Poder", "subcategoria": "Voltaje inestable",
                 "descripcion": "Potencia insuficiente o condensador dañado.",
                 "solucion": "1. Desconecte dispositivos externos.\n2. Instale una fuente de mayor wattage.",
                 "codigo": 105}
        else:
            d = {"categoria": "Placa Base", "subcategoria": "Falla de POST",
                 "descripcion": "Fuente operativa pero placa base inactiva.",
                 "solucion": "1. Realice Clear CMOS (retire pila 30 segundos).\n2. Pruebe encender solo con CPU, 1 RAM y PSU.",
                 "codigo": 106}
        self.finalizar_diagnostico(d)

    def finalizar_diagnostico(self, dictamen):
        self.dictamen_final = dictamen
        self.arbol_fase = 2
        prefijo = self.dni_usuario_activo[:4] if self.dni_usuario_activo and len(self.dni_usuario_activo) >= 4 else "USER"
        # .strip() garantiza consistencia exacta con los id_ticket en Supabase
        self.ticket_id_actual = f"{prefijo}-TICKET-{random.randint(1000, 9999)}".strip()
        self.ticket_sincronizado = False
        self.pantalla_diagnostico()

    # =========================================================================
    # PANTALLA: MAPA VISUAL DE HARDWARE (Fase 3)
    # =========================================================================
    def pantalla_hardware_map(self, categoria_afectada: str):
        """
        Vista rediseñada del Mapa de Componentes del Sistema.
        Delega el renderizado completo a MotherboardMapView (dark-tech, alta fidelidad).
        """
        self.limpiar_panel()

        # Marco contenedor principal — fondo dark slate
        frame = ctk.CTkFrame(
            self,
            width=920, height=660,
            corner_radius=12,
            fg_color="#0b0f19",
            border_width=1,
            border_color="#1e293b",
        )
        frame.place(relx=0.5, rely=0.5, anchor="center")
        frame.grid_propagate(False)

        # Encabezado del panel
        header = ctk.CTkFrame(frame, fg_color="#0f172a", corner_radius=0)
        header.pack(fill="x")

        ctk.CTkLabel(
            header,
            text="🖥  Mapa de Componentes del Sistema",
            font=("Segoe UI", 15, "bold"),
            text_color="#06b6d4",
        ).pack(side="left", padx=18, pady=10)

        # Badge de categoría afectada
        if categoria_afectada:
            ctk.CTkLabel(
                header,
                text=f"  ⚠  {categoria_afectada}  ",
                font=("Segoe UI", 11, "bold"),
                text_color="#ef4444",
                fg_color="#450a0a",
                corner_radius=6,
            ).pack(side="left", padx=6)

        ctk.CTkLabel(
            header,
            text=f"Operador: {self.dni_usuario_activo}",
            font=("Consolas", 10),
            text_color="#475569",
        ).pack(side="right", padx=18)

        # ── Delegación al nuevo MotherboardMapView ──────────────────────
        MotherboardMapView(
            parent=frame,
            hw_data=self.hardware_detectado or {},
            categoria_diag=categoria_afectada,
            cmd_volver=self.pantalla_diagnostico,
            cmd_visor_3d=self.abrir_visor_3d,
        )

    # =========================================================================
    # VISOR 3D WEB / GEMELO DIGITAL (Fase 3 Extended)
    # =========================================================================
    def abrir_visor_3d(self, id_ticket: str | None = None):
        """
        Dispara el Gemelo Digital 3D en el navegador web pasando el id_ticket real.
        Usa la URL de producción (Vercel) configurada en WEB_VIEWER_URL — nunca localhost.
        Si la telemetría aún no ha sido sincronizada a Supabase, lanza una
        sincronización en segundo plano para que el visor 3D disponga de los datos.
        """
        # 1. Obtener o resolver id_ticket real (siempre con .strip() para
        #    garantizar consistencia exacta con los registros en Supabase)
        if not id_ticket:
            if not getattr(self, "ticket_id_actual", None):
                prefijo = self.dni_usuario_activo[:4] if self.dni_usuario_activo and len(self.dni_usuario_activo) >= 4 else "USER"
                self.ticket_id_actual = f"{prefijo}-TICKET-{random.randint(1000, 9999)}".strip()
            id_ticket = self.ticket_id_actual

        # Normalizar: eliminar espacios que romperían la búsqueda en BD
        id_ticket = str(id_ticket).strip()

        # 2. Sincronizar en Supabase si aún no se ha subido
        if self.dictamen_final and not getattr(self, "ticket_sincronizado", False):
            hw = self.hardware_detectado or {}
            df = self.dictamen_final
            self.ticket_sincronizado = True

            def _sync_inmediato():
                exito = CloudGateway.subir_ticket(id_ticket, self.dni_usuario_activo or "USER", hw, df)
                if exito:
                    print(f"[NUBE-3D] Ticket {id_ticket} sincronizado para Gemelo Digital 3D.")
                solucion_texto = str(df.get("solucion", "Sin recomendacion especifica.")).strip()
                CloudGateway.subir_sugerencia(id_ticket, solucion_texto)

            threading.Thread(target=_sync_inmediato, daemon=True).start()

        # 3. Usar abrir_gemelo_digital: construye URL de producción,
        #    abre el navegador y copia al portapapeles automáticamente
        enlace_completo = abrir_gemelo_digital(id_ticket, root_widget=self)

        # 4. Mostrar feedback visual al usuario con el enlace real generado
        self.modal_gemelo_digital(id_ticket, enlace_completo)


    def modal_gemelo_digital(self, id_ticket: str, url: str):
        """Ventana emergente informativa de lanzamiento del Gemelo Digital 3D."""
        v = ctk.CTkToplevel(self)
        v.title("Gemelo Digital 3D")
        v.geometry("560x320")
        v.resizable(False, False)
        v.grab_set()

        ctk.CTkLabel(
            v, text="🌐 Gemelo Digital 3D — IndiServ Analytica",
            font=FONT_TITLE, text_color=COLOR_CYAN
        ).pack(pady=(16, 4))

        ctk.CTkLabel(
            v,
            text=f"Abriendo gemelo digital 3D en el navegador...\n(Ticket: {id_ticket})",
            font=FONT_LABEL, justify="center"
        ).pack(pady=4)

        entry_url = ctk.CTkEntry(v, width=490, font=FONT_SMALL)
        entry_url.insert(0, url)
        entry_url.configure(state="readonly")
        entry_url.pack(pady=6)

        # Feedback inmediato: el enlace ya fue copiado por abrir_gemelo_digital()
        lbl_copiado = ctk.CTkLabel(
            v,
            text=f"✅ Enlace público copiado al portapapeles:\n{url}",
            font=FONT_SMALL, text_color=COLOR_OK, wraplength=510, justify="center"
        )
        lbl_copiado.pack(pady=(0, 4))

        def copiar_portapapeles():
            try:
                self.clipboard_clear()
                self.clipboard_append(url)
                self.update()
                lbl_copiado.configure(
                    text=f"✅ Enlace público copiado al portapapeles:\n{url}",
                    text_color=COLOR_OK
                )
            except Exception as e:
                lbl_copiado.configure(text=f"Error al copiar: {e}", text_color=COLOR_ERR)

        btn_box = ctk.CTkFrame(v, fg_color="transparent")
        btn_box.pack(pady=6)

        ctk.CTkButton(
            btn_box, text="📋 Copiar Enlace",
            command=copiar_portapapeles, width=150, height=34,
            fg_color="#1F6AA5", hover_color="#144F7A"
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            btn_box, text="🌐 Reabrir Navegador",
            command=lambda: webbrowser.open(url), width=150, height=34,
            fg_color="#29946d", hover_color="#1e6b4f"
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            btn_box, text="Cerrar",
            command=v.destroy, width=90, height=34,
            fg_color="gray"
        ).pack(side="left", padx=6)


    # =========================================================================
    def guardar_reporte_final(self):
        """Exporta el reporte en TXT y JSON, y sincroniza en la nube (Fase 3)."""
        df = self.dictamen_final
        hw = self.hardware_detectado or {}
        prefijo = self.dni_usuario_activo[:4] if self.dni_usuario_activo and len(self.dni_usuario_activo) >= 4 else "USER"
        if not getattr(self, "ticket_id_actual", None):
            self.ticket_id_actual = f"{prefijo}-TICKET-{random.randint(1000, 9999)}".strip()
        # .strip() asegura consistencia exacta con el id_ticket en Supabase
        ticket_id = str(self.ticket_id_actual).strip()

        # 1. Exportación Técnica Dual: TXT
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

        # 2. Exportación Técnica Dual: Estructurado (JSON)
        import json
        nombre_json = f"Reporte_Diagnostico_{ticket_id}.json"
        datos_json = {
            "ticket_id": ticket_id,
            "operador_dni": self.dni_usuario_activo,
            "telemetria": hw,
            "diagnostico": df
        }
        with open(nombre_json, "w", encoding="utf-8") as f:
            json.dump(datos_json, f, indent=4, ensure_ascii=False)

        # 3. Bitácora local
        with open("historial_local.txt", "a", encoding="utf-8") as h:
            h.write(f"[{ticket_id}] {df['categoria']} - {df['subcategoria']} (Código #{df['codigo']})\n")

        # 4. Sincronizacion en la nube (Fase 3) — hilo daemon
        def tarea_nube():
            # 4a. Reporte principal
            exito_ticket = CloudGateway.subir_ticket(ticket_id, self.dni_usuario_activo, hw, df)
            if exito_ticket:
                print(f"[NUBE] Ticket {ticket_id} sincronizado a Supabase.")
            else:
                print(f"[NUBE] Error al sincronizar ticket {ticket_id}.")

            # 4b. Sugerencia consolidada del diagnostico
            # La solucion del dictamen puede tener multiples pasos; se usa tal cual
            # ya viene numerada (ej. "1. ...\n2. ...\n3. ...")
            solucion_texto = str(df.get("solucion", "Sin recomendacion especifica.")).strip()
            if not solucion_texto:
                solucion_texto = "Sin recomendacion especifica."
            CloudGateway.subir_sugerencia(ticket_id, solucion_texto)

        threading.Thread(target=tarea_nube, daemon=True).start()

        self.pantalla_dashboard()

    # =========================================================================
    # MODAL 1: HISTORIAL LOCAL
    # =========================================================================
    def mostrar_historial_local(self):
        v = ctk.CTkToplevel(self)
        v.title("Bitácora e Historial Local")
        v.geometry("560x400")
        v.grab_set()

        ctk.CTkLabel(v, text="Historial de Diagnósticos Registrados",
                     font=FONT_TITLE).pack(pady=10)

        box = ctk.CTkTextbox(v, width=510, height=290, font=FONT_MONO)
        box.pack(pady=5)

        if os.path.exists("historial_local.txt"):
            with open("historial_local.txt", "r", encoding="utf-8") as f:
                contenido = f.read()
            box.insert("0.0", contenido if contenido else "No hay registros guardados aún.")
        else:
            box.insert("0.0", "No se encontró el archivo historial_local.txt.")
        box.configure(state="disabled")

    # =========================================================================
    # MODAL 2: BUZÓN DE SUGERENCIAS
    # =========================================================================
    def modal_sugerencias(self):
        v = ctk.CTkToplevel(self)
        v.title("Buzon de Soporte y Sugerencias")
        v.geometry("520x380")
        v.grab_set()

        ctk.CTkLabel(v, text="Describa el error o mejora que desea proponer:",
                     font=FONT_LABEL).pack(pady=10)

        txt_sug = ctk.CTkTextbox(v, width=460, height=150)
        txt_sug.pack(pady=5)

        lbl_estado = ctk.CTkLabel(v, text="", font=FONT_SMALL)
        lbl_estado.pack(pady=4)

        def enviar_feedback():
            texto = txt_sug.get("0.0", "end").strip()
            if not texto:
                lbl_estado.configure(text="Ingrese una descripcion valida.", text_color=COLOR_ERR)
                return

            t_id = f"SUG-{random.randint(10000, 99999)}"

            # 1. Guardar copia local (sin cambios)
            with open("sugerencias_locales.txt", "a", encoding="utf-8") as s:
                s.write(f"[{t_id}] {texto}\n")

            # 2. Sincronizar en Supabase en hilo daemon
            # El texto del operador puede ser multilinea; se consolida tal cual
            # Payload estricto: solo id_ticket y sugerencia
            def _subir():
                CloudGateway.subir_sugerencia(t_id, texto)

            threading.Thread(target=_subir, daemon=True).start()

            lbl_estado.configure(
                text=f"Sugerencia registrada y enviada. Ticket: {t_id}",
                text_color=COLOR_OK
            )
            txt_sug.delete("0.0", "end")

        ctk.CTkButton(v, text="Enviar Sugerencia", command=enviar_feedback, width=220).pack(pady=6)



# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = AppIndiServ()
    app.mainloop()