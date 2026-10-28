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
run = p.add_run("CRONOGRAMA OFICIAL Y PLAN DE TRABAJO DEL PROYECTO\n(FORMATO MS PROJECT - 8 SEMANAS)\n\n")
run.font.bold = True
run.font.size = Pt(15)
run.font.name = 'Arial'
run.font.color.rgb = RGBColor(10, 37, 64)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run('PROYECTO:\n"IndiServ Analytica: Sistema de Auditoría y Diagnóstico de Hardware en Python con Persistencia Cloud (Supabase)"\n\n\n')
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
p.add_run("• Huaman Rios, Sebastian\n"
          "• Samame Pisco, Jesus Vierick\n"
          "• Mamani Zela, Ana de Gabriela\n"
          "• Alvarado Romero, Fher Eli\n\n\n\n")

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
doc.add_paragraph("El diagnóstico manual de hardware en talleres y empresas depende fuertemente de métodos empíricos. Esta carencia de automatización deriva en tiempos de respuesta prolongados, refacciones innecesarias y falta de auditoría sobre los análisis realizados.")

doc.add_paragraph("1.2 Justificación técnica y académica", style='Heading 2 Custom')
doc.add_paragraph("Este proyecto aplica los cuatro pilares de la Programación Orientada a Objetos (POO): Herencia, Polimorfismo, Encapsulamiento y Abstracción. A través de la herencia se estructura una jerarquía de clases de hardware, y mediante el polimorfismo se estandariza el diagnóstico. El software se integrará con Supabase para almacenamiento persistente, prescindiendo de módulos web en favor de una solución de escritorio puramente orientada a objetos.")

doc.add_paragraph("1.3 Estructura del Cronograma", style='Heading 2 Custom')
doc.add_paragraph("El presente plan de trabajo está estructurado bajo las 7 fases estándar de gestión de proyectos de software (tipo Microsoft Project). El horizonte temporal comprende 8 semanas (del 12 de octubre al 04 de diciembre de 2026), divididas en actividades secuenciales y en paralelo.")

# ===============================
# TABLAS BASE FUNCS
# ===============================
def create_table_blue(header, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(header))
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    for i, text in enumerate(header):
        hdr_cells[i].text = text
        # Shade header to UNMSM Blue
        tc = hdr_cells[i]._tc
        tcPr = tc.get_or_add_tcPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), '0A2540')
        tcPr.append(shd)
        
        # Make font bold and white
        for paragraph in hdr_cells[i].paragraphs:
            for run in paragraph.runs:
                run.font.bold = True
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(255, 255, 255)
    
    for row_data in rows:
        row_cells = table.add_row().cells
        for i, text in enumerate(row_data):
            row_cells[i].text = text
            for paragraph in row_cells[i].paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(9)
            
    # Apply widths if provided
    if widths:
        for row in table.rows:
            for idx, width in enumerate(widths):
                row.cells[idx].width = width

# ===============================
# 2. RESUMEN EJECUTIVO (7 FASES)
# ===============================
doc.add_paragraph("2. TABLA RESUMEN EJECUTIVO (7 FASES)", style='Heading 1 Custom')
header_res = ["ID", "Fase del Proyecto", "Duración", "Fecha de Inicio", "Fecha de Fin"]
rows_res = [
    ["1", "INICIO DEL PROYECTO", "4 días", "12/10/2026", "15/10/2026"],
    ["2", "FASE DE PLANIFICACIÓN", "7 días", "16/10/2026", "26/10/2026"],
    ["3", "FASE DE DISEÑO", "8 días", "27/10/2026", "05/11/2026"],
    ["4", "FASE DE DESARROLLO", "18 días", "06/11/2026", "01/12/2026"],
    ["5", "FASE DE PRUEBAS", "8 días", "24/11/2026", "03/12/2026"],
    ["6", "DESPLIEGUE", "6 días", "27/11/2026", "04/12/2026"],
    ["7", "CIERRE DEL PROYECTO", "5 días", "28/11/2026", "04/12/2026"]
]
create_table_blue(header_res, rows_res)
doc.add_paragraph("")

