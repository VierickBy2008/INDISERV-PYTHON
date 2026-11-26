"""
ui/dashboard_tabs.py — Dashboard principal y sus 5 pestañas de telemetría.
"""

from __future__ import annotations

import sys
import threading
import tkinter as tk
import customtkinter as ctk

from core.hardware import LectorHardware, calcular_health_score, _inferir_refrigeracion
from core.diagnostico import EvaluadorTelemetria
from core.ui_theme import (
    P,
    F_H2, F_H3, F_SMALL, F_CAPTION,
    Badge,
    BarraMetrica,
    TarjetaMetrica,
    boton,
    tarjeta,
    overline,
    estilo_tabview,
    estilo_textbox,
    habilitar_scroll_fluido,
    toast,
    nivel_por_umbral,
    color_por_umbral,
)


class DashboardMixin:
    """Mixin con el dashboard principal y las pestañas General, CPU/RAM, Gráficos, Discos y Red."""

    def pantalla_dashboard(self, forzar_reconstruccion: bool = False):
        hw = self.hardware_detectado or {}
        cache_key = (id(hw), self.dni_usuario_activo)
        dash = getattr(self, "_dashboard_frame", None)
        if (
            not forzar_reconstruccion
            and dash is not None
            and getattr(self, "_dashboard_cache_key", None) == cache_key
        ):
            try:
                if dash.winfo_exists():
                    self.limpiar_panel(mostrar_fondo=False, destruir_dashboard=False)
                    dash.place(relx=0.5, rely=0.5, relwidth=0.96, relheight=0.94, anchor="center")
                    dash.lift()
                    self._refrescar_avatar_topbar()
                    self._actualizar_texto_btn_fullscreen()
                    return
            except Exception:
                pass

        self.limpiar_panel(mostrar_fondo=False, destruir_dashboard=True)
        score = calcular_health_score(hw)
        if score >= 80:
            t_score, lbl_score = "ok", f"Salud Global: {score}/100 · Óptimo"
        elif score >= 55:
            t_score, lbl_score = "warn", f"Salud Global: {score}/100 · Atención"
        else:
            t_score, lbl_score = "err", f"Salud Global: {score}/100 · Crítico"

        frame = ctk.CTkFrame(
            self, corner_radius=14,
            fg_color=P["bg"], border_width=1, border_color=P["borde_fuerte"]
        )
        frame.place(relx=0.5, rely=0.5, relwidth=0.96, relheight=0.94, anchor="center")
        self._dashboard_frame = frame
        self._dashboard_cache_key = cache_key

        topbar = ctk.CTkFrame(
            frame, fg_color=P["surface"], corner_radius=11,
            border_width=1, border_color=P["borde"]
        )
        topbar.pack(side="top", fill="x", padx=14, pady=(12, 8))

        izq = ctk.CTkFrame(topbar, fg_color="transparent")
        izq.pack(side="left", padx=14, pady=9)
        fila_tit = ctk.CTkFrame(izq, fg_color="transparent")
        fila_tit.pack(anchor="w")

        self._lbl_topbar_avatar = ctk.CTkLabel(
            fila_tit, text="", width=32, height=32, corner_radius=16,
            fg_color=P["card_alt"], text_color=P["cian"], font=F_SMALL, cursor="hand2"
        )
        self._lbl_topbar_avatar.pack(side="left", padx=(0, 8))
        self._lbl_topbar_avatar.bind("<Button-1>", lambda _e: self.modal_mi_cuenta())
        self._refrescar_avatar_topbar()

        ctk.CTkLabel(
            fila_tit, text="●", font=("Segoe UI", 14), text_color=P["primario"]
        ).pack(side="left", padx=(0, 7))
        ctk.CTkLabel(
            fila_tit, text="IndiServ Analytica",
            font=F_H2, text_color=P["texto"]
        ).pack(side="left")
        Badge(fila_tit, f"ID {self.dni_usuario_activo or 'LOCAL'}", tipo="info").pack(
            side="left", padx=(10, 0)
        )
        Badge(fila_tit, lbl_score, tipo=t_score).pack(side="left", padx=(6, 0))

        der = ctk.CTkFrame(topbar, fg_color="transparent")
        der.pack(side="right", padx=10, pady=9)
        boton(der, "💾 Guardar Ticket", self._guardar_escaneo_manual,
              variante="primario", width=122, height=32, font=F_SMALL).pack(side="left", padx=(0, 5))
        boton(der, "👤 Mi Cuenta", self.modal_mi_cuenta,
              variante="util", width=102, height=32, font=F_SMALL,
              hover_border_color=P["primario"]).pack(side="left", padx=(0, 5))
        self._btn_fullscreen = boton(
            der, self._texto_btn_fullscreen(), self.alternar_pantalla_completa,
            variante="util", width=124, height=32, font=F_SMALL
        )
        self._btn_fullscreen.pack(side="left", padx=(0, 5))
        boton(der, "⟳ Re-escanear", self._reescanear_rapido,
              variante="util", width=106, height=32, font=F_SMALL,
              hover_border_color=P["cian"]).pack(side="left", padx=(0, 5))
        boton(der, "Cerrar Sesión", self.cerrar_sesion,
              variante="peligro", width=104, height=32, font=F_SMALL).pack(side="left")

        # Empaquetar el Command Dock ANTES del Tabview con side="bottom" garantiza
        # que nunca se recorte verticalmente en ninguna resolución ni en pantalla completa.
        dock = ctk.CTkFrame(
            frame, fg_color=P["surface"], corner_radius=12,
            border_width=1, border_color=P["borde"]
        )
        dock.pack(side="bottom", fill="x", padx=14, pady=(6, 12))

        fila1 = ctk.CTkFrame(dock, fg_color="transparent")
        fila1.pack(fill="x", padx=12, pady=(10, 6))
        for col in range(4):
            fila1.grid_columnconfigure(col, weight=1, uniform="diag_primary")

        boton(
            fila1, "▶  Árbol de Diagnóstico", self.iniciar_diagnostico,
            variante="primario", height=40, font=F_H3,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        boton(
            fila1, "◈  Diagnóstico Multisíntoma", self.pantalla_multisintoma,
            variante="modulo", height=40, font=F_H3,
            hover_border_color=P["cian"],
        ).grid(row=0, column=1, sticky="ew", padx=6)
        boton(
            fila1, "✦  Buscador Asistido IA", self.pantalla_buscador,
            variante="modulo", height=40, font=F_H3,
            hover_border_color=P["azul_h"],
        ).grid(row=0, column=2, sticky="ew", padx=6)
        boton(
            fila1, "⚡  Micro-Stress Test CPU", self.pantalla_stress_test,
            variante="modulo", height=40, font=F_H3,
            hover_border_color=P["violeta_h"],
        ).grid(row=0, column=3, sticky="ew", padx=(6, 0))

        ctk.CTkFrame(dock, height=1, fg_color=P["borde"]).pack(fill="x", padx=12, pady=(2, 6))

        fila2 = ctk.CTkFrame(dock, fg_color="transparent")
        fila2.pack(fill="x", padx=12, pady=(0, 10))
        for col in range(5):
            fila2.grid_columnconfigure(col, weight=1, uniform="diag_util")

        boton(
            fila2, "Mapa 2D Hardware",
            lambda: self._abrir_mapa_desde_vista("", self.pantalla_dashboard),
            variante="util", height=34, font=F_SMALL,
            hover_border_color=P["ambar"],
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        boton(
            fila2, "Gemelo Digital 3D", self.abrir_visor_3d,
            variante="util", height=34, font=F_SMALL,
            hover_border_color=P["cian"],
        ).grid(row=0, column=1, sticky="ew", padx=5)
        boton(
            fila2, "Mis Tickets Privados", self.modal_mis_tickets,
            variante="util", height=34, font=F_SMALL,
            hover_border_color=P["primario"],
        ).grid(row=0, column=2, sticky="ew", padx=5)
        boton(
            fila2, "Sugerencias", self.modal_sugerencias,
            variante="util", height=34, font=F_SMALL,
            hover_border_color=P["borde_fuerte"],
        ).grid(row=0, column=3, sticky="ew", padx=5)
        boton(
            fila2, "Privacidad y Legal", self.modal_politica_privacidad,
            variante="util", height=34, font=F_SMALL,
            hover_border_color=P["borde_fuerte"],
        ).grid(row=0, column=4, sticky="ew", padx=(5, 0))

        self._hw_dashboard = hw
        self._tabs_cargadas: set[str] = set()
        self.tabs_dashboard = ctk.CTkTabview(
            frame, command=self._cargar_tab_dashboard_actual, **estilo_tabview()
        )
        self.tabs_dashboard.pack(side="top", fill="both", expand=True, pady=(0, 4), padx=14)

        for nombre in ("General", "CPU / RAM", "Gráficos", "Discos", "Red"):
            self.tabs_dashboard.add(nombre)

        # Renderizado diferido (lazy): solo construimos "General" al entrar y
        # las demás pestañas se crean al primer clic para ahorrar >70% de widgets iniciales.
        self._cargar_tab_dashboard("General")

    def _cargar_tab_dashboard_actual(self):
        try:
            nombre = self.tabs_dashboard.get()
        except Exception:
            return
        self._cargar_tab_dashboard(nombre)

    def _cargar_tab_dashboard(self, nombre: str):
        if nombre in self._tabs_cargadas:
            return
        self._tabs_cargadas.add(nombre)
        hw = self._hw_dashboard or {}
        tab = self.tabs_dashboard.tab(nombre)
        constructores = {
            "General": self._tab_general,
            "CPU / RAM": self._tab_cpu_ram,
            "Gráficos": self._tab_graficos,
            "Discos": self._tab_discos,
            "Red": self._tab_red,
        }
        fn = constructores.get(nombre)
        if fn:
            fn(tab, hw)

    def _refrescar_avatar_topbar(self):
        lbl = getattr(self, "_lbl_topbar_avatar", None)
        if not lbl:
            return
        try:
            if not lbl.winfo_exists():
                return
        except Exception:
            return
        info = getattr(self, "usuario_activo_info", {}) or {}
        av_img = self._decodificar_avatar_ctk(info.get("avatar_data"), size=30, cache_key="topbar")
        if av_img is not None:
            lbl.configure(image=av_img, text="", fg_color="transparent")
        else:
            nick = str(info.get("nickname") or self.dni_usuario_activo or "OP").strip()
            iniciales = nick[:2].upper()
            lbl.configure(image=None, text=iniciales, fg_color=P["card_alt"], text_color=P["cian"])

    def _guardar_escaneo_manual(self):
        """Guarda manualmente un ticket del perfil actual de hardware en Supabase solo si el usuario lo pide."""
        hw = self.hardware_detectado or {}
        if not self.dni_usuario_activo:
            toast(self, "Inicie sesión con su cuenta para guardar tickets en la nube.", tipo="warn")
            return
        score = calcular_health_score(hw)
        ficha = EvaluadorTelemetria.generar_ficha_cpuz_texto(hw)
        t_id = self._registrar_evento_nube(
            tipo_evento="Escaneo Profundo Manual",
            categoria="Perfil Técnico de Hardware",
            subcategoria=f"{hw.get('nombre_cpu', 'CPU')} · {hw.get('so', 'OS')} · Salud {score}/100",
            solucion=ficha or "Escaneo técnico guardado bajo demanda por el operador.",
            prefijo_evento="SCAN",
        )
        if t_id:
            toast(self, f"Ticket guardado en tu historial privado: {t_id}", tipo="ok")

    def _reescanear_rapido(self):
        toast(self, "Actualizando telemetría de hardware del equipo en segundo plano…", tipo="info", duracion_ms=1800)

        def _bg():
            try:
                self.hardware_detectado = LectorHardware.escanear_entorno()
            except Exception:
                pass
            self._post_ui(lambda: self.pantalla_dashboard(forzar_reconstruccion=True))

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

        # ── COLUMNA IZQUIERDA: CPU CON SCROLL COMPLETO Y FLUIDO ───────────────
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
            font=F_H3, text_color=P["texto"], anchor="w", wraplength=420
        ).pack(fill="x", padx=12, pady=(0, 4))

        body_cpu = ctk.CTkScrollableFrame(c_cpu, fg_color="transparent", corner_radius=0)
        body_cpu.pack(fill="both", expand=True, padx=6, pady=(0, 8))
        habilitar_scroll_fluido(body_cpu)

        # Panel estructurado de Telemetría de Silicio (cuadrícula + cachés + ISA)
        spec_grid = ctk.CTkFrame(body_cpu, fg_color="transparent")
        spec_grid.pack(fill="x", padx=6, pady=(2, 8))
        for col in range(4):
            spec_grid.grid_columnconfigure(col, weight=1, uniform="spec_cell")

        def _celda_silicio(parent, row, col, label, valor, color_val=P["texto"], colspan=1):
            cell = ctk.CTkFrame(
                parent, fg_color=P["surface"], corner_radius=7,
                border_width=1, border_color=P["borde"]
            )
            cell.grid(
                row=row, column=col, columnspan=colspan,
                padx=(0 if col == 0 else 2, 0 if col + colspan == 4 else 2),
                pady=2, sticky="nsew"
            )
            overline(cell, label).pack(anchor="w", padx=8, pady=(4, 0))
            ctk.CTkLabel(
                cell, text=str(valor or "N/D"), font=("Segoe UI Semibold", 11),
                text_color=color_val, anchor="w"
            ).pack(fill="x", padx=8, pady=(0, 4))

        _celda_silicio(spec_grid, 0, 0, "CODE NAME", hw.get("cpu_codename", "N/D"), P["cian"], colspan=2)
        _celda_silicio(spec_grid, 0, 2, "SOCKET", hw.get("cpu_socket", "N/D"), P["texto"])
        _celda_silicio(
            spec_grid, 0, 3, "TECH · TDP",
            f"{hw.get('cpu_tecnologia_nm', '?')} · {hw.get('cpu_tdp_max_w', '?')}",
            P["primario"],
        )

        f_actual_mhz = hw.get("frecuencia_actual_mhz")
        reloj_txt = f"{float(f_actual_mhz):.0f} MHz" if isinstance(f_actual_mhz, (int, float)) and f_actual_mhz > 0 else f"{hw.get('frecuencia_actual_ghz', '?')} GHz"
        bus_val = self._num(hw.get("cpu_bus_mhz"), 100.0)
        _celda_silicio(spec_grid, 1, 0, "RELOJ ACTUAL", reloj_txt, P["cian"])
        _celda_silicio(spec_grid, 1, 1, "MULTIPLICADOR", hw.get("cpu_multiplicador", "N/D"), P["texto"])
        _celda_silicio(spec_grid, 1, 2, "BUS · VCORE", f"{bus_val:.1f} MHz · {hw.get('cpu_voltaje_v', 'N/D')}", P["ambar"])
        _celda_silicio(
            spec_grid, 1, 3, "FAM / MOD / STEP",
            f"{hw.get('cpu_family', '?')} / {hw.get('cpu_model', '?')} / {hw.get('cpu_stepping', '?')}",
            P["texto_sec"],
        )

        _celda_silicio(
            spec_grid, 2, 0, "CACHÉS DEL SILICIO (L1 / L2 / L3)",
            f"L1: {hw.get('cpu_l1_cache', 'N/D')}    |    L2: {hw.get('cpu_l2_cache', 'N/D')}    |    L3: {hw.get('cpu_l3_cache', 'N/D')}",
            P["texto"], colspan=3,
        )
        virt_raw = hw.get("cpu_virtualizacion")
        virt_txt = "✔ Activa" if virt_raw is True else ("✖ Inactiva" if virt_raw is False else "N/D")
        virt_col = P["primario"] if virt_raw is True else (P["ambar"] if virt_raw is False else P["texto_dim"])
        _celda_silicio(spec_grid, 2, 3, "VT-x / AMD-V", virt_txt, virt_col)

        isa_lista = hw.get("cpu_isa_flags") or []
        isa_str = " · ".join(isa_lista) if isa_lista else "N/D"
        isa_bar = ctk.CTkFrame(
            spec_grid, fg_color=P["surface"], corner_radius=7,
            border_width=1, border_color=P["borde"]
        )
        isa_bar.grid(row=3, column=0, columnspan=4, pady=(2, 0), sticky="ew")
        overline(isa_bar, "INSTRUCCIONES SOPORTADAS (ISA)", color=P["cian"]).pack(anchor="w", padx=8, pady=(4, 0))
        ctk.CTkLabel(
            isa_bar, text=isa_str, font=F_CAPTION, text_color=P["texto_sec"],
            anchor="w", justify="left", wraplength=405
        ).pack(fill="x", padx=8, pady=(0, 5))

        BarraMetrica(
            body_cpu, "Carga Global de CPU", uso_cpu, f"{uso_cpu:.1f}%", warn=70, err=90
        ).pack(fill="x", padx=6, pady=(2, 8))

        overline(body_cpu, "Distribución por Hilo Lógico", color=P["cian"]).pack(anchor="w", padx=6, pady=(2, 4))
        box_cores = ctk.CTkFrame(
            body_cpu, fg_color=P["surface"], corner_radius=8,
            border_width=1, border_color=P["borde"]
        )
        box_cores.pack(fill="x", padx=6, pady=(0, 6))

        usos = [float(p or 0.0) for p in (hw.get("uso_por_nucleo", []) or [])]
        filas_cores = max(1, (len(usos) + 1) // 2)
        alto_canvas = max(96, filas_cores * 34 + 16)
        canvas_cores = tk.Canvas(
            box_cores, height=alto_canvas, bg=P["surface"], highlightthickness=0, bd=0
        )
        canvas_cores.pack(fill="x", padx=6, pady=6)

        def _dibujar_cores(event=None):
            w = max(320, event.width if event else canvas_cores.winfo_width())
            if w <= 1:
                w = 380
            canvas_cores.delete("all")
            pad_x, gap_x, row_h = 8, 16, 34
            col_w = max(110, (w - 2 * pad_x - gap_x) / 2.0)
            for idx, pct in enumerate(usos):
                col = idx % 2
                row = idx // 2
                x0 = pad_x + col * (col_w + gap_x)
                y0 = 8 + row * row_h
                pct_c = max(0.0, min(100.0, pct))
                fill_col = color_por_umbral(pct_c, warn=75, err=92)
                canvas_cores.create_text(
                    x0, y0, text=f"Core #{idx}", anchor="nw",
                    fill=P["texto_sec"], font=F_CAPTION
                )
                canvas_cores.create_text(
                    x0 + col_w, y0, text=f"{pct_c:.0f}%", anchor="ne",
                    fill=P["texto"], font=F_CAPTION
                )
                by = y0 + 17
                canvas_cores.create_rectangle(
                    x0, by, x0 + col_w, by + 6, fill=P["card_alt"], outline=""
                )
                fw = max(2.0, col_w * (pct_c / 100.0)) if pct_c > 0 else 0
                if fw > 0:
                    canvas_cores.create_rectangle(
                        x0, by, x0 + fw, by + 6, fill=fill_col, outline=""
                    )

        canvas_cores.bind("<Configure>", _dibujar_cores)
        _dibujar_cores()

        # ── COLUMNA DERECHA: RAM CON SCROLL COMPLETO Y FLUIDO ─────────────────
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

        body_ram = ctk.CTkScrollableFrame(c_ram, fg_color="transparent", corner_radius=0)
        body_ram.pack(fill="both", expand=True, padx=6, pady=(4, 8))
        habilitar_scroll_fluido(body_ram)

        ram_grid = ctk.CTkFrame(body_ram, fg_color="transparent")
        ram_grid.pack(fill="x", padx=6, pady=(2, 8))
        for col in range(3):
            ram_grid.grid_columnconfigure(col, weight=1, uniform="ram_cell")

        def _celda_ram(col, label, valor, color_val=P["texto"]):
            cell = ctk.CTkFrame(
                ram_grid, fg_color=P["surface"], corner_radius=7,
                border_width=1, border_color=P["borde"]
            )
            cell.grid(
                row=0, column=col,
                padx=(0 if col == 0 else 2, 0 if col == 2 else 2),
                sticky="nsew"
            )
            overline(cell, label).pack(anchor="w", padx=8, pady=(4, 0))
            ctk.CTkLabel(
                cell, text=str(valor), font=("Segoe UI Semibold", 11),
                text_color=color_val, anchor="w"
            ).pack(fill="x", padx=8, pady=(0, 4))

        es_dual = (hw.get("ram_ranuras_ocupadas") or 0) >= 2
        _celda_ram(0, "CAPACIDAD TOTAL", hw.get("ram_total_mb", "?"), P["texto"])
        _celda_ram(1, "DISPONIBLE", hw.get("ram_disponible_mb", "?"), P["primario"])
        _celda_ram(
            2, "MODO DE CANAL",
            f"{hw.get('ram_canal_modo', 'Dual-Channel' if es_dual else 'Single-Channel')} ({hw.get('ram_ranuras_ocupadas', '?')} slot)",
            P["primario"] if es_dual else P["ambar"],
        )

        uso_ram = self._num(hw.get("ram_uso_pct", 0))
        BarraMetrica(
            body_ram, "Uso de Memoria Física", uso_ram, f"{uso_ram:.1f}%", warn=75, err=90
        ).pack(fill="x", padx=6, pady=(0, 10))

        overline(body_ram, "Módulos Físicos Detectados (SMBIOS)", color=P["primario"]).pack(anchor="w", padx=6, pady=(2, 4))
        box_ram = ctk.CTkFrame(
            body_ram, fg_color=P["surface"], corner_radius=8,
            border_width=1, border_color=P["borde"]
        )
        box_ram.pack(fill="x", padx=6, pady=(0, 6))

        modulos = hw.get("ram_modulos", []) or []
        if not modulos:
            ctk.CTkLabel(
                box_ram, text="Sin detalle individual de slots vía WMI.",
                font=F_SMALL, text_color=P["texto_dim"]
            ).pack(anchor="w", padx=10, pady=10)
        for i, m in enumerate(modulos, 1):
            item = ctk.CTkFrame(
                box_ram, fg_color=P["card_alt"], corner_radius=8,
                border_width=1, border_color=P["borde"]
            )
            item.pack(fill="x", padx=6, pady=5)
            f1 = ctk.CTkFrame(item, fg_color="transparent")
            f1.pack(fill="x", padx=10, pady=(6, 2))
            ctk.CTkLabel(
                f1, text=f"Slot #{i} · {m.get('ranura', 'DIMM')} ({m.get('formato', 'DIMM')})",
                font=F_H3, text_color=P["texto"]
            ).pack(side="left")
            Badge(f1, f"{m.get('capacidad_gb', '?')} GB", tipo="info").pack(side="right")
            v_mv = f" · {m['voltaje_mv'] / 1000:.2f} V" if m.get("voltaje_mv") else ""
            cfg_spd = m.get("velocidad_config_mhz", m.get("velocidad_mhz", "?"))
            ctk.CTkLabel(
                item,
                text=(
                    f"{m.get('fabricante', 'OEM')} · {m.get('tipo', '?')} @ {cfg_spd} MHz "
                    f"(Nominal: {m.get('velocidad_mhz', '?')} MHz{v_mv})\n"
                    f"Part Number: {m.get('part_number', 'N/D')} · Banco: {m.get('banco', 'N/A')}"
                ),
                font=F_CAPTION, text_color=P["texto_sec"], anchor="w", justify="left"
            ).pack(fill="x", padx=10, pady=(0, 6))

    def _tab_graficos(self, tab, hw: dict):
        gpus = hw.get("gpus", []) or []
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=6, pady=4)
        habilitar_scroll_fluido(scroll)

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
            if g.get("resolucion") and g.get("resolucion") != "N/D":
                hz_txt = f" @ {g['refresh_hz']} Hz" if g.get("refresh_hz") else ""
                self._fila_dato(c, "Salida de Pantalla", f"{g['resolucion']}{hz_txt}")
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
        habilitar_scroll_fluido(sf)

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
        habilitar_scroll_fluido(sp)

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
