"""
generar_informe_tecnico.py
==========================
Script auxiliar que compila el informe académico formal `INFORME_TECNICO_INDISERV.docx`
para la sustentación del curso Programación Orientada a Objetos I (POO I).
"""

import docx
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def sombrear_celda(celda, color_hex: str):
    tc = celda._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color_hex)
    tcPr.append(shd)


def crear_tabla(doc, encabezados, filas, anchos=None):
    tabla = doc.add_table(rows=1, cols=len(encabezados))
    tabla.style = "Table Grid"
    hdr_cells = tabla.rows[0].cells
    for i, texto in enumerate(encabezados):
        hdr_cells[i].text = texto
        sombrear_celda(hdr_cells[i], "0A2540")
        run = hdr_cells[i].paragraphs[0].runs[0]
        run.font.bold = True
        run.font.size = Pt(9.5)
        run.font.name = "Calibri"
        run.font.color.rgb = RGBColor(255, 255, 255)

    for idx_fila, datos_fila in enumerate(filas):
        row_cells = tabla.add_row().cells
        bg = "F4F6F9" if idx_fila % 2 == 1 else "FFFFFF"
        for i, texto in enumerate(datos_fila):
            row_cells[i].text = str(texto)
            sombrear_celda(row_cells[i], bg)
            for p in row_cells[i].paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)
                    r.font.name = "Calibri"

    if anchos:
        for row in tabla.rows:
            for idx, width in enumerate(anchos):
                row.cells[idx].width = width

    doc.add_paragraph("")
    return tabla


def agregar_vineta(doc, titulo_negrita: str, texto_cuerpo: str):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(4)
    r_bold = p.add_run(titulo_negrita)
    r_bold.font.bold = True
    r_bold.font.name = "Calibri"
    r_bold.font.size = Pt(10.5)
    r_txt = p.add_run(texto_cuerpo)
    r_txt.font.name = "Calibri"
    r_txt.font.size = Pt(10.5)


