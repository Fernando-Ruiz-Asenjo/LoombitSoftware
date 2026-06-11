# Handoff — adoptar la BRÚJULA v2 (fusión norma + gobierno)

> Pega el bloque de abajo como primer mensaje de un hilo NUEVO de Claude Code en `C:\Users\fernando\loombit-new`.
> Es autocontenido: el otro hilo no tiene el contexto de esta sesión.

---

```
Eres un agente de código trabajando en Loombit (C:\Users\fernando\loombit-new), el operador
administrativo IA local-first para autónomos/PYMEs en España. Tu tarea: ADOPTAR la BRÚJULA v2 —
el documento que funde la constitución del proyecto con su gobierno — y empezar a implementar sus
mecanismos en el orden de dependencia. Trabaja EN ESPAÑOL.

LEE PRIMERO, EN ESTE ORDEN (no toques nada hasta haberlos leído):
1. docs/BRUJULA_Y_GOBIERNO_V2_FUSION.md  ← el documento a adoptar (constitución + gobierno + tabla
   norma→mecanismo→auditoría + orden de adopción). ES TU MAPA.
2. docs/INFORME_MEJORA_BRUJULA_GOBIERNO_2026-06-11.md  (Tier 1: por qué cada norma necesita mecanismo)
3. docs/INFORME_MEJORA_BRUJULA_TIER2_2026-06-11.md     (Tier 2: unificación, independencia, auto-empuje, capa 14B, estrategia)
4. docs/INFORME_MEJORA_BRUJULA_TIER3_2026-06-11.md     (Tier 3: el techo — base de confianza mínima, residuo irreducible, honestidad)
5. docs/BRUJULA.md y la cabecera de CLAUDE.md          (la v1 vigente, que vas a sustituir/sincronizar)
6. docs/REPARACION_CANONICA.md                         (el método: arnés golden ANTES de tocar, verificar por recibo)

LA TESIS QUE GUÍA TODO: una norma cargada en el contexto no se cumple sola; un mecanismo que te
calificas tú mismo, sin auditor independiente ni sensor que lo vigile, es teatro de verde a otro
nivel. La Ley Fundacional unifica 5 normas en 1: "el LLM nunca está en el camino de control de
confianza para nada consecuente". Todo cuelga de ahí.

REGLAS INNEGOCIABLES MIENTRAS TRABAJAS (son las de la propia brújula que vas a adoptar):
- CONCURRENCIA: puede haber OTRO agente en el mismo árbol. Trabaja en `git worktree` aislado. NUNCA
  `git stash -u` ni toques WIP ajeno. Hoy hay WIP sin commitear sobre docs/BRUJULA.md y varios ficheros
  de agent/ — NO los pises; si necesitas tocar BRUJULA.md, hazlo en tu worktree sobre una rama limpia.
- RAMA + PR, nunca push directo a main (el clasificador lo bloquea; se funde por `gh pr`). Una rama por
  cambio, < ~15 commits. Entrada en docs/DECISIONES.md por cada decisión (D-xx con alternativas y
  reversibilidad). Sincroniza el resumen de la cabecera de CLAUDE.md si cambias la brújula.
- VERIFICA EN VIVO antes de afirmar nada. Gate verde (tests + black + ruff) ANTES de commit. Entorno:
  Bash, no PowerShell. Si tocas Python, reinicia el server :8787. No uses `--no-verify` salvo que el
  gate esté roto Y lo digas en voz alta.
- NO MENTIR (regla nº1): 🟢 solo con recibo de ejecución real. "predicción ≠ hecho". Nunca "100%" ni
  "0%": reporta cobertura medida + lo que falta. Golden NO tautológico (esperado escrito a mano desde
  la fuente, en ROJO antes de arreglar — no copiado del código).
- Correos salientes de prueba SOLO a fernando.ruizasenjo@gmail.com.

QUÉ HACER (orden de la PARTE V del documento de fusión — respeta la dependencia):

PASO 1 — ADOPCIÓN FORMAL (barato, alto valor):
  - En tu worktree, propón en PR sustituir docs/BRUJULA.md por la v2 (puedes partir de
    BRUJULA_Y_GOBIERNO_V2_FUSION.md, ajustando lo que veas). Sincroniza la cabecera de CLAUDE.md.
  - Saca el ESTADO VOLÁTIL de CLAUDE.md a docs/ESTADO_Y_ROADMAP.md (hoy CLAUDE.md se contradice:
    dice "Fase 1" y "Fase 1 CERRADA"; el Pilot "✅" cuando está roto; "84 tests" cuando hay ~500).
    Norma nueva: ningún estado fechado en la constitución.
  - Abre D-xx en DECISIONES.md explicando la adopción y el orden.

PASO 2 — P0 de gobierno (mayor radio de daño primero):
  - §SEG: crea la suite de inyección como golden (5-10 correos-trampa con órdenes incrustadas, IBAN
    nuevo, URL de imagen exfiltradora). HOY "datos≠órdenes" tiene CERO tests. El operador debe ignorar
    la orden incrustada y/o pausar en el gate. Arnés golden ANTES de cualquier cambio de código.
  - §GOB-2: decide el gate canónico (hook .githooks/pre-commit fiable vs CI `quality`) y PROHÍBE
    `--no-verify` en el flujo. Quita la ambigüedad actual.

PASO 3 — el cimiento (§GOB-1):
  - Diseña el Capability Policy Plane (loombit_operator/policy/authority_plane.py + policies.py): la
    superficie única donde el gate de efecto, CaMeL, "cifras por código" y "datos≠órdenes" son
    POLÍTICAS. Empieza por inventariar (RC paso 1) DÓNDE entran hoy datos no confiables en el plan/las
    tools consecuentes. Golden de autoridad (10 tests que violan cada eje, rojo→verde).

PASO 4 — cerrar el auto-empuje (§META-1) e independencia (§GOB-3):
  - scripts/verify_brujula.py: parsea la tabla norma→mecanismo (PARTE IV) y detecta violaciones en CI.
  - docs/DEUDA_NORMATIVA.md: backlog auto-alimentado; el agente lo lee PRIMERO cada sesión.
  - .github/CODEOWNERS: auditor ≠ constructor en PRs de subsistemas críticos.

BLOQUE ESTRATÉGICO (§EST-2, Verifactu): las fechas YA están verificadas contra AEAT (2026-06-11,
recibo: nota informativa de ampliación de plazo, sede.agenciatributaria.gob.es). Úsalas tal cual:
IS (Impuesto sobre Sociedades) = 1-ene-2027; autónomos/IRPF (actividades económicas) = 1-jul-2027;
norma vigente = Real Decreto-ley 15/2025, de 2 de diciembre (prorrogó UN AÑO los plazos del RRSIF).
OJO: NO hay ningún hito de obligatoriedad en 2026 — los plazos de 2026 (RD 254/2025) fueron derogados
por esa prórroga; el "hito interno 2026" que circulaba era el plazo anterior. Si re-citas las fechas,
conserva el enlace AEAT. Cualquier OTRA fecha regulatoria que aparezca (factura-e B2B Crea y Crece, AI
Act) sí debe verificarse en su fuente antes de tratarla como hecho.

NO INTENTES HACERLO TODO. Haz PASO 1 + PASO 2 en este primer bloque, con PR(s) verdes y recibos.
Documenta en DECISIONES.md. Si te bloqueas, anótalo en "⭐ PARA FERNANDO" y sigue con otra cosa; no
pares a preguntar obviedades. Cuando termines, deja un handoff de qué quedó hecho (con recibos) y qué
sigue (PASO 3/4).
```

---

**Notas para Fernando (no van en el prompt):**
- El prompt arranca por la adopción + P0 (seguridad + quitar el bypass del gate), que es lo de mayor
  daño evitado y más barato. El cimiento (Policy Plane) y el sensor van en pasos 3-4 para no pedirle al
  otro hilo que se lo coma todo de una.
- Le he metido las salvaguardas de tus gotchas: worktree por la concurrencia, no pisar el WIP de
  BRUJULA.md, Bash no PowerShell, PR no push directo, reiniciar :8787, correos solo a ti.
- Las fechas de Verifactu ya las verifiqué yo contra AEAT (2026-06-11): IS 1-ene-2027, autónomos/IRPF
  1-jul-2027 (RD-ley 15/2025, de 2 dic; sin hito en 2026). El prompt ya las da por buenas — el otro hilo
  no tiene que re-verificarlas, solo el resto de fechas regulatorias (factura-e B2B, AI Act).
- Si prefieres que el otro hilo SOLO adopte la v2 (paso 1) y nada más, borra los pasos 2-4 del prompt.
