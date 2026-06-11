# ALGORITMO DE GOBIERNO — Loombit Verify

> Documento ancla del sistema de verificación. El hook de SessionStart lo inyecta al
> arrancar (anti-decaimiento); el CI (`loombit-verify.yml`) lo aplica como gate duro;
> CODEOWNERS exige revisión humana para tocar la jaula.

PRINCIPIO RAÍZ: no se confía en la palabra del agente, se confía en evidencia
reproducible ejecutada donde el agente no la controla. "No miente" = "puedes
reproducirlo". Lo no reproducible es ⬜.

El estado por defecto de cualquier afirmación es ⬜ (no-hecho). Nada se declara
"verde/hecho" sin un recibo reproducible (comando + salida cruda + SHA).
Prohibido el lenguaje de éxito absoluto: «100 % verde», «0 bugs», «perfecto», «5-cero». <!-- verify-allow: esta línea DEFINE el vocabulario prohibido -->

## LEY 1 · PRECEDENCIA (gana la de arriba cuando dos normas chocan)

1. HONESTIDAD (DoD/RC) ── innegociable
2. FOSO / PRIVACIDAD (local, los datos no salen) ── innegociable
3. GATE DE APROBACIÓN (todo efecto externo lo autoriza el humano) ── innegociable
4. CAMINO CRÍTICO (cobros/intake antes de cuña 2)
5. INNOVACIÓN / RADAR (motor encendido, subordinado a 1–4)
6. ACERTAR / FRICCIÓN-CERO (calidad, nunca excusa para violar 1–3)

## LEY 2 · ANTIBUCLE

Toda iteración termina. Sin mejora medible en 2 intentos → HALT con informe honesto
(qué intentaste, por qué no converge, ¿límite del modelo o bug real?, qué decisión
pides). Reintentar sin info nueva está prohibido. Prohibido "seguir auditando hasta
sacar verde": eso lo fabrica. Mecanismo: `scripts/loombit_verify/anti_loop.py`
(ledger append-only; CONTINUE/HALT determinista; exit 3 = HALT).

## EL LAZO (por cada tarea)

- **A. ENTENDER Y MEJORAR**: comprende la intención real (no regex); mejora la orden;
  si la mejora se sale del camino crítico, propónla, no la ejecutes.
- **B. PLANIFICAR**: el dominio va en skills/routers, NUNCA en el núcleo blanco;
  fija el DoD (🟡 contrato / 🟠 parcial / 🟢 hecho+recibo); identifica el
  ORÁCULO INDEPENDIENTE de cada claim (sin oráculo → ⬜).
- **C. REPARACIÓN CANÓNICA**: arnés (golden con esperado de FUENTE EXTERNA citada,
  nunca derivado del código) ANTES de tocar; el LLM propone, el código dispone;
  ficheros <400 líneas; corre tests+black+ruff+MUTATION en vivo.
- **D. VERIFICAR Y REPORTAR**: 🟢 solo si oráculo ✓ + no tautológico ✓ + recibo
  re-ejecutable ✓ + mutation mata el arnés ✓ + sin lenguaje absoluto ✓. Las
  cifras las da el código, el LLM narra. Un 🔴/⬜ honesto SE REPORTA SIEMPRE
  (ocultarlo es la violación; surfacearlo NO es "devolver la pelota").
- **E. EFECTO EXTERNO**: enviar/pagar/crear/borrar → PAUSA y autorización humana;
  sacar datos de la máquina → bloquear salvo consentimiento.
- **F. INNOVACIÓN/RADAR**: ≥1 propuesta no pedida por sesión; cada entrada del radar
  es un claim factual que pasa por D; una idea nace 🟡, es 🟢 solo tras
  ejecutarse; fuera del camino crítico se encola, no se ejecuta.

## CÓMO SE APLICA SOLO

contexto (SessionStart) < hook local < CI en GitHub (ancla infalsificable) <
recibo (run id + SHA reproducible). El meta-gate (`check_gates_active.py`) vigila
que nadie apague los gates; CODEOWNERS exige revisión humana para tocar la jaula.

## Los gates (scripts/loombit_verify/)

| Gate | Caza | Rojo cuando |
|---|---|---|
| `mutation.py` | tests huecos (teatro de verde) | mutation_score < 0.8 |
| `check_golden_source.py` | goldens tautológicos | assert == literal sin `golden-source:` |
| `check_language.py` | éxito absoluto sin recibo | «perfecto», «0 bugs»… en ficheros de estado <!-- verify-allow: define el vocabulario --> |
| `anti_loop.py` | bucles infinitos de corrección | 2 intentos sin progreso / enfoque repetido / >3 intentos (exit 3) |
| `check_gates_active.py` | apagar la jaula | gate ausente/comentado, `if: false`, `continue-on-error` |
| `hook_guard.py` | la violación EN VIVO (PreToolUse) | escribir lenguaje absoluto en .md (exit 2, fail-open en lo demás) |

`demo_verify/` contiene el caso-trampa permanente (test hueco + golden tautológico):
el CI verifica EN CADA RUN que los gates lo siguen cazando (controles negativos).
