"""
core/diagnostico.py — Motor Inferencial Adaptativo (Fase 2)
===========================================================
Módulo ampliado con tres capacidades nuevas:

  1. MotorDiagnostico  — árbol lineal original (preservado sin cambios)
  2. MatrizSintomas    — correlación multivariable ponderada entre síntomas
                         y causas raíz (porcentaje de probabilidad)
  3. BuscadorAsistido  — fuzzy matching sobre corpus de términos técnicos
                         usando difflib (stdlib, sin dependencias externas)
  4. MicroStressTest   — benchmark CPU multihilo (10 s) con muestreo de
                         frecuencias en tiempo real para detectar thermal
                         throttling
"""

from __future__ import annotations

import math
import time
import difflib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import psutil


# =============================================================================
# 1. MOTOR DIAGNÓSTICO ORIGINAL (preservado sin cambios)
# =============================================================================
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


# =============================================================================
# 2. MATRIZ PONDERADA DE SÍNTOMAS
# =============================================================================

# Lista canónica de síntomas seleccionables por el operador.
# El índice de cada ítem es su ID en el sistema de pesos.
SINTOMAS_DISPONIBLES: list[str] = [
    "La PC no da señal de encendido (sin luces ni ventiladores)",   # 0
    "Pantalla negra al encender (sin imagen en monitor)",            # 1
    "Pitidos durante el POST al iniciar el equipo",                  # 2
    "Pantallas azules (BSOD) frecuentes o aleatorias",              # 3
    "Reinicios aleatorios o arranque en bucle (Boot Loop)",          # 4
    "Temperatura de CPU muy alta / aviso de sobrecalentamiento",     # 5
    "Ventilador de CPU inactivo, trabado o excesivamente ruidoso",   # 6
    "Sistema extremadamente lento o congelado",                      # 7
    "Disco duro / SSD al 100% de uso de forma constante",           # 8
    "Memoria RAM al límite o uso de memoria anormalmente alto",      # 9
    "GPU no detectada, pantalla con artefactos o parpadeos",         # 10
    "Sin señal de video aunque el equipo intenta arrancar",          # 11
    "Apagados bruscos o cortes de energía sin previo aviso",         # 12
    "Errores al leer archivos o datos corruptos en disco",           # 13
    "Conexión de red inestable, pérdida de paquetes o ping alto",    # 14
]

# Mapa de causas raíz con pesos por síntoma.
# Peso 0.0–1.0: cuánta evidencia aporta ese síntoma a esta causa.
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
            # Score bruto: suma de pesos de síntomas que coinciden
            score = sum(pesos.get(i, 0.0) for i in indices)
            if score == 0:
                continue
            # Máximo teórico: si se hubieran seleccionado TODOS los síntomas de esta causa
            max_posible = sum(pesos.values())
            # Probabilidad = qué porcentaje del máximo teórico se alcanzó
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


# =============================================================================
# 3. BUSCADOR ASISTIDO / PREDICTIVO (FUZZY MATCHING)
# =============================================================================

# Corpus de búsqueda: (keywords_en_minúsculas, causa_raíz, rama_árbol_id)
# rama_árbol_id → 0-6 corresponden a las ramas del árbol lineal en main.py
_CORPUS: list[tuple[str, str, int | None]] = [
    # Fuente de Poder
    ("no enciende no arranca sin luz sin energia apagado",              "Fuente de Poder (PSU)", 0),
    ("apagado brusco corte voltaje psu fuente watt amperaje",          "Fuente de Poder (PSU)", 0),
    ("ventilador fuente no gira ruido psu fan",                        "Fuente de Poder (PSU)", 0),
    # Placa Base
    ("pitido bip beep post bios placa sonido error arranque",          "Placa Base", 1),
    ("reinicio continuo bucle boot loop cmos bios",                    "Placa Base", 3),
    ("condensador quemado placa base pcb cortocircuito",               "Placa Base", 1),
    # Memoria RAM
    ("ram memoria modulo dimm xmp expo frecuencia inestable slot",     "Memoria RAM", 6),
    ("bsod pantallazo azul crash kernel error dump memoria",           "Memoria RAM", 6),
    ("pantalla azul reinicio automatico error irql not less equal",    "Memoria RAM", 6),
    # CPU / Enfriamiento
    ("calor temperatura sobrecalentamiento termal throttling cpu",     "CPU / Enfriamiento Térmico", 2),
    ("ventilador cpu cooler ruido inactivo disipador pasta termica",   "CPU / Enfriamiento Térmico", 2),
    ("throttle frecuencia baja rendimiento caida procesador",          "CPU / Enfriamiento Térmico", 2),
    # GPU
    ("gpu grafica tarjeta nvidia amd artefacto parpadeo pixelado",     "Tarjeta Gráfica (GPU)", 1),
    ("pantalla negra sin video señal monitor hdmi displayport",        "Tarjeta Gráfica (GPU)", 1),
    ("driver grafico crash reinstalar ddu blackscreen",                "Tarjeta Gráfica (GPU)", 1),
    # Almacenamiento
    ("disco saturado 100 ssd hdd smart lento lentitud cuello botella", "Almacenamiento (SSD / HDD)", 5),
    ("archivo corrupto error lectura chkdsk disco duro nvme sata",     "Almacenamiento (SSD / HDD)", 5),
    ("desaparece ssd nvme m2 termal desconecta caliente",              "Almacenamiento (SSD / HDD)", 4),
    # Software / SO
    ("driver software actualizacion windows update error sistema",     "Software / Sistema Operativo", 3),
    ("malware virus lento proceso parasito startup inicio",            "Software / Sistema Operativo", 5),
    ("sfc dism modo seguro reparar sistema corrupto bootloader",       "Software / Sistema Operativo", 3),
    # Red
    ("red internet conexion ping latencia perdida paquetes wifi",      "Adaptador de Red", None),
    ("adaptador ethernet driver red inestable tcp dns reset",          "Adaptador de Red", None),
]


