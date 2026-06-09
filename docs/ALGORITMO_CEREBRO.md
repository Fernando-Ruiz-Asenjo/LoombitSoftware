# ALGORITMO DEL CEREBRO — especificación implementable (cognición · agente · fiabilidad)

> Cada comportamiento del cerebro escrito como ALGORITMO determinista + su test golden, para
> programarlo sin ambigüedad y verificarlo por recibo. **Principio rector: el LLM PROPONE, el
> código DISPONE.** Nada consecuente (€, fechas, IBAN, impuestos, asignación de campos, gates)
> lo decide el LLM. Los pasos marcados `[CÓDIGO]` son deterministas y testeables; los `[LLM]` son
> llamadas acotadas y NO consecuentes (enrutar / envolver), con fallback determinista.
>
> Estado: **borrador 1** — se amplía de uno en uno. Cada ALG tiene: Propósito · Entrada · Salida ·
> Algoritmo · Errores · Casos golden · Mapa al código.

---

## ALG-0 · MAESTRO: atender una petición

**Propósito:** orquestar toda petición con fiabilidad por construcción.
**Entrada:** `mensaje:str`, `conversacion:[{role,content}]`.
**Salida:** una de {respuesta, pregunta, tarjeta_confirmacion_datos, tarjeta_aprobacion_efecto, error_honesto}.

```
atender(mensaje, conversacion):
  0. [CÓDIGO] si es_cortesia(mensaje): return saludo_instantaneo()          # smalltalk, sin LLM
  1. [LLM]    intent = clasificar_intencion(mensaje, conversacion)          # ALG-1.1
  2. [CÓDIGO] tools  = seleccionar_tools(intent)                            # ALG-1.2
  3. [CÓDIGO] params, faltan, ambiguo = extraer_params(mensaje, intent)     # ALG-1.3
  4. [CÓDIGO] si ambiguo: return preguntar(desambiguar(ambiguo))
             si falta_requerido(intent, faltan): return preguntar(pedir(faltan))
  5. [CÓDIGO] errs = validar_params(intent, params)                         # ALG-1.4
             si errs: return abstener_o_preguntar(errs)
  6. [CÓDIGO] si es_consecuente(intent) y not confirmado(params):
                return gate_de_datos(intent, params)                        # ALG-2.1
  7. [CÓDIGO] resultado = TOOL[intent].ejecutar(params)                     # ALG-3.x (código puro)
  8. [CÓDIGO] si efecto_externo(resultado): return gate_de_efecto(resultado)# ALG-2.2 (ya existe)
  9. [LLM]    return presentar_fiel(resultado)                              # ALG-4.1
```

**Errores:** cualquier paso `[LLM]` que falle por red/ctx → ALG-0.2 (reintento) → si persiste, error honesto.
**Casos golden:** un "hola" no llama al LLM pesado (paso 0); una petición de 303 recorre 1→9 sin que el LLM toque las cifras (las pone el paso 7).
**Mapa:** `loombit_operator/agent/loop.py` (bucle), `tools/registry.py` (paso 2), `tools/dominio.py` (paso 7).

---

## ALG-0.1 · asegurar_contexto (fiabilidad de infra)

**Propósito:** que una petición con tools NUNCA dé `400` por desbordar el contexto del modelo.
**Entrada:** `system_prompt`, `tools`, `historial`, `max_tokens`, `n_ctx_modelo`.
**Salida:** `ok` | `recorte_aplicado` | `aviso_setup`.

```
asegurar_contexto(system, tools, historial, max_tokens, n_ctx):
  1. [CÓDIGO] presupuesto = n_ctx - max_tokens - MARGEN(256)
  2. [CÓDIGO] coste = tokens(system) + tokens(tools) + tokens(historial) + tokens(mensaje)
  3. [CÓDIGO] si coste <= presupuesto: return ok
  4. [CÓDIGO] # recorte por prioridad, sin tocar lo esencial:
             historial = ultimos_N(historial)            # poda turnos viejos
             tools     = top_k_por_intencion(tools, k)    # mantiene las de la intención
             si sigue > presupuesto:
                 return aviso_setup("Carga el modelo a >=8192 ctx: lms load ... -c 8192")
  5. [CÓDIGO] return recorte_aplicado(system, tools, historial)
```

