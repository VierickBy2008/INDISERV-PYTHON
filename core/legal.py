"""
core/legal.py — Política de Privacidad y Términos y Condiciones de Uso
======================================================================
Documento legal integrado en IndiServ Analytica para aceptación expresa
del operador en las pantallas de Registro, Mi Cuenta y Dashboard.
"""

from __future__ import annotations

VERSION_POLITICA = "v2.0 — Noviembre 2026"

POLITICA_PRIVACIDAD_TEXTO = """\
========================================================================
  POLÍTICA DE PRIVACIDAD Y TÉRMINOS Y CONDICIONES DE USO
  IndiServ Analytica — Sistema Experto de Diagnóstico y Gemelo Digital 3D
  Versión: v2.0 (Vigente desde Noviembre 2026)
========================================================================

Al registrarse, iniciar sesión o utilizar IndiServ Analytica (en adelante,
"el Software"), usted ("el Usuario") declara haber leído, comprendido y
aceptado íntegramente las condiciones establecidas en el presente documento.
Si no está de acuerdo con alguna de estas cláusulas, debe abstenerse de
crear una cuenta o utilizar la aplicación.

------------------------------------------------------------------------
1. NATURALEZA Y FINALIDAD DEL SOFTWARE
------------------------------------------------------------------------
IndiServ Analytica es una plataforma de software técnico y académico
destinada a la recopilación de telemetría de hardware local, evaluación
asistida de fallas mediante un motor experto, pruebas de rendimiento de CPU
y visualización interactiva mediante un Gemelo Digital 3D en la nube.

------------------------------------------------------------------------
2. ORIGEN PÚBLICO DE LOS DATOS DEL PADRÓN DE VERIFICACIÓN (UNMSM)
------------------------------------------------------------------------
El Usuario reconoce y acepta expresamente que los datos de validación
académica utilizados para verificar el registro de operadores autorizados
(número de DNI, código de estudiante, nombres completos y especialidad o
carrera profesional) provienen del PADRÓN OFICIAL PÚBLICO DE LA UNIVERSIDAD
NACIONAL MAYOR DE SAN MARCOS (UNMSM), documentación institucional de
acceso público.

De conformidad con la Ley N.° 29733 (Ley de Protección de Datos Personales
del Perú) y su Reglamento (D.S. N.° 003-2013-JUS), el tratamiento de datos
procedentes de fuentes accesibles para el público se realiza estrictamente
con fines de validación de identidad, control de acceso académico y
prevención de registros apócrifos dentro del Software. Dichos datos NO son
vendidos, alquilados ni cedidos a terceros con fines comerciales ni
publicitarios.

------------------------------------------------------------------------
3. INFORMACIÓN RECOPILADA Y EXCLUSIÓN DE ARCHIVOS PRIVADOS
------------------------------------------------------------------------
Para operar correctamente, el Software recopila únicamente:
  a) Datos de cuenta del operador: DNI, alias/nickname, correo electrónico,
     resumen criptográfico (hash) de la contraseña y, de forma estrictamente
     opcional, una foto de perfil (avatar comprimido de hasta 192×192 px)
     cargada voluntariamente por el Usuario desde la sección "Mi Cuenta".
  b) Identificadores de seguridad de sesión: huella técnica unidireccional
     del dispositivo (device_hash) para reconocer equipos de confianza,
     tokens temporales de sesión de 15 minutos y códigos OTP de un solo uso.
  c) Telemetría técnica del equipo: fabricante y modelo de placa base,
     versión de BIOS, modelo de CPU, núcleos/hilos, frecuencias, memoria
     RAM instalada, modelo de GPU y VRAM, unidades de almacenamiento,
     factor de forma (Laptop, PC o Smartphone), adaptador de red activo,
     IP local, latencia de prueba y versión del sistema operativo.
  d) Resultados de diagnóstico: categoría de falla detectada, sugerencias
     técnicas y código único de ticket (id_ticket).

El Software NO recopila, lee, indexa ni transmite bajo ninguna circunstancia:
  • Documentos personales, galería completa, videos ni archivos del disco
    (excepto la imagen única de avatar que el Usuario seleccione de forma
    expresa y voluntaria para su perfil).
  • Contraseñas del sistema operativo, sesiones del navegador ni historial.
  • Pulsaciones de teclado (keylogging), capturas de pantalla ni audio.
  • Información bancaria, financiera ni de tarjetas de pago.

------------------------------------------------------------------------
4. SEGURIDAD DE ACCESO, OTP POR CORREO Y ALMACENAMIENTO EN LA NUBE
------------------------------------------------------------------------
Los tickets de diagnóstico y su resumen técnico (specs_json) se sincronizan
con Supabase con el fin de habilitar la consulta privada de flota y el
visor web 3D (IndiServ Web3D en Vercel).

Para proteger las cuentas contra accesos no autorizados, el Software emplea:
  • Verificación en dos pasos mediante códigos OTP de 6 dígitos enviados al
    correo electrónico del Usuario (vía Brevo) para registro, accesos desde
    nuevos dispositivos, cambio o recuperación de contraseña y eliminación
    de cuenta. Los códigos expiran en 10 minutos (máximo 5 intentos) y solo
    se almacenan en forma de firma HMAC-SHA256.
  • Sesiones controladas en servidor con duración máxima de 15 minutos y
    revocación inmediata al cerrar sesión o modificar la contraseña.
  • Notificaciones de seguridad por correo ante cambios críticos de cuenta.

El Usuario comprende y acepta que el enlace del Gemelo Digital 3D
(?ticket=<id_ticket>) permite visualizar únicamente la configuración técnica
del hardware y el dictamen del ticket asociado. Es responsabilidad exclusiva
del Usuario decidir con quién comparte dicho enlace.

------------------------------------------------------------------------
5. MICRO-STRESS TEST DE CPU Y EXENCIÓN DE RESPONSABILIDAD
------------------------------------------------------------------------
El módulo "Micro-Stress Test CPU" somete de manera intencional y controlada
a los núcleos del procesador a una carga aproximada del 90% durante un
periodo breve (5 a 15 segundos) con el objetivo de verificar potencia real
y estabilidad térmica.

Al ejecutar esta prueba, el Usuario acepta que:
  • La ejecución es completamente voluntaria y puede cancelarse en cualquier
    instante mediante el botón "Cancelar Test".
  • Los equipos con refrigeración deficiente, pasta térmica seca, baterías
    degradadas o fallas eléctricas previas pueden calentarse o apagarse por
    protección propia del hardware.
  • Todos los dictámenes, diagnósticos y recomendaciones emitidos por el
    Software tienen carácter estrictamente técnico-orientativo y educativo;
    no sustituyen el criterio de un servicio técnico profesional certificado.
  • Los desarrolladores y autores del Software quedan exentos de toda
    responsabilidad por daños preexistentes, manipulación física incorrecta
    de componentes, pérdida de garantía del fabricante o pérdida de datos
    derivada de acciones tomadas por el Usuario.

------------------------------------------------------------------------
6. DERECHOS DEL USUARIO (DERECHOS ARCO — LEY N.° 29733)
------------------------------------------------------------------------
El Usuario ejerce directamente, de forma autónoma y en tiempo real sus
derechos de Acceso, Rectificación, Cancelación y Oposición (ARCO) desde la
sección "Mi Cuenta" integrada en Desktop, Web y Android:
  • Acceso: consultar sus datos de operador, dispositivos de confianza y
    tickets privados asociados.
  • Rectificación: actualizar o retirar su foto de perfil y cambiar o
    recuperar su contraseña con verificación OTP por correo.
  • Cancelación (Eliminación Total): eliminar permanentemente su cuenta tras
    re-autenticación y confirmación OTP. Esta acción borra de forma
    irreversible en servidor el perfil del operador, su foto de perfil,
    sesiones activas, dispositivos de confianza, códigos OTP y todos los
    tickets de diagnóstico y sugerencias vinculados a su DNI.
  • Oposición y soporte adicional: también disponible mediante el módulo
    "Buzón de Sugerencias / Soporte" incluido en la aplicación.

------------------------------------------------------------------------
7. ACEPTACIÓN EXPRESA Y CONFORMIDAD
------------------------------------------------------------------------
Al marcar la casilla de aceptación y continuar con el registro o inicio de
sesión, el Usuario otorga su consentimiento libre, previo, expreso e
informado para el tratamiento de los datos técnicos, de perfil opcional y
de seguridad aquí descritos, declarando conformidad plena con esta
Política de Privacidad y Términos de Uso (v2.0).
"""