class BuscadorAsistido:
    """
    Búsqueda fuzzy sobre el corpus de diagnóstico.
    Usa difflib (stdlib) — sin dependencias externas.
    """

    @staticmethod
    def buscar(texto_usuario: str, top_n: int = 5) -> list[dict]:
        """
        Parámetros
        ----------
        texto_usuario : descripción libre del problema en español.
        top_n         : número máximo de resultados a devolver.

        Retorna
        -------
        Lista de dicts: {causa, score (0–1), rama_id, palabras_clave}.
        Ordenada desc. por score.
        """
        texto_norm = texto_usuario.lower().strip()
        if len(texto_norm) < 2:
            return []

        tokens_usuario = set(texto_norm.split())
        vistos: dict[str, float] = {}   # causa → mejor score acumulado

        for keywords, causa, rama_id in _CORPUS:
            tokens_corpus = set(keywords.split())

            # Métrica 1: overlap exacto de tokens (más rápido, más preciso)
            overlap = len(tokens_usuario & tokens_corpus)
            score_overlap = overlap / max(len(tokens_usuario), 1)

            # Métrica 2: similitud de subcadena con SequenceMatcher
            ratio = difflib.SequenceMatcher(None, texto_norm, keywords, autojunk=False).ratio()

            # Score combinado ponderado
            score = score_overlap * 0.65 + ratio * 0.35

            if score < 0.04:   # umbral mínimo para filtrar ruido
                continue

            entrada_previa = vistos.get(causa)
            if entrada_previa is None or score > entrada_previa:
                vistos[causa] = score

        # Construir resultado final con la entrada más representativa por causa
        resultados = []
        for causa, score in vistos.items():
            # Buscar la rama_id del mejor match para esta causa
            rama_id = next(
                (r for kw, c, r in _CORPUS if c == causa),
                None
            )
            resultados.append({
                "causa": causa,
                "score": round(score, 3),
                "rama_id": rama_id,
                "confianza_pct": round(min(score * 100, 99), 1),
            })

        resultados.sort(key=lambda x: x["score"], reverse=True)
        return resultados[:top_n]


# =============================================================================
# 4. MICRO-STRESS TEST CONTROLADO
# =============================================================================

