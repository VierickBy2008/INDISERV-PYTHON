import docx
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

doc = docx.Document()

# Define custom styles
# UNMSM Blue: #0A2540 -> 10, 37, 64
style_h1 = doc.styles.add_style('Heading 1 Custom', WD_STYLE_TYPE.PARAGRAPH)
style_h1.font.name = 'Calibri'
style_h1.font.size = Pt(14)
style_h1.font.bold = True
style_h1.font.color.rgb = RGBColor(10, 37, 64)

style_h2 = doc.styles.add_style('Heading 2 Custom', WD_STYLE_TYPE.PARAGRAPH)
style_h2.font.name = 'Calibri'
style_h2.font.size = Pt(12)
style_h2.font.bold = True
style_h2.font.color.rgb = RGBColor(10, 37, 64)

# ===============================
# PORTADA
# ===============================
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run("UNIVERSIDAD NACIONAL MAYOR DE SAN MARCOS\n(Universidad del Perú, Decana de América)\n")
run.font.bold = True
run.font.size = Pt(16)
run.font.color.rgb = RGBColor(10, 37, 64)
run.font.name = 'Arial'

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run("FACULTAD DE CIENCIAS MATEMÁTICAS\nESCUELA PROFESIONAL DE COMPUTACIÓN CIENTÍFICA\n\n\n")
run.font.bold = True
run.font.size = Pt(14)
run.font.name = 'Arial'

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run("CRONOGRAMA DETALLADO Y PLAN DE TRABAJO DEL PROYECTO FINAL\n\n")
run.font.bold = True
run.font.size = Pt(15)
run.font.name = 'Arial'
run.font.color.rgb = RGBColor(10, 37, 64)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run('PROYECTO:\n"IndiServ Analytica: Sistema de Auditoría, Diagnóstico de Hardware y Gestión Cloud"\n\n\n')
run.font.bold = True
run.font.size = Pt(13)
run.font.name = 'Arial'

p = doc.add_paragraph()
run = p.add_run("Curso: ")
run.font.bold = True
p.add_run("Programación Orientada a Objetos 1 - Sección 1\n")
run2 = p.add_run("Docente: ")
run2.font.bold = True
p.add_run("Prof. Lyses Augusto Hidalgo Pereda\n\n")

run3 = p.add_run("Equipo de Desarrollo (Estudiantes):\n")
run3.font.bold = True
p.add_run("• Huaman Rios, Sebastian (Motor de Diagnóstico POO)\n"
          "• Samame Pisco, Jesus Vierick (Seguridad y Control de Acceso)\n"
          "• Alvarado Romero, Fher Eli (Persistencia Cloud y Supabase)\n"
          "• Zevallos Silva, Franco David (Integración y Generación de Reportes)\n"
          "• Quispe Espinoza, Grover Patrick (Telemetría de Bajo Nivel y Excepciones)\n"
          "• Mamani Zela, Ana de Gabriela (Pruebas Unitarias y Documentación)\n\n\n\n")

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run_l = p.add_run("Lima, Perú - 2026")
run_l.font.bold = True
run_l.font.name = 'Arial'

doc.add_page_break()

# ===============================
# 1. INTRODUCCIÓN Y ALCANCE
# ===============================
doc.add_paragraph("1. INTRODUCCIÓN Y ALCANCE DEL PROYECTO", style='Heading 1 Custom')

doc.add_paragraph("1.1 Descripción de la problemática", style='Heading 2 Custom')
doc.add_paragraph("El diagnóstico manual de hardware en talleres y centros de soporte técnico informático presenta deficiencias notables debido a la dependencia del conocimiento empírico de los operadores. Esta falta de estandarización ocasiona prolongados tiempos de atención, reemplazo innecesario de componentes y diagnósticos imprecisos. Las empresas y técnicos requieren una solución automatizada que audite y determine de forma sistemática el estado de salud del hardware, unificando los criterios de evaluación.")

doc.add_paragraph("1.2 Justificación técnica y académica", style='Heading 2 Custom')
doc.add_paragraph("Desde el punto de vista académico, el desarrollo de IndiServ Analytica justifica el aprendizaje y aplicación profunda de los pilares de la Programación Orientada a Objetos (POO). El uso de Clases Abstractas y Herencia permitirá modelar los distintos componentes físicos (CPU, GPU, RAM, Storage, Motherboard) derivando de una estructura base genérica. El Polimorfismo facilitará que métodos estandarizados como inspect() o getHealthStatus() actúen de manera específica según la naturaleza del dispositivo. Finalmente, el Encapsulamiento garantizará el acceso seguro a los atributos críticos, como la telemetría recolectada, logrando un código mantenible, escalable y altamente modular.")

