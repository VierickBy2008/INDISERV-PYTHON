"""
ui/stress_y_arbol.py — Micro-Stress Test CPU, Árbol de Diagnóstico Guiado y Mapa 2D de Hardware.
"""

from __future__ import annotations

import customtkinter as ctk
import psutil

from core.security import generate_secure_ticket_id
from core.diagnostico import (
    EvaluadorTelemetria,
    MotorDiagnostico,
    MicroStressTest,
    RAMAS_ARBOL,
    obtener_dictamen,
)
from core.hardware_map import MotherboardMapView
from core.ui_theme import (
    P,
    F_H2, F_H3, F_SMALL, F_CAPTION,
    Badge,
    BarraMetrica,
    TarjetaMetrica,
    PuntoPulso,
    Sparkline,
    boton,
    tarjeta,
    overline,
    estilo_segmentado,
    estilo_textbox,
    toast,
    animar_entrada_panel,
)


class StressYArbolMixin:
    """Mixin con Micro-Stress Test, Árbol de Diagnóstico y Mapa 2D Interactivo."""

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
            self._iniciar_stress, variante="violeta", width=165, height=38
        )
        self._btn_stress.pack(side="left", padx=5)

        self._btn_cancelar_stress = boton(
            btn_row, "⏹  Cancelar",
            self._cancelar_stress, variante="peligro", width=125, height=38, state="disabled"
        )
        self._btn_cancelar_stress.pack(side="left", padx=5)

        self._btn_guardar_stress = boton(
            btn_row, "💾 Guardar en Nube",
            self._guardar_resultado_stress_nube, variante="primario", width=175, height=38, state="disabled"
        )
        self._btn_guardar_stress.pack(side="left", padx=5)

        self._btn_accion_termica = boton(
            btn_row, "🩺 Diagnosticar Enfriamiento",
            lambda: self.ejecutar_diagnostico_directo(302),
            variante="neutro", width=215, height=38
        )
        self._btn_accion_termica.pack(side="left", padx=5)

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
        if hasattr(self, "_btn_guardar_stress") and self._btn_guardar_stress.winfo_exists():
            self._btn_guardar_stress.configure(state="disabled", text="💾 Guardar en Nube")
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
                self._stress_append_main(
                    "\nℹ Resultado listo en memoria. Pulse '💾 Guardar en Nube' si desea registrar este ticket.\n"
                )
                if hasattr(self, "_btn_guardar_stress") and self._btn_guardar_stress.winfo_exists():
                    self._btn_guardar_stress.configure(state="normal", text="💾 Guardar en Nube")

        if hasattr(self, "_btn_stress") and self._btn_stress.winfo_exists():
            self._btn_stress.configure(state="normal", text="▶  Reiniciar Test")

    def _guardar_resultado_stress_nube(self):
        resultado = self._ultimo_resultado_stress
        if not resultado or resultado.get("cancelado") or "error" in resultado:
            return
        if not self.dni_usuario_activo:
            toast(self, "Inicie sesión para guardar resultados en la nube.", tipo="warn")
            return
        estado_txt = "THROTTLING DETECTADO" if resultado.get("throttling") else "ESTABLE"
        ficha = EvaluadorTelemetria.generar_ficha_cpuz_texto(self.hardware_detectado)
        t_stress = self._registrar_evento_nube(
            tipo_evento="Micro-Stress CPU",
            categoria=f"Micro-Stress CPU ({estado_txt})",
            subcategoria=(
                f"{resultado.get('rendimiento_avg_mops', 0)} Mops/s · "
                f"Freq prom. {resultado.get('freq_avg_ghz', 0)} GHz · "
                f"Uso máx. {resultado.get('uso_max_pct', 0)}%"
            ),
            solucion=f"{resultado.get('diagnostico', 'Benchmark completado.')}\n\n{ficha}",
            prefijo_evento="STRESS",
        )
        if t_stress:
            self._stress_append_main(f"\n✔ Ticket guardado en tu historial privado: {t_stress}\n")
            if hasattr(self, "_btn_guardar_stress") and self._btn_guardar_stress.winfo_exists():
                self._btn_guardar_stress.configure(state="disabled", text=f"✔ Guardado ({t_stress[-4:]})")
            toast(self, f"Resultado guardado en la nube: {t_stress}", tipo="ok")

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
            Badge(
                f_badges,
                f"✔ Guardado: {ticket}" if self.ticket_sincronizado else f"Sin guardar en nube · #{df['codigo']}",
                tipo="ok" if self.ticket_sincronizado else "warn",
            ).pack(side="right")

            ctk.CTkLabel(
                banner, text=df["descripcion"], font=F_H2,
                text_color=P["texto"], anchor="w", justify="left", wraplength=830
            ).pack(fill="x", padx=14, pady=(2, 10))

            overline(cuerpo, "Guía de Solución Técnica y Perfil CPU-Z Verificado", color=P["cian"]).pack(
                anchor="w", padx=18, pady=(4, 2)
            )

            ficha_cpuz = EvaluadorTelemetria.generar_ficha_cpuz_texto(self.hardware_detectado)
            resultado_txt = (
                f"Categoría: {df['categoria']}   |   Subcategoría: {df['subcategoria']}\n"
                f"Descripción: {df['descripcion']}\n"
                f"────────────────────────────────────────────────────────────────────\n"
                f"GUÍA DE SOLUCIÓN PASO A PASO:\n{df['solucion']}\n\n"
                f"{ficha_cpuz}\n\n"
                f"Ticket Preparado: {ticket}   |   Código Interno: #{df['codigo']} "
                f"(pulse '💾 Guardar Ticket y Reporte' para subirlo a la nube)"
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
                btn_frame, "💾 Guardar Ticket y Reporte",
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
        self.ticket_sincronizado = False
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
