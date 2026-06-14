# MÉTODO — Deep Research por Vueltas (harness 3-votos) · artefacto reutilizable

> **Qué es esto:** el método con el que se hizo la investigación de innovación/mercado de Loombit
> (junio 2026), documentado para **re-ejecutarlo** cuando haga falta. No es un relato: es un **molde**
> con su plantilla de prompt, sus fases y sus reglas de honestidad. Si vas a investigar algo para
> Loombit (un competidor, una tecnología, una cuña), **usa esto**.
>
> **Procedencia:** sesión "Loombit skills and market opportunities" (cliSessionId `6d7fa254`) +
> re-lanzamiento V5 (run `wf_91899f87-01b`, 2026-06-14). Destilados resultantes:
> `docs/DESTILADO_STUFF_CAJA_AGENTE_LOOMBIT_2026-06-14.md`. Señales en `docs/RADAR.jsonl` (D-90).

---

## 1. Por qué este método (y no "preguntar y creer")

Investigar con un LLM tiene un fallo mortal: **suena verídico aunque no lo sea**. Blogs reciclan cifras
("$450B/año", "23 min para reconcentrarse") que nadie verificó nunca. Si Loombit decide su estrategia
sobre humo, construye sobre humo. El método ataca eso con **tres palancas**:

1. **Verificación adversarial a 3 votos.** Cada afirmación falsable se somete a 3 verificadores
   independientes que intentan **refutarla**. Hacen falta **2 de 3 refutaciones para matarla**. Solo lo
   que sobrevive entra en el destilado; **lo refutado va al final, citado** (para no repetir el humo).
2. **Filtro duro por idea** (no "¿es interesante?" sino "¿merece código de Loombit?"):
   **valor alto/muy alto · utilidad grande · visión y trayectoria · gancho monetizable**. Lo que no pasa
   el filtro, se descarta y **no aparece**.
3. **Tres gorras a la vez** (encuadre, no fases): **ingeniero senior de agentes IA · director de
   marketing prosumer · director de think-tank.** Obliga a juzgar cada hallazgo por lo técnico, lo
   comercial y lo estratégico al tiempo — no solo "mola técnicamente".

Encima de todo, **dos invariantes de Loombit** que cada hallazgo debe respetar para sobrevivir:
- **Foso LOCAL:** ¿corre sin que los datos del usuario salgan de la máquina? Si es cloud-only, se dice.
- **Ley fundacional:** el LLM propone / el código dispone + gate humano en el efecto externo. Un patrón
  que ponga al LLM en el camino de control de algo consecuente (€, IBAN, fechas, envíos) **no encaja**.

---

## 2. El harness, fase por fase

Implementado como la skill/`Workflow` **`deep-research`** (fan-out multi-agente). Cinco fases:

| Fase | Qué hace | Regla clave |
|---|---|---|
| **1. Scope** | Descompone la pregunta en **5-6 ángulos** (broad, producto/madurez, licencia, académico/tesis, protocolos, contrarian/escéptico) | un ángulo "contrarian" SIEMPRE, para no auto-confirmarse |
| **2. Search** | Un agente web por ángulo, en paralelo | dedup de resultados; cuenta "novel vs filtered" |
| **3. Fetch** | Dedup de URLs → descarga top ~15-24 fuentes → extrae **afirmaciones falsables** | una afirmación no falsable no se puede verificar → fuera |
| **4. Verify** | **3 votos adversariales por afirmación**; 2/3 refutaciones la matan | el voto se registra (3-0, 2-1, 1-2, 0-3) y queda en el recibo |
| **5. Synthesize** | Fusiona duplicados semánticos, rankea por confianza, **cita fuentes**, separa confirmado vs refutado | "afterSynthesis" < "confirmed": se mergean los que dicen lo mismo |

**Recibo que deja:** run id + `stats` (ángulos, fuentes, afirmaciones extraídas/verificadas/confirmadas/
matadas) + por hallazgo: `claim`, `confidence`, `vote`, `evidence`, `sources`. Eso es lo que hace
**auditable** la investigación: no "me fío", sino "enséñame el voto y la fuente".

---

## 3. Las 5 vueltas (objetivo · mejora del prompt · resultado)

> **Honestidad:** el prompt **verbatim** de V5 está en §4 (lo tengo literal). De V1-V4 documento
> objetivo + resultado (del destilado y del contexto de sesión); el texto literal de sus prompts vive en
> la sesión `6d7fa254`. No reconstruyo verbatim lo que no tengo.

| Vuelta | Objetivo | Resultado | Estado |
|---|---|---|---|
| **V1** | GTM fiscal-España: precios Holded/Quipu, Kit Digital, timing VeriFactu | el job murió (0 bytes); **no se inventaron cifras** | **PENDIENTE** (re-lanzable) |
| **V2** | "La Stuff": ¿qué capa indispensable es Loombit ante un ordenador? | **14 de 88** afirmaciones sobrevivieron | CERRADA (§ destilado 1-10) |
| **V3** | Caja→agente · OpenClaw a fondo · modelos de cualquier tamaño | hueco "fallthrough a agente local" verificado vacío | CERRADA |
| **V4** | Modelos computer-use+grounding+OCR para Jetson Orin NX 16GB | Holo1.5-7B, PaddleOCR-VL, Agent-S2 (con licencias/VRAM) | CERRADA |
| **V5** | UI generativa/adaptativa 2026 (Vercel AI SDK, Thesys C1, tldraw, malleable) | **6 de 25** verificadas; 2 de 5 ejes sin sobrevivir → pendiente V6 | CERRADA (§ destilado 11) |

