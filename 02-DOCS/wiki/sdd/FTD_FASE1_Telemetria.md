# FTD — Fase 1: Telemetría Profunda y Arquitectura Asíncrona

**Proyecto:** IndiServ Analytica  
**Estado:** ✅ IMPLEMENTADA Y VALIDADA  
**Fecha:** 2026-10-04

---

## Intent

Transformar `core/hardware.py` en un perfilador de hardware exhaustivo sin bloquear la GUI de CustomTkinter, añadir concurrencia en `main.py` y organizar el Dashboard en pestañas modulares.

## Scope

| Área | Entregable |
|---|---|
| `core/hardware.py` | Reescritura completa — perfilador WMI + psutil |
| `main.py` | Hilo de carga + CTkTabview (5 pestañas) |
| Retrocompatibilidad | 7 claves legacy preservadas sin excepción |

## Checklist

- [x] **Motherboard & BIOS** — `ASUSTeK ROG STRIX B550-F GAMING`, BIOS v3621 (13/01/2025) vía `Win32_BaseBoard` + `Win32_BIOS`
- [x] **CPU Granular** — Ryzen 7 5700X, 8 físicos / 16 lógicos, 3.4 GHz actual, uso por núcleo (16 barras)
- [x] **RAM Detallada** — 32 GB DDR4 @2666 MHz, 2 ranuras ocupadas (DIMM_A2 + DIMM_B2) vía `Win32_PhysicalMemory`
- [x] **GPU** — NVIDIA RTX 5060 Ti, 4095 MB VRAM, driver 32.0.16.1714 vía `Win32_VideoController`
- [x] **Almacenamiento** — 2 discos físicos + 2 particiones (C: 90.9% ⚠, D: 74.7%)
- [x] **Red & SO** — Ethernet 2, IP 192.168.31.160, latencia 32 ms a 8.8.8.8, Uptime dinámico
- [x] **Hilo secundario** — `threading.Thread` + splash `CTkProgressBar(mode="indeterminate")` → `self.after(0, callback)` thread-safe
- [x] **Dashboard con pestañas** — General · CPU/RAM · Gráficos · Discos · Red
- [x] **Claves legacy** — `nombre_cpu`, `nucleos`, `ram_total_mb`, `ram_disponible_mb`, `so`, `alerta_ram`, `alerta_cpu` ✅

## Evidence (salida real del escaneo)

```
mb_modelo      : ROG STRIX B550-F GAMING (WI-FI)
bios_fecha     : 13/01/2025   bios_version: 3621
nombre_cpu     : AMD Ryzen 7 5700X 8-Core Processor
nucleos_fisicos: 8   nucleos: 16
freq_base_ghz  : 3.4   freq_actual_ghz: 3.4
ram_tipo       : DDR4   velocidad: 2666 MHz   ranuras: 2
gpu_principal  : NVIDIA GeForce RTX 5060 Ti   vram: 4095 MB
ip_local       : 192.168.31.160   latencia: 32 ms
so             : Windows 11   build: 10.0.26300
uptime         : 2h 23m
```

## Issues corregidos durante la implementación

| Bug | Causa raíz | Fix |
|---|---|---|
| `bios_fecha = '17/e(//Dat'` | WMI CIM moderno devuelve `/Date(epoch_ms)/` no ISO | Parseo por regex + `datetime.utcfromtimestamp` |
| `ip_local = MAC address` | `psutil` en Windows expone MACs antes que IPs | Filtro `"-" not in a.address` añadido |

## Next step — Fase 2

- Matriz ponderada de síntomas múltiples
- Fuzzy matching sobre el árbol de diagnóstico
- Micro-stress test multihilo (10 s CPU + detección de thermal throttling)
