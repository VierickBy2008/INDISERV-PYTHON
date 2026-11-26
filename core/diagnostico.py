"""
core/diagnostico.py — Motor Inferencial Adaptativo (Fase 2)
===========================================================
Módulo ampliado con tres capacidades nuevas:

  1. MotorDiagnostico  — árbol lineal original (preservado sin cambios)
  2. MatrizSintomas    — correlación multivariable ponderada entre síntomas
                         y causas raíz (porcentaje de probabilidad)
  3. CATALOGO_DICTAMENES / RAMAS_ARBOL — fuente única de las hojas del árbol
                         guiado (incluye la nueva rama 8: Red / Internet)
  4. EvaluadorTelemetria — evidencias objetivas a partir de la telemetría
  5. BuscadorAsistido  — búsqueda en lenguaje natural (normalización, sinónimos,
                         raíces, tolerancia a typos) sobre TODAS las hojas y
                         ejecución directa del diagnóstico (difflib, stdlib)
  6. MicroStressTest   — benchmark CPU acotado, cancelable y con paradas de
                         seguridad; orquestado en un hilo para no bloquear la GUI
"""

from __future__ import annotations

import difflib
import math
import re
import subprocess
import sys
import threading
import time
import unicodedata
from typing import Callable

import psutil


class MotorDiagnostico:
    @staticmethod
    def evaluar_energia(cable_ok: bool, switch_ok: bool, ventilador_gira: bool, intermitente: bool):
        if not cable_ok:
            return {
                "categoria": "Fuente de Poder",
                "subcategoria": "Cable desconectado",
                "descripcion": "Falla de alimentación básica.",
                "solucion": "1. Desconecte el cable de poder de la parte trasera.\n2. Reconecte firmemente en ambos extremos.\n3. Pruebe encender.",
                "codigo": 101
            }
        if not switch_ok:
            return {
                "categoria": "Fuente de Poder",
                "subcategoria": "Interruptor apagado",
                "descripcion": "Interruptor principal en OFF.",
                "solucion": "1. Posicione el interruptor trasero en 'I'.\n2. Intente encender el equipo.",
                "codigo": 102
            }
        if not ventilador_gira and not intermitente:
            return {
                "categoria": "Fuente de Poder",
                "subcategoria": "Falla total de PSU",
                "descripcion": "La fuente no entrega señal eléctrica.",
                "solucion": "1. Desconecte el equipo.\n2. Realice la prueba del clip (puentear PS_ON y GND).\n3. Reemplace la fuente de poder si no gira.",
                "codigo": 103
            }
        if not ventilador_gira and intermitente:
            return {
                "categoria": "Fuente de Poder",
                "subcategoria": "Ventilador trabado",
                "descripcion": "Riesgo de sobrecalentamiento en PSU.",
                "solucion": "1. Apague de inmediato.\n2. Limpie el polvo de la PSU.\n3. Si sigue fallando, reemplace la fuente.",
                "codigo": 104
            }
        if ventilador_gira and intermitente:
            return {
                "categoria": "Fuente de Poder",
                "subcategoria": "Voltaje inestable",
                "descripcion": "Potencia insuficiente o condensador dañado.",
                "solucion": "1. Desconecte dispositivos externos.\n2. Si enciende, la fuente no soporta la carga total. Reemplace por una de mayor wattage.",
                "codigo": 105
            }
        return {
            "categoria": "Placa Base",
            "subcategoria": "Falla de POST",
            "descripcion": "Fuente operativa pero placa base inactiva.",
            "solucion": "1. Realice un Clear CMOS (retire la pila por 30s).\n2. Pruebe encender solo con CPU, 1 memoria RAM y la fuente.",
            "codigo": 106
        }


SINTOMAS_DISPONIBLES: list[str] = [
    "La PC no da señal de encendido (sin luces ni ventiladores)",
    "Pantalla negra al encender (sin imagen en monitor)",
    "Pitidos durante el POST al iniciar el equipo",
    "Pantallas azules (BSOD) frecuentes o aleatorias",
    "Reinicios aleatorios o arranque en bucle (Boot Loop)",
    "Temperatura de CPU muy alta / aviso de sobrecalentamiento",
    "Ventilador de CPU inactivo, trabado o excesivamente ruidoso",
    "Sistema extremadamente lento o congelado",
    "Disco duro / SSD al 100% de uso de forma constante",
    "Memoria RAM al límite o uso de memoria anormalmente alto",
    "GPU no detectada, pantalla con artefactos o parpadeos",
    "Sin señal de video aunque el equipo intenta arrancar",
    "Apagados bruscos o cortes de energía sin previo aviso",
    "Errores al leer archivos o datos corruptos en disco",
    "Conexión de red inestable, pérdida de paquetes o ping alto",
]

_CAUSAS_RAIZ: dict[str, dict] = {
    "Fuente de Poder (PSU)": {
        "descripcion": "La PSU no entrega voltaje estable o suficiente en uno o más rieles.",
        "solucion": (
            "1. Realice la prueba del clip (cortocircuitar PS_ON con GND).\n"
            "2. Mida voltajes en rieles +12V y +5V con multímetro.\n"
            "3. Desconecte dispositivos no esenciales para reducir carga.\n"
            "4. Reemplace la fuente si los voltajes se desvían >5%."
        ),
        "codigo_base": 100,
        "pesos": {0: 0.95, 12: 0.90, 4: 0.65, 1: 0.40, 6: 0.30},
    },
    "Placa Base": {
        "descripcion": "Fallo en POST, condensador dañado, slot PCIe/RAM defectuoso o BIOS corrupta.",
        "solucion": (
            "1. Realice Clear CMOS (retire la pila de litio 30 segundos).\n"
            "2. Pruebe con configuración mínima: CPU + 1 módulo RAM + PSU.\n"
            "3. Inspeccione la PCB buscando condensadores hinchados o quemados.\n"
            "4. Actualice la BIOS si es posible desde un equipo funcional."
        ),
        "codigo_base": 200,
        "pesos": {0: 0.60, 2: 0.80, 4: 0.65, 1: 0.55, 3: 0.40},
    },
    "Memoria RAM": {
        "descripcion": "Módulo defectuoso, mal asentado o perfil XMP/EXPO inestable.",
        "solucion": (
            "1. Limpie los contactos de los módulos con goma de borrar.\n"
            "2. Ejecute MemTest86 al menos 2 pasadas completas.\n"
            "3. Pruebe los módulos de a uno para aislar el defectuoso.\n"
            "4. Desactive el perfil XMP/EXPO en la BIOS para velocidad base."
        ),
        "codigo_base": 300,
        "pesos": {2: 0.80, 3: 0.90, 9: 0.95, 7: 0.55, 1: 0.45, 4: 0.50},
    },
    "CPU / Enfriamiento Térmico": {
        "descripcion": "Disipación insuficiente produce throttling o apagado de protección térmica.",
        "solucion": (
            "1. Aplique pasta térmica nueva (retire la anterior con isopropílico).\n"
            "2. Limpie el disipador y los filtros de polvo del chasis.\n"
            "3. Verifique que el cooler esté correctamente montado y su conector en CPU_FAN.\n"
            "4. Mejore el flujo de aire del chasis (positiva/negativa)."
        ),
        "codigo_base": 400,
        "pesos": {5: 0.95, 6: 0.85, 7: 0.55, 12: 0.50, 4: 0.45},
    },
    "Tarjeta Gráfica (GPU)": {
        "descripcion": "GPU no inicializada, driver corrupto, slot PCIe suelto o sobrecalentamiento.",
        "solucion": (
            "1. Desinstale drivers actuales con DDU (Display Driver Uninstaller).\n"
            "2. Reinstale el driver desde el sitio oficial (NVIDIA/AMD).\n"
            "3. Reinserte la GPU en el slot PCIe y asegure los clips.\n"
            "4. Verifique que los conectores de alimentación PCIe estén firmes."
        ),
        "codigo_base": 500,
        "pesos": {10: 0.95, 11: 0.80, 2: 0.60, 1: 0.55, 3: 0.50},
    },
    "Almacenamiento (SSD / HDD)": {
        "descripcion": "Unidad con sectores defectuosos, saturación I/O o S.M.A.R.T. crítico.",
        "solucion": (
            "1. Revise el estado S.M.A.R.T. con CrystalDiskInfo.\n"
            "2. Desactive el servicio SysMain si el disco es HDD mecánico.\n"
            "3. Ejecute chkdsk /f /r desde WinRE o terminal elevada.\n"
            "4. Considere migrar el sistema operativo a un SSD NVMe."
        ),
        "codigo_base": 600,
        "pesos": {8: 0.90, 13: 0.85, 7: 0.65, 4: 0.45},
    },
    "Software / Sistema Operativo": {
        "descripcion": "Driver corrupto, actualización defectuosa o infección de malware.",
        "solucion": (
            "1. Inicie en Modo Seguro para aislar el problema.\n"
            "2. Desinstale las últimas actualizaciones desde el historial de Windows Update.\n"
            "3. Ejecute: sfc /scannow  y luego  DISM /Online /Cleanup-Image /RestoreHealth.\n"
            "4. Realice un análisis antimalware con Malwarebytes offline."
        ),
        "codigo_base": 700,
        "pesos": {3: 0.80, 4: 0.70, 7: 0.65, 8: 0.50, 13: 0.45},
    },
    "Adaptador de Red": {
        "descripcion": "Driver de red, cable defectuoso o configuración TCP/IP incorrecta.",
        "solucion": (
            "1. Actualice el driver del adaptador desde el gestor de dispositivos.\n"
            "2. Ejecute: netsh winsock reset  y reinicie el equipo.\n"
            "3. Pruebe con otro cable Ethernet o diferente punto de acceso Wi-Fi.\n"
            "4. Revise la configuración del router (DNS, DHCP, QoS)."
        ),
        "codigo_base": 800,
        "pesos": {14: 0.95, 7: 0.20},
    },
}