def construir_informe():
    doc = docx.Document()

    # Configuración de estilos académicos
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)

    style_h1 = doc.styles.add_style("Heading 1 POO", WD_STYLE_TYPE.PARAGRAPH)
    style_h1.font.name = "Calibri"
    style_h1.font.size = Pt(14)
    style_h1.font.bold = True
    style_h1.font.color.rgb = RGBColor(10, 37, 64)
    style_h1.paragraph_format.space_before = Pt(12)
    style_h1.paragraph_format.space_after = Pt(6)

    style_h2 = doc.styles.add_style("Heading 2 POO", WD_STYLE_TYPE.PARAGRAPH)
    style_h2.font.name = "Calibri"
    style_h2.font.size = Pt(12)
    style_h2.font.bold = True
    style_h2.font.color.rgb = RGBColor(29, 78, 216)
    style_h2.paragraph_format.space_before = Pt(8)
    style_h2.paragraph_format.space_after = Pt(4)

    # =========================================================================
    # 1. PORTADA / ENCABEZADO FORMAL
    # =========================================================================
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(
        "UNIVERSIDAD NACIONAL MAYOR DE SAN MARCOS\n"
        "(Universidad del Perú, Decana de América)\n"
    )
    r.font.bold = True
    r.font.size = Pt(16)
    r.font.color.rgb = RGBColor(10, 37, 64)
    r.font.name = "Arial"

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(
        "FACULTAD DE CIENCIAS MATEMÁTICAS\n"
        "ESCUELA PROFESIONAL DE COMPUTACIÓN CIENTÍFICA\n\n\n"
    )
    r.font.bold = True
    r.font.size = Pt(13)
    r.font.name = "Arial"

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("INFORME TÉCNICO DE ARQUITECTURA, MODULARIDAD Y CALIDAD DE SOFTWARE\n\n")
    r.font.bold = True
    r.font.size = Pt(15)
    r.font.name = "Arial"
    r.font.color.rgb = RGBColor(10, 37, 64)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(
        "PROYECTO: IndiServ Analytica\n"
        "Sistema Experto de Auditoría, Diagnóstico de Hardware y Gestión Cloud\n\n\n"
    )
    r.font.bold = True
    r.font.size = Pt(13)
    r.font.name = "Arial"

    p = doc.add_paragraph()
    r1 = p.add_run("Curso: ")
    r1.font.bold = True
    p.add_run("Programación Orientada a Objetos I (POO I) - Sección 1\n")
    r2 = p.add_run("Docente: ")
    r2.font.bold = True
    p.add_run("Prof. Lyses Augusto Hidalgo Pereda\n\n")

    r3 = p.add_run("Equipo de Desarrollo:\n")
    r3.font.bold = True
    p.add_run(
        "• Huaman Rios, Sebastian — Arquitectura POO, Motor de Diagnóstico y Mapa 2D\n"
        "• Samame Pisco, Jesus Vierick — Seguridad, Autenticación y Control de Acceso\n"
        "• Alvarado Romero, Fher Eli — Persistencia Cloud y Pasarela Supabase\n"
        "• Zevallos Silva, Franco David — Controlador Principal (GUI) y Reportes Duales\n"
        "• Quispe Espinoza, Grover Patrick — Telemetría de Bajo Nivel (WMI/psutil)\n"
        "• Mamani Zela, Ana de Gabriela — Arnés de Pruebas (Harness) y Documentación\n\n\n"
    )

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rl = p.add_run("Lima, Perú — Octubre 2026")
    rl.font.bold = True
    rl.font.name = "Arial"

    doc.add_page_break()

    # =========================================================================
    # 2. DE C++ A PYTHON: EVOLUCIÓN DE LA MODULARIDAD
    # =========================================================================
    doc.add_paragraph("1. DE C++ A PYTHON: EVOLUCIÓN DE LA MODULARIDAD", style="Heading 1 POO")

    doc.add_paragraph("1.1 Traducción de Interfaces (.h) e Implementaciones (.cpp) a Paquetes Python (.py)", style="Heading 2 POO")
    doc.add_paragraph(
        "En la etapa inicial concebida en C++, la modularidad física exigía dividir cada abstracción en dos "
        "archivos: un archivo de cabecera (.h) encargado de declarar la interfaz pública de la clase (atributos, "
        "firmas de métodos y contratos) y un archivo de implementación (.cpp) con la lógica compilada. Al evolucionar "
        "IndiServ Analytica hacia Python, esta separación se trasladó al sistema de paquetes (directorio core/ con "
        "__init__.py) y módulos independientes (.py), donde cada archivo agrupa cohesivamente una responsabilidad "
        "única y expone su contrato mediante clases públicas, métodos estáticos (@staticmethod) y anotaciones de "
        "tipos (Type Hints)."
    )

    crear_tabla(
        doc,
        ["Concepto en C++ (.h / .cpp)", "Equivalente en IndiServ Analytica (Python)", "Principio de POO I Aplicado"],
        [
            [
                "Cabecera (.h): Declaración de firmas públicas y constantes",
                "Clases fachada (LectorHardware, CloudGateway, MotherboardMapView) y Type Hints",
                "Abstracción: el cliente conoce qué hace la clase sin depender de cómo lo hace.",
            ],
            [
                "Implementación (.cpp): Funciones privadas y detalles de bajo nivel",
                "Funciones internas con prefijo guion bajo (_wmi_query, _escanear_cpu, _get_client)",
                "Encapsulamiento: ocultación de detalles internos del módulo.",
            ],
            [
                "Directivas #include y namespaces",
                "Paquete estructurado core/ e importaciones explícitas (from core.X import Y)",
                "Modularidad y Bajo Acoplamiento entre subsistemas.",
            ],
            [
                "Destructores y limpieza manual de memoria",
                "Gestión del ciclo de vida de widgets (limpiar_panel, _clear_tooltip) y contextos with",
                "Responsabilidad Única en el manejo de recursos gráficos y de E/S.",
            ],
        ],
        [Inches(2.0), Inches(2.3), Inches(2.2)],
    )

    doc.add_paragraph("1.2 Justificación del Diseño Orientado a Objetos Adoptado", style="Heading 2 POO")
    agregar_vineta(
        doc,
        "Encapsulamiento y Ocultación de Información: ",
        "El controlador gráfico (AppIndiServ) nunca ejecuta comandos de consola ni sentencias SQL directamente. "
        "Toda consulta WMI/psutil está encapsulada dentro de LectorHardware (core/hardware.py) y toda operación "
        "con Supabase está encapsulada en CloudGateway (core/cloud_gateway.py).",
    )
    agregar_vineta(
        doc,
        "Principio de Responsabilidad Única (SRP): ",
        "Cada módulo dentro del paquete core/ tiene una sola razón para cambiar: hardware.py lee sensores del "
        "equipo; diagnostico.py ejecuta los algoritmos inferenciales y de estrés; hardware_map.py dibuja el esquema "
        "2D en Canvas; cloud_gateway.py persiste en la nube; y gemelo_digital.py construye el enlace hacia el visor 3D.",
    )
    agregar_vineta(
        doc,
        "Composición y Delegación sobre Herencia Profunda: ",
        "La clase principal AppIndiServ hereda de customtkinter.CTk para adquirir el comportamiento de una ventana "
        "de escritorio, pero delega las tareas especializadas componiendo e instanciando objetos colaboradores "
        "(MotherboardMapView, MicroStressTest) y servicios estáticos.",
    )

    # =========================================================================
    # 3. ARQUITECTURA DEL SISTEMA Y ANATOMÍA DEL MAIN (+1000 LÍNEAS)
    # =========================================================================
    doc.add_paragraph("2. ARQUITECTURA DEL SISTEMA Y ANATOMÍA DEL ARCHIVO PRINCIPAL (main.py)", style="Heading 1 POO")

    doc.add_paragraph("2.1 Rol de main.py como Controlador Orquestador de la Interfaz", style="Heading 2 POO")
    doc.add_paragraph(
        "El archivo main.py (1,401 líneas) define la clase central AppIndiServ(ctk.CTk), la cual actúa como "
        "Controlador Orquestador bajo un esquema Vista-Controlador. Su función no es calcular diagnósticos ni "
        "interrogar al sistema operativo por su cuenta, sino administrar el estado de la sesión (dni_usuario_activo, "
        "hardware_detectado, dictamen_final, ticket_id_actual), construir dinámicamente las pantallas de usuario, "
        "capturar eventos (clics, teclado, hilos secundarios) y coordinar la comunicación entre los módulos del "
        "paquete core/."
    )

    doc.add_paragraph("2.2 Desglose Estructural de Bloques Funcionales en main.py", style="Heading 2 POO")
    crear_tabla(
        doc,
        ["Rango de Líneas", "Bloque Funcional", "Clases / Objetos Instanciados", "Responsabilidad Específica"],
        [
            [
                "Líneas 1 – 43",
                "Configuración e Importaciones",
                "Constantes de estilo, temas de CustomTkinter",
                "Importa las clases del paquete core/ y define la paleta cromática y tipográfica.",
            ],
            [
                "Líneas 47 – 94",
                "Constructor (__init__) y Estado",
                "AppIndiServ(ctk.CTk), CTkImage, CTkLabel",
                "Inicializa la ventana 960x680, encapsula los atributos de sesión y provee utilidades (limpiar_panel, _hw).",
            ],
            [
                "Líneas 96 – 245",
                "Portal de Seguridad y Escaneo Asíncrono",
                "CloudGateway, LectorHardware, threading.Thread, CTkProgressBar",
                "Valida login/registro contra Supabase y lanza el escaneo de hardware en un hilo secundario sin congelar la GUI.",
            ],
            [
                "Líneas 247 – 471",
                "Dashboard Técnico en Pestañas",
                "CTkTabview (General, CPU/RAM, Gráficos, Discos, Red), CTkTextbox",
                "Presenta la telemetría recolectada en 5 pestañas de solo lectura y ofrece la botonera de navegación a los 6 módulos.",
            ],
            [
                "Líneas 474 – 671",
                "Diagnóstico Multisíntoma y Buscador Fuzzy",
                "MatrizSintomas, BuscadorAsistido, CTkScrollableFrame, BooleanVar",
                "Conecta los selectores múltiples y la caja de búsqueda en lenguaje libre con los motores matemáticos de core/diagnostico.py.",
            ],
            [
                "Líneas 674 – 760",
                "Micro-Stress Test de CPU",
                "MicroStressTest (instancia con callbacks), self.after()",
                "Ejecuta el benchmark multihilo de 10 s y actualiza el registro en tiempo real de forma segura entre hilos (thread-safe).",
            ],
            [
                "Líneas 762 – 1081",
                "Asistente Inferencial (Árbol de Decisión)",
                "Máquina de estados (arbol_fase, arbol_rama, arbol_paso)",
                "Guía paso a paso por 7 ramas de síntomas mediante preguntas binarias/múltiples hasta emitir el dictamen y el ticket.",
            ],
            [
                "Líneas 1083 – 1251",
                "Mapa 2D y Lanzador del Gemelo Digital 3D",
                "MotherboardMapView, abrir_gemelo_digital, CTkToplevel",
                "Delega el renderizado esquemático 2D a hardware_map.py y sincroniza el ticket en segundo plano al abrir el visor 3D web.",
            ],
            [
                "Líneas 1253 – 1401",
                "Exportación Dual, Bitácora y Punto de Entrada",
                "Archivos TXT/JSON, CloudGateway, CTkToplevel, app.mainloop()",
                "Genera el reporte dual (.txt y .json), sincroniza con Supabase en un hilo daemon y administra modales de historial y sugerencias.",
            ],
        ],
        [Inches(1.1), Inches(1.5), Inches(1.8), Inches(2.1)],
    )

    doc.add_paragraph("2.3 Justificación Técnica de su Extensión (1,401 Líneas)", style="Heading 2 POO")
    doc.add_paragraph(
        "La longitud de main.py responde a una decisión arquitectónica deliberada propia de aplicaciones de escritorio "
        "basadas en código declarativo con CustomTkinter (sin archivos externos .ui o XML):"
    )
    agregar_vineta(
        doc,
        "Construcción Programática de 8 Vistas y 3 Ventanas Modales: ",
        "Cada pantalla (Login, Registro, Splash de Carga, Dashboard de 5 pestañas, Árbol Inferencial de 7 ramas, "
        "Multisíntoma, Buscador Asistido y Micro-Stress Test) instancia, posiciona y estiliza decenas de widgets.",
    )
    agregar_vineta(
        doc,
        "Coordinación Asíncrona (Multithreading) Segura: ",
        "En lugar de bloquear el hilo principal de la interfaz durante operaciones lentas (consultas WMI de 3–5 s, "
        "benchmark de CPU de 10 s o peticiones HTTP a Supabase), AppIndiServ utiliza hilos secundarios (threading.Thread) "
        "y sincroniza las respuestas hacia la GUI mediante el planificador de eventos self.after(0, ...).",
    )
    agregar_vineta(
        doc,
        "Lógica de Negocio Desacoplada: ",
        "A pesar de sus 1,401 líneas de gestión de interfaz y eventos, el cálculo pesado reside fuera de main.py: "
        "el perfilador de hardware (536 líneas), el motor de diagnóstico (494 líneas), el mapa 2D (1,039 líneas) "
        "y la pasarela cloud (199 líneas) están completamente encapsulados en el paquete core/.",
    )

    doc.add_page_break()

    # =========================================================================
    # 4. COMPONENTES Y MÓDULOS DESARROLLADOS
    # =========================================================================
    doc.add_paragraph("3. COMPONENTES Y MÓDULOS DESARROLLADOS", style="Heading 1 POO")

    doc.add_paragraph("3.1 Módulo Esquemático 2D (core/hardware_map.py)", style="Heading 2 POO")
    doc.add_paragraph(
        "La clase MotherboardMapView encapsula la representación visual en 2D de la placa base sobre un lienzo "
        "nativo tk.Canvas de 860 × 490 píxeles. Aplica composición visual por capas: dibuja primero el sustrato PCB "
        "con pistas de circuito y tornillos de montaje, y sobre él posiciona cada subcomponente con coordenadas "
        "geométricas delimitadas (bounding boxes) para permitir detección de colisiones del cursor (_hit_test) y "
        "tarjetas emergentes (tooltips) en tiempo real."
    )

    crear_tabla(
        doc,
        ["Componente (Clave)", "Método de Renderizado", "Coordenadas 2D (x1, y1) → (x2, y2)", "Comportamiento ante Falla (DIAG_TO_COMP)"],
        [
            ["Panel I/O Trasero (IO)", "_draw_io_panel()", "(40, 42) → (86, 186)", "Resalta borde en rojo (#ef4444) ante fallas de Red / Adaptador."],
            ["Socket CPU + Cooler (CPU)", "_draw_cpu_socket()", "(209, 58) → (321, 170)", "Cambia tapa IHS a rojo alerta y muestra etiqueta [!] REVISIÓN REQUERIDA."],
            ["Ranuras DIMM x4 (RAM)", "_draw_ram_slots()", "(416, 48) → (517, 180)", "Colorea ranuras ocupadas según telemetría y alerta revisión XMP/EXPO."],
            ["Slot M.2 NVMe (M2)", "_draw_m2_slot()", "(176, 189) → (355, 225)", "Resalta disipador M.2 e informa riesgo de Thermal Throttling o S.M.A.R.T."],
            ["PCIe x16 + Tarjeta GPU (GPU)", "_draw_pcie_gpu()", "(130, 242) → (560, 334)", "Dibuja tarjeta triple-fan con VRAM real y alerta falla de PCIe/Video."],
            ["Fuente de Poder (PSU)", "_draw_psu_zone()", "(44, 360) → (180, 458)", "Ubicada en esquina inferior izquierda (y1=360 > GPU y2=334), sin solapamiento."],
            ["Bahía SATA (BAY)", "_draw_storage_bay()", "(540, 360) → (705, 458)", "Representa bahías secundarias SATA 1–3 en esquina inferior derecha."],
        ],
        [Inches(1.5), Inches(1.4), Inches(1.6), Inches(2.0)],
    )

    agregar_vineta(
        doc,
        "Corrección Geométrica de la Fuente de Poder (PSU): ",
        "En versiones previas, la zona de la fuente de alimentación podía solaparse visualmente con el área inferior "
        "de la tarjeta gráfica. En el diseño actual de MotherboardMapView, la GPU ocupa la franja vertical y = 242..334, "
        "mientras que la PSU fue reubicada en la esquina inferior izquierda en y = 360..458 (con un margen limpio de "
        "26 píxeles respecto a la GPU), incluyendo rejilla de ventilación y conector ATX de 24 pines.",
    )
    agregar_vineta(
        doc,
        "Feedback Visual Inteligente de Fallas: ",
        "El diccionario estático DIAG_TO_COMP traduce la categoría del dictamen inferencial (por ejemplo, 'Fuente de Poder' "
        "→ 'PSU', 'Enfriamiento' → 'CPU', 'Memoria RAM' → 'RAM') para que el método _state_colors() conmute "
        "automáticamente los colores del componente afectado al estado crítico (#ef4444 / #450a0a) y despliegue un "
        "indicador visual de alerta (_badge_alert).",
    )

    doc.add_paragraph("3.2 Módulo de Persistencia Cloud y Conexión con Visor 3D", style="Heading 2 POO")
    doc.add_paragraph(
        "La capa de persistencia sigue el patrón Gateway mediante la clase CloudGateway (core/cloud_gateway.py), "
        "apoyada en la función serializadora construir_resumen_para_bd() (core/hardware.py) y el conector "
        "abrir_gemelo_digital() (core/gemelo_digital.py):"
    )
    agregar_vineta(
        doc,
        "Gestión de Datos de Auditoría en Supabase: ",
        "CloudGateway encapsula el cliente oficial supabase-py 2.x para interactuar con tres tablas en PostgreSQL: "
        "padron_oficial (verificación de identidad por DNI), usuarios_app (autenticación de operadores), "
        "reportes_diagnostico (almacenamiento de tickets con columnas tipadas y un objeto JSONB specs_json con el "
        "snapshot completo de BIOS, CPU, RAM, GPUs, discos y red) y sugerencias_locales (payload estricto de dos "
        "columnas: id_ticket y sugerencia). Se emplea la operación idempotente upsert(on_conflict='id_ticket') "
        "para garantizar consistencia sin duplicados.",
    )
    agregar_vineta(
        doc,
        "Enlace con el Visor Complementario (Gemelo Digital 3D): ",
        "El módulo core/config.py garantiza que la constante WEB_VIEWER_URL apunte siempre al entorno de producción "
        "en Vercel (https://indiserv-web3d.vercel.app), bloqueando referencias accidentales a localhost. Cuando el "
        "operador solicita el Gemelo Digital 3D, abrir_gemelo_digital() sanitiza el identificador del ticket con "
        ".strip() y codificación URL, dispara una sincronización preventiva hacia Supabase si el ticket aún no había "
        "sido subido, abre el navegador predeterminado y copia el enlace público al portapapeles.",
    )

    # =========================================================================
    # 5. VALIDACIÓN Y CALIDAD DE SOFTWARE (EL ARNÉS / HARNESS)
    # =========================================================================
    doc.add_paragraph("4. VALIDACIÓN Y CALIDAD DE SOFTWARE (EL ARNÉS DE PRUEBAS / HARNESS)", style="Heading 1 POO")

    doc.add_paragraph("4.1 Justificación del Arnés de Pruebas Automatizado", style="Heading 2 POO")
    doc.add_paragraph(
        "Un arnés de pruebas (Test Harness) permite verificar de forma repetible, aislada y no intrusiva que los "
        "módulos del sistema cumplen sus contratos sin necesidad de recorrer manualmente todas las pantallas de la "
        "interfaz gráfica ni modificar el código de producción. El script test_supabase_insert.py fue actualizado "
        "para cubrir de extremo a extremo las cinco áreas críticas del proyecto empleando objetos simulados (HW_MOCK), "
        "ventanas ocultas (root.withdraw()) e intercepción controlada del navegador (unittest.mock.patch)."
    )

    doc.add_paragraph("4.2 Resultados de las Pruebas Ejecutadas", style="Heading 2 POO")
    crear_tabla(
        doc,
        ["Suite de Prueba en el Arnés", "Módulo Auditado", "Verificaciones Realizadas", "Resultado Observado"],
        [
            [
                "TEST 1: test_hardware_map_2d",
                "core/hardware_map.py (MotherboardMapView)",
                "Renderizado de 5 categorías de falla, >50 primitivas en Canvas, coordenadas dentro de 860x490, no colisión PSU/GPU (GPU y2=334 < PSU y1=360), hit-test y tooltips en los 6 componentes.",
                "PASSED [OK]",
            ],
            [
                "TEST 2: test_serializacion_telemetria",
                "core/hardware.py y core/diagnostico.py",
                "Serialización JSON de construir_resumen_para_bd (CPU, RAM, GPU), heurísticas de _inferir_refrigeracion, cálculo de calcular_health_score (80/100) y detección de Thermal Throttling (0.6% vs 23.7%).",
                "PASSED [OK]",
            ],
            [
                "TEST 3: test_tickets_y_enlaces_publicos",
                "core/gemelo_digital.py y core/config.py",
                "Guardia anti-localhost en WEB_VIEWER_URL, formato regex de ticket (XXXX-TICKET-XXXX), sanitización .strip() y generación de URL pública hacia Vercel.",
                "PASSED [OK]",
            ],
            [
                "TEST 4: test_reportes_diagnostico",
                "core/cloud_gateway.py (Supabase)",
                "Upsert real en tabla reportes_diagnostico con payload expandido y objeto JSONB specs_json (id_ticket: TKT-TEST-EXPANDED).",
                "PASSED [OK] (1 fila confirmada)",
            ],
            [
                "TEST 5: test_sugerencias_locales",
                "core/cloud_gateway.py (Supabase)",
                "Upsert real en tabla sugerencias_locales validando el contrato estricto de 2 columnas (id_ticket, sugerencia).",
                "PASSED [OK] (1 fila confirmada)",
            ],
        ],
        [Inches(1.6), Inches(1.5), Inches(2.3), Inches(1.1)],
    )

    # =========================================================================
    # 6. CONCLUSIONES ACADÉMICAS SOBRE LOS PRINCIPIOS DE POO APLICADOS
    # =========================================================================
    doc.add_paragraph("5. CONCLUSIONES ACADÉMICAS SOBRE LOS PRINCIPIOS DE POO APLICADOS", style="Heading 1 POO")

    agregar_vineta(
        doc,
        "1. Abstracción y Modelado del Dominio Real: ",
        "Cada entidad del problema técnico (el perfilador de hardware, el árbol de diagnóstico, la matriz de "
        "síntomas, el mapa físico de la placa base y la pasarela hacia la nube) fue abstraída en una clase con un "
        "propósito claro y comprensible, facilitando tanto el mantenimiento como la defensa académica del código.",
    )
    agregar_vineta(
        doc,
        "2. Encapsulamiento y Protección del Estado: ",
        "El estado de la sesión y del diagnóstico se mantiene encapsulado en los atributos de instancia de AppIndiServ, "
        "mientras que los detalles complejos de acceso al sistema operativo (PowerShell CIM/WMI) y red (PostgREST) "
        "permanecen ocultos detrás de métodos públicos bien definidos.",
    )
    agregar_vineta(
        doc,
        "3. Modularidad y Separación de Responsabilidades: ",
        "La transición desde la estructura clásica de cabeceras (.h) e implementaciones (.cpp) de C++ hacia el paquete "
        "modular core/ en Python demostró que el principio de Responsabilidad Única permite que un archivo controlador "
        "de interfaz de 1,401 líneas conviva ordenadamente con módulos especializados sin mezclar lógica de vista con "
        "lógica de negocio.",
    )
    agregar_vineta(
        doc,
        "4. Verificabilidad mediante Diseño Desacoplado: ",
        "Gracias a que las clases de diagnóstico, telemetría, renderizado 2D y nube están desacopladas del bucle "
        "principal de eventos de la ventana, el arnés de pruebas (test_supabase_insert.py) pudo instanciarlas y "
        "validarlas automáticamente con un 100% de éxito sin alterar una sola línea del código de producción.",
    )

    ruta_salida = "INFORME_TECNICO_INDISERV.docx"
    doc.save(ruta_salida)
    print(f"[OK] Documento generado exitosamente: {ruta_salida}")


if __name__ == "__main__":
    construir_informe()