**Errores:** si ni recortando cabe → `aviso_setup` claro en la UI (no un 400 mudo).
**Casos golden:** con n_ctx=4096 y 14 tools → recorta o avisa, NUNCA 400; con n_ctx=8192 → ok sin recorte.
**Mapa:** `agent/loop.py` (antes de cada `llm.chat`), `agent/prompts.py` (tamaño del system).

---

## ALG-0.2 · llamar_llm_con_reintento (fiabilidad de red)

**Propósito:** un hipo transitorio del LLM no tumba el run.
```
llamar_llm_con_reintento(payload):
  1. [CÓDIGO] para intento en 1..3:
       2. resp = POST /chat/completions(payload)
       3. si resp.ok: return resp
       4. si resp.status en {400_por_contexto}: return ERROR_NO_REINTENTABLE  # lo arregla ALG-0.1
       5. si resp.status en {429,500,502,503,504} o timeout:
             esperar(backoff = 0.5 * 2^(intento-1)); continuar
       6. si no: return ERROR(resp)
  7. [CÓDIGO] return ERROR("modelo ocupado tras 3 intentos")
```
**Casos golden:** un 503 seguido de 200 → devuelve el 200 (1 reintento); un 400 de contexto → no reintenta (lo maneja ALG-0.1).
**Mapa:** `llm.py` (método `chat`).

---

## ALG-1.1 · clasificar_intencion ([LLM] acotado + fallback)

**Propósito:** decidir el dominio de la petición. Es lo ÚNICO subjetivo, y es no consecuente.
**Salida:** uno de `{cobro, calcular_303, registrar_factura, email, cita, buscar_correo, resumen_dia, conciliacion, otro}`.
```
clasificar_intencion(mensaje, conversacion):
  1. [CÓDIGO] hit = match_determinista(mensaje)     # palabras inequívocas (303, factura, cobro...)
             si hit es único: return hit            # no gastamos LLM si es obvio
  2. [LLM]    intent = llm_elige_de_lista(mensaje, conversacion, LISTA_INTENCIONES)
  3. [CÓDIGO] si intent no in LISTA_INTENCIONES: return "otro"   # nunca confiar a ciegas
  4. [CÓDIGO] return intent
```
**Casos golden:** "reclama el cobro…" → `cobro` sin LLM; "no sé, échame una mano con esto raro" → `otro` (no inventa dominio).
**Mapa:** nuevo `agent/intencion.py`; se apoya en `tools/registry.select_tool_names`.

---

## ALG-1.3 · extraer_params (PARSERS deterministas, NO el LLM)

> El corazón de la fiabilidad: las cifras/fechas/identificadores los saca CÓDIGO, no el modelo.

### ALG-1.3a · parsear_importe(texto) -> Decimal|None
```
1. normaliza: quita "€", espacios; "1.500,75" (es) -> 1500.75 ; "1,500.75" (en) -> 1500.75
2. busca el patrón numérico; si hay varios, devuelve lista con su contexto ("base", "iva", "total")
3. si ninguno: None
```
**Golden:** "1.500€" -> 1500.00 ; "2.000 más 21%" -> base=2000, tipo=0.21 ; "" -> None.

### ALG-1.3b · parsear_fecha(texto, hoy) -> date|None
```
1. formatos: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, "1 de mayo de 2026", "mañana", "el jueves"
2. relativas ("mañana","el jueves") se resuelven con `hoy` (determinista)
3. si no casa: None  (NUNCA inventar una fecha)
```
**Golden:** "1 de mayo de 2026" -> 2026-05-01 ; "el jueves" con hoy=mar 9/6 -> 2026-06-11 ; "pronto" -> None.

### ALG-1.3c · parsear_tipo_iva(texto) -> Decimal|None
```
1. "21%","21","0.21" -> 0.21 ; admite 0/4/5/10/21
2. si el valor no está en {0,0.04,0.05,0.10,0.21}: None (lo rechazará ALG-1.4)
```
**Golden:** "21%" -> 0.21 ; "40%" -> 0.40 (pasa al validador, que lo rechaza) ; "tipo raro" -> None.