class MatrizSintomas:
    """
    Motor de correlación multivariable.
    Recibe índices de síntomas seleccionados → devuelve causas ordenadas
    por porcentaje de probabilidad relativa.
    """

    SINTOMAS = SINTOMAS_DISPONIBLES

    @staticmethod
    def calcular_probabilidades(indices: list[int]) -> list[dict]:
        """
        Parámetros
        ----------
        indices : lista de enteros (0–14) correspondientes a síntomas seleccionados.

        Retorna
        -------
        Lista de dicts ordenada desc. por 'probabilidad' (0–100).
        Cada dict tiene: causa, probabilidad, descripcion, solucion, codigo.
        """
        if not indices:
            return []

        resultados = []
        for causa, datos in _CAUSAS_RAIZ.items():
            pesos = datos["pesos"]
            score = sum(pesos.get(i, 0.0) for i in indices)
            if score == 0:
                continue
            max_posible = sum(pesos.values())
            pct = round(min((score / max_posible) * 100, 99.9), 1)
            resultados.append({
                "causa": causa,
                "probabilidad": pct,
                "descripcion": datos["descripcion"],
                "solucion": datos["solucion"],
                "codigo": datos["codigo_base"],
            })

        resultados.sort(key=lambda x: x["probabilidad"], reverse=True)
        return resultados


RAMAS_ARBOL: list[dict] = [
    {"id": 0, "icono": "⚡", "titulo": "Sin señales de encendido",
     "detalle": "No hay luces ni ventiladores al pulsar el botón."},
    {"id": 1, "icono": "🔊", "titulo": "Pantalla negra con pitidos",
     "detalle": "Enciende, pero sin imagen y la placa emite beeps."},
    {"id": 2, "icono": "🌡", "titulo": "Sobrecalentamiento del CPU",
     "detalle": "Aviso térmico al iniciar o apagados por calor."},
    {"id": 3, "icono": "🔁", "titulo": "Reinicio continuo (Boot Loop)",
     "detalle": "El equipo se reinicia una y otra vez."},
    {"id": 4, "icono": "💾", "titulo": "SSD M.2 NVMe inestable",
     "detalle": "La unidad se calienta o desaparece del sistema."},
    {"id": 5, "icono": "🐢", "titulo": "Lentitud / cuellos de botella",
     "detalle": "Enciende, pero responde lento o se congela."},
    {"id": 6, "icono": "🟦", "titulo": "Pantallas azules (RAM / XMP)",
     "detalle": "BSOD o inestabilidad general bajo carga."},
    {"id": 7, "icono": "🌐", "titulo": "Red / Internet inestable",
     "detalle": "Sin conexión, ping alto o páginas que no cargan."},
]