doc.add_paragraph("1.3 Objetivos del software", style='Heading 2 Custom')
doc.add_paragraph("Objetivo General:\nDesarrollar un sistema experto de escritorio para la auditoría y diagnóstico de hardware, respaldado por una arquitectura POO en Python, con control de accesos y persistencia estructurada en la nube mediante Supabase.")
doc.add_paragraph("Objetivos Específicos:\n"
                  "• Implementar un módulo de diagnóstico profundo mediante extracción de telemetría a bajo nivel empleando bibliotecas como WMI, psutil y py-cpuinfo.\n"
                  "• Desarrollar un sistema de autenticación y control de acceso robusto manejando sesiones y roles (Técnico / Administrador).\n"
                  "• Centralizar la persistencia de datos mediante el modelado relacional en PostgreSQL y almacenamiento cloud, posibilitando el historial auditable por ticket.\n"
                  "• Garantizar la modularidad del código aplicando los pilares de POO y emitiendo reportes de auditoría generados en un flujo continuo.")

# ===============================
# 2. EDT
# ===============================
doc.add_paragraph("2. ESTRUCTURA DE DESGLOSE DEL TRABAJO (EDT / WBS)", style='Heading 1 Custom')
doc.add_paragraph("A continuación se presenta la jerarquía detallada de los entregables del proyecto:")
edt = [
    "1.0 Módulo de Seguridad y Control de Acceso (Autenticación)",
    "      1.1 Modelado de base de datos de usuarios (Supabase).",
    "      1.2 Desarrollo de clases de seguridad (User, SessionManager, AuthController).",
    "      1.3 Implementación de validación de credenciales y roles.",
    "2.0 Motor de Diagnóstico Orientado a Objetos (Python POO)",
    "      2.1 Diseño de arquitectura de clases base y derivadas (HardwareComponent, CPU, GPU, etc.).",
    "      2.2 Implementación de recolección de telemetría a bajo nivel (WMI, psutil).",
    "      2.3 Programación de métodos polimórficos de inspección y pruebas de estrés.",
    "3.0 Base de Datos y Persistencia Cloud (Supabase)",
    "      3.1 Modelado relacional en PostgreSQL (telemetría, tickets, logs).",
    "      3.2 Configuración de cliente Python (.env) y conexión de API.",
    "      3.3 Desarrollo de repositorios y servicios de persistencia (DAO).",
    "4.0 Integración de Módulos, Generador de Reportes y Validación",
    "      4.1 Unificación del flujo: Login -> Diagnóstico -> Cloud.",
    "      4.2 Generación de reportes locales exportables y tickets.",
    "      4.3 Manejo global de excepciones, logging y consistencia de datos.",
    "5.0 Pruebas Unitarias, Documentación Técnica y Sustentación Final",
    "      5.1 Ejecución de pruebas unitarias sobre clases de POO.",
    "      5.2 Redacción del manual técnico de arquitectura y usuario.",
    "      5.3 Preparación para la sustentación y defensa final del proyecto."
]
for item in edt:
    p = doc.add_paragraph(item)
    p.paragraph_format.space_after = Pt(2)

doc.add_page_break()

# ===============================
# 3. CRONOGRAMA POR HITOS
# ===============================
doc.add_paragraph("3. CRONOGRAMA DETALLADO POR HITOS", style='Heading 1 Custom')

def create_table(header, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(header))
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    for i, text in enumerate(header):
        hdr_cells[i].text = text
        # Shade header
        tc = hdr_cells[i]._tc
        tcPr = tc.get_or_add_tcPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), 'D9D9D9')
        tcPr.append(shd)
        hdr_cells[i].paragraphs[0].runs[0].font.bold = True
        hdr_cells[i].paragraphs[0].runs[0].font.size = Pt(9)
    
    for row_data in rows:
        row_cells = table.add_row().cells
        for i, text in enumerate(row_data):
            row_cells[i].text = text
            row_cells[i].paragraphs[0].runs[0].font.size = Pt(9)
            
    # Apply widths if provided
    if widths:
        for row in table.rows:
            for idx, width in enumerate(widths):
                row.cells[idx].width = width

