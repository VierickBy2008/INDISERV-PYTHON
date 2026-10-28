# FTD — Fase 3: UI Visual, Reportes y Sincronización en la Nube

**Proyecto:** IndiServ Analytica  
**Estado:** ✅ IMPLEMENTADA  
**Fecha:** 2026-10-04

---

## Intent

Cerrar el Plan Integral de Expansión implementando la capa de visualización interactiva del hardware, la exportación dual estructurada y la sincronización a la nube mediante Supabase REST API en segundo plano.

## Scope

| Área | Entregable |
|---|---|
| `main.py` | `pantalla_hardware_map` (CTkCanvas) + Actualización de GUI en `pantalla_diagnostico` |
| `main.py` | `guardar_reporte_final` expandido para exportación dual (TXT y JSON) y llamado asíncrono a la nube |
| `core/cloud_gateway.py` | Nuevo método estático `subir_ticket` para enviar el payload estructurado a Supabase |

## Checklist

- [x] **Diagrama Visual del Hardware (Hardware Map)** — Implementado con `CTkCanvas` dibujando una representación de la Motherboard y sus conectores/componentes clave.
- [x] **Resaltado Inteligente** — El componente afectado se extrae del `dictamen_final['categoria']` y se resalta en rojo `#E63946` con contorno más grueso y el símbolo `⚠`.
- [x] **Exportación Técnica Dual** — El método `guardar_reporte_final` ahora genera el ticket en TXT (formato clásico con telemetría extendida de Fase 1) y un gemelo idéntico en formato estructurado `.json` para analítica local.
- [x] **Sincronización a Supabase** — Añadido método `CloudGateway.subir_ticket(...)` usando `requests.post` a `rest/v1/tickets_diagnostico`.
- [x] **Hilo en Segundo Plano (Thread-safe)** — La subida a la nube corre sobre un hilo `threading.Thread(target=tarea_nube, daemon=True)` para evitar colgar la aplicación si la conexión al BaaS (Supabase) tarda o falla.

## Evidencia (Salida de Exportación JSON Dual)
```json
{
    "ticket_id": "USER-TICKET-8234",
    "operador_dni": "12345678",
    "telemetria": {
        "nombre_cpu": "AMD Ryzen 7 5700X 8-Core Processor",
        "gpu_principal": "NVIDIA GeForce RTX 5060 Ti",
        "ram_total_mb": 32684
    },
    "diagnostico": {
        "categoria": "Memoria RAM",
        "subcategoria": "Falla de integridad",
        "codigo": 302
    }
}
```

## Resumen del Proyecto y Conformidad con SDD / Arnés Operativo

Con esta fase, **IndiServ Analytica** cumple el 100% de los requerimientos pactados en el Plan Integral.
- Arquitectura 100% Python mantenida (sin C++ / DLLs extras).
- Reglas de retrocompatibilidad cumplidas a lo largo de las 3 fases (las claves legacy en el perfilador siguen ahí).
- El sistema ha pasado de ser un simple formulario a un Sistema Experto multihilo, con perfilamiento a bajo nivel, lógica fuzzy inferencial, stress testing y persistencia cloud.

---

El plan ha concluido.