### ALG-1.3d · validar_iban(iban) / validar_nif(nif) -> bool
```
IBAN: longitud por país + checksum mod-97 == 1
NIF/CIF: letra de control correcta (algoritmo oficial)
```
**Golden:** IBAN con checksum malo -> False ; NIF "12345678Z" -> True/False según letra.

**Mapa:** nuevo `agent/parsers.py` (puro, 100% testeable).

---

## ALG-1.4 · validar_params (rechaza lo imposible)

```
validar_params(intent, params):
  errs = []
  para cada importe: si < 0 -> err("importe negativo")
  para cada tipo_iva: si tipo not in {0,0.04,0.05,0.10,0.21} -> err("IVA imposible")
  para cada fecha: si no es fecha válida -> err
  si intent paga/envía y hay IBAN: si not validar_iban -> err("IBAN inválido")
  return errs
```
**Golden:** IVA 40% -> err (no calcula) ; base -100 -> err.
**Mapa:** `agent/parsers.py` + uso en cada tool de `tools/dominio.py`.

---

## ALG-2.1 · gate_de_datos (confirmar ANTES de lo consecuente) — NUEVO

**Propósito:** que nunca se calcule/envíe algo consecuente con datos que el LLM pudo malinterpretar.
```
gate_de_datos(intent, params):
  1. [CÓDIGO] resumen = describir_humano(params)   # "Ventas 12.000€@21%; Compras 3.000€@21%"
  2. devuelve tarjeta_confirmacion(resumen, accion="Calcular", "Corregir")
  3. al confirmar -> reanuda ALG-0 desde paso 7 con confirmado(params)=True
```
**Golden:** un 303 no produce número hasta confirmar; "Corregir" vuelve a preguntar.
**Mapa:** `agent/loop.py` (nuevo estado `pending_data`), UI: tarjeta como la de aprobación.

---

## ALG-3.1 · plan_cobro (YA IMPLEMENTADO — su algoritmo)

**Entrada:** `total, fecha_vencimiento, cobrado=0, tipo_interes_anual=None`. **Todo código.**
```
plan_cobro(total, venc, cobrado, tipo):
  1. saldo = total - cobrado
  2. si saldo <= 0: return {accion:"no_reclamar", motivo:"cobrada"}
  3. dias = hoy - venc
  4. etapa = escalonar(dias)   # <0 por_vencer; 0 hoy; 1-7 amistoso; 8-21 firme; 22-60 formal; >60 judicial
  5. si dias <= 0: return {accion:"esperar"|"preparar_recordatorio", saldo, etapa}
  6. interes = tipo ? simple(saldo,tipo,dias) : tipo_legal_BOE(saldo, venc)   # determinista, con cita
  7. return {accion:"reclamar", saldo, etapa, compensacion:40, interes,
             escalar_humano: etapa==judicial}
```
**Golden:** 1500€, venc 2026-05-01, hoy 2026-06-09 -> saldo 1500, 39 días, "formal", comp 40€, interés 16,27€@10,15% (BOE).
**Mapa:** `cobros.py::dunning_plan` + `tipos_demora.py`; tool en `tools/dominio.py::_plan_cobro`. ✅ verificado e2e.

---

## ALG-3.2 · calcular_303 (desde líneas dadas)

```
calcular_303(lineas):
  1. [CÓDIGO] para cada línea: cuota = redondea(base * tipo)   # tipo ya validado por ALG-1.4
  2. devengado = suma(cuotas de sentido=="devengado")          # ventas/emitidas
  3. deducible = suma(cuotas de sentido=="soportado" y deducible)
  4. resultado = devengado - deducible
  5. return {devengado, deducible, resultado, casillas, avisos, echo_lineas}
```
**Golden:** ventas 12.000@21 + compras 3.000@21 -> dev 2.520, ded 630, resultado **1.890 a ingresar** (EXACTO).
**Riesgo conocido:** si el LLM rellena las `lineas` (mis-asigna ventas/compras o inventa), el cálculo es correcto pero los datos no. → por eso ALG-3.4 (desde facturas registradas) y el gate de datos (ALG-2.1).
**Mapa:** `skill_d_fiscal/modelo_303.py::calcular_303`; tool `tools/dominio.py::_calcular_303` (con guard + echo). 🟠