doc.add_page_break()

# ===============================
# 3. CRONOGRAMA DETALLADO (EDT / MS PROJECT)
# ===============================
doc.add_paragraph("3. ESTRUCTURA DE DESGLOSE DEL TRABAJO (EDT DETALLADO)", style='Heading 1 Custom')

header_edt = ["ID", "Nombre de la Tarea / Subtarea", "Duración", "Inicio", "Fin", "Predec.", "Responsable"]
col_widths_edt = [Inches(0.4), Inches(2.2), Inches(0.7), Inches(0.8), Inches(0.8), Inches(0.6), Inches(1.0)]

doc.add_paragraph("FASE 1: INICIO DEL PROYECTO (Semana 1)", style='Heading 2 Custom')
rows_f1 = [
    ["1.1", "Acta de constitución del proyecto", "2d", "12/10/26", "13/10/26", "-", "Equipo Comp."],
    ["1.2", "Definición de roles en el equipo", "1d", "14/10/26", "14/10/26", "1.1", "Jesus S."],
    ["1.3", "Alineación con los requerimientos de POO 1", "1d", "15/10/26", "15/10/26", "1.2", "Ana M."]
]
create_table_blue(header_edt, rows_f1, col_widths_edt)
doc.add_paragraph("")

doc.add_paragraph("FASE 2: FASE DE PLANIFICACIÓN (Semanas 1 y 2)", style='Heading 2 Custom')
rows_f2 = [
    ["2.1", "Especificación de requerimientos de software", "3d", "16/10/26", "20/10/26", "1.3", "Fher A."],
    ["2.2", "Modelado conceptual del sistema de diagnóstico", "2d", "21/10/26", "22/10/26", "2.1", "Sebastian H."],
    ["2.3", "Configuración del repositorio Git", "2d", "23/10/26", "26/10/26", "2.2", "Jesus S."]
]
create_table_blue(header_edt, rows_f2, col_widths_edt)
doc.add_paragraph("")

doc.add_paragraph("FASE 3: FASE DE DISEÑO (Semanas 2 y 3)", style='Heading 2 Custom')
rows_f3 = [
    ["3.1", "Diagrama de clases UML (HardwareComponent, CPU, etc.)", "4d", "27/10/26", "30/10/26", "2.2", "Sebastian H."],
    ["3.2", "Diseño de la arquitectura de autenticación (Login)", "2d", "02/11/26", "03/11/26", "2.1", "Jesus S."],
    ["3.3", "Esquema relacional de la base de datos Supabase", "2d", "04/11/26", "05/11/26", "3.2", "Fher A."]
]
create_table_blue(header_edt, rows_f3, col_widths_edt)
doc.add_paragraph("")

doc.add_paragraph("FASE 4: FASE DE DESARROLLO (Semanas 4, 5 y 6)", style='Heading 2 Custom')
rows_f4 = [
    ["4.1", "Sprint 1: Módulo de autenticación y sesiones", "5d", "06/11/26", "12/11/26", "3.2, 3.3", "Jesus S."],
    ["4.2", "Sprint 2: Motor POO (psutil, WMI, polimorfismo)", "8d", "13/11/26", "24/11/26", "3.1", "Sebastian H."],
    ["4.3", "Sprint 3: Integración de Supabase (Tickets y Telemetría)", "5d", "25/11/26", "01/12/26", "4.1, 4.2", "Fher A."]
]
create_table_blue(header_edt, rows_f4, col_widths_edt)
doc.add_paragraph("")

doc.add_paragraph("FASE 5: FASE DE PRUEBAS (Semanas 6 y 7)", style='Heading 2 Custom')
rows_f5 = [
    ["5.1", "Pruebas unitarias (pytest) de las clases POO", "3d", "24/11/26", "26/11/26", "4.2", "Ana M."],
    ["5.2", "Pruebas de estrés de hardware", "3d", "27/11/26", "01/12/26", "5.1", "Sebastian H."],
    ["5.3", "Validación de integridad de datos en Supabase", "2d", "02/12/26", "03/12/26", "4.3", "Jesus S."]
]
create_table_blue(header_edt, rows_f5, col_widths_edt)
doc.add_paragraph("")