### Las mejoras de prompt entre vueltas (lo que se aprendió)

Cada vuelta mejoró el molde del prompt. Estas son las mejoras acumuladas (el porqué de cada una):

1. **Exigir madurez real con fuente y fecha** (GA/beta/paper/demo). Sin esto, V2 dejaba pasar "demos"
   como si fueran producto. → ahora cada hallazgo lleva estado de madurez.
2. **"Lo refutado al final, citado".** En vez de tirar el humo, se documenta para no repetirlo. Nació
   tras ver cifras de blog recicladas (§10 del destilado).
3. **Encaje LOCAL + ley propose/dispose como criterio de supervivencia**, no como nota. Un hallazgo que
   no respeta el foso o pone al LLM en el camino de control **no sobrevive**, por bueno que sea técnico.
4. **Honestidad de alcance: "no investigado ≠ ausencia".** V5 lo formalizó: 2 ejes (malleable software,
   protocolos server-driven UI) dieron 0 afirmaciones verificadas → se marcan **pendiente**, NO "no
   existe". Los *leads* descargados se guardan para la siguiente vuelta.
5. **Pedir el desglose explícito (a) adoptar ya / (b) vigilar / (c) descartar y por qué / (d) refutado.**
   Convierte el informe en decisión accionable, no en lectura.
6. **Filtro duro por idea desde el prompt** (valor/utilidad/visión/monetizable), no al final. Recorta el
   ruido en origen.

---

## 4. Plantilla reutilizable (cópiala para la próxima vuelta)

Esta es la forma estable del prompt, generalizada desde V5 (la más evolucionada). Rellena `<...>`:

```
VUELTA <N> — <TÍTULO DEL TEMA> para un operador de IA LOCAL-FIRST (Loombit).

PREGUNTA CENTRAL: <una pregunta, concreta, con el stack de Loombit nombrado:
  FastAPI + LLM local Qwen en Jetson Orin NX 16GB, UI single-page, núcleo blanco + skills>.

EJES A CUBRIR (verifica cada afirmación a 3 votos; solo entra lo verificado, lo refutado al final):
  1. <ángulo broad/primario>
  2. <ángulo producto/madurez>
  3. <ángulo licencia/coste/encaje>
  4. <ángulo académico/tesis>
  5. <ángulo protocolos/estándares>
  (+ el harness añade SIEMPRE un ángulo contrarian/escéptico: seguridad y plano de control)

PARA CADA HALLAZGO QUE SOBREVIVA, EXIGE:
  - Encaje LOCAL-FIRST (¿corre sin enviar datos del usuario a la nube? si es cloud-only, dilo).
  - Cumplimiento de la ley "el LLM propone / el código dispone + gate humano en el efecto externo":
    el patrón NO puede ser el camino de control de nada consecuente (€, fechas, IBAN, envíos).
  - Filtro de valor: valor alto/muy alto · utilidad grande · visión y trayectoria · gancho monetizable.
  - Madurez real (GA / beta / paper / demo) con fuente y fecha.

ENTREGABLE: informe citado con (a) qué adoptar YA y cómo, (b) qué vigilar, (c) qué descartar y por qué,
  (d) lo refutado al final. Si un eje no produce afirmaciones verificadas, decláralo PENDIENTE (no
  ausente) y guarda los leads.
```

**Cómo lanzarla:** `Skill(deep-research, args=<la plantilla rellena>)` → invoca
`Workflow({name:"deep-research", args:...})`. El harness corre en segundo plano y avisa al cerrar.

---

## 5. Reglas de honestidad del método (innegociables)

- **Nada 🟢 sin recibo real.** Un hallazgo verificado es "verificado en esta vuelta", no "hecho en
  Loombit". Construir sobre él sigue exigiendo el arnés y el gate (Definición de Hecho).
- **Self-reported ≠ neutral.** Los benchmarks que se auto-reportan se marcan como tal; no se citan como
  verdad de leaderboard. (Ej.: el OCR en español no está benchmarkeado en ningún candidato → se dice.)
- **Un eje sin supervivientes es PENDIENTE, no vacío.** Guardar los leads para la siguiente vuelta.
- **Lo refutado se publica.** Para no volver a tropezar con el mismo humo.
- **Predicción ≠ hecho.** "Cabe en 16GB", "corre en local" → hasta medirlo en vivo es predicción.

---

## 6. Pendiente abierto

- **V1 (GTM fiscal-España)** sigue pendiente: no hay cifras verificadas de competidores ES. Re-lanzable
  con la plantilla §4.
- **V6 (sugerida por V5):** malleable software / end-user programming (Ink&Switch, Geoffrey Litt) +
  protocolos server-driven UI para render **sin JS/React** (AG-UI, MCP-UI/MCP-apps, A2UI, shadcn
  registry-as-protocol) — la vía Python-native es el hueco real del stack de Loombit. Leads ya en §11.4
  del destilado.

---

## 7. Recibo de conducta (D-70)

Este artefacto deja recibo `innovacion` en `docs/RECIBOS_CONDUCTA.jsonl` (validado por
`tests/test_conducta.py`). Las **mejoras de prompt** de §3 NO se registran como recibo `mejora_prompt`
porque no hay un `eval` con `n_casos` que dé `antes_score`/`despues_score` reales — registrarlas con
números inventados violaría la regla nº 1. Se documentan cualitativamente y basta.