---

## ALG-3.3 · registrar_factura (YA IMPLEMENTADO)

```
registrar_factura(contraparte, base, numero, iva|tipo, sentido, fecha, nif):
  1. [CÓDIGO] iva = iva ?? redondea(base*tipo)         # tipo validado
  2. total = base + iva
  3. sentido_303 = sentido=="emitida" ? "devengado" : "soportado"
  4. persistir Expediente factura_intake {fields, sentido} en entidad
  5. return recibo {numero, total, id}
```
**Golden:** emitida 2.000@21 -> total 2.420, persiste con sentido devengado.
**Mapa:** `skill_d_fiscal/intake.py::registrar_factura`; tool `tools/dominio.py::_registrar_factura`. ✅ e2e.

---

## ALG-3.4 · calcular_303_desde_registradas (el 303 FIABLE) — PENDIENTE

**Propósito:** el 303 sale de facturas REGISTRADAS (datos reales), no de una frase parseada por el LLM.
```
calcular_303_registradas(periodo):
  1. [CÓDIGO] lineas, avisos = recopilar_lineas(store)   # lee todos los factura_intake
  2. si vacío: return "No hay facturas registradas. Regístralas y calculo el 303 real."
  3. res = calcular_303(lineas)                          # ALG-3.2, datos auditables
  4. return echo(n_facturas) + borrador(res) + avisos
```
**Golden:** registro 2 facturas (1000@21 emitida, 200@21 recibida) -> 303 = 210-42 = **168 a ingresar**, citando 2 facturas.
**Mapa:** `skill_d_fiscal/intake.py::recopilar_lineas` + `calcular_303`; tool nueva en `tools/dominio.py`.

---

## ALG-4.1 · presentar_fiel (RELAY) — NUEVO

**Propósito:** el número que ve el usuario == el que calculó el código (el LLM no lo parafrasea).
```
presentar_fiel(resultado):
  1. [CÓDIGO] bloque = formato_canonico(resultado)        # cifras, casillas, avisos
  2. [LLM]    intro = una_frase_calida(contexto)           # SOLO el envoltorio, sin tocar cifras
  3. [CÓDIGO] return intro + "\n\n" + bloque               # el bloque va verbatim
```
**Golden:** si la tool dice 1.890€, la respuesta contiene "1.890" literal (no "unos 1.900").
**Mapa:** `agent/loop.py` (marcar resultados de tools de cálculo como "render verbatim").

---

## ALG-4.2 · abstencion_honesta (PARCIAL — cerrar)

```
abstencion_honesta(intent, params):
  1. [CÓDIGO] si TOOL[intent] no existe o no_aplica:
       return "Esto aún no lo puedo hacer: <qué falta concreto>. Lo que sí puedo: <alternativa>." + task_done
  2. PROHIBIDO: 'plan manual' largo, prometer pasos no ejecutables, pedir datos en bucle.
```
**Golden:** "concilia mi banco" sin tool -> 1-2 frases honestas + qué necesita; NO promete conciliar.
**Mapa:** `agent/prompts.py` (bloque ABSTENCIÓN) + futura detección determinista.

---

## Arnés golden (gate)
Todos los "Casos golden" de arriba viven en `tests/` y corren en `scripts/verify.py`. Un commit que
rompa cualquiera deja el gate ROJO. Sin recibo verde, no se commitea. **Predicción ≠ hecho.**

## Pendiente de pasar a algoritmo (siguientes entregas, uno a uno)
seleccionar_tools (ALG-1.2 detalle) · gate_de_efecto (ALG-2.2) · conciliación · telar/dedup ·
reconciliación calendario↔correo · memoria de conversación · daily_brief · email (destinatario/redacción)
· cita/calendario · datos≠órdenes (anti-inyección) · anti-fraude IBAN-swap.