doc.add_paragraph("FASE 6: DESPLIEGUE (Semanas 7 y 8)", style='Heading 2 Custom')
rows_f6 = [
    ["6.1", "Empaquetado del software (Ejecutable/Instalador)", "3d", "27/11/26", "01/12/26", "4.2", "Ana M."],
    ["6.2", "Configuración final de variables de entorno seguras (.env)", "1d", "02/12/26", "02/12/26", "4.3", "Fher A."],
    ["6.3", "Pruebas de usuario y revisión de reportes locales", "2d", "03/12/26", "04/12/26", "6.1, 6.2", "Equipo Comp."]
]
create_table_blue(header_edt, rows_f6, col_widths_edt)
doc.add_paragraph("")

doc.add_paragraph("FASE 7: CIERRE DEL PROYECTO (Semana 8)", style='Heading 2 Custom')
rows_f7 = [
    ["7.1", "Elaboración del informe técnico final", "2d", "28/11/26", "01/12/26", "5.1", "Ana M."],
    ["7.2", "Preparación de diapositivas de sustentación", "2d", "02/12/26", "03/12/26", "7.1", "Fher A."],
    ["7.3", "Ensayo para la sustentación con el docente", "1d", "04/12/26", "04/12/26", "7.2", "Equipo Comp."]
]
create_table_blue(header_edt, rows_f7, col_widths_edt)
doc.add_paragraph("")

doc.add_page_break()

# ===============================
# 4. RACI
# ===============================
doc.add_paragraph("4. MATRIZ DE RESPONSABILIDADES (MATRIZ RACI)", style='Heading 1 Custom')
doc.add_paragraph("R = Responsable | A = Aprobador | C = Consultado | I = Informado")
header_raci = ["Fase del Proyecto", "Sebastian H.", "Jesus S.", "Ana M.", "Fher A."]
rows_raci = [
    ["1. Inicio del Proyecto", "C", "R", "R", "I"],
    ["2. Fase de Planificación", "R", "R", "C", "A"],
    ["3. Fase de Diseño", "R", "R", "I", "R"],
    ["4. Fase de Desarrollo", "R", "R", "I", "R"],
    ["5. Fase de Pruebas", "A", "C", "R", "I"],
    ["6. Despliegue", "I", "I", "R", "R"],
    ["7. Cierre del Proyecto", "R", "R", "R", "R"]
]
create_table_blue(header_raci, rows_raci)
doc.add_paragraph("")

# ===============================
# 5. GESTIÓN DE RIESGOS
# ===============================
doc.add_paragraph("5. GESTIÓN DE RIESGOS TÉCNICOS Y PLAN DE CONTINGENCIA", style='Heading 1 Custom')
header_riesgos = ["Fase Afectada", "Riesgo Identificado", "Impacto", "Plan de Contingencia"]
col_widths_riesgos = [Inches(1.2), Inches(2.2), Inches(0.8), Inches(2.8)]
rows_riesgos = [
    ["F4: Desarrollo", "Incompatibilidad de scripts WMI/psutil en Windows", "Alto", "Uso de bloques try/except y librerías de respaldo (fallback) estándar de Python."],
    ["F3: Diseño", "Modelo relacional ineficiente en Supabase", "Alto", "Revisión cruzada del esquema y pruebas de inserción mock antes del Desarrollo."],
    ["F4: Desarrollo", "Permisos de Administrador insuficientes", "Medio", "Validar permisos al inicio del script (UAC) y restringir telemetría si falla."],
    ["F2: Planificación", "Conflictos y desincronización en Git", "Medio", "Creación de ramas individuales (Branching) y Pull Requests con revisión de pares."],
    ["F6: Despliegue", "Fallo al empaquetar en binario (.exe)", "Alto", "Investigar pyinstaller con anticipación y excluir librerías innecesarias del venv."]
]
create_table_blue(header_riesgos, rows_riesgos, col_widths_riesgos)

doc.save("Cronograma_IndiServ_Analytica_POO1.docx")
print("DOCX MS Project generated successfully!")
