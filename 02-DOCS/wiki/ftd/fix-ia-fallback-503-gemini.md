# Fix Auditoría IA: Resiliencia ante Gemini HTTP 503 y Catálogo Comercial

## Intent
Corregir la regresión reportada donde la Auditoría de IA muestra el código técnico en bruto (ej. `Xiaomi 23053RN02L` o `SM-...`) en lugar del nombre comercial real cuando `gemini-3-flash-preview` responde `HTTP 503` (sobrecarga temporal).

## Scope
- **Incluido (`IndiServ_Web3D`)**:
  - `supabase/functions/analizar-dispositivo-ia/index.ts`: ampliar la cadena de modelos Gemini con reintentos ante `HTTP 503`/`429`, además de enriquecer `buildHeuristicFallback()` con un diccionario amplio de códigos comerciales (Samsung, Xiaomi/Redmi/POCO, Motorola, Pixel, OnePlus, Honor/Huawei, Realme).
  - `src/utils/deviceAuditFallback.js`: sincronizar el diccionario amplio de códigos comerciales en el respaldo cliente.
  - `src/components/MobileScannerView.jsx`: mostrar `aviso_ia` si hubo fallback temporal y botón de reintento claro.
- **Excluido**:
  - `IndiServ_Python` y el esquema SQL de Supabase.

## Checklist
- [x] Identificar los modelos Gemini activos (`HTTP 200`) para la clave configurada.
- [x] Actualizar `supabase/functions/analizar-dispositivo-ia/index.ts` con lista multi-modelo resiliente + reintento ante `503`/timeout.
- [x] Ampliar `src/utils/deviceAuditFallback.js` y mostrar aviso claro en `MobileScannerView.jsx`.
- [x] Compilar (`npm run build` + `npx cap sync android`), subir a `main` e indicar el redespliegue de la Edge Function en Supabase.

## Evidence
- Prueba en vivo contra `analizar-dispositivo-ia`: devolvió `origen: "heuristica"` con `aviso_ia: "Gemini HTTP 503; se aplicó auditoría heurística."`.
- Benchmark directo de modelos disponibles para la API Key:
  - `gemini-3.5-flash-lite` → `HTTP 200` en `2.36 s` (identificó `"Xiaomi Redmi 12"` para `23053RN02L`).
  - `gemini-flash-lite-latest` → `HTTP 200` en `2.89 s`.
  - `gemini-3-flash-preview` y `gemini-flash-latest` → `503`/timeout (>10 s).
- `index.ts` actualizado con `modelsToTry = ["gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3-flash-preview", "gemini-flash-latest"]` y `try/catch` por modelo para no abortar la cadena ante timeout.

## Next
Hacer Deploy de la Edge Function `analizar-dispositivo-ia` en Supabase Dashboard y probar el botón "Verificar Modelo y Piezas con IA" en el teléfono.