class MicroStressTest:
    """
    Benchmark matemático multihilo en CPU.
    Duración: DURACION_SEG segundos.
    Detecta caídas de frecuencia ≥ THROTTLE_UMBRAL_PCT → thermal throttling.
    """

    DURACION_SEG: int = 10
    THROTTLE_UMBRAL_PCT: float = 12.0   # caída de freq considerada throttling

    def __init__(
        self,
        callback_progreso: Callable[[str], None],
        callback_resultado: Callable[[dict], None],
    ):
        """
        callback_progreso(mensaje) : llamado cada 0.5 s con el estado actual.
        callback_resultado(dict)   : llamado al finalizar con el análisis completo.
        """
        self._cb_prog  = callback_progreso
        self._cb_res   = callback_resultado
        self._activo   = False

    # ------------------------------------------------------------------
    def iniciar(self) -> None:
        """Lanza el test en un hilo daemon (no bloquea la GUI)."""
        if self._activo:
            return
        self._activo = True
        hilo = threading.Thread(target=self._run, daemon=True)
        hilo.start()

    # ------------------------------------------------------------------
    @staticmethod
    def _worker_cpu() -> float:
        """Carga matemática intensiva durante DURACION_SEG segundos."""
        end = time.time() + MicroStressTest.DURACION_SEG
        acum = 1.0
        while time.time() < end:
            # Operaciones mixtas: sqrt, multiplicaciones float
            acum = math.sqrt(acum * 999_983.0 + 1.777_777) % 1_000_000.0
        return acum

    # ------------------------------------------------------------------
    def _run(self) -> None:
        n_cores = psutil.cpu_count(logical=True) or 4
        self._cb_prog(
            f"[INICIANDO] Cargando {n_cores} hilos lógicos — {self.DURACION_SEG} segundos…\n"
        )

        muestras_freq: list[float] = []
        muestras_uso:  list[float] = []
        inicio = time.time()

        with ThreadPoolExecutor(max_workers=n_cores, thread_name_prefix="stress") as pool:
            # Lanzar todos los workers simultáneamente
            _futures = [pool.submit(self._worker_cpu) for _ in range(n_cores)]

            # Monitor de frecuencias mientras trabajan
            while time.time() - inicio < self.DURACION_SEG:
                elapsed = time.time() - inicio
                freq = psutil.cpu_freq()
                uso  = psutil.cpu_percent(interval=None)

                freq_actual = freq.current if freq else 0.0
                muestras_freq.append(freq_actual)
                muestras_uso.append(uso)

                barra = self._barra_progreso(elapsed, self.DURACION_SEG)
                self._cb_prog(
                    f"[{barra}] {elapsed:4.1f}s  |  "
                    f"Freq: {freq_actual/1000:.2f} GHz  |  "
                    f"CPU: {uso:.0f}%\n"
                )
                time.sleep(0.5)

        self._activo = False
        resultado = self._analizar(muestras_freq, muestras_uso)
        self._cb_resultado_seguro(resultado)

    # ------------------------------------------------------------------
    def _cb_resultado_seguro(self, resultado: dict) -> None:
        self._cb_res(resultado)

    # ------------------------------------------------------------------
    @staticmethod
    def _barra_progreso(elapsed: float, total: float, ancho: int = 20) -> str:
        relleno = int((elapsed / total) * ancho)
        return "█" * relleno + "░" * (ancho - relleno)

    # ------------------------------------------------------------------
    def _analizar(self, muestras_freq: list[float], muestras_uso: list[float]) -> dict:
        if not muestras_freq:
            return {"error": "Sin muestras de frecuencia disponibles."}

        freq_max  = max(muestras_freq)
        freq_min  = min(muestras_freq)
        freq_avg  = sum(muestras_freq) / len(muestras_freq)
        uso_max   = max(muestras_uso) if muestras_uso else 0.0
        uso_avg   = sum(muestras_uso) / len(muestras_uso) if muestras_uso else 0.0

        caida_pct = ((freq_max - freq_min) / freq_max * 100) if freq_max > 0 else 0.0
        throttling_detectado = caida_pct >= self.THROTTLE_UMBRAL_PCT

        if throttling_detectado:
            diagnostico = (
                f"⚠  THERMAL THROTTLING DETECTADO\n"
                f"   Caída de frecuencia: {caida_pct:.1f}% ({freq_max/1000:.2f} → {freq_min/1000:.2f} GHz)\n"
                f"   El procesador redujo su velocidad por exceso de calor.\n\n"
                f"ACCIONES RECOMENDADAS:\n"
                f"  1. Reemplace la pasta térmica del CPU.\n"
                f"  2. Limpie el disipador y los filtros de polvo.\n"
                f"  3. Mejore el flujo de aire del chasis.\n"
                f"  4. Considere un cooler de mayor capacidad."
            )
        else:
            diagnostico = (
                f"✅  RENDIMIENTO ESTABLE — Sin throttling detectado\n"
                f"   Variación de frecuencia: {caida_pct:.1f}% (umbral: {self.THROTTLE_UMBRAL_PCT}%)\n"
                f"   El enfriamiento del CPU es adecuado para carga sostenida.\n\n"
                f"OBSERVACIONES:\n"
                f"  • Freq. máxima alcanzada: {freq_max/1000:.2f} GHz\n"
                f"  • Freq. mínima durante test: {freq_min/1000:.2f} GHz\n"
                f"  • Uso CPU promedio: {uso_avg:.1f}%"
            )

        return {
            "throttling": throttling_detectado,
            "freq_max_ghz": round(freq_max / 1000, 3),
            "freq_min_ghz": round(freq_min / 1000, 3),
            "freq_avg_ghz": round(freq_avg / 1000, 3),
            "caida_pct":    round(caida_pct, 1),
            "uso_max_pct":  round(uso_max, 1),
            "uso_avg_pct":  round(uso_avg, 1),
            "n_muestras":   len(muestras_freq),
            "diagnostico":  diagnostico,
        }