CATALOGO_DICTAMENES: dict[int, dict] = {
    101: {"categoria": "Fuente de Poder", "subcategoria": "Cable desconectado",
          "descripcion": "Falla de alimentación básica.",
          "solucion": "1. Desconecte el cable de poder.\n2. Reconecte firmemente en ambos extremos."},
    102: {"categoria": "Fuente de Poder", "subcategoria": "Interruptor apagado",
          "descripcion": "Interruptor principal en OFF.",
          "solucion": "1. Posicione el switch trasero en 'I'.\n2. Pruebe encender el equipo."},
    103: {"categoria": "Fuente de Poder", "subcategoria": "Falla total de PSU",
          "descripcion": "La fuente no entrega señal eléctrica.",
          "solucion": "1. Desconecte el equipo.\n2. Realice la prueba del clip (puentear PS_ON y GND).\n3. Reemplace la fuente."},
    104: {"categoria": "Fuente de Poder", "subcategoria": "Ventilador trabado",
          "descripcion": "Riesgo de sobrecalentamiento en PSU.",
          "solucion": "1. Limpie el polvo de la fuente.\n2. Si el ventilador no gira, cambie la fuente."},
    105: {"categoria": "Fuente de Poder", "subcategoria": "Voltaje inestable",
          "descripcion": "Potencia insuficiente o condensador dañado.",
          "solucion": "1. Desconecte dispositivos externos.\n2. Instale una fuente de mayor wattage."},
    106: {"categoria": "Placa Base", "subcategoria": "Falla de POST",
          "descripcion": "Fuente operativa pero placa base inactiva.",
          "solucion": "1. Realice Clear CMOS (retire pila 30 segundos).\n2. Pruebe encender solo con CPU, 1 RAM y PSU."},
    201: {"categoria": "Memoria RAM", "subcategoria": "No detectada",
          "descripcion": "Fallo de inicialización de RAM.",
          "solucion": "1. Retire la RAM y limpie contactos.\n2. Reinserte en el slot principal."},
    202: {"categoria": "Tarjeta Gráfica", "subcategoria": "No inicializada",
          "descripcion": "Falla en tarjeta gráfica o PCIe.",
          "solucion": "1. Limpie el slot PCIe.\n2. Verifique cables PCIe de alimentación."},
    203: {"categoria": "Placa Base", "subcategoria": "Cortocircuito",
          "descripcion": "Falla crítica general.",
          "solucion": "1. Inspeccione la placa buscando condensadores hinchados."},
    204: {"categoria": "Video", "subcategoria": "Sin señal",
          "descripcion": "Problema de cable o monitor.",
          "solucion": "1. Verifique cables HDMI/DisplayPort.\n2. Conecte al puerto de la placa base."},
    301: {"categoria": "Enfriamiento", "subcategoria": "Ventilador inactivo",
          "descripcion": "Falla térmica por ventilador inoperativo.",
          "solucion": "1. Verifique el conector CPU_FAN en la placa base.\n2. Reemplace el cooler."},
    302: {"categoria": "Enfriamiento", "subcategoria": "Mantenimiento térmico",
          "descripcion": "Pasta térmica degradada o seca.",
          "solucion": "1. Retire el disipador.\n2. Limpie con alcohol isopropílico y aplique pasta nueva."},
    303: {"categoria": "Placa Base", "subcategoria": "Falla de sensor",
          "descripcion": "Sensor reporta falso calor en BIOS.",
          "solucion": "1. Actualice la BIOS.\n2. Verifique la telemetría térmica."},
    401: {"categoria": "Hardware", "subcategoria": "Falla Pre-POST",
          "descripcion": "Inestabilidad eléctrica o de RAM grave.",
          "solucion": "1. Realice un Clear CMOS.\n2. Pruebe con un solo módulo de RAM."},
    402: {"categoria": "Software", "subcategoria": "Bootloader corrupto",
          "descripcion": "Cargador de arranque dañado.",
          "solucion": "1. Use USB de instalación.\n2. Ejecute bootrec /fixboot y /rebuildbcd."},
    403: {"categoria": "Software", "subcategoria": "Conflicto de SO",
          "descripcion": "Falla de driver o actualización reciente.",
          "solucion": "1. Inicie en Modo Seguro.\n2. Desinstale actualizaciones recientes."},
    501: {"categoria": "Almacenamiento", "subcategoria": "Thermal Throttling",
          "descripcion": "El SSD corta conexión por sobrecalentamiento.",
          "solucion": "1. Instale un disipador pasivo para M.2.\n2. Mejore el flujo de aire del chasis."},
    502: {"categoria": "Almacenamiento", "subcategoria": "Chequeo Preventivo",
          "descripcion": "Sin corte térmico directo detectado.",
          "solucion": "1. Use CrystalDiskInfo para evaluar la salud S.M.A.R.T."},
    601: {"categoria": "Rendimiento", "subcategoria": "Proceso parásito",
          "descripcion": "Consumo anómalo de recursos en reposo.",
          "solucion": "1. Identifique el proceso y realice un análisis antimalware."},
    602: {"categoria": "Rendimiento", "subcategoria": "Saturación I/O",
          "descripcion": "Cuello de botella de disco.",
          "solucion": "1. Desactive el servicio SysMain.\n2. Considere migrar de disco mecánico a SSD."},
    603: {"categoria": "Rendimiento", "subcategoria": "Saturación de Inicio",
          "descripcion": "Exceso de aplicaciones en arranque.",
          "solucion": "1. Abra el Administrador de Tareas y deshabilite apps de inicio innecesarias."},
    701: {"categoria": "RAM", "subcategoria": "Configuración Base",
          "descripcion": "Verificación de frecuencia base.",
          "solucion": "1. Verifique en BIOS que la velocidad coincida con la especificación de fábrica."},
    702: {"categoria": "RAM", "subcategoria": "Inestabilidad XMP/EXPO",
          "descripcion": "Perfil de overclock inestable o memoria dañada.",
          "solucion": "1. Ejecute MemTest86.\n2. Desactive o relaje el perfil XMP/EXPO en la BIOS."},
    801: {"categoria": "Adaptador de Red", "subcategoria": "Sin conectividad",
          "descripcion": "El adaptador está desconectado, deshabilitado o sin driver operativo.",
          "solucion": "1. Verifique el cable Ethernet o reconecte la red Wi-Fi.\n"
                      "2. Habilite el adaptador en 'Conexiones de red' y actualice su driver.\n"
                      "3. Ejecute: netsh winsock reset  y reinicie el equipo."},
    802: {"categoria": "Adaptador de Red", "subcategoria": "Latencia alta / pérdida de paquetes",
          "descripcion": "Conexión inestable: ping elevado, cortes o lag.",
          "solucion": "1. Pruebe por cable Ethernet para descartar interferencia Wi-Fi.\n"
                      "2. Reinicie el router y cierre descargas en segundo plano.\n"
                      "3. Actualice el driver del adaptador y revise QoS en el router."},
    803: {"categoria": "Adaptador de Red", "subcategoria": "Resolución DNS",
          "descripcion": "Hay conexión, pero los nombres de dominio no se resuelven.",
          "solucion": "1. Ejecute: ipconfig /flushdns.\n"
                      "2. Configure DNS públicos (1.1.1.1 / 8.8.8.8).\n"
                      "3. Revise proxy/VPN o extensiones que intercepten el navegador."},
}