header = ["ID", "Actividad Detallada", "Principios POO / Herramientas", "Inicio", "Fin", "Entregable Técnico", "Responsable(s)"]
col_widths = [Inches(0.4), Inches(2.0), Inches(1.3), Inches(0.7), Inches(0.7), Inches(1.0), Inches(1.1)]

doc.add_paragraph("HITO 1: Sistema de Inicio de Sesión y Control de Acceso (Semana 7: 10 de Octubre de 2026)", style='Heading 2 Custom')
rows_h1 = [
    ["1.1", "Modelado de clases de seguridad (User, SessionManager, AuthController).", "Encapsulamiento, POO", "04/10/26", "06/10/26", "Módulo Auth (.py)", "Jesus Vierick"],
    ["1.2", "Validación de credenciales, hash seguro y comunicación con API de autenticación.", "hashlib, supabase-py", "07/10/26", "10/10/26", "Sistema de Login Funcional", "Jesus / Franco Z."]
]
create_table(header, rows_h1, col_widths)
doc.add_paragraph("")

doc.add_paragraph("HITO 2: Diagnóstico del Sistema y Motor POO (Semana 9: 24 de Octubre de 2026)", style='Heading 2 Custom')
rows_h2 = [
    ["2.1", "Arquitectura de clases de hardware (Clase base abstracta HardwareComponent con subclases).", "Clases Abstractas, Herencia", "11/10/26", "17/10/26", "Diagrama y Código Base", "Sebastian Huaman"],
    ["2.2", "Implementación de métodos polimórficos: inspect(), runBenchmark(), getHealthStatus().", "Polimorfismo, Sobrescritura", "18/10/26", "21/10/26", "Métodos Implementados", "Sebastian Huaman"],
    ["2.3", "Recolección de telemetría a bajo nivel, pruebas de estrés y empaquetado estructurado.", "WMI, psutil, py-cpuinfo", "22/10/26", "24/10/26", "Script de Telemetría", "Grover Quispe"]
]
create_table(header, rows_h2, col_widths)
doc.add_paragraph("")

doc.add_paragraph("HITO 3: Base de Datos y Persistencia Cloud - Supabase (Semana 11: 07 de Noviembre de 2026)", style='Heading 2 Custom')
rows_h3 = [
    ["3.1", "Modelado relacional en PostgreSQL (Tablas: users, diagnostics_tickets, hardware_telemetry).", "PostgreSQL, Supabase", "25/10/26", "31/10/26", "Esquema DB Desplegado", "Fher Alvarado"],
    ["3.2", "Cliente Python para Supabase usando variables de entorno (.env).", "python-dotenv", "01/11/26", "03/11/26", "Módulo Configurado", "Fher Alvarado"],
    ["3.3", "Servicios de persistencia de datos (DAO / Repositorios orientados a objetos) y serialización.", "Patrón DAO, Encapsulamiento", "04/11/26", "07/11/26", "Clases Repositorio", "Fher / Ana Mamani"]
]
create_table(header, rows_h3, col_widths)
doc.add_paragraph("")

doc.add_paragraph("HITO 4: Unificación de Sistemas y Generación de Reportes (Semana 13: 21 de Noviembre de 2026)", style='Heading 2 Custom')
rows_h4 = [
    ["4.1", "Integración total del flujo: Login -> Diagnóstico de hardware -> Subida a Supabase -> Emisión de ticket local.", "Integración de Sistemas", "08/11/26", "15/11/26", "App Integrada Beta", "Franco Zevallos"],
    ["4.2", "Manejo global de excepciones, logging y consistencia de datos.", "Manejo de Excepciones", "16/11/26", "21/11/26", "App Estable (RC)", "Grover Quispe"]
]
create_table(header, rows_h4, col_widths)
doc.add_paragraph("")

doc.add_paragraph("FASE FINAL: Pruebas, Documentación y Sustentación (Semanas 14 y 15: Finales de Noviembre / Diciembre 2026)", style='Heading 2 Custom')
rows_h5 = [
    ["5.1", "Pruebas unitarias de las clases POO, optimización.", "unittest / pytest", "22/11/26", "28/11/26", "Reporte de Pruebas", "Ana Mamani"],
    ["5.2", "Elaboración del manual técnico de arquitectura.", "Documentación Técnica", "29/11/26", "02/12/26", "Manual PDF", "Ana / Grover"],
    ["5.3", "Preparación de la defensa y sustentación final del proyecto.", "Presentaciones, Exposición", "03/12/26", "05/12/26", "Material Exposición", "Equipo Completo"]
]
create_table(header, rows_h5, col_widths)

