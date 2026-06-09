# Investigación 5 — Auditoría dura + radar de Skills (2026-06-08)

> Auditoría sin maquillaje del estado real + investigación destilada de ideas y posibles
> Skills. Aplica el DoD con dureza (🟢 = servicio real + recibo). Compañera de
> `RADAR_INNOVACION.md` (que ya barrió L1-L4) y de `ESTADO_Y_ROADMAP.md` (estado canónico).

## Marco (dos hechos duros)
- **Reloj regulatorio España**: VeriFactu obligatorio **1-jul-2027** (IS antes 1-ene-2027);
  factura-e B2B **1-oct-2027** (>8M€) / 2028 (resto); **multa hasta 50.000 €** por software
  no conforme. Mercado **forzado por ley**.
- **Frontera técnica**: consenso 2026 = **los SLM locales son el futuro de los agentes**
  (NVIDIA); Microsoft ya tiene **Fara-1.5**, computer-use SOTA **on-device**. Es la tesis
  local-first de Loombit.

---

## PARTE A — Auditoría dura

### 🟢 de verdad vs "humo honesto" (🟡)
| Capa | Real (🟢, con recibo) | Solo código+tests (🟡) |
|---|---|---|
| Conectores | OAuth Google · Gmail send · Calendar create · Gmail search · Calendar read | Microsoft Graph |
| Percepción | Brief con datos reales · contactos reales · galaxia_intel (importes con procedencia) | — |
| Plataforma | Servidor MCP (protocolo) · nombres humanos · proactividad | MCP capacidades envueltas |
| **Vertical (el producto)** | — | **Cobros e2e · Conciliación N43 · Fiscal/303 · VL escaneadas · Pilot** |

### Veredicto
Base de **conectores 🟢 excelente** + mucha **"inteligencia" 🟡** — pero el producto (cerrar
UN flujo vertical de punta a punta con recibos ×5) **NO está cerrado**. Muchos cerebros
(cobros, conciliación, fiscal, VL) sin un bucle real completado. Es el riesgo que el propio
`PLAN_MAESTRO` nombra: **anchura en vez de profundidad**.

### Progreso vs las 2 métricas
- **Operatividad** (🟢/anunciadas): **~45%**.
- **Autonomía supervisada** (pasos del bucle /7): **~5/7 ≈ 70%** — falta EJECUTAR e2e repetible ×5.
- **Fases**: 0✅ 1✅ 2🟢 **3🟠←el trabajo real** 4🟢 5🟡 6⬜ 7⬜.

### Gaps duros (para uso diario de un autónomo)
1. Ningún flujo cerrado ×5 con recibos (cobros e2e).
2. Sin entrada de datos reales sostenida (cuentas a cobrar nacen por API, no de facturas/banco).
3. Conciliación sin extracto N43 real.
4. Pilot sin recibo real (AEAT/banca/Sede).
5. VeriFactu sin empezar — lo único con fecha legal y multa.

### Deuda / riesgos
- **8 ficheros >400 líneas**: `agent/memory.py` 950, `tools/pilot.py` 694, `routers/computer.py`
  673, `agent/loop.py` 647, `skill_blanca_oauth.py` 550, `pilot/windows_control.py` 537,
  `conciliacion.py` 445, `tools/connectors.py` 436.
- `CLAUDE.md` miente ("Fase actual: Fase 1", cerrada en D-24).
- Lección D-27 (datos de prueba que llegaron al panel real) → falta un **gate anti-seed**.

### Dirección
Dejar de añadir anchura; **cerrar profundidad: cobros 🟢 ×5 + lazo de entrada real**. En
paralelo, **arrancar VeriFactu** (reloj legal + venta de 50k€). El resto (galaxia, MCP, VL) es
infraestructura ya construida, no el cuello de botella.

---

## PARTE B — Radar de Skills (priorizado, duro)

**Foso de Loombit:** opera TUS herramientas en local, sin que los datos salgan, con marco
legal español y profundidad administrativa. Rivales = cloud/US/genéricos. Ser "el operador
privado del autónomo español", no competir de frente.

| Pri | Skill (taxonomía) | Tesis | Fase | Esfuerzo | DoD |
|---|---|---|---|---|---|
| 1 | `Skill D Fiscal · VeriFactu` | Mercado forzado por ley + multa 50k€; `expedientes.py` (cadena de hashes) ya es base | 4+ | M | 1 factura conforme (QR + "VERI*FACTU" + hash) |
| 2 | `Skill A WhatsApp` (Pilot) | 92% de PYMEs; Meta valida+amenaza; foso = opera TU WhatsApp local | 6 | M-L | 1 conversación real con aprobación |
| 3 | `Skill A Banca · N43/PSD2` | Cierra conciliación → cierra cobros e2e | 3 | M | 1 extracto N43 real conciliado e2e |
| 4 | `Skill W Pilot` con Fara-1.5 | Computer-use SOTA local → planner+verifier para webs | 6 | L | 1 trámite web verificado |
| 5 | `Skill D Cobros` — cerrar e2e | Terminar el flujo ×5 con recibos = LA prioridad de producto | 3 | M | Bucle ×5 sin intervención salvo aprobación |
| 6 | `Skill D Laboral · Seguridad Social` | Nóminas, RED, autónomos = cuña 2 natural | Futuro | L | (no ahora) |
| 7 | `Fábrica de Skills` (flywheel) | Loombit que fabrica sus skills; foso que compone | 5+ | L | 1 plantilla desde casos reales |
| 8 | `Skill D Fiscal · 303/130/390 auto-draft` | Borrador desde facturas reales; el humano presenta (riesgo cero) | 3-4 | M | 1 borrador 303 de un trimestre real |

### Apuestas técnicas
- **SLM-first confirmado** (NVIDIA/Microsoft): la arquitectura local 14B/7B es la dirección
  correcta. Doble vía: SLM para tool-calling, 14B para razonar.
- **Fara-1.5 / MagenticLite** (Microsoft): evaluar como motor del Pilot navegador.
- **Qwen3-VL** (radar L3): upgrade del VL-7B recién cableado.
- **MCP cliente** (ya somos servidor): consumir herramientas de terceros locales → ecosistema.

### Recomendación de un párrafo
Próximas 2-3 sesiones, una consigna: **cerrar cobros e2e a 🟢 ×5** (`Skill A Banca N43` + lazo
factura→cuenta). En paralelo, **arrancar `Skill D Fiscal VeriFactu`** (reloj legal, vende solo).
Pausar anchura. Eso convierte "demo impresionante" en "producto que un autónomo paga".

### Fuentes
- [AEAT VeriFactu](https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/nota-informativa-ampliacion-plazo-adaptacion-facturacion.html)
- [El Economista — factura-e 2027](https://www.eleconomista.es/legal/noticias/13847044/03/26/la-nueva-factura-electronica-para-pymes-y-autonomos-arrancara-el-1-de-julio-de-2027.html)
- [NVIDIA — SLM agents](https://research.nvidia.com/labs/lpr/slm-agents/) · [arXiv 2506.02153](https://arxiv.org/abs/2506.02153)
- [Microsoft Fara-1.5 / MagenticLite](https://aitoolly.com/ai-news/article/2026-05-22-microsoft-research-unveils-magenticlite-magenticbrain-and-fara15-a-new-era-of-agentic-experiences-fo)
