# Diseño — Adaptador de navegador del Skill W Pilot (batir a Gemini Spark en local)

> Cierra el pendiente del roadmap del Pilot ("adaptador Playwright/CDP + contrato de coordenadas") y el
> encargo: **manejar el equipo (con permisos) y Chrome MUY BIEN** para órdenes complejas tipo "comprar
> billetes de avión", **en local + gobernado**. Cruza la **destilación de Gemini Spark** (D-92) con el
> barrido SOTA (D-92/§7) y los patrones de browser-use / Skyvern / OpenClaw.
>
> **Estado:** el **núcleo gobernado** (allowlist + gate-antes-de-pagar + a11y-model) está **construido y
> testeado** (`pilot/browser.py`, 🟡). El *driving* Playwright/CDP y la visión-fallback son **🟠/⬜
> DECLARADOS** (necesitan dependencia Playwright + el VL + verificación en vivo).

## 1. Cruce con Gemini Spark — la vara contra la que diseñamos

Gemini Spark (Google I/O 2026): asistente agéntico **24/7 en VMs de Google Cloud** que lee tu
correo/Drive/Sheets, organiza agenda, **redacta y actúa**, e integra terceros (Uber/OpenTable/Zillow).
Su "comprar/reservar" ocurre en la nube, con tus datos en Google.

| Capacidad de Gemini Spark | Respuesta de Loombit (local + gobernada) |
|---|---|
| Ejecuta reservas/compras en webs (cloud) | Adaptador de navegador **local** (Playwright/CDP) + **gate humano ANTES del pago** |
| Tus datos viajan a las VMs de Google | **Local-first**: el navegador y las credenciales viven en tu máquina |
| Modelo frontera, siempre encendido | 14B local (no iguala el razonamiento bruto) → se **compensa con a11y-first + gate + foso** |
| "Confía en Google" | **No-mentir + gate sagrado + cuarentena de la web no confiable (CaMeL)** |
| Horizontal/personal | **Admin profundo español** (cobros, 303, VeriFactu) sobre el mismo motor |

**Dónde se gana:** lo que Spark hace en cloud, Loombit lo hace **en local y pausando antes de cualquier
efecto/pago** — el cuadrante (local + gobernado) donde Google no puede entrar sin romper su modelo.

## 2. Decisión de arquitectura (ya resuelta por el radar — no re-debatir)

**Accessibility-tree-FIRST + visión SELECTIVA.** AgentOccam y la práctica de producción: el a11y-tree
**iguala o bate a visión** en los benchmarks y **ahorra tokens** (decisivo para el 14B local); la visión se
usa **solo** para lo no-accesible/muy-visual. Es la **misma filosofía** que el `ui_snapshot`/UIA-first que
el Pilot ya aplica en el escritorio. Listón: WebVoyager (~89% browser-use OSS) / WebArena; **OSWorld** para
control de equipo (SOTA 2026 ~72-82%, **sigue fallando → el gate humano ES la red de seguridad**).

## 3. Arquitectura del adaptador (3 capas)

1. **Gobernanza (CONSTRUIDA hoy, `pilot/browser.py`, determinista, sin red):**
   - `BROWSER_STEPS` = espacio de acciones a11y-first (navigate, a11y_snapshot, click_element, type_text,
     select_option, extract, scroll, wait) — patrón inspirado en el *controller* de browser-use.
   - `dominio_permitido()` — **allowlist de dominios, CERRADA por defecto** (el navegador no va a cualquier
     sitio). Estilo `allowed_domains` de browser-use.
   - `es_paso_consecuente()` + `validar_secuencia()` — marca **pago/compra/envío/borrado** → **GATE humano
     ANTES de ejecutar**. Es la pieza que a Spark/OpenClaw les falta y a Loombit le sobra.
   - `SAFETY_CONTRACT` — mismo que `executor.py` (local, no-sube, no-ejecuta-sin-aprobación, recibos, dry_run).
2. **Driving (🟠 DECLARADO):** Playwright/CDP que abre Chrome, toma el `a11y_snapshot` real, ejecuta
   `click_element` por índice del árbol (no coordenadas frágiles), con recibo local. Dependencia Playwright
   (lazy/opcional, como `pypdf` en `docs_intel`). Auth por **perfil real** (credenciales guardadas, no
   hardcoded).
3. **Visión-fallback (⬜, usa el VL local):** estilo Skyvern — cuando el a11y-tree no basta, `click(prompt=
   "el botón verde Comprar")` + **extracción estructurada con JSON schema** (confirmación, precio).

## 4. Qué copiar de cada repo (a minar al implementar la capa 2/3)

- **browser-use** (`browser_use/controller`, `browser_use/dom`): el registro del **espacio de acciones** y
  cómo construye el árbol DOM/a11y y mapea elementos clicables por índice; los *recovery loops*; `BrowserProfile`.
- **Skyvern**: **visión-fallback** (click por prompt) + **extracción con JSON schema** + robustez sin XPaths.
- **OpenClaw**: la **cascada de permisos `global→provider→agent→session→sandbox`** (modelo para extender el
  Policy Plane a la navegación), el **sandbox Docker** del navegador (CDP) y el patrón **node-as-tools**.

## 5. Plan por incrementos (anti-dispersión)

1. **🟡 hecho:** núcleo gobernado (`pilot/browser.py`) + golden (`tests/test_pilot_browser.py`).
2. **🟠 siguiente:** capa de driving Playwright/CDP (dependencia opcional) + `a11y_snapshot` real + recibo +
   tool `browser_*` registrada con `requires_approval` en pasos consecuentes (integra el gate existente).
3. **⬜ después:** visión-fallback con el VL local (Skyvern-style) + extracción con schema.
4. **⬜ luego:** cascada de permisos por capa (OpenClaw) en el Policy Plane.
5. **🟢 cierre:** un "comprar billetes" e2e contra una web real **de prueba**, pausando en el pago, con
   recibo — y correos/efectos de prueba SOLO a `admin@construiaapp.com`.

## 6. Frontera honesta

- Lo construido hoy es la **gobernanza** (allowlist + gate + a11y-model), no el control real del navegador
  (eso es la capa 2, 🟠, necesita Playwright + verificación en vivo).
- El 14B local **no iguala** a un frontera-cloud en razonamiento; la apuesta es **a11y-first (barato) + gate
  + foso local**, no ganar en potencia bruta.
- Código de browser-use/Skyvern/OpenClaw leído a nivel **arquitectura/doc**, no fichero-a-fichero (un raw
  de browser-use dio 404); los ficheros a minar quedan nombrados arriba para leerlos al construir la capa 2.