doc.add_page_break()

# ===============================
# 4. RACI
# ===============================
doc.add_paragraph("4. MATRIZ DE RESPONSABILIDADES (MATRIZ RACI)", style='Heading 1 Custom')
doc.add_paragraph("R = Responsable (Realiza la tarea) | A = Aprobador (Aprueba el resultado) | C = Consultado (Asesora) | I = Informado (Recibe reportes)")
header_raci = ["ID", "Tarea / Fase del Proyecto", "Sebastian H.", "Jesus S.", "Fher A.", "Franco Z.", "Grover Q.", "Ana M."]
rows_raci = [
    ["1.0", "Módulo de Seguridad y Autenticación", "C", "R", "I", "C", "I", "C"],
    ["2.0", "Motor de Diagnóstico POO (Hardware)", "R", "I", "C", "I", "R", "I"],
    ["3.0", "DB y Persistencia Cloud (Supabase)", "I", "I", "R", "A", "C", "C"],
    ["4.0", "Integración General y Reportes", "A", "C", "C", "R", "I", "I"],
    ["5.0", "Manejo de Excepciones y Pruebas", "I", "I", "C", "C", "R", "R"],
    ["6.0", "Documentación y Sustentación", "R", "R", "R", "R", "R", "R"]
]
create_table(header_raci, rows_raci)
doc.add_paragraph("")

# ===============================
# 5. GANTT
# ===============================
doc.add_paragraph("5. DIAGRAMA DE GANTT TABULAR", style='Heading 1 Custom')
header_gantt = ["Fase / Hito", "S7", "S8", "S9", "S10", "S11", "S12", "S13", "S14", "S15"]
rows_gantt = [
    ["1. Seguridad (Login / Roles)", "██", "██", "", "", "", "", "", "", ""],
    ["2. Diagnóstico POO (Hardware)", "", "██", "██", "██", "", "", "", "", ""],
    ["3. DB & Persistencia Cloud", "", "", "", "██", "██", "██", "", "", ""],
    ["4. Integración y Reportes", "", "", "", "", "", "██", "██", "", ""],
    ["5. Pruebas y Documentación", "", "", "", "", "", "", "", "██", "██"]
]
create_table(header_gantt, rows_gantt)
doc.add_paragraph("*Leyenda: Las celdas con '██' indican las semanas de ejecución principal de la actividad.")
doc.add_paragraph("")

# ===============================
# 6. RIESGOS
# ===============================
doc.add_paragraph("6. GESTIÓN DE RIESGOS TÉCNICOS Y PLAN DE CONTINGENCIA", style='Heading 1 Custom')
header_riesgos = ["Riesgo Identificado", "Prob", "Impacto", "Plan de Contingencia"]
col_widths_riesgos = [Inches(2.5), Inches(0.8), Inches(0.8), Inches(3.0)]
rows_riesgos = [
    ["Incompatibilidad de comandos WMI/APIs en distintas versiones de Windows", "Media", "Alto", "Implementar bloques try/except con fallbacks a librerías de nivel superior (ej. psutil genérico) en caso de que WMI falle."],
    ["Permisos insuficientes de administrador para escaneo de bajo nivel", "Alta", "Medio", "Detectar el nivel de privilegios al iniciar; si no es administrador, solicitar elevación de permisos (UAC) o funcionar en modo de lectura limitada (Safe Mode)."],
    ["Latencia o límites de conexión con Supabase", "Baja", "Alto", "Configurar tiempos de espera adecuados (timeouts) en el cliente de Python y habilitar un modo offline temporal guardando logs localmente para sincronización posterior."],
    ["Desincronización de código en el repositorio Git (Equipo 6 miembros)", "Alta", "Alto", "Establecer una estricta política de ramas (Branching) por módulo asignado. Integración a la rama main gestionada exclusivamente por Pull Requests validados."]
]
create_table(header_riesgos, rows_riesgos, col_widths_riesgos)

doc.save("Cronograma_IndiServ_Analytica_POO1.docx")
print("DOCX successfully updated!")