def rama_de_codigo(codigo: int) -> int:
    """Rama del árbol a la que pertenece una hoja (1xx→0 … 8xx→7)."""
    return max(0, min(len(RAMAS_ARBOL) - 1, int(codigo) // 100 - 1))


def obtener_dictamen(codigo: int) -> dict:
    """Copia independiente del dictamen (incluye la clave 'codigo')."""
    base = CATALOGO_DICTAMENES[int(codigo)]
    return {**base, "codigo": int(codigo)}


ACCION_ARBOL   = "arbol_guiado"
ACCION_MAPA    = "mapa_2d"
ACCION_3D      = "gemelo_3d"
ACCION_REPORTE = "guardar_reporte"
ACCION_STRESS  = "stress_test"


def acciones_para(codigo: int) -> list[str]:
    """Acciones disponibles para un dictamen según el caso."""
    acciones = [ACCION_MAPA, ACCION_3D, ACCION_REPORTE, ACCION_ARBOL]
    rama = rama_de_codigo(codigo)
    if rama in (2, 5) or int(codigo) in (105, 401, 501, 702):
        acciones.append(ACCION_STRESS)
    return acciones


def _num(valor, defecto: float = 0.0) -> float:
    try:
        return float(str(valor).split()[0])
    except (TypeError, ValueError, IndexError):
        return defecto


class EvaluadorTelemetria:
    """Convierte la telemetría profunda estilo CPU-Z en evidencias específicas asociadas a códigos."""

    @staticmethod
    def evaluar(hw: dict | None) -> list[dict]:
        if not hw:
            return []
        ev: list[dict] = []

        cpu_nom = str(hw.get("nombre_cpu") or "CPU").strip()
        socket = str(hw.get("cpu_socket") or "").strip()
        tdp = str(hw.get("cpu_tdp_max_w") or "").strip()
        volt = str(hw.get("cpu_voltaje_v") or "").strip()

        uso_cpu = _num(hw.get("uso_cpu_total"))
        if uso_cpu >= 40:
            ev.append({
                "codigos": [601],
                "nivel": "warn",
                "texto": f"Uso de CPU en reposo elevado ({uso_cpu:.0f}%) en {cpu_nom} ({hw.get('nucleos_fisicos', '?')}C/{hw.get('nucleos', '?')}T).",
            })

        base, actual = _num(hw.get("frecuencia_base_ghz")), _num(hw.get("frecuencia_actual_ghz"))
        if base > 0 and 0 < actual < base * 0.55:
            extra_cpuz = " · ".join(x for x in (socket, f"Vcore {volt}" if volt and volt != "N/D" else "", f"TDP {tdp}" if tdp and tdp != "N/D" else "") if x)
            ev.append({
                "codigos": [302, 301],
                "nivel": "warn",
                "texto": f"Posible throttling/recorte de reloj en {cpu_nom}: {actual:.2f} / {base:.2f} GHz"
                         + (f" ({extra_cpuz})" if extra_cpuz else "") + ".",
            })

        # RAM: saturación, Single-Channel y velocidad SPD por debajo de la nominal (XMP/EXPO)
        ram = _num(hw.get("ram_uso_pct"))
        if ram >= 85 or hw.get("alerta_ram"):
            ev.append({
                "codigos": [702, 701, 601],
                "nivel": "warn",
                "texto": f"Memoria RAM al límite ({ram:.0f}% en uso · {hw.get('ram_disponible_mb', '?')} libres de {hw.get('ram_total_mb', '?')}).",
            })

        modulos = hw.get("ram_modulos", []) or []
        if len(modulos) == 1 and int(hw.get("ram_total_mb_int") or 0) >= 4096:
            m0 = modulos[0]
            ev.append({
                "codigos": [701],
                "nivel": "info",
                "texto": f"RAM en Single-Channel (1× {m0.get('capacidad_gb', '?')} GB {m0.get('tipo', 'DDR')} @ {m0.get('velocidad_config_mhz', m0.get('velocidad_mhz', '?'))} MHz · {m0.get('fabricante', 'OEM')}): añadir un 2.º módulo habilita Dual-Channel (+15–25% ancho de banda).",
            })

        for m in modulos:
            try:
                rated = int(m.get("velocidad_mhz") or 0)
                cfg = int(m.get("velocidad_config_mhz") or 0)
            except (TypeError, ValueError):
                rated = cfg = 0
            if rated >= 2666 and 0 < cfg < rated - 200:
                ev.append({
                    "codigos": [701],
                    "nivel": "warn",
                    "texto": f"RAM {m.get('part_number', m.get('ranura', 'DIMM'))} operando a {cfg} MHz de {rated} MHz nominales: active XMP/EXPO en BIOS {hw.get('bios_version', '')}.",
                })
                break

        # Virtualización por hardware en BIOS
        if hw.get("cpu_virtualizacion") is False:
            ev.append({
                "codigos": [603],
                "nivel": "info",
                "texto": f"Virtualización por hardware (VT-x/AMD-V) desactivada en BIOS {hw.get('mb_fabricante', '')} v{hw.get('bios_version', '?')}: limita WSL2, Docker y emuladores.",
            })

        # Almacenamiento: saturación o disco mecánico HDD
        discos = hw.get("discos_fisicos", []) or []
        modelo_d0 = str(discos[0].get("modelo", "Disco")) if discos else "Disco"
        if discos and all(str(d.get("tipo", "")).upper() == "HDD" for d in discos):
            ev.append({
                "codigos": [602, 603],
                "nivel": "warn",
                "texto": f"Sistema operando únicamente en disco mecánico HDD ({modelo_d0}): principal causa de arranques lentos y disco al 100%.",
            })

        for p in hw.get("particiones", []) or []:
            uso = _num(p.get("uso_pct"))
            if uso >= 90:
                ev.append({
                    "codigos": [602, 502],
                    "nivel": "warn",
                    "texto": f"Partición {p.get('letra', '?')} saturada ({uso:.0f}% · solo {p.get('libre_gb', '?')} GB libres en {modelo_d0}).",
                })

        # GPU y pantalla (Hz)
        gpus = hw.get("gpus", []) or []
        if str(hw.get("gpu_principal", "")).strip() in ("", "No detectada"):
            ev.append({"codigos": [202, 204], "nivel": "warn",
                       "texto": "No se detectó GPU dedicada/integrada."})
        else:
            for g in gpus:
                g_nom = str(g.get("nombre", "")).lower()
                hz = g.get("refresh_hz")
                if hz == 60 and any(k in g_nom for k in ("rtx ", "rx 6", "rx 7", "rx 8", "rx 9")):
                    ev.append({
                        "codigos": [204],
                        "nivel": "info",
                        "texto": f"GPU {g.get('nombre')} con salida configurada a 60 Hz ({g.get('resolucion', 'N/D')}): verifique en Pantalla Avanzada si su monitor soporta 120/144+ Hz.",
                    })
                    break

        # BIOS antigua (> 4 años)
        bios_fec = str(hw.get("bios_fecha", "")).strip()
        m_anio = re.search(r"(\d{4})$", bios_fec)
        if m_anio:
            anio_bios = int(m_anio.group(1))
            if 2005 <= anio_bios <= 2021:
                ev.append({
                    "codigos": [303, 701],
                    "nivel": "info",
                    "texto": f"Firmware BIOS v{hw.get('bios_version', '?')} ({bios_fec}) de {hw.get('mb_fabricante', '')} {hw.get('mb_modelo', '')} tiene más de 4 años: revisar actualizaciones AGESA/microcódigo.",
                })

        # Red
        adaptador = str(hw.get("adaptador_activo", "")).strip()
        latencia = str(hw.get("latencia_ms", "N/A"))
        if adaptador in ("", "Ninguno"):
            ev.append({"codigos": [801], "nivel": "err",
                       "texto": "No hay adaptador de red activo."})
        elif latencia.upper().startswith("N/A"):
            ev.append({"codigos": [803, 801], "nivel": "warn",
                       "texto": "La prueba de latencia/DNS no obtuvo respuesta."})
        elif _num(latencia) >= 150:
            ev.append({"codigos": [802], "nivel": "warn",
                       "texto": f"Latencia de red alta ({latencia}) en {adaptador}."})

        lic = hw.get("licencia_windows")
        if isinstance(lic, dict) and lic.get("sospecha_kms"):
            dias_txt = f" ({lic['dias_restantes']} días restantes)" if lic.get("dias_restantes") else ""
            srv_txt = f" · KMS: {lic['servidor_kms']}" if lic.get("servidor_kms") else ""
            ev.append({
                "codigos": [],
                "nivel": "warn",
                "texto": f"Licencia Windows KMS no oficial detectada{dias_txt}{srv_txt} (observación de software, no afecta salud de hardware).",
            })
        return ev

    @staticmethod
    def generar_ficha_cpuz_texto(hw: dict | None) -> str:
        """Genera un bloque técnico conciso estilo CPU-Z para enriquecer cada dictamen."""
        if not hw:
            return ""
        isa = ", ".join(hw.get("cpu_isa_flags") or []) or "N/D"
        virt_s = "Activa (BIOS)" if hw.get("cpu_virtualizacion") is True else (
            "Desactivada (BIOS)" if hw.get("cpu_virtualizacion") is False else "N/D"
        )
        modulos = hw.get("ram_modulos") or []
        spd_resumen = " / ".join(
            f"{m.get('capacidad_gb', '?')}GB {m.get('tipo', '')} {m.get('fabricante', '')} ({m.get('velocidad_config_mhz', m.get('velocidad_mhz', '?'))} MHz)"
            for m in modulos[:4]
        ) or f"{hw.get('ram_total_mb', '?')} {hw.get('ram_tipo', '')}"

        gpus = hw.get("gpus") or []
        gpu_det = (
            f"{gpus[0].get('nombre', '?')} (Driver {gpus[0].get('driver_version', '?')}"
            + (f" · {gpus[0].get('resolucion')} @ {gpus[0].get('refresh_hz')}Hz" if gpus[0].get("refresh_hz") else "")
            + ")"
            if gpus else str(hw.get("gpu_principal", "N/D"))
        )

        evidencias = EvaluadorTelemetria.evaluar(hw)
        hallazgos = "\n".join(f"  • [{e['nivel'].upper()}] {e['texto']}" for e in evidencias) if evidencias else "  • Sin anomalías de telemetría detectadas en este equipo."

        return (
            "════════════════════════════════════════════════════════════════════\n"
            "PERFIL TÉCNICO CPU-Z VERIFICADO EN ESTE EQUIPO:\n"
            f"  CPU / Codename  : {hw.get('nombre_cpu', '?')}  [{hw.get('cpu_codename', 'N/D')}]\n"
            f"  Socket / Proceso: {hw.get('cpu_socket', 'N/D')}  ·  Tech: {hw.get('cpu_tecnologia_nm', 'N/D')}  ·  Max TDP: {hw.get('cpu_tdp_max_w', 'N/D')}\n"
            f"  Relojes / Vcore : {hw.get('frecuencia_actual_mhz', '?')} MHz ({hw.get('cpu_multiplicador', 'N/D')})  ·  Bus {hw.get('cpu_bus_mhz', 100)} MHz  ·  Vcore {hw.get('cpu_voltaje_v', 'N/D')}\n"
            f"  F/M/S & Cachés  : Family {hw.get('cpu_family', '?')} / Model {hw.get('cpu_model', '?')} / Step {hw.get('cpu_stepping', '?')}  ·  L1 {hw.get('cpu_l1_cache', 'N/D')} | L2 {hw.get('cpu_l2_cache', 'N/D')} | L3 {hw.get('cpu_l3_cache', 'N/D')}\n"
            f"  Instrucciones   : {isa}\n"
            f"  Virtualización  : {virt_s}  ·  Placa/BIOS: {hw.get('mb_fabricante', '?')} {hw.get('mb_modelo', '?')} (v{hw.get('bios_version', '?')} · {hw.get('bios_fecha', '?')})\n"
            f"  Memoria SPD     : {hw.get('ram_total_mb', '?')} [{hw.get('ram_canal_modo', 'N/D')}] — {spd_resumen}\n"
            f"  Gráficos        : {gpu_det}\n"
            "HALLAZGOS ESPECÍFICOS DETECTADOS EN TU HARDWARE:\n"
            f"{hallazgos}"
        )

    @staticmethod
    def codigos_respaldados(evidencias: list[dict]) -> set[int]:
        return {c for e in evidencias for c in e["codigos"]}


_CORPUS: dict[int, list[str]] = {
    101: ["cable", "cable poder", "cable energia", "enchufe", "tomacorriente", "suelto",
          "desconectado", "no enciende"],
    102: ["interruptor", "switch fuente", "boton trasero", "off", "interruptor fuente", "no enciende"],
    103: ["no enciende", "sin luces", "sin ventiladores", "muerta", "fuente quemada", "no energia",
          "nada", "psu", "fuente"],
    104: ["ventilador fuente", "psu ventilador", "trabado", "olor quemado", "fuente ruido",
          "fuente caliente", "a veces enciende"],
    105: ["apagado", "apagados bruscos", "corte energia", "voltaje", "intermitente", "aleatoriamente",
          "watts", "fuente insuficiente", "apagado solo", "enciende a veces"],
    106: ["no post", "ventiladores giran", "luces encendidas", "placa no arranca", "clear cmos",
          "no arranca", "enciende sin imagen"],
    201: ["pitidos cortos", "pitido corto", "pitido repetitivo", "ram no detectada", "pitido memoria",
          "pitido"],
    202: ["pitido largo", "largo cortos", "grafica no inicializa", "gpu pitido", "pcie",
          "tarjeta grafica no detectada", "gpu no detectada", "artefactos", "grafica", "gpu"],
    203: ["tono continuo", "pitido continuo", "cortocircuito", "condensador", "condensador hinchado",
          "placa quemada"],
    204: ["pantalla negra", "sin senal", "monitor", "hdmi", "displayport", "no imagen",
          "sin video", "monitor negro", "cable video"],
    301: ["ventilador cpu", "cooler", "cpu fan", "ventilador procesador", "ventilador no gira",
          "cooler detenido", "ventilador ruido"],
    302: ["temperatura", "temperatura alta", "pasta termica", "disipador", "temperatura cpu",
          "sobrecalentamiento", "mantenimiento termico", "throttling cpu", "ventilador ruido"],
    303: ["sensor", "sensor temperatura", "falso", "lectura erronea", "bios temperatura",
          "aviso falso"],
    401: ["reinicio antes logo", "antes bios", "pre post", "reinicio bios", "boot loop",
          "reinicio bucle", "reinicio"],
    402: ["bootloader", "bootrec", "bcd", "no carga windows", "arranque danado",
          "reinicio sin logo", "boot"],
    403: ["logo windows", "reinicio windows", "actualizacion", "driver", "modo seguro",
          "conflicto", "windows update", "reinicio"],
    501: ["ssd desaparece", "nvme desaparece", "ssd desconecta", "nvme", "m2", "ssd temperatura",
          "disco desaparece", "ssd throttling", "ssd"],
    502: ["smart", "crystaldiskinfo", "salud disco", "estado disco", "sectores", "chequeo disco",
          "disco duro ruido", "archivo corrupto", "chkdsk"],
    601: ["proceso", "cpu 100", "cpu alto", "malware", "virus", "consumo cpu", "uso cpu",
          "lento", "procesador 100"],
    602: ["disco 100", "disco saturado", "sysmain", "hdd lento", "disco lento", "cuello botella",
          "disco lleno", "almacenamiento lleno", "lento"],
    603: ["inicio lento", "arranque lento", "aplicaciones inicio", "programas inicio", "startup",
          "tarda iniciar", "tarda encender"],
    701: ["frecuencia ram", "velocidad ram", "ram lenta", "mhz", "configuracion ram", "ram"],
    702: ["pantalla azul", "bsod", "xmp", "expo", "memtest", "irql", "ram inestable", "pantallazo",
          "juegos", "crash", "memoria", "ram"],
    801: ["sin internet", "sin conexion", "red desconectada", "adaptador red", "wifi no conecta",
          "ethernet", "cable red", "internet", "red"],
    802: ["ping", "ping alto", "latencia", "lag", "perdida paquetes", "internet lento",
          "cortes internet", "red inestable", "wifi lento", "internet", "red"],
    803: ["dns", "paginas no cargan", "navegador", "sitios no abren", "dns error", "internet"],
}

_SINONIMOS: dict[str, str] = {
    "prende": "enciende", "prender": "enciende", "encender": "enciende", "enciendo": "enciende",
    "encendido": "enciende", "arrancar": "arranca", "inicia": "arranca",
    "beep": "pitido", "beeps": "pitido", "bip": "pitido", "bips": "pitido", "pitazo": "pitido",
    "pita": "pitido", "suena": "pitido", "pitidos": "pitido",
    "calienta": "temperatura", "caliente": "temperatura", "calor": "temperatura",
    "sobrecalienta": "sobrecalentamiento", "temp": "temperatura", "termico": "temperatura",
    "reinicia": "reinicio", "reinicios": "reinicio", "reiniciando": "reinicio", "reboot": "reinicio",
    "reinici": "reinicio", "bucle": "boot loop", "bootloop": "boot loop", "loop": "boot loop",
    "lenta": "lento", "lentitud": "lento", "congela": "lento", "congelado": "lento",
    "traba": "lento", "trabada": "lento", "pesada": "lento",
    "apaga": "apagado", "apago": "apagado", "apagones": "apagado",
    "pantallazo": "pantalla azul", "pantallazos": "pantalla azul", "azul": "pantalla azul",
    "bluescreen": "bsod",
    "wifi": "wifi", "wi": "wifi", "internet": "internet", "conexion": "conexion",
    "lag": "lag", "lagea": "lag", "laggea": "lag",
    "grafica": "grafica", "video": "video", "gpu": "gpu", "nvidia": "gpu", "radeon": "gpu",
    "ventilador": "ventilador", "fan": "ventilador", "abanico": "ventilador",
    "memoria": "memoria", "memorias": "memoria", "ram": "ram",
    "m.2": "m2", "nvme": "nvme", "solido": "ssd",
    "hdd": "disco", "duro": "disco", "discos": "disco", "unidad": "disco",
    "virus": "virus", "malware": "malware",
    "señal": "senal", "imagen": "imagen", "negra": "negra", "oscura": "negra",
}

_STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al", "a", "y", "o", "u",
    "en", "con", "por", "para", "que", "se", "me", "mi", "mis", "su", "sus", "es", "esta", "estan",
    "muy", "mucho", "mucha", "cuando", "como", "pero", "lo", "le", "les", "ya", "hay", "tiene",
    "tengo", "hace", "hacen", "pc", "computadora", "ordenador", "equipo", "laptop", "maquina",
    "sola", "solo", "veces", "vez", "rato", "despues", "luego", "durante", "mientras", "todo",
    "toda", "sistema", "problema", "cada", "siempre", "este", "eso", "esto", "estoy", "ser",
    "sale", "salen", "aparece", "aparecen", "da", "dan", "queda", "quedo",
}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto).lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.replace("%", " ").replace("m.2", "m2")
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def _raiz(token: str) -> str:
    """Stemming ligero en español: quita plurales y sufijos frecuentes."""
    for suf in ("amiento", "imiento", "mente", "aciones", "acion", "ando", "iendo",
                "ados", "idos", "adas", "idas", "ado", "ido", "ada", "ida"):
        if len(token) - len(suf) >= 4 and token.endswith(suf):
            return token[: -len(suf)]
    if len(token) > 4 and token.endswith("es"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def _tokens(texto: str) -> list[str]:
    salida: list[str] = []
    for tok in _normalizar(texto).split():
        canon = _SINONIMOS.get(tok, tok)
        for t in canon.split():
            if t not in _STOPWORDS:
                salida.append(t)
    return salida


def _coincide(tok_term: str, raices_usuario: dict[str, str]) -> str | None:
    """Devuelve el token del usuario que coincide con un token del término."""
    r = _raiz(tok_term)
    for tok_u, r_u in raices_usuario.items():
        if r == r_u or tok_term == tok_u:
            return tok_u
        largo = min(len(r), len(r_u))
        if largo >= 5 and (r.startswith(r_u) or r_u.startswith(r)):
            return tok_u
        if largo >= 5 and difflib.SequenceMatcher(None, r, r_u).ratio() >= 0.86:
            return tok_u
    return None


class BuscadorAsistido:
    """
    Búsqueda en lenguaje natural sobre TODAS las hojas del árbol de diagnóstico.

    Algoritmo (determinista y explicable):
      1. Normaliza (minúsculas, sin tildes), aplica sinónimos y elimina stopwords.
      2. Para cada hoja suma el peso de sus términos encontrados: una frase de
         n tokens pesa n (más específica = más evidencia). Coincidencias por
         raíz, prefijo o similitud ≥ 0.86 (errores de tipeo).
      3. Score = 0.55·cobertura de la consulta + 0.45·fuerza de la evidencia,
         + bonus si la telemetría real respalda la hoja.
    """

    UMBRAL_MIN = 0.12
    BONUS_TELEMETRIA = 0.08

    @staticmethod
    def buscar(texto_usuario: str, top_n: int = 5, hw: dict | None = None) -> list[dict]:
        """
        Retorna una lista ordenada de dicts con: causa, categoria, subcategoria,
        codigo, rama_id, score (0–1), confianza_pct, terminos, respaldo_telemetria.
        """
        tokens = _tokens(texto_usuario or "")
        if not tokens or len(_normalizar(texto_usuario)) < 2:
            return []
        raices = {t: _raiz(t) for t in dict.fromkeys(tokens)}
        respaldados = EvaluadorTelemetria.codigos_respaldados(EvaluadorTelemetria.evaluar(hw))

        resultados = []
        for codigo, terminos in _CORPUS.items():
            peso, cubiertos, encontrados = 0.0, set(), []
            for termino in terminos:
                partes = termino.split()
                hits = [_coincide(p, raices) for p in partes]
                if all(hits):
                    peso += len(partes)
                    cubiertos.update(hits)
                    encontrados.append(termino)
            if peso == 0:
                continue
            cobertura = len(cubiertos) / len(raices)
            fuerza = min(1.0, peso / 4.0)
            score = 0.55 * cobertura + 0.45 * fuerza
            respaldo = codigo in respaldados
            if respaldo:
                score += BuscadorAsistido.BONUS_TELEMETRIA
            if score < BuscadorAsistido.UMBRAL_MIN:
                continue
            d = CATALOGO_DICTAMENES[codigo]
            resultados.append({
                "causa": f"{d['categoria']} — {d['subcategoria']}",
                "categoria": d["categoria"],
                "subcategoria": d["subcategoria"],
                "codigo": codigo,
                "rama_id": rama_de_codigo(codigo),
                "score": round(min(score, 0.99), 3),
                "confianza_pct": round(min(score, 0.99) * 100, 1),
                "terminos": encontrados,
                "respaldo_telemetria": respaldo,
                "_peso": peso,
            })

        resultados.sort(key=lambda r: (r["score"], r["_peso"], -r["codigo"]), reverse=True)
        for r in resultados:
            r.pop("_peso", None)
        return resultados[:top_n]

    @staticmethod
    def diagnosticar(texto_usuario: str, hw: dict | None = None, codigo: int | None = None) -> dict | None:
        """
        Ejecuta el diagnóstico de forma directa: resuelve la hoja del árbol
        (la mejor coincidencia o `codigo` si se fuerza), adjunta el dictamen
        completo, la evidencia de telemetría y las acciones disponibles.
        """
        resultados = BuscadorAsistido.buscar(texto_usuario, top_n=5, hw=hw)
        if codigo is None:
            if not resultados:
                return None
            elegido = resultados[0]
        else:
            elegido = next((r for r in resultados if r["codigo"] == codigo), None)
            if elegido is None:
                d = CATALOGO_DICTAMENES[int(codigo)]
                elegido = {"causa": f"{d['categoria']} — {d['subcategoria']}",
                           "categoria": d["categoria"], "subcategoria": d["subcategoria"],
                           "codigo": int(codigo), "rama_id": rama_de_codigo(codigo),
                           "score": 0.0, "confianza_pct": 0.0, "terminos": [],
                           "respaldo_telemetria": False}
        evidencias = EvaluadorTelemetria.evaluar(hw)
        relacionadas = [e for e in evidencias if elegido["codigo"] in e["codigos"]]
        return {
            "consulta": texto_usuario,
            "resultado": elegido,
            "alternativas": [r for r in resultados if r["codigo"] != elegido["codigo"]][:4],
            "dictamen": obtener_dictamen(elegido["codigo"]),
            "rama_id": elegido["rama_id"],
            "evidencias": relacionadas,
            "evidencias_globales": evidencias,
            "acciones": acciones_para(elegido["codigo"]),
        }


_WORKER_SRC = r"""
import math, sys, time
dur = float(sys.argv[1]); duty = float(sys.argv[2])
fin = time.perf_counter() + dur
ops = 0; acc = 1.0; ultimo = 0.0; tramo = 0.05
try:
    while True:
        ahora = time.perf_counter()
        if ahora >= fin:
            break
        ocupado = ahora + tramo * duty
        while time.perf_counter() < ocupado:
            for _ in range(2000):
                acc = math.sqrt(acc * 999983.0 + 1.777777) % 1000000.0
            ops += 2000
        time.sleep(tramo * (1.0 - duty))
        if ahora - ultimo >= 0.2:
            print(ops, flush=True); ultimo = ahora
    print(ops, flush=True)
except (BrokenPipeError, OSError, KeyboardInterrupt):
    pass
"""


class MicroStressTest:
    """
    Benchmark de CPU acotado, seguro y cancelable.

    • Orquestación en un hilo `threading` → la GUI nunca se bloquea.
    • Carga en procesos ligeros (sólo stdlib) con prioridad BAJA y ciclo de
      trabajo del 85 %, dejando un núcleo lógico libre para el sistema. Si no
      se pueden crear procesos (p. ej. ejecutable congelado) usa hilos.
    • Cada worker tiene su propio deadline; además el orquestador los termina
      al finalizar, al cancelar o ante una condición de seguridad.
    • Paradas de seguridad: caída de rendimiento crítica sostenida, RAM libre
      < 5 % o temperatura ≥ 95 °C (si el SO expone sensores).
    • Throttling: caída de frecuencia reportada y/o caída sostenida del
      rendimiento real (ops/s), que es fiable aunque Windows reporte una
      frecuencia fija.
    """

    DURACION_SEG: int = 10
    DURACION_MAX_SEG: int = 30
    THROTTLE_UMBRAL_PCT: float = 15.0
    INTERVALO_MUESTREO: float = 0.5
    DUTY_CYCLE: float = 0.90
    MAX_WORKERS: int = 128
    CAIDA_CRITICA_PCT: float = 55.0
    RAM_MIN_LIBRE_PCT: float = 4.0
    TEMP_MAX_C: float = 95.0

    def __init__(
        self,
        callback_progreso: Callable[[str], None],
        callback_resultado: Callable[[dict], None],
        callback_muestra: Callable[[dict], None] | None = None,
        duracion_seg: float | None = None,
        modo: str = "auto",
        duty_cycle: float | None = None,
        max_workers: int | None = None,
        cpu_nombre: str | None = None,
    ):
        """
        callback_progreso(mensaje) : línea de log legible.
        callback_resultado(dict)   : análisis final (o {'error': …}).
        callback_muestra(dict)     : muestra estructurada para gráficos en vivo.
        modo                       : 'auto' | 'procesos' | 'hilos'.
        """
        self._cb_prog = self._aislar(callback_progreso)
        self._cb_res = callback_resultado or (lambda r: None)
        self._cb_muestra = self._aislar(callback_muestra)
        self.duracion = max(1.0, min(float(duracion_seg or self.DURACION_SEG), self.DURACION_MAX_SEG))
        self.modo = modo
        self.duty = max(0.2, min(float(duty_cycle or self.DUTY_CYCLE), 0.96))
        self.n_logicos = psutil.cpu_count(logical=True) or 2
        self.n_fisicos = psutil.cpu_count(logical=False) or max(1, self.n_logicos // 2)
        if max_workers is not None:
            self.n_workers = max(1, min(int(max_workers), self.MAX_WORKERS))
        else:
            self.n_workers = max(1, min(self.n_logicos, self.MAX_WORKERS))
        self.cpu_nombre = (cpu_nombre or "").strip() or "Procesador Detectado"
        self._activo = False
        self._stop = threading.Event()
        self._hilo: threading.Thread | None = None
        self._procs: list[subprocess.Popen] = []
        self._hilos_carga: list[threading.Thread] = []
        self._ops: list[int] = []
        self.modo_efectivo: str | None = None
        self.resultado: dict | None = None

    @staticmethod
    def _aislar(cb):
        """Envuelve un callback para que un error de la UI no aborte el benchmark."""
        if cb is None:
            return lambda *_: None

        def _seguro(*args):
            try:
                cb(*args)
            except Exception as exc:
                print(f"[MicroStressTest] callback ignorado: {type(exc).__name__}: {exc}")

        return _seguro

    @property
    def activo(self) -> bool:
        return self._activo

    def iniciar(self) -> bool:
        """Lanza el test en un hilo daemon. Devuelve False si ya corría."""
        if self._activo:
            return False
        self._activo = True
        self._stop.clear()
        self.resultado = None
        self._hilo = threading.Thread(target=self._run, name="micro-stress", daemon=True)
        self._hilo.start()
        return True

    def cancelar(self) -> None:
        """Cancelación segura: detiene muestreo y termina los workers."""
        self._stop.set()
        self._detener_workers()

    def esperar(self, timeout: float | None = None) -> bool:
        """Bloquea hasta que el test termine (uso en pruebas). True si terminó."""
        if self._hilo is None:
            return True
        self._hilo.join(timeout)
        return not self._hilo.is_alive()

    @staticmethod
    def _worker_cpu() -> float:
        """Compatibilidad: carga matemática corta en el hilo actual."""
        fin = time.time() + 0.05
        acum = 1.0
        while time.time() < fin:
            acum = math.sqrt(acum * 999_983.0 + 1.777_777) % 1_000_000.0
        return acum

    def _lanzar_procesos(self) -> None:
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS
        dur = f"{self.duracion + 0.5:.2f}"
        for i in range(self.n_workers):
            p = subprocess.Popen(
                [sys.executable, "-c", _WORKER_SRC, dur, f"{self.duty:.2f}"],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, bufsize=1, creationflags=flags,
            )
            self._procs.append(p)
            if sys.platform != "win32":
                try:
                    psutil.Process(p.pid).nice(10)
                except Exception:
                    pass
            threading.Thread(target=self._leer_worker, args=(i, p), daemon=True).start()

    def _leer_worker(self, idx: int, proc: subprocess.Popen) -> None:
        try:
            for linea in proc.stdout:
                try:
                    self._ops[idx] = int(linea.strip())
                except ValueError:
                    pass
        except Exception:
            pass

    def _lanzar_hilos(self) -> None:
        """
        Kernel multihilo nativo en C (hashlib.pbkdf2_hmac SHA-256 + FPU float).
        pbkdf2_hmac libera el GIL de Python (Py_BEGIN_ALLOW_THREADS), por lo que
        todos los núcleos/hilos lógicos de cualquier procesador (Intel, AMD, ARM)
        trabajan en paralelo real al ~90%+ sin necesidad de crear subprocesos
        externos ni sufrir retrasos de tuberías stdout, tanto en .py como en .exe.
        """
        import hashlib

        fin = time.perf_counter() + self.duracion + 0.5
        tramo = 0.040
        t_activo = tramo * self.duty
        t_pausa = max(0.001, tramo * (1.0 - self.duty))
        payload = b"IndiServ-Analytica-CPU-Stress-Vector-Benchmark"

        def _carga(idx: int):
            salt = f"core-{idx}".encode("ascii")
            acc = 1.0 + idx * 0.1
            while not self._stop.is_set() and time.perf_counter() < fin:
                t_ini = time.perf_counter()
                while (time.perf_counter() - t_ini) < t_activo and not self._stop.is_set():
                    hashlib.pbkdf2_hmac("sha256", payload, salt, 6000)
                    acc = math.sqrt(acc * 999_983.0 + 1.777_777) % 1_000_000.0
                    self._ops[idx] += 6000
                if self._stop.wait(t_pausa):
                    break

        self._hilos_carga.clear()
        for i in range(self.n_workers):
            h = threading.Thread(target=_carga, args=(i,), name=f"stress-{i}", daemon=True)
            self._hilos_carga.append(h)
            h.start()

    def _detener_workers(self) -> None:
        for p in list(self._procs):
            try:
                if p.poll() is None:
                    p.terminate()
            except Exception:
                pass
        for p in list(self._procs):
            try:
                p.wait(timeout=1.5)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        self._procs.clear()

    def workers_vivos(self) -> int:
        vivos = sum(1 for p in self._procs if p.poll() is None)
        return vivos + sum(1 for h in self._hilos_carga if h.is_alive())

    @staticmethod
    def _leer_temperatura() -> float | None:
        lector = getattr(psutil, "sensors_temperatures", None)
        if lector is None:
            return None
        try:
            lecturas = [t.current for grupo in (lector() or {}).values() for t in grupo if t.current]
            return max(lecturas) if lecturas else None
        except Exception:
            return None

    def _run(self) -> None:
        resultado: dict
        muestras_freq: list[float] = []
        muestras_uso: list[float] = []
        muestras_ops: list[float] = []
        motivo: str | None = None
        try:
            self._ops = [0] * self.n_workers
            if self.modo == "procesos" and not getattr(sys, "frozen", False):
                try:
                    self._lanzar_procesos()
                    self.modo_efectivo = "procesos"
                except Exception:
                    self._detener_workers()
                    self._lanzar_hilos()
                    self.modo_efectivo = "nativo-multihilo"
            else:
                self._lanzar_hilos()
                self.modo_efectivo = "nativo-multihilo"

            self._cb_prog(
                f"[CPU] {self.cpu_nombre} ({self.n_fisicos}C/{self.n_logicos}T)\n"
                f"[INICIO] {self.n_workers} hilos activos (kernel C SHA256+FPU sin GIL, "
                f"objetivo ~{self.duty * 100:.0f}% carga) · {self.duracion:.0f} s\n"
                + "─" * 64 + "\n"
            )

            psutil.cpu_percent(interval=None)
            self._stop.wait(0.12)
            psutil.cpu_percent(interval=None)

            t0 = time.perf_counter()
            t_prev, ops_prev = t0, sum(self._ops)
            criticas_consecutivas = 0
            variacion_consecutiva = 0
            base_samples: list[float] = []
            base_thr = 0.0
            thr_suavizado = 0.0

            while not self._stop.is_set():
                if self._stop.wait(self.INTERVALO_MUESTREO):
                    break
                ahora = time.perf_counter()
                elapsed = ahora - t0
                ops_tot = sum(self._ops)
                dt = max(ahora - t_prev, 1e-6)
                thr_raw = max(0.0, (ops_tot - ops_prev) / dt / 1e6)
                t_prev, ops_prev = ahora, ops_tot

                thr_suavizado = thr_raw if thr_suavizado <= 0.0 else (0.65 * thr_raw + 0.35 * thr_suavizado)

                freq = psutil.cpu_freq()
                f_mhz = float(freq.current) if freq and freq.current else 0.0
                if f_mhz <= 0.0 and freq and freq.max:
                    f_mhz = float(freq.max)
                uso = float(psutil.cpu_percent(interval=None))
                ram_libre = 100.0 - float(psutil.virtual_memory().percent)
                temp = self._leer_temperatura()

                muestras_freq.append(f_mhz)
                muestras_uso.append(uso)
                muestras_ops.append(round(thr_suavizado, 3))

                n_m = len(muestras_ops)
                if 2 <= n_m <= 4 and thr_suavizado > 0:
                    base_samples.append(thr_suavizado)
                    base_thr = sum(base_samples) / len(base_samples)
                elif n_m == 1 and thr_suavizado > 0:
                    base_thr = thr_suavizado

                caida = 0.0
                if n_m >= 3 and base_thr > 0:
                    caida = max(0.0, (base_thr - thr_suavizado) / base_thr * 100.0)

                if n_m == 1:
                    estado = "CARGANDO"
                else:
                    if caida >= self.THROTTLE_UMBRAL_PCT:
                        variacion_consecutiva += 1
                    else:
                        variacion_consecutiva = 0

                    if variacion_consecutiva >= 2:
                        estado = "THROTTLING"
                    elif uso >= 82.0:
                        estado = "ÓPTIMO 90%+"
                    else:
                        estado = "ESTABLE"

                    if caida >= self.CAIDA_CRITICA_PCT:
                        criticas_consecutivas += 1
                    else:
                        criticas_consecutivas = 0

                    if criticas_consecutivas >= 4:
                        motivo = f"caída severa sostenida de potencia ({caida:.0f}%)"

                if ram_libre < self.RAM_MIN_LIBRE_PCT:
                    motivo = f"RAM libre crítica ({ram_libre:.1f}%)"
                if temp is not None and temp >= self.TEMP_MAX_C:
                    motivo = f"temperatura crítica ({temp:.0f} °C)"

                progreso = min(1.0, elapsed / self.duracion)
                self._cb_muestra({
                    "t": round(elapsed, 2),
                    "progreso": progreso,
                    "freq_mhz": f_mhz,
                    "uso_pct": uso,
                    "mops": round(thr_suavizado, 2),
                    "ram_libre_pct": round(ram_libre, 1),
                    "temp_c": temp,
                    "estado": estado,
                    "caida_pct": round(caida, 1),
                    "workers": self.workers_vivos(),
                })
                self._cb_prog(
                    f"  {elapsed:4.1f}s │ {f_mhz / 1000:4.2f} GHz │ CPU {uso:5.1f}% │ "
                    f"{thr_suavizado:6.2f} Mops/s │ RAM libre {ram_libre:4.1f}% │ {estado}\n"
                )

                if motivo:
                    self._cb_prog(f"\n[GUARDIA DE SEGURIDAD] Prueba detenida: {motivo}.\n")
                    break
                if elapsed >= self.duracion:
                    break

            cancelado = self._stop.is_set() and motivo is None
            self._stop.set()
            self._detener_workers()
            for h in list(self._hilos_carga):
                try:
                    h.join(timeout=0.4)
                except Exception:
                    pass
            self._hilos_carga.clear()

            resultado = self._analizar(muestras_freq, muestras_uso, muestras_ops)
            resultado.update({
                "cancelado": cancelado,
                "detenido_por_seguridad": motivo is not None,
                "motivo_parada": motivo,
                "modo": self.modo_efectivo,
                "workers": self.n_workers,
                "cpu_nombre": self.cpu_nombre,
                "duracion_objetivo_s": self.duracion,
            })
            if cancelado:
                resultado["diagnostico"] = "⏹  TEST CANCELADO POR EL OPERADOR\n" + resultado.get("diagnostico", "")
        except Exception as exc:
            self._stop.set()
            self._detener_workers()
            self._hilos_carga.clear()
            resultado = {"error": f"{type(exc).__name__}: {exc}", "cancelado": False,
                         "n_muestras": len(muestras_ops)}
        finally:
            self._activo = False
        self.resultado = resultado
        self._cb_resultado_seguro(resultado)

    def _cb_resultado_seguro(self, resultado: dict) -> None:
        try:
            self._cb_res(resultado)
        except Exception as exc:
            print(f"[MicroStressTest] Error en callback_resultado: {exc}")

    @staticmethod
    def _barra_progreso(elapsed: float, total: float, ancho: int = 20) -> str:
        relleno = int((min(elapsed, total) / total) * ancho)
        return "█" * relleno + "░" * (ancho - relleno)

    @staticmethod
    def _caida_sostenida(serie: list[float]) -> float:
        """% de caída entre el primer y el último cuartil de la serie."""
        datos = [v for v in serie if v > 0]
        if len(datos) < 2:
            return 0.0
        k = max(1, len(datos) // 4)
        ini = sum(datos[:k]) / k
        fin = sum(datos[-k:]) / k
        return max(0.0, (ini - fin) / ini * 100) if ini > 0 else 0.0

    def _analizar(self, muestras_freq: list[float], muestras_uso: list[float],
                  muestras_ops: list[float] | None = None) -> dict:
        muestras_ops = list(muestras_ops or [])
        if not muestras_freq and not muestras_ops:
            return {"error": "Sin muestras de frecuencia disponibles."}

        freqs = [f for f in muestras_freq if f > 0]
        freq_max = max(freqs) if freqs else 0.0
        freq_min = min(freqs) if freqs else 0.0
        freq_avg = sum(freqs) / len(freqs) if freqs else 0.0
        uso_max = max(muestras_uso) if muestras_uso else 0.0
        uso_avg = sum(muestras_uso) / len(muestras_uso) if muestras_uso else 0.0

        caida_pct = ((freq_max - freq_min) / freq_max * 100) if freq_max > 0 else 0.0
        caida_freq_sost = self._caida_sostenida(freqs)

        ops_utiles = muestras_ops[2:] if len(muestras_ops) > 4 else muestras_ops
        thr_avg = sum(ops_utiles) / len(ops_utiles) if ops_utiles else 0.0
        thr_max = max(ops_utiles) if ops_utiles else 0.0
        caida_thr = self._caida_sostenida(ops_utiles)

        u = self.THROTTLE_UMBRAL_PCT
        throttling_freq = caida_pct >= u and caida_freq_sost >= u / 2
        throttling_thr = len(ops_utiles) >= 4 and caida_thr >= u
        throttling = throttling_freq or throttling_thr

        if throttling:
            nivel = "err" if max(caida_pct, caida_thr) >= 25 else "warn"
            fuente = []
            if throttling_freq:
                fuente.append(f"frecuencia −{caida_pct:.1f}% ({freq_max / 1000:.2f} → {freq_min / 1000:.2f} GHz)")
            if throttling_thr:
                fuente.append(f"rendimiento sostenido −{caida_thr:.1f}%")
            diagnostico = (
                "⚠  THERMAL THROTTLING DETECTADO\n"
                f"   Evidencia: {'; '.join(fuente)}.\n"
                "   El procesador redujo su velocidad bajo carga sostenida (calor o límite de potencia).\n\n"
                "ACCIONES RECOMENDADAS:\n"
                "  1. Reemplace la pasta térmica del CPU.\n"
                "  2. Limpie el disipador y los filtros de polvo.\n"
                "  3. Mejore el flujo de aire del chasis.\n"
                "  4. Considere un cooler de mayor capacidad."
            )
        else:
            nivel = "ok"
            diagnostico = (
                "✅  RENDIMIENTO ESTABLE — Sin throttling detectado\n"
                f"   Variación de frecuencia: {caida_pct:.1f}% · rendimiento sostenido: −{caida_thr:.1f}% "
                f"(umbral: {u}%)\n"
                "   El enfriamiento del CPU es adecuado para carga sostenida.\n\n"
                "OBSERVACIONES:\n"
                f"  • Freq. máxima alcanzada: {freq_max / 1000:.2f} GHz\n"
                f"  • Freq. mínima durante test: {freq_min / 1000:.2f} GHz\n"
                f"  • Uso CPU promedio: {uso_avg:.1f}%"
            )

        return {
            "throttling": throttling,
            "nivel": nivel,
            "freq_max_ghz": round(freq_max / 1000, 3),
            "freq_min_ghz": round(freq_min / 1000, 3),
            "freq_avg_ghz": round(freq_avg / 1000, 3),
            "caida_pct": round(caida_pct, 1),
            "caida_freq_sostenida_pct": round(caida_freq_sost, 1),
            "caida_rendimiento_pct": round(caida_thr, 1),
            "rendimiento_avg_mops": round(thr_avg, 2),
            "rendimiento_max_mops": round(thr_max, 2),
            "indice_rendimiento": int(round(thr_avg * 100)),
            "uso_max_pct": round(uso_max, 1),
            "uso_avg_pct": round(uso_avg, 1),
            "n_muestras": max(len(muestras_freq), len(muestras_ops)),
            "diagnostico": diagnostico,
        }
