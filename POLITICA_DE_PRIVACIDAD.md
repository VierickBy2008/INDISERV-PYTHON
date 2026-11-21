# Política de Privacidad y Términos y Condiciones de Uso — IndiServ Analytica

**Versión:** v1.0 (Vigente desde Noviembre 2026)

Al registrarse, iniciar sesión o utilizar **IndiServ Analytica** (en adelante, "el Software"), usted ("el Usuario") declara haber leído, comprendido y aceptado íntegramente las condiciones establecidas en este documento.

---

## 1. Naturaleza y Finalidad del Software
**IndiServ Analytica** es una plataforma de software técnico y académico orientada a la lectura de telemetría de hardware local, diagnóstico asistido mediante motor experto, pruebas de rendimiento de CPU y visualización interactiva de un Gemelo Digital 3D en la nube.

## 2. Origen Público de los Datos del Padrón de Verificación (UNMSM)
El Usuario reconoce y acepta expresamente que los datos de validación académica utilizados para verificar el acceso de operadores autorizados (**DNI, código de estudiante, nombres completos y carrera/especialidad**) provienen del **Padrón Oficial Público de la Universidad Nacional Mayor de San Marcos (UNMSM)**, fuente institucional de acceso público.

Conforme a la **Ley N.° 29733 (Ley de Protección de Datos Personales del Perú)** y su Reglamento (D.S. N.° 003-2013-JUS), estos datos se utilizan exclusivamente para validar la identidad y el acceso académico dentro del Software. En ningún caso se comercializan, alquilan ni ceden a terceros con fines publicitarios.

## 3. Información Recopilada y Exclusión de Archivos Privados
El Software recopila únicamente:
- **Datos de cuenta del operador**: DNI, alias/nickname, correo electrónico y contraseña ingresada al registrarse.
- **Telemetría técnica del equipo**: fabricante y modelo de placa base, BIOS, modelo de CPU, núcleos/hilos, frecuencias, RAM instalada, GPU y VRAM, unidades de almacenamiento, factor de forma (`Laptop` o `PC de escritorio`), adaptador de red activo, IP local, latencia y versión de Windows.
- **Resultados de diagnóstico**: categoría de falla detectada, sugerencias técnicas y código único de ticket (`id_ticket`).

El Software **NO** recopila ni transmite archivos personales, documentos, fotografías, contraseñas del sistema operativo, historial de navegación, pulsaciones de teclado ni datos bancarios.

## 4. Almacenamiento en la Nube (Supabase) y Visor 3D (Vercel)
Los tickets y su resumen técnico (`specs_json`) se almacenan en **Supabase** para habilitar su inspección visual en el Gemelo Digital 3D alojado en **Vercel** (`indiserv-web3d.vercel.app`). El Usuario entiende y acepta que cualquier persona con el enlace exacto del ticket (`?ticket=<id_ticket>`) podrá ver las especificaciones técnicas del equipo asociadas a dicho reporte.

## 5. Micro-Stress Test de CPU y Exención de Responsabilidad
El módulo **Micro-Stress Test CPU** aplica una carga controlada (~90%) sobre los núcleos del procesador durante un periodo breve (5 a 15 s) para medir potencia sostenida y estabilidad térmica.
- Su ejecución es voluntaria y cancelable en cualquier momento.
- Los dictámenes y recomendaciones tienen carácter **técnico-orientativo y académico**; no sustituyen a un servicio técnico certificado.
- Los autores del Software no asumen responsabilidad por daños preexistentes en el equipo, manipulación física del hardware ni pérdida de datos derivada de decisiones del Usuario.

## 6. Derechos del Usuario (Derechos ARCO — Ley N.° 29733)
El Usuario puede ejercer sus derechos de **Acceso, Rectificación, Cancelación y Oposición (ARCO)** y solicitar la eliminación de su cuenta o tickets mediante el módulo **Buzón de Sugerencias / Soporte** de la aplicación.

## 7. Aceptación Expresa
Al marcar la casilla de aceptación en el registro o inicio de sesión, el Usuario otorga su consentimiento libre, previo, expreso e informado con todos los puntos de esta Política de Privacidad y Términos y Condiciones de Uso.
