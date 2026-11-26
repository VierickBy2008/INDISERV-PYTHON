"""
ui/diagnostico_views.py — Vistas de Diagnóstico Multisíntoma y Buscador Asistido IA.
"""

from __future__ import annotations

import random
import customtkinter as ctk

from core.diagnostico import (
    EvaluadorTelemetria,
    MatrizSintomas,
    BuscadorAsistido,
    CATALOGO_DICTAMENES,
    RAMAS_ARBOL,
    obtener_dictamen,
    rama_de_codigo,
    acciones_para,
)
from core.ui_theme import (
    P,
    F_H3, F_SMALL, F_CAPTION,
    Badge,
    BarraMetrica,
    boton,
    tarjeta,
    entrada,
    overline,
    estilo_checkbox,
    estilo_combo,
    estilo_textbox,
    habilitar_scroll_fluido,
    toast,
    animar_entrada_panel,
)


class DiagnosticoMixin:
    """Mixin con la Matriz Multisíntoma y el Buscador Asistido IA."""

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
        self._filtro_sint_after: str | None = None
        self._entry_filtro_sint.bind("<KeyRelease>", lambda _e: self._programar_filtro_sintomas())

        scroll = ctk.CTkScrollableFrame(col_izq, fg_color=P["surface"], corner_radius=8)
        scroll.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        habilitar_scroll_fluido(scroll)

        self._check_vars: list[ctk.BooleanVar] = []
        self._check_widgets: list[tuple[str, ctk.CTkCheckBox]] = []
        self._check_visibles: list[bool] = []
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
            self._check_visibles.append(True)

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
        habilitar_scroll_fluido(self._cards_multisintoma)

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

    def _programar_filtro_sintomas(self):
        if getattr(self, "_filtro_sint_after", None):
            try:
                self.after_cancel(self._filtro_sint_after)
            except Exception:
                pass
        self._filtro_sint_after = self.after(120, self._filtrar_checkboxes_sintomas)

    def _filtrar_checkboxes_sintomas(self):
        self._filtro_sint_after = None
        if not hasattr(self, "_entry_filtro_sint") or not self._entry_filtro_sint.winfo_exists():
            return
        q = self._entry_filtro_sint.get().strip().lower()
        vis = getattr(self, "_check_visibles", None)
        for idx, (texto, chk) in enumerate(getattr(self, "_check_widgets", [])):
            mostrar = (not q) or (q in texto)
            if vis is not None and idx < len(vis) and vis[idx] == mostrar:
                continue
            if mostrar:
                chk.pack(anchor="w", pady=4, padx=8, fill="x")
            else:
                chk.pack_forget()
            if vis is not None and idx < len(vis):
                vis[idx] = mostrar

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
        habilitar_scroll_fluido(self._scroll_resultados_busq)

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
        ficha_cpuz = EvaluadorTelemetria.generar_ficha_cpuz_texto(self.hardware_detectado)
        tb_sol = ctk.CTkTextbox(self._panel_dictamen_busq, height=135, **estilo_textbox())
        tb_sol.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        self._insertar_y_bloquear(
            tb_sol,
            f"{df['solucion']}\n\n{ficha_cpuz}\n\n"
            f"Ticket preparado: {ticket}  ·  Código Interno: #{df['codigo']} (guardado manual bajo demanda)"
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
