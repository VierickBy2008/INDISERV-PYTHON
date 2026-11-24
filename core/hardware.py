"""
core/hardware.py — Perfilador de Hardware Exhaustivo (Fase 1)
=============================================================
Recopila telemetría profunda de la máquina Windows mediante psutil,
platform y consultas WMI nativas vía PowerShell (subprocess puro, sin
DLLs externas ni compiladores).

RETROCOMPATIBILIDAD GARANTIZADA
  El dict retornado siempre incluye las claves legacy:
    nombre_cpu, nucleos, ram_total_mb, ram_disponible_mb, so,
    alerta_ram, alerta_cpu
  Estas clave son usadas por main.py y guardar_reporte_final().
"""

from __future__ import annotations

import os
import sys
import platform
import subprocess
import json
import time
import re
import datetime
from pathlib import Path
import psutil
from typing import Any


def _run_cmd(args: list[str], timeout: int = 5) -> str:
    """Ejecuta un comando nativo del SO y devuelve stdout limpio o '' si falla."""
    try:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        res = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=creation_flags,
        )
        if res.returncode == 0 and res.stdout:
            return res.stdout.strip()
    except Exception:
        pass
    return ""


def _read_sys_file(path: str) -> str:
    """Lee un archivo virtual de /sys o /proc en Linux sin lanzar excepciones."""
    try:
        p = Path(path)
        if p.exists():
            return p.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        pass
    return ""


def _wmi_query(clase_wmi: str, propiedades: list[str]) -> list[dict[str, Any]]:
    """
    Ejecuta Get-CimInstance <clase_wmi> en PowerShell (solo Windows) y devuelve
    una lista de dicts con las propiedades solicitadas.
    En Linux o macOS retorna [] inmediatamente.
    """
    if sys.platform != "win32":
        return []
    props_str = ", ".join(propiedades)
    script = (
        f"Get-CimInstance -ClassName {clase_wmi} | "
        f"Select-Object {props_str} | "
        "ConvertTo-Json -Depth 2 -Compress"
    )
    try:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            creationflags=creation_flags,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        data = json.loads(result.stdout.strip())
        if isinstance(data, dict):
            return [data]
        return data
    except Exception:
        return []


def _escanear_motherboard_bios() -> dict[str, str]:
    """Fabricante, modelo, versión y fecha de BIOS (Windows, Linux y macOS)."""
    if sys.platform.startswith("linux"):
        mb_fab = _read_sys_file("/sys/class/dmi/id/board_vendor") or _read_sys_file("/sys/class/dmi/id/sys_vendor") or "Linux OEM"
        mb_mod = _read_sys_file("/sys/class/dmi/id/board_name") or _read_sys_file("/sys/class/dmi/id/product_name") or _read_sys_file("/proc/device-tree/model") or "Placa Base Linux"
        bios_fab = _read_sys_file("/sys/class/dmi/id/bios_vendor") or mb_fab
        bios_ver = _read_sys_file("/sys/class/dmi/id/bios_version") or "UEFI/Linux"
        bios_fec = _read_sys_file("/sys/class/dmi/id/bios_date") or "Desconocida"
        return {
            "mb_fabricante": mb_fab,
            "mb_modelo": mb_mod,
            "bios_fabricante": bios_fab,
            "bios_version": bios_ver,
            "bios_fecha": bios_fec,
        }

    if sys.platform == "darwin":
        hw_model = _run_cmd(["sysctl", "-n", "hw.model"]) or "Mac"
        boot_rom = "Apple Silicon / EFI"
        sp_out = _run_cmd(["system_profiler", "SPHardwareDataType", "-json"], timeout=6)
        if sp_out:
            try:
                sp_items = json.loads(sp_out).get("SPHardwareDataType", [])
                if sp_items:
                    info = sp_items[0]
                    hw_model = info.get("machine_model") or info.get("machine_name") or hw_model
                    boot_rom = info.get("boot_rom_version") or info.get("os_loader_version") or boot_rom
            except Exception:
                pass
        return {
            "mb_fabricante": "Apple Inc.",
            "mb_modelo": hw_model,
            "bios_fabricante": "Apple Inc.",
            "bios_version": boot_rom,
            "bios_fecha": "Integrado",
        }

    mb = _wmi_query("Win32_BaseBoard", ["Manufacturer", "Product"])
    bios = _wmi_query("Win32_BIOS", ["Manufacturer", "SMBIOSBIOSVersion", "ReleaseDate"])

    mb_data = mb[0] if mb else {}
    bios_data = bios[0] if bios else {}

    fecha_raw = bios_data.get("ReleaseDate", "") or ""
    fecha_bios = "Desconocida"
    epoch_match = re.search(r"/Date\((\d+)\)/", fecha_raw)
    if epoch_match:
        ts = int(epoch_match.group(1)) / 1000
        d = datetime.datetime.utcfromtimestamp(ts)
        fecha_bios = d.strftime("%d/%m/%Y")
    elif len(fecha_raw) >= 8 and fecha_raw[:8].isdigit():
        fecha_bios = f"{fecha_raw[6:8]}/{fecha_raw[4:6]}/{fecha_raw[:4]}"

    return {
        "mb_fabricante": mb_data.get("Manufacturer", "Desconocido"),
        "mb_modelo": mb_data.get("Product", "Desconocido"),
        "bios_fabricante": bios_data.get("Manufacturer", "Desconocido"),
        "bios_version": bios_data.get("SMBIOSBIOSVersion", "Desconocida"),
        "bios_fecha": fecha_bios,
    }


_LAPTOP_CHASSIS_TYPES: set[int] = {8, 9, 10, 14, 30, 31, 32}
_DESKTOP_CHASSIS_TYPES: set[int] = {3, 4, 5, 6, 7, 13, 15, 16}


def _clasificar_tipo_equipo(
    chassis_types: list[int],
    pc_system_type: int | None,
    tiene_bateria: bool,
) -> str:
    """
    Determina si el equipo es 'laptop' o 'desktop' priorizando SMBIOS ChassisTypes
    y Win32_ComputerSystem.PCSystemType, con batería (psutil) como fallback.
    """
    chassis_set = set(chassis_types)
    if (chassis_set & _LAPTOP_CHASSIS_TYPES) or pc_system_type == 2:
        return "laptop"
    if (chassis_set & _DESKTOP_CHASSIS_TYPES) or pc_system_type == 1:
        return "desktop"
    if tiene_bateria:
        return "laptop"
    return "desktop"


