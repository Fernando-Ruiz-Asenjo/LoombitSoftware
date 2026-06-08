# Capacidades y herramientas — cómo y con qué construimos Loombit

Análisis honesto de lo que YO (Claude en Cowork) puedo aportar a este proyecto, qué
herramientas reales usaremos en cada fase, y dónde están mis límites. Sin adornos.

## A. Mis capacidades reales (verificadas en esta sesión)

| Capacidad | Qué hace | Límite honesto |
|---|---|---|
| Ficheros (read/edit) + shell | Crear/editar código, correr Python/Node, **git local y push a GitHub**, tests | El entorno actual SÍ permite push al remoto (verificado 2026-06-08) |
| Búsqueda y fetch web | Investigar docs, APIs, mercado | Algunas páginas JS no renderizan en fetch simple |
| Sub-agentes | Lanzar revisores/QA en paralelo (p. ej. revisión de seguridad) | Cada uno arranca sin contexto previo |
| Tareas programadas (cron) | Ejecutar trabajo recurrente (briefing diario, daemon de aprendizaje) | Corre en este entorno, no en tu máquina aún |
| Artifacts (HTML vivo) | Páginas que leen de tus conectores y se re-abren con datos frescos | Solo Chart.js/Grid.js/Mermaid desde CDN |
| Skills de documento | Generar `.docx`, `.xlsx`, `.pdf`, `.pptx` reales | — |
| skill-creator | Empaquetar las "skills" de Loombit como skills reutilizables de Cowork | No edita skills ya instaladas en esta sesión |
| Claude en Chrome | Automatizar navegador real (DOM-aware) | Requiere extensión conectada |
| Computer use | Controlar el escritorio (capturas, clics) | Navegadores en modo solo-lectura; terminales sin escritura |

## B. Conectores reales disponibles (en el registro, sin conectar todavía)

Esto es lo más importante para el "con qué". Loombit necesita oficina real, y estos
conectores los podemos enchufar **hoy** (requieren tu autorización OAuth):

- **Gmail** — `search_threads`, `get_thread`, `create_draft`, `list_drafts`, `list_labels`.
- **Google Calendar** — `create_event`, `list_events`, `find_free_time`, `update_event`, `delete_event`.
- **Google Drive** — `search_files`, `read_file_content`, `create_file`.
- **Microsoft 365** — `outlook_email_search`, `outlook_calendar_search`, SharePoint/OneDrive.
- **Exa** — búsqueda web + búsqueda de documentación de código, para investigación técnica.

Doble uso estratégico:
1. **Prototipar y validar** los flujos de oficina de Loombit en horas, no semanas:
   yo manejo Gmail/Calendar reales vía estos conectores para descubrir el contrato
   real antes de que tú lo implementes en el backend FastAPI.
2. **Referencia de verdad**: lo que estos conectores devuelven es el shape real al
   que el código de Loombit (`skill_blanca_connector_execution.py`) debe ajustarse.

## C. Tu stack (lo que ya tienes)

- FastAPI + Python, núcleo blanco + skills (buena base, ya verificada).
- LM Studio + Qwen local (`qwen2.5-14b-instruct` instructor, `qwen2.5-coder-7b-instruct` coder).
- Capa de conectores con modos local_outbox/SMTP/Google/Microsoft (código real 🟡).
- Jetson Orin NX como objetivo de despliegue (hardware aún no comprado).

## D. Mapa fase -> herramienta (el "cómo y con qué")

| Fase | Construyo con | Tú aportas |
|---|---|---|
| 0 Fundación | shell (estructura, CI), ficheros, este repo | Subir a GitHub (te doy el comando) |
| 1 Verdad de conectores | Gmail/Calendar connectors para validar contrato; sub-agente de revisión de seguridad | Crear app OAuth en Google Cloud + cuenta de prueba |
| 2 Percepción real | Gmail/Calendar/Drive (read-only) para el brief real; skills xlsx/pdf para informes | Consentir las fuentes (OAuth) |
| 3 Bucle autonomía | shell para implementar el flujo; conectores como oráculo de datos reales | Aprobar acciones (humano en el bucle) |
| 4 UI humana | **Artifact HTML vivo** que lee de los conectores = la nueva UI de Loombit | Feedback de usabilidad |
| 5 Aprendizaje | **Tarea programada (cron)** = el daemon de memoria operativa | Revisar plantillas propuestas |
| 6 Endurecimiento | sub-agentes para revisión de seguridad; Claude en Chrome para Skill Pilot navegador | Definir política de empresa/consentimiento |
| 7 Jetson | shell para portar/benchmarkear scripts | Comprar Jetson y correr el benchmark físico |

## E. Mis límites (para que nunca te mienta sobre lo que puedo)

- **Push a GitHub:** en el entorno actual SÍ puedo commitear y hacer push al remoto
  (verificado el 2026-06-08). El push directo a `main` puede pedir tu autorización
  explícita según el clasificador de permisos.
- **No tengo tus credenciales**: cada conector Google/Microsoft requiere que TÚ
  autorices el OAuth. Yo no puedo "auto-conectarme" a tu correo.
- **No tengo Jetson**: cualquier número de rendimiento sobre la placa lo mides tú.
- **No entreno pesos de modelos**: el "aprendizaje" de Loombit es memoria operativa
  (patrones de casos/recibos), no fine-tuning.
- **El sandbox es efímero**: lo que importa se guarda en tu carpeta o en GitHub.

## F. Siguiente acción concreta que puedo hacer ya

1. Conectar Gmail + Google Calendar (tú autorizas) y hacer un **brief real de tu día**
   para probar la Fase 2 en vivo, hoy.
2. O empezar la Fase 0 de código: partir el `main.py` monolítico en routers.
3. O montar el **artifact** del dashboard humano (Fase 4) como prototipo.

Tú eliges el primer movimiento; cualquiera de los tres avanza el plan de verdad.