def _escanear_tipo_equipo() -> dict[str, Any]:
    """
    Detecta el factor de forma ('laptop' | 'desktop') en Windows, Linux y macOS.
    """
    chassis_types: list[int] = []
    pc_system_type: int | None = None

    try:
        tiene_bateria = psutil.sensors_battery() is not None
    except Exception:
        tiene_bateria = False

    if sys.platform.startswith("linux"):
        raw_ct = _read_sys_file("/sys/class/dmi/id/chassis_type")
        if raw_ct.isdigit():
            chassis_types.append(int(raw_ct))
        if not tiene_bateria:
            try:
                ps_dir = Path("/sys/class/power_supply")
                if ps_dir.exists():
                    tiene_bateria = any(p.name.upper().startswith("BAT") for p in ps_dir.iterdir())
            except Exception:
                pass
        pc_system_type = 2 if (set(chassis_types) & _LAPTOP_CHASSIS_TYPES or tiene_bateria) else 1

    elif sys.platform == "darwin":
        hw_model = (_run_cmd(["sysctl", "-n", "hw.model"]) or "").lower()
        batt_info = (_run_cmd(["pmset", "-g", "batt"]) or "").lower()
        if "internalbattery" in batt_info:
            tiene_bateria = True
        if "macbook" in hw_model or tiene_bateria:
            chassis_types = [10]
            pc_system_type = 2
        else:
            chassis_types = [3]
            pc_system_type = 1

    else:
        enclosures = _wmi_query("Win32_SystemEnclosure", ["ChassisTypes"])
        cs = _wmi_query("Win32_ComputerSystem", ["PCSystemType"])
        for enc in enclosures:
            raw_ct = enc.get("ChassisTypes")
            if isinstance(raw_ct, list):
                for val in raw_ct:
                    try:
                        chassis_types.append(int(val))
                    except (TypeError, ValueError):
                        pass
            elif raw_ct is not None:
                try:
                    chassis_types.append(int(raw_ct))
                except (TypeError, ValueError):
                    pass
        if cs:
            raw_pst = cs[0].get("PCSystemType")
            if raw_pst is not None:
                try:
                    pc_system_type = int(raw_pst)
                except (TypeError, ValueError):
                    pc_system_type = None

    tipo_equipo = _clasificar_tipo_equipo(chassis_types, pc_system_type, tiene_bateria)

    return {
        "tipo_equipo": tipo_equipo,
        "chassis_types": chassis_types,
        "pc_system_type": pc_system_type,
        "tiene_bateria": tiene_bateria,
    }


def _escanear_cpu() -> dict[str, Any]:
    """CPU: modelo, frecuencias, núcleos físicos/lógicos, uso por núcleo (Windows, Linux y macOS)."""
    cpu_wmi = _wmi_query("Win32_Processor", ["Name", "NumberOfCores", "NumberOfLogicalProcessors"])
    cpu_data = cpu_wmi[0] if cpu_wmi else {}

    nombre_cpu = (cpu_data.get("Name") or "").strip()
    if not nombre_cpu and sys.platform.startswith("linux"):
        cpuinfo = _read_sys_file("/proc/cpuinfo")
        for line in cpuinfo.splitlines():
            if ":" in line and line.split(":", 1)[0].strip().lower() in ("model name", "hardware", "processor"):
                cand = line.split(":", 1)[1].strip()
                if cand and not cand.isdigit():
                    nombre_cpu = cand
                    break
        if not nombre_cpu:
            lscpu_out = _run_cmd(["lscpu"])
            for line in lscpu_out.splitlines():
                if "model name:" in line.lower():
                    nombre_cpu = line.split(":", 1)[1].strip()
                    break
    elif not nombre_cpu and sys.platform == "darwin":
        nombre_cpu = _run_cmd(["sysctl", "-n", "machdep.cpu.brand_string"])

    if not nombre_cpu:
        nombre_cpu = (platform.processor() or "CPU Genérica Detectada").strip()

    nucleos_fisicos = int(cpu_data.get("NumberOfCores") or psutil.cpu_count(logical=False) or 1)
    nucleos_logicos = int(cpu_data.get("NumberOfLogicalProcessors") or psutil.cpu_count(logical=True) or 1)

    try:
        freq = psutil.cpu_freq()
    except Exception:
        freq = None
    freq_base_ghz = round(freq.max / 1000, 2) if freq and freq.max else 0.0
    freq_actual_ghz = round(freq.current / 1000, 2) if freq and freq.current else 0.0
    if freq_actual_ghz <= 0.0 and sys.platform == "darwin":
        freq_base_ghz = freq_base_ghz or 3.20
        freq_actual_ghz = 3.20

    uso_por_nucleo = psutil.cpu_percent(interval=0.5, percpu=True)

    return {
        "nombre_cpu": nombre_cpu,
        "nucleos_fisicos": nucleos_fisicos,
        "nucleos": nucleos_logicos,
        "frecuencia_base_ghz": freq_base_ghz,
        "frecuencia_actual_ghz": freq_actual_ghz,
        "uso_por_nucleo": uso_por_nucleo,
        "uso_cpu_total": round(sum(uso_por_nucleo) / len(uso_por_nucleo), 1) if uso_por_nucleo else 0.0,
        "alerta_cpu": nucleos_logicos <= 2,
    }


def _escanear_ram() -> dict[str, Any]:
    """RAM: total/libre (psutil) + velocidad, tipo y ranuras (WMI)."""
    memoria = psutil.virtual_memory()
    ram_total_mb_int = int(memoria.total / (1024 * 1024))
    ram_libre_mb_int = int(memoria.available / (1024 * 1024))

    modulos_wmi = _wmi_query(
        "Win32_PhysicalMemory",
        ["Capacity", "Speed", "SMBIOSMemoryType", "DeviceLocator", "BankLabel"]
    )

    tipo_map = {
        20: "DDR", 21: "DDR2", 22: "DDR2 FB-DIMM",
        24: "DDR3", 26: "DDR4", 34: "DDR5", 0: "Desconocido"
    }

    modulos = []
    for m in modulos_wmi:
        tipo_num = int(m.get("SMBIOSMemoryType") or 0)
        cap_bytes = int(m.get("Capacity") or 0)
        modulos.append({
            "ranura": m.get("DeviceLocator", "?"),
            "banco": m.get("BankLabel", "?"),
            "capacidad_gb": round(cap_bytes / (1024 ** 3), 1),
            "velocidad_mhz": m.get("Speed", "?"),
            "tipo": tipo_map.get(tipo_num, f"Tipo {tipo_num}"),
        })

    if not modulos and sys.platform != "win32":
        tipo_fb = "Unified LPDDR" if sys.platform == "darwin" else "DDR4/DDR5"
        modulos.append({
            "ranura": "DIMM 0",
            "banco": "System Memory",
            "capacidad_gb": round(memoria.total / (1024 ** 3), 1),
            "velocidad_mhz": "N/A",
            "tipo": tipo_fb,
        })

    tipo_ram = modulos[0]["tipo"] if modulos else "Desconocido"
    velocidad_ram = modulos[0]["velocidad_mhz"] if modulos else "?"

    return {
        "ram_total_mb": f"{ram_total_mb_int} MB",
        "ram_disponible_mb": f"{ram_libre_mb_int} MB",
        "alerta_ram": ram_total_mb_int <= 2048,
        "ram_total_mb_int": ram_total_mb_int,
        "ram_libre_mb_int": ram_libre_mb_int,
        "ram_uso_pct": round(memoria.percent, 1),
        "ram_tipo": tipo_ram,
        "ram_velocidad_mhz": velocidad_ram,
        "ram_ranuras_ocupadas": len(modulos),
        "ram_modulos": modulos,
    }


def _escanear_gpu() -> dict[str, Any]:
    """GPU(s): modelo, VRAM y versión del driver."""
    gpus_wmi = _wmi_query(
        "Win32_VideoController",
        ["Name", "AdapterRAM", "DriverVersion", "VideoProcessor"]
    )

    gpus = []
    for g in gpus_wmi:
        vram_bytes = int(g.get("AdapterRAM") or 0)
        if vram_bytes < 0:
            vram_bytes += 2 ** 32
        gpus.append({
            "nombre": g.get("Name", "GPU Desconocida"),
            "procesador": g.get("VideoProcessor", ""),
            "vram_mb": round(vram_bytes / (1024 ** 2), 0),
            "driver_version": g.get("DriverVersion", "Desconocida"),
        })

    if not gpus and sys.platform.startswith("linux"):
        nv_out = _run_cmd(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"])
        if nv_out:
            for line in nv_out.splitlines():
                partes = [p.strip() for p in line.split(",")]
                if len(partes) >= 3:
                    try:
                        vram_mb = float(partes[1])
                    except ValueError:
                        vram_mb = 0.0
                    gpus.append({
                        "nombre": partes[0],
                        "procesador": partes[0],
                        "vram_mb": vram_mb,
                        "driver_version": partes[2],
                    })
        lspci_out = _run_cmd(["lspci"])
        for line in lspci_out.splitlines():
            low = line.lower()
            if any(k in low for k in ("vga compatible controller:", "3d controller:", "display controller:")):
                desc = line.split(":", 2)[-1].strip()
                if desc and not any(desc in g["nombre"] for g in gpus):
                    gpus.append({
                        "nombre": desc,
                        "procesador": desc,
                        "vram_mb": 0.0,
                        "driver_version": "Kernel DRM/Mesa",
                    })

    elif not gpus and sys.platform == "darwin":
        sp_gpu = _run_cmd(["system_profiler", "SPDisplaysDataType", "-json"], timeout=6)
        if sp_gpu:
            try:
                items = json.loads(sp_gpu).get("SPDisplaysDataType", [])
                for it in items:
                    nombre_g = it.get("sppci_model") or it.get("_name") or "Apple Integrated GPU"
                    vram_str = str(it.get("spdisplays_vram") or it.get("spdisplays_vram_shared") or "0")
                    m_vram = re.search(r"(\d+)", vram_str)
                    vram_val = float(m_vram.group(1)) if m_vram else 0.0
                    if "gb" in vram_str.lower():
                        vram_val *= 1024.0
                    gpus.append({
                        "nombre": nombre_g,
                        "procesador": nombre_g,
                        "vram_mb": vram_val,
                        "driver_version": str(it.get("spdisplays_metal") or "Apple Metal"),
                    })
            except Exception:
                pass

    gpu_principal = gpus[0]["nombre"] if gpus else "No detectada"

    return {
        "gpu_principal": gpu_principal,
        "gpus": gpus,
    }


def _escanear_almacenamiento() -> dict[str, Any]:
    """Discos físicos (tipo de interfaz) + particiones lógicas."""
    discos_fisicos_wmi = _wmi_query(
        "Win32_DiskDrive",
        ["Model", "MediaType", "InterfaceType", "Size", "SerialNumber"]
    )

    discos_fisicos = []
    for d in discos_fisicos_wmi:
        tam_bytes = int(d.get("Size") or 0)
        interfaz = (d.get("InterfaceType") or "").upper()
        media = (d.get("MediaType") or "").lower()

        if "nvme" in (d.get("Model") or "").lower() or "nvme" in interfaz:
            tipo_disco = "NVMe SSD"
        elif interfaz in ("USB", "1394"):
            tipo_disco = "Externo USB"
        elif "ssd" in media or "solid" in media:
            tipo_disco = "SATA SSD"
        else:
            tipo_disco = "HDD"

        discos_fisicos.append({
            "modelo": d.get("Model", "Disco Desconocido"),
            "tipo": tipo_disco,
            "interfaz": interfaz,
            "capacidad_gb": round(tam_bytes / (1024 ** 3), 1),
        })

    if not discos_fisicos and sys.platform.startswith("linux"):
        lsblk_out = _run_cmd(["lsblk", "-J", "-b", "-d", "-o", "NAME,MODEL,SIZE,ROTA,TRAN"])
        if lsblk_out:
            try:
                for bd in json.loads(lsblk_out).get("blockdevices", []):
                    nombre_d = str(bd.get("name") or "")
                    if nombre_d.startswith(("loop", "ram", "zram")):
                        continue
                    tam_b = int(bd.get("size") or 0)
                    if tam_b <= 0:
                        continue
                    tran = str(bd.get("tran") or "").upper()
                    rota = bd.get("rota")
                    es_rot = rota in (True, 1, "1")
                    modelo_d = (bd.get("model") or f"/dev/{nombre_d}").strip()
                    if "NVME" in tran or nombre_d.startswith("nvme"):
                        t_disco = "NVMe SSD"
                    elif tran == "USB":
                        t_disco = "Externo USB"
                    elif not es_rot:
                        t_disco = "SATA SSD"
                    else:
                        t_disco = "HDD"
                    discos_fisicos.append({
                        "modelo": modelo_d,
                        "tipo": t_disco,
                        "interfaz": tran or "BLK",
                        "capacidad_gb": round(tam_b / (1024 ** 3), 1),
                    })
            except Exception:
                pass

    elif not discos_fisicos and sys.platform == "darwin":
        try:
            uso_root = psutil.disk_usage("/")
            discos_fisicos.append({
                "modelo": "Apple Internal SSD",
                "tipo": "NVMe SSD",
                "interfaz": "NVMe",
                "capacidad_gb": round(uso_root.total / (1024 ** 3), 1),
            })
        except Exception:
            pass

    particiones = []
    for part in psutil.disk_partitions(all=False):
        if sys.platform.startswith("linux") and (
            part.mountpoint.startswith("/snap") or part.fstype in ("squashfs", "tmpfs", "devtmpfs")
        ):
            continue
        try:
            uso = psutil.disk_usage(part.mountpoint)
            particiones.append({
                "letra": part.mountpoint,
                "fs": part.fstype,
                "total_gb": round(uso.total / (1024 ** 3), 1),
                "usado_gb": round(uso.used / (1024 ** 3), 1),
                "libre_gb": round(uso.free / (1024 ** 3), 1),
                "uso_pct": uso.percent,
            })
        except PermissionError:
            continue

    return {
        "discos_fisicos": discos_fisicos,
        "particiones": particiones,
    }


def _escanear_red_y_so() -> dict[str, Any]:
    """Adaptador activo, ping a gateway/DNS, uptime y compilación de Windows."""
    boot_ts = psutil.boot_time()
    uptime_seg = time.time() - boot_ts
    horas = int(uptime_seg // 3600)
    minutos = int((uptime_seg % 3600) // 60)
    uptime_str = f"{horas}h {minutos}m"

    so_version = f"{platform.system()} {platform.release()}"
    build_win = platform.version()

    adaptadores = []
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()
    for iface, stat in stats.items():
        if stat.isup:
            ips = [
                a.address for a in addrs.get(iface, [])
                if ":" not in a.address
                and "-" not in a.address
                and not a.address.startswith("127.")
            ]
            if ips:
                adaptadores.append({"nombre": iface, "ip": ips[0], "velocidad_mbps": stat.speed})

    adaptador_activo = adaptadores[0]["nombre"] if adaptadores else "Ninguno"
    ip_local = adaptadores[0]["ip"] if adaptadores else "N/A"

    latencia_ms = _ping_latencia("8.8.8.8")

    return {
        "so": so_version,
        "so_build": build_win,
        "uptime": uptime_str,
        "adaptador_activo": adaptador_activo,
        "ip_local": ip_local,
        "latencia_ms": latencia_ms,
    }


def _ping_latencia(host: str) -> str:
    """Devuelve la latencia en ms como string (Windows, Linux y macOS), o 'N/A' si falla."""
    try:
        if sys.platform == "win32":
            cmd = ["ping", "-n", "1", "-w", "2000", host]
            enc = "cp850"
        elif sys.platform == "darwin":
            cmd = ["ping", "-c", "1", "-W", "2000", host]
            enc = "utf-8"
        else:
            cmd = ["ping", "-c", "1", "-W", "2", host]
            enc = "utf-8"

        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding=enc,
            errors="replace",
            timeout=5,
            creationflags=creation_flags,
        )
        for line in result.stdout.splitlines():
            if "tiempo" in line.lower() or "time" in line.lower() or "ms" in line.lower():
                m = re.search(r"(?:tiempo|time)[<=](\d+(?:\.\d+)?)\s*ms", line, re.IGNORECASE)
                if m:
                    val_ms = int(round(float(m.group(1))))
                    return f"{val_ms} ms"
    except Exception:
        pass
    return "N/A"


def _tiene_firma_portatil(hw: dict[str, Any]) -> bool:
    """
    Respaldo por huella de hardware: detecta procesadores móviles (H/HS/HX/U),
    GPUs Laptop/Mobile, memorias SO-DIMM/LPDDR o placas base de portátiles
    (ej. LENOVO LNVNB, ASUS TUF FA506/FX505, ROG GU603/G513, Acer Nitro, HP Victus/Omen)
    por si la tabla SMBIOS del fabricante reporta un ChassisType genérico.
    """
    texto = " ".join(
        str(hw.get(k, "") or "")
        for k in (
            "nombre_cpu",
            "gpu_principal",
            "mb_fabricante",
            "mb_modelo",
            "ram_tipo",
            "equipo_modelo_comercial",
            "equipo_familia",
        )
    ).lower()
    if any(
        kw in texto
        for kw in (
            "laptop",
            "notebook",
            "portable",
            "mobile",
            "macbook",
            "thinkpad",
            "ideapad",
            "legion",
            "loq",
            "zenbook",
            "vivobook",
            "rog ",
            "tuf gaming a",
            "tuf gaming f",
            "nitro ",
            "pavilion",
            "victus",
            "inspiron",
            "latitude",
            "xps ",
            "swift ",
            "matebook",
            "lnvnb",
            "fa506",
            "fx505",
            "fx506",
            "fa507",
            "gu603",
            "g513",
            "sodimm",
            "so-dimm",
            "lpddr",
        )
    ):
        return True
    if re.search(r"\b(?:i[3579]-|ryzen\s+[3579]\s+|ultra\s+[579]\s+)?\d{4,5}(?:hs|hx|h|u|g[1-7])\b", texto):
        return True
    return False


_OEM_INVALIDOS = {
    "",
    "none",
    "null",
    "unknown",
    "n/a",
    "na",
    "invalid",
    "default string",
    "system product name",
    "system manufacturer",
    "system version",
    "to be filled by o.e.m.",
    "to be filled by oem",
    "not applicable",
    "not specified",
    "base board product name",
    "oem",
    "0",
    "1.0",
}

_MARCAS_NORM = (
    ("asustek", "ASUS"),
    ("micro-star", "MSI"),
    ("hewlett-packard", "HP"),
    ("hp inc", "HP"),
    ("dell inc", "Dell"),
    ("apple inc", "Apple"),
    ("acer incorporated", "Acer"),
    ("gigabyte technology", "GIGABYTE"),
    ("huawei technologies", "HUAWEI"),
)


def _limpiar_campo_oem(valor: Any) -> str:
    txt = str(valor or "").strip()
    if not txt:
        return ""
    if txt.lower() in _OEM_INVALIDOS:
        return ""
    if "to be filled" in txt.lower() or "default string" in txt.lower():
        return ""
    return txt


def _normalizar_marca_oem(marca: str) -> str:
    limpia = _limpiar_campo_oem(marca)
    if not limpia:
        return ""
    low = limpia.lower()
    for pref, norm in _MARCAS_NORM:
        if pref in low:
            return norm
    return limpia


def _resolver_modelo_comercial(
    vendor: str = "",
    model: str = "",
    family: str = "",
    version: str = "",
    sku: str = "",
    mb_fabricante: str = "",
    mb_modelo: str = "",
    tipo_equipo: str = "desktop",
) -> dict[str, Any]:
    """
    Resuelve un nombre comercial legible para laptops/PCs OEM (Windows, Linux y macOS)
    sin llamadas externas, filtrando cadenas genéricas y evitando duplicar la marca.
    """
    fab = _normalizar_marca_oem(vendor)
    mod = _limpiar_campo_oem(model)
    fam = _limpiar_campo_oem(family)
    ver = _limpiar_campo_oem(version)
    sku_clean = _limpiar_campo_oem(sku)

    if "_" in mod:
        partes_u = mod.split("_")
        if len(partes_u) == 2 and partes_u[1] and partes_u[0].endswith(partes_u[1]):
            mod = partes_u[0].strip()

    es_oem = bool(mod or fam or ver)
    nombre_comercial = ""
    codigo_modelo = mod

    if es_oem:
        if fab.upper() == "LENOVO":
            comercial_lenovo = ""
            for cand in (ver, fam):
                if cand and cand.lower() != mod.lower() and not re.match(r"^[0-9A-Z]{4,10}$", cand):
                    comercial_lenovo = cand
                    break
            if comercial_lenovo:
                base = comercial_lenovo if comercial_lenovo.lower().startswith("lenovo") else f"{fab} {comercial_lenovo}"
                nombre_comercial = f"{base} ({mod})" if mod and mod.lower() not in base.lower() else base
            elif mod:
                nombre_comercial = mod if mod.lower().startswith("lenovo") else f"{fab} {mod}"
            elif fam:
                nombre_comercial = f"{fab} {fam}"

        elif fab.lower() == "apple":
            base_mac = mod or fam or "Mac"
            if not base_mac.lower().startswith("apple"):
                base_mac = f"Apple {base_mac}"
            if ver and ver.lower() not in base_mac.lower():
                nombre_comercial = f"{base_mac} ({ver})"
            else:
                nombre_comercial = base_mac
            codigo_modelo = ver or mod

        else:
            principal = mod or fam or ver
            if fam and principal and len(principal) <= 8 and fam.lower() != principal.lower() and not re.match(r"^[0-9A-Z_-]{2,8}$", fam):
                principal = f"{fam} ({principal})"
            if fab and fab.lower() not in principal.lower():
                nombre_comercial = f"{fab} {principal}".strip()
            else:
                nombre_comercial = principal
    else:
        mb_fab_norm = _normalizar_marca_oem(mb_fabricante)
        mb_mod_clean = _limpiar_campo_oem(mb_modelo)
        if mb_fab_norm and mb_mod_clean:
            placa_txt = mb_mod_clean if mb_fab_norm.lower() in mb_mod_clean.lower() else f"{mb_fab_norm} {mb_mod_clean}"
        else:
            placa_txt = mb_mod_clean or mb_fab_norm or "Placa Estándar"
        pref_tipo = "Portátil" if tipo_equipo == "laptop" else "PC de Escritorio"
        nombre_comercial = f"{pref_tipo} · {placa_txt}"
        fab = mb_fab_norm or "Personalizado"

    return {
        "equipo_fabricante": fab or "Desconocido",
        "equipo_modelo_comercial": nombre_comercial,
        "equipo_familia": fam,
        "equipo_codigo_modelo": codigo_modelo,
        "equipo_sku": sku_clean,
        "equipo_es_oem": es_oem,
    }


def _escanear_modelo_equipo(mb: dict[str, Any], tipo_equipo: str = "desktop") -> dict[str, Any]:
    """Lee el modelo comercial real del equipo en Windows (WMI), Linux (DMI) o macOS."""
    vendor = ""
    model = ""
    family = ""
    version = ""
    sku = ""

    if sys.platform.startswith("linux"):
        vendor = _read_sys_file("/sys/class/dmi/id/sys_vendor")
        model = _read_sys_file("/sys/class/dmi/id/product_name")
        family = _read_sys_file("/sys/class/dmi/id/product_family")
        version = _read_sys_file("/sys/class/dmi/id/product_version")
        sku = _read_sys_file("/sys/class/dmi/id/product_sku")

    elif sys.platform == "darwin":
        vendor = "Apple Inc."
        hw_model = _run_cmd(["sysctl", "-n", "hw.model"]) or ""
        model = hw_model
        sp_out = _run_cmd(["system_profiler", "SPHardwareDataType", "-json"], timeout=6)
        if sp_out:
            try:
                sp_items = json.loads(sp_out).get("SPHardwareDataType", [])
                if sp_items:
                    info = sp_items[0]
                    model = info.get("machine_name") or model
                    version = info.get("machine_model") or hw_model
                    family = info.get("chip_type") or ""
                    sku = info.get("model_number") or ""
            except Exception:
                pass

    elif sys.platform == "win32":
        cs = _wmi_query("Win32_ComputerSystem", ["Manufacturer", "Model", "SystemFamily", "SystemSKUNumber"])
        csp = _wmi_query("Win32_ComputerSystemProduct", ["Vendor", "Name", "Version"])
        cs0 = cs[0] if cs else {}
        csp0 = csp[0] if csp else {}
        vendor = cs0.get("Manufacturer") or csp0.get("Vendor") or ""
        model = cs0.get("Model") or csp0.get("Name") or ""
        family = cs0.get("SystemFamily") or ""
        version = csp0.get("Version") or ""
        sku = cs0.get("SystemSKUNumber") or ""

    return _resolver_modelo_comercial(
        vendor=str(vendor or ""),
        model=str(model or ""),
        family=str(family or ""),
        version=str(version or ""),
        sku=str(sku or ""),
        mb_fabricante=str(mb.get("mb_fabricante") or ""),
        mb_modelo=str(mb.get("mb_modelo") or ""),
        tipo_equipo=tipo_equipo,
    )


_KMS_PUBLICOS_CONOCIDOS = (
    "localhost",
    "127.0.0.",
    "::1",
    "0.0.0.0",
    "kms8.msguides",
    "kms9.msguides",
    "kms.msguides",
    "kms.lotro.cc",
    "kms.digiboy",
    "s8.uk.to",
    "s9.uk.to",
    "kms.chinancpy",
    "kms.03k.org",
    "kms.loli.beer",
    "kms.v0v.bid",
    "e8.us.to",
    "e9.us.to",
    "kms.cangshui",
    "kms.moerats",
    "kms.shuax",
)


def _es_servidor_kms_no_oficial(servidor: str) -> bool:
    s = (servidor or "").strip().lower()
    if not s:
        return False
    return any(ind in s for ind in _KMS_PUBLICOS_CONOCIDOS)


def _es_servidor_kms_privado_corporativo(servidor: str) -> bool:
    s = (servidor or "").strip().lower()
    if not s or _es_servidor_kms_no_oficial(s):
        return False
    if re.match(r"^(10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)$", s):
        return True
    if s.endswith((".local", ".lan", ".corp", ".internal", ".intra")):
        return True
    return False


def _leer_kms_registro_windows() -> str:
    """Lee KeyManagementServiceName en modo solo lectura (solo Windows)."""
    if sys.platform != "win32":
        return ""
    try:
        import winreg

        ruta = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\SoftwareProtectionPlatform"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, ruta, 0, winreg.KEY_READ) as clave:
            val, _ = winreg.QueryValueEx(clave, "KeyManagementServiceName")
            return str(val or "").strip()
    except Exception:
        return ""


def _extraer_canal_licencia(producto: dict[str, Any]) -> str:
    raw = f"{producto.get('ProductKeyChannel') or ''} {producto.get('Description') or ''}".upper()
    if "OEM:DM" in raw or "OEM_DM" in raw:
        return "OEM_DM"
    if "OEM" in raw:
        return "OEM"
    if "KMSCLIENT" in raw or "VOLUME:KMS" in raw or "VOLUME_KMS" in raw:
        return "VOLUME_KMSCLIENT"
    if "VOLUME:MAK" in raw or "VOLUME_MAK" in raw or "MAK" in raw:
        return "VOLUME_MAK"
    if "RETAIL" in raw:
        return "RETAIL"
    return "DESCONOCIDO"


def _clasificar_licencia_windows(
    producto: dict[str, Any] | None,
    tiene_llave_uefi: bool = False,
    kms_registro: str = "",
) -> dict[str, Any]:
    """
    Clasifica de forma determinista y honesta el estado de licenciamiento Windows
    a partir de SoftwareLicensingProduct/Service + Registro en solo lectura.
    Jamás expone llaves completas (solo partial_key de 5 caracteres y booleano tiene_llave_uefi).
    """
    if not producto:
        sospecha_kms = _es_servidor_kms_no_oficial(kms_registro)
        return {
            "aplicable": True,
            "estado": "Sin Activar / Sin Licencia Detectada",
            "tipo_badge": "err" if sospecha_kms else "warn",
            "etiqueta_badge": "NO OFICIAL (KMS)" if sospecha_kms else "SIN ACTIVAR",
            "canal": "N/D",
            "activa": False,
            "permanente": False,
            "dias_restantes": None,
            "tiene_llave_uefi": bool(tiene_llave_uefi),
            "partial_key": "",
            "es_original": False,
            "sospecha_kms": sospecha_kms,
            "servidor_kms": kms_registro.strip(),
            "detalle": "No se detectó un producto de Windows activado con clave parcial instalada.",
        }

    canal = _extraer_canal_licencia(producto)
    try:
        status_code = int(producto.get("LicenseStatus") or 0)
    except (TypeError, ValueError):
        status_code = 0
    try:
        grace_min = int(producto.get("GracePeriodRemaining") or 0)
    except (TypeError, ValueError):
        grace_min = 0

    partial_raw = str(producto.get("PartialProductKey") or "").strip().upper()
    partial_key = partial_raw[-5:] if partial_raw else ""

    kms_wmi = str(producto.get("KeyManagementServiceMachine") or "").strip()
    servidor_kms = kms_wmi or str(kms_registro or "").strip()
    kms_no_oficial = _es_servidor_kms_no_oficial(servidor_kms)
    kms_corporativo = _es_servidor_kms_privado_corporativo(servidor_kms)

    activa = status_code == 1
    permanente = bool(activa and grace_min == 0)
    dias_restantes = max(1, round(grace_min / 1440.0)) if grace_min > 0 else None

    if not activa:
        etiqueta_est = {
            0: "Sin licencia",
            2: "Período de gracia inicial",
            3: "Gracia adicional",
            5: "Notificación / Expirada",
            6: "Gracia extendida",
        }.get(status_code, "No activada")
        return {
            "aplicable": True,
            "estado": f"Sin Activar ({etiqueta_est})",
            "tipo_badge": "err" if status_code in (0, 5) else "warn",
            "etiqueta_badge": "SIN ACTIVAR",
            "canal": canal,
            "activa": False,
            "permanente": False,
            "dias_restantes": dias_restantes,
            "tiene_llave_uefi": bool(tiene_llave_uefi),
            "partial_key": partial_key,
            "es_original": False,
            "sospecha_kms": kms_no_oficial,
            "servidor_kms": servidor_kms,
            "detalle": f"Windows reporta estado '{etiqueta_est}' (canal {canal}).",
        }

    if canal == "VOLUME_KMSCLIENT" or kms_no_oficial:
        if kms_no_oficial or tiene_llave_uefi or (not permanente and not kms_corporativo):
            motivos = []
            if dias_restantes is not None:
                motivos.append(f"activación temporal ({dias_restantes} días restantes)")
            if servidor_kms:
                motivos.append(f"servidor KMS '{servidor_kms}'")
            if tiene_llave_uefi:
                motivos.append("superpuesto sobre llave OEM de fábrica en UEFI")
            resumen_motivo = ", ".join(motivos) or "canal VOLUME_KMSCLIENT en equipo personal"
            return {
                "aplicable": True,
                "estado": "Activación KMS No Oficial (Sospecha Crack)",
                "tipo_badge": "err",
                "etiqueta_badge": "NO OFICIAL (KMS)",
                "canal": canal,
                "activa": True,
                "permanente": False,
                "dias_restantes": dias_restantes,
                "tiene_llave_uefi": bool(tiene_llave_uefi),
                "partial_key": partial_key,
                "es_original": False,
                "sospecha_kms": True,
                "servidor_kms": servidor_kms,
                "detalle": f"Canal {canal}: {resumen_motivo}.",
            }
        return {
            "aplicable": True,
            "estado": "Licencia Volumen Empresarial (KMS Interno)",
            "tipo_badge": "warn",
            "etiqueta_badge": "EMPRESARIAL",
            "canal": canal,
            "activa": True,
            "permanente": permanente,
            "dias_restantes": dias_restantes,
            "tiene_llave_uefi": bool(tiene_llave_uefi),
            "partial_key": partial_key,
            "es_original": True,
            "sospecha_kms": False,
            "servidor_kms": servidor_kms,
            "detalle": f"Licencia por volumen corporativo vinculada al servidor interno '{servidor_kms}'.",
        }

    if canal == "VOLUME_MAK":
        return {
            "aplicable": True,
            "estado": "Licencia Volumen Empresarial (MAK)",
            "tipo_badge": "warn",
            "etiqueta_badge": "EMPRESARIAL",
            "canal": canal,
            "activa": True,
            "permanente": permanente,
            "dias_restantes": dias_restantes,
            "tiene_llave_uefi": bool(tiene_llave_uefi),
            "partial_key": partial_key,
            "es_original": True,
            "sospecha_kms": False,
            "servidor_kms": servidor_kms,
            "detalle": "Clave de activación múltiple (VOLUME_MAK) orientada a entornos empresariales.",
        }

    if canal in ("OEM_DM", "OEM") and permanente:
        uefi_txt = "vinculada a la placa base (UEFI)" if tiene_llave_uefi else "de canal OEM"
        return {
            "aplicable": True,
            "estado": "Original OEM de Fábrica",
            "tipo_badge": "ok",
            "etiqueta_badge": "ORIGINAL OEM",
            "canal": canal,
            "activa": True,
            "permanente": True,
            "dias_restantes": None,
            "tiene_llave_uefi": bool(tiene_llave_uefi),
            "partial_key": partial_key,
            "es_original": True,
            "sospecha_kms": False,
            "servidor_kms": "",
            "detalle": f"Licencia OEM {uefi_txt} con activación permanente oficial.",
        }

    if canal == "RETAIL" and permanente:
        return {
            "aplicable": True,
            "estado": "Original Retail / Digital",
            "tipo_badge": "ok",
            "etiqueta_badge": "ORIGINAL RETAIL",
            "canal": canal,
            "activa": True,
            "permanente": True,
            "dias_restantes": None,
            "tiene_llave_uefi": bool(tiene_llave_uefi),
            "partial_key": partial_key,
            "es_original": True,
            "sospecha_kms": False,
            "servidor_kms": "",
            "detalle": (
                "Activación Retail/Digital permanente validada por Windows "
                "(por software no se distingue comprobante de compra en claves Retail ya validadas)."
            ),
        }

    return {
        "aplicable": True,
        "estado": "Licencia Activa (Canal Estándar)",
        "tipo_badge": "info",
        "etiqueta_badge": "ACTIVA",
        "canal": canal,
        "activa": True,
        "permanente": permanente,
        "dias_restantes": dias_restantes,
        "tiene_llave_uefi": bool(tiene_llave_uefi),
        "partial_key": partial_key,
        "es_original": True,
        "sospecha_kms": False,
        "servidor_kms": servidor_kms,
        "detalle": f"Windows activado bajo canal {canal}.",
    }


def _escanear_licencia_windows() -> dict[str, Any]:
    """
    Audita la licencia de Windows en modo solo lectura sin privilegios de administrador.
    En Linux/macOS retorna inmediatamente estado POSIX sin ejecutar PowerShell ni importar winreg.
    """
    if sys.platform != "win32":
        return {
            "aplicable": False,
            "estado": "No aplica (POSIX)",
            "tipo_badge": "neutro",
            "etiqueta_badge": "NO APLICA",
            "canal": "N/D",
            "activa": None,
            "permanente": None,
            "dias_restantes": None,
            "tiene_llave_uefi": False,
            "partial_key": "",
            "es_original": None,
            "sospecha_kms": False,
            "servidor_kms": "",
            "detalle": "Sistema no Windows",
        }

    kms_reg = _leer_kms_registro_windows()
    ps_script = (
        "$p = Get-CimInstance -ClassName SoftwareLicensingProduct "
        "-Filter \"ApplicationID='55c92734-d682-4d71-983e-d6ec3f16059f' AND PartialProductKey IS NOT NULL\" | "
        "Select-Object Name, Description, ProductKeyChannel, LicenseStatus, GracePeriodRemaining, "
        "PartialProductKey, KeyManagementServiceMachine, KeyManagementServicePort; "
        "$s = Get-CimInstance -ClassName SoftwareLicensingService | Select-Object -First 1; "
        "$hasUefi = $false; $svcKms = ''; "
        "if ($s) { "
        "  $hasUefi = -not [string]::IsNullOrWhiteSpace($s.OA3xOriginalProductKey); "
        "  if ($s.KeyManagementServiceName) { $svcKms = [string]$s.KeyManagementServiceName } "
        "}; "
        "[PSCustomObject]@{ products = @($p); hasUefi = $hasUefi; svcKms = $svcKms } | "
        "ConvertTo-Json -Depth 3 -Compress"
    )

    producto_sel: dict[str, Any] | None = None
    tiene_llave_uefi = False
    svc_kms = ""

    try:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            creationflags=creation_flags,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            tiene_llave_uefi = bool(data.get("hasUefi"))
            svc_kms = str(data.get("svcKms") or "").strip()
            prods = data.get("products") or []
            if isinstance(prods, dict):
                prods = [prods]
            for item in prods:
                if isinstance(item, dict) and int(item.get("LicenseStatus") or 0) == 1:
                    producto_sel = item
                    break
            if producto_sel is None and prods and isinstance(prods[0], dict):
                producto_sel = prods[0]
    except Exception:
        pass

    return _clasificar_licencia_windows(
        producto_sel,
        tiene_llave_uefi=tiene_llave_uefi,
        kms_registro=kms_reg or svc_kms,
    )


class LectorHardware:
    """
    API pública del módulo de hardware.

    Uso:
        datos = LectorHardware.escanear_entorno()

    El dict resultante conserva TODAS las claves legacy para no romper
    el código existente en main.py y guardar_reporte_final().
    """

    @staticmethod
    def escanear_entorno() -> dict[str, Any]:
        """
        Recopila telemetría completa de la máquina.
        Garantiza retrocompatibilidad con las claves originales.
        """
        mb = _escanear_motherboard_bios()
        tipo_eq = _escanear_tipo_equipo()
        modelo_eq = _escanear_modelo_equipo(mb, tipo_eq.get("tipo_equipo", "desktop"))
        cpu = _escanear_cpu()
        ram = _escanear_ram()
        gpu = _escanear_gpu()
        storage = _escanear_almacenamiento()
        red = _escanear_red_y_so()
        licencia_win = _escanear_licencia_windows()

        datos: dict[str, Any] = {}
        datos.update(mb)
        datos.update(tipo_eq)
        datos.update(modelo_eq)
        datos.update(cpu)
        datos.update(ram)
        datos.update(gpu)
        datos.update(storage)
        datos.update(red)
        datos["licencia_windows"] = licencia_win

        if datos.get("tipo_equipo") != "laptop" and _tiene_firma_portatil(datos):
            datos["tipo_equipo"] = "laptop"

        return datos


def calcular_health_score(hw: dict[str, Any]) -> int:
    """
    Calcula un score de salud del sistema del 0 al 100 basado en reglas de auditoría.

    Penalizaciones aplicadas:
      -20  Disco C: saturado (≥ 90 % de uso)
      -10  Disco C: casi lleno (≥ 80 %)
      -15  RAM muy limitada (< 4 GB)
      -10  RAM escasa (< 8 GB)
      -15  CPU con latencia alta (ping ≥ 200 ms)
      -10  GPU no detectada
      -10  Sin adaptador de red activo
      -5   Frecuencia de CPU muy baja (< 1.5 GHz)
    """
    score = 100

    for part in hw.get("particiones", []):
        letra = str(part.get("letra", "")).strip().upper()
        if letra.startswith("C") or letra == "/":
            uso = part.get("uso_pct", 0)
            if uso >= 90:
                score -= 20
            elif uso >= 80:
                score -= 10
            break

    ram_mb = hw.get("ram_total_mb_int", 0)
    if ram_mb < 4096:
        score -= 15
    elif ram_mb < 8192:
        score -= 10

    latencia_str = str(hw.get("latencia_ms", "N/A"))
    if latencia_str != "N/A":
        try:
            latencia_num = int(latencia_str.split()[0])
            if latencia_num >= 200:
                score -= 15
        except (ValueError, IndexError):
            pass
    if hw.get("adaptador_activo", "Ninguno") in ("Ninguno", ""):
        score -= 10

    if hw.get("gpu_principal", "No detectada") in ("No detectada", ""):
        score -= 10

    freq_actual = hw.get("frecuencia_actual_ghz", 0.0) or 0.0
    if 0 < freq_actual < 1.5:
        score -= 5

    return max(0, min(100, score))


def _formatear_gpu(hw: dict[str, Any]) -> str:
    """'NVIDIA GeForce RTX 5060 Ti (4095 MB)' o listado de todas las GPUs."""
    gpus = hw.get("gpus", [])
    if not gpus:
        return hw.get("gpu_principal", "No detectada")
    partes = []
    for g in gpus:
        vram = int(g.get("vram_mb", 0))
        vram_str = f"{vram} MB" if vram else "VRAM desconocida"
        partes.append(f"{g.get('nombre', 'GPU desconocida')} ({vram_str})")
    return " | ".join(partes)


def _formatear_almacenamiento(hw: dict[str, Any]) -> str:
    """'NVMe SSD Patriot 240GB / HDD WD 1TB' con estado de saturación."""
    discos = hw.get("discos_fisicos", [])
    if not discos:
        return "Sin discos detectados"
    partes = []
    for d in discos:
        cap = d.get("capacidad_gb", 0)
        cap_str = f"{cap:.0f} GB" if cap else "?"
        partes.append(f"{d.get('tipo', '?')} {d.get('modelo', '?')} {cap_str}")
    return " / ".join(partes)


def _inferir_refrigeracion(hw: dict[str, Any]) -> str:
    """
    Infiere el tipo de refrigeración a partir del nombre de la CPU y la
    telemetría disponible. Sin sensor directo en WMI, usamos heurísticas.
    """
    cpu = (hw.get("nombre_cpu", "") or "").lower()
    if any(x in cpu for x in ("celeron", "pentium", "atom", "n4", "n5", "n3")):
        return "Cooler Integrado (Low-TDP)"
    if any(x in cpu for x in ("i9", "ryzen 9", "threadripper", "epyc")):
        return "Cooler Torre Alta Gama / AIO Líquida (inferido)"
    if any(x in cpu for x in ("i7", "ryzen 7", "i5", "ryzen 5")):
        return "Cooler Torre Aire o AIO (inferido)"
    return "Cooler Estándar (inferido)"


def construir_resumen_para_bd(
    ticket_id: str,
    hw: dict[str, Any],
    diag: dict[str, Any],
    owner_dni: str | None = None,
) -> dict[str, Any]:
    """
    Construye el payload limpio y tipado para la tabla 'reportes_diagnostico'.

    Todas las columnas de texto se coercen a str; health_score a int;
    specs_json es un dict nativo (supabase-py lo serializa a jsonb).
    """
    cpu_info   = f"{hw.get('nombre_cpu', '?')} ({hw.get('nucleos_fisicos', '?')}C/{hw.get('nucleos', '?')}T @ {hw.get('frecuencia_actual_ghz', '?')} GHz)"
    ram_info   = f"{hw.get('ram_total_mb', '?')} {hw.get('ram_tipo', '')} @ {hw.get('ram_velocidad_mhz', '?')} MHz ({hw.get('ram_ranuras_ocupadas', '?')} ranuras)"
    gpu_info   = _formatear_gpu(hw)
    storage    = _formatear_almacenamiento(hw)
    refrig     = _inferir_refrigeracion(hw)
    hscore     = calcular_health_score(hw)
    tipo_final = hw.get("tipo_equipo")
    if tipo_final != "laptop" and _tiene_firma_portatil(hw):
        tipo_final = "laptop"

    modelo_com = str(hw.get("equipo_modelo_comercial") or "").strip()
    mb_mod_raw = str(hw.get("mb_modelo") or "?").strip()
    if tipo_final == "laptop" and modelo_com and hw.get("equipo_es_oem"):
        placa_base = f"{modelo_com} (Placa {mb_mod_raw})" if mb_mod_raw and mb_mod_raw != "?" else modelo_com
    else:
        placa_base = f"{hw.get('mb_fabricante', '?')} {mb_mod_raw}"

    clean_dni = str(owner_dni).strip() if owner_dni else ""
    lic = hw.get("licencia_windows") if isinstance(hw.get("licencia_windows"), dict) else {}
    specs_json: dict[str, Any] = {
        "tipo_equipo": tipo_final or "desktop",
        "modelo_comercial": modelo_com or None,
        "modelo_codigo": hw.get("equipo_codigo_modelo") or None,
        "owner_dni": clean_dni or None,
        "tipo_evento": str(diag.get("tipo_evento") or "Diagnóstico"),
        "chassis_types": hw.get("chassis_types", []),
        "bios": {
            "version": hw.get("bios_version"),
            "fecha":   hw.get("bios_fecha"),
        },
        "cpu": {
            "nombre":          hw.get("nombre_cpu"),
            "nucleos_fisicos": hw.get("nucleos_fisicos"),
            "nucleos_logicos": hw.get("nucleos"),
            "freq_base_ghz":   hw.get("frecuencia_base_ghz"),
            "freq_actual_ghz": hw.get("frecuencia_actual_ghz"),
            "uso_total_pct":   hw.get("uso_cpu_total"),
        },
        "ram": {
            "total_mb":    hw.get("ram_total_mb_int"),
            "libre_mb":    hw.get("ram_libre_mb_int"),
            "uso_pct":     hw.get("ram_uso_pct"),
            "tipo":        hw.get("ram_tipo"),
            "velocidad":   hw.get("ram_velocidad_mhz"),
            "ranuras":     hw.get("ram_ranuras_ocupadas"),
            "modulos":     hw.get("ram_modulos", []),
        },
        "gpus": hw.get("gpus", []),
        "discos": {
            "fisicos":     hw.get("discos_fisicos", []),
            "particiones": hw.get("particiones", []),
        },
        "red": {
            "adaptador":  hw.get("adaptador_activo"),
            "ip":         hw.get("ip_local"),
            "latencia_ms":hw.get("latencia_ms"),
        },
        "so": {
            "nombre":  hw.get("so"),
            "build":   hw.get("so_build"),
            "uptime":  hw.get("uptime"),
            "licencia": {
                "aplicable": lic.get("aplicable"),
                "estado": lic.get("estado"),
                "canal": lic.get("canal"),
                "activa": lic.get("activa"),
                "permanente": lic.get("permanente"),
                "dias_restantes": lic.get("dias_restantes"),
                "tiene_llave_uefi": bool(lic.get("tiene_llave_uefi")),
                "partial_key": str(lic.get("partial_key") or "")[-5:],
                "sospecha_kms": bool(lic.get("sospecha_kms")),
                "servidor_kms": str(lic.get("servidor_kms") or ""),
            } if isinstance(hw.get("licencia_windows"), dict) else None,
        },
        "diagnostico_codigo": diag.get("codigo"),
    }

    return {
        "id_ticket":       str(ticket_id),
        "cpu":             str(cpu_info),
        "ram":             str(ram_info),
        "gpu":             str(gpu_info),
        "almacenamiento":  str(storage),
        "placa_base":      str(placa_base),
        "refrigeracion":   str(refrig),
        "health_score":    int(hscore),
        "diagnostico":     str(diag.get("categoria", "") + " — " + diag.get("subcategoria", "")),
        "solucion":        str(diag.get("solucion", "")),
        "specs_json":      specs_json,
    }
