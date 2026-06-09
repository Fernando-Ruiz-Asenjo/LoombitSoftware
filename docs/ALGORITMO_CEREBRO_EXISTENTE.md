# CEREBRO — algoritmos de lo que YA EXISTE (debe funcionar al 100%)

> Inventario AS‑IS del cerebro: cada comportamiento que YA está en código, escrito como algoritmo +
> su test golden + estado real + `fichero:línea`. NO incluye features nuevas sin implementar (esas
> están en `ALGORITMO_CEREBRO.md`). Objetivo: que cada una de estas se VERIFIQUE al 100% por recibo.
>
> Estado: ✅ verificado por recibo (esta sesión) · 🟢 con tests · 🟠 existe, SIN verificación dura ·
> ⚠️ existe pero con fallo conocido.

---

# Familia 1 · MOTOR DEL AGENTE (bucle ReAct) — `agent/loop.py`

## F1.1 · create(task, history) — sembrar el run  ✅
```
1. run = store.create(task)
2. messages = [system_prompt(perfil, memoria)] + turnos(history) + [user: task]
3. guardar run
```
**Golden:** con history, el run incluye los turnos previos (memoria). `loop.py:101`

## F1.2 · _execute(run) — bucle ReAct  🟠
```
repetir hasta task_done / max_steps / pausa:
  1. asegurar contexto (PENDIENTE ALG-0.1) ; llamar LLM con tools (PENDIENTE reintento ALG-0.2)
  2. si el LLM pide tool(s): por cada una → _execute_tool_call
  3. si PENDING_APPROVAL → marcar pending_approval y PARAR
  4. si PENDING_QUESTION → marcar pending_question y PARAR
  5. si task_done → completar con resumen saneado
  6. anti-bucle: _maybe_cut_for_flailing / _inject_loop_hint
al acabar: _update_memory + _aprender_de_fallo
```
**Golden:** una tarea de correo recorre contacts_find→gmail_send→task_done sin pasos muertos. `loop.py:250`
**Riesgo:** sin ALG-0.1/0.2 puede dar 400 o morir por hipo transitorio (ya documentado).

## F1.3 · _execute_tool_call(tc) — ejecutar una tool con gate  ✅(gate)
```
1. si gmail_send se "delata" como bot → pedir reescritura humana
2. auto_envio = (gmail_send ∧ destinatario_claro ∧ no proactivo)        # D-20
3. si tool.requires_approval ∧ ¬auto_envio → devolver PENDING_APPROVAL (pausa)
4. ejecutar tool ; capturar errores como texto (no romper el run)
5. si resultado es PENDING_QUESTION autorredactable → autocorregir y seguir
```
**Golden:** calendar_create → siempre PENDING_APPROVAL; correo a destinatario claro → ejecuta. `loop.py:442`

## F1.4 · accept_approval / resume / _resume_execute — reanudar tras OK  🟠
```
1. validar que el run está en pending_approval
2. run.approve() → RUNNING ; sustituir placeholder PENDING_APPROVAL por el resultado real
3. continuar el bucle desde donde estaba
```
**Golden:** aprobar un evento → se crea el evento real y el run completa. (Verificado e2e con calendar_create esta sesión ✅) `loop.py:137,149,154`

## F1.5 · accept_answer(answer) — responder a una pregunta del agente  🟠
```
1. validar pending_question
2. añadir {user: answer} al historial del run ; sustituir el PENDING_QUESTION
3. continuar el bucle
```
**Golden:** el agente pregunta una ruta → respondes → sigue sin re-preguntar. `loop.py:212`

## F1.6 · _maybe_cut_for_flailing — anti-bucle  🟠
```
si 2+ errores seguidos de la misma tool / sin avanzar → cortar con mensaje honesto
```
**Golden:** 2 fallos seguidos de gmail_search → corta, no entra en bucle. `loop.py:539`

## F1.7 · destinatario_claro / _recipiente_resuelto — política de envío (D-20)  🟠
```
destinatario_claro(to): el usuario lo dio explícito (con "@") o contacts_find lo resolvió sin ambigüedad
```
**Golden:** "envía a juan@x.com" → claro ; "envía a David" con 2 Davids → NO claro (pausa/pregunta). `loop.py:589,604`

## F1.8 · _describe_for_approval — qué se muestra al aprobar  ⚠️
```
traduce (tool,args) a {reason, proposed_action} legible para la tarjeta
```
**Golden:** calendar_create → "Crear un evento" + detalle. **Fallo conocido:** el `proposed_action` salió pobre (título vacío) en la prueba de hoy → mejorar. `loop.py:633`

## F1.9 · saneadores del bucle — _strip_tool_artifacts / _is_error_result / _error_brief  🟠
```
limpian el texto que ve el usuario (fuera nombres de tool/artefactos) y clasifican errores
```
**Golden:** un resultado con "task_done" dentro → se elimina del texto visible. `loop.py:664,725,730`

## F1.10 · _update_memory / _aprender_de_fallo — cerrar el run  🟠
```
al terminar: add_history(task,result,tools) ; si falló, reflexionar y guardar lección
```
**Golden:** un run completado deja entrada en history. `loop.py:570,773`

---

# Familia 2 · FRICCIÓN CERO — `agent/smalltalk.py`

## F2.1 · respuesta_social(task) — cortesía instantánea (sin 14B)  🟢
```
1. norm = sin acentos/min ; 2. si norm ∈ saludos/gracias/despedidas → devolver respuesta cálida fija
3. si no → None (sigue el agente normal)
```
**Golden:** "hola" → respuesta al instante (0 LLM) ; "reclama un cobro" → None. `smalltalk.py:78` (verificado ✅ "hola" instantáneo)

---

# Familia 3 · MEMORIA OPERATIVA — `agent/memory.py`

## F3.1 · owner / set_owner — identidad del titular  🟠
```
get: {nombre, empresa, email...} ; set: persiste y se refleja en el saludo del telar
```
**Golden:** set_owner(nombre="Fernando") → el telar saluda "Fernando". `memory.py:476,479`

## F3.2 · add_contact / find_contact — agenda  🟠
```
find(query): match por nombre/email/tokens → lista ordenada por probabilidad (mejor primero)
```
**Golden:** find("David") con 2 → devuelve ambos ordenados ; find("juan@x") → exacto. `memory.py:517,547`

## F3.3 · add_history / history — histórico de tareas  🟠
```
add(task,result,tools,run_id) → entrada datada ; alimenta to_context_block (recuperación por relevancia)
```
**Golden:** tras un run, history contiene la tarea. `memory.py:558`

## F3.4 · add_procedure / find_procedure — procedimientos aprendidos  🟠
```
find(task): recupera el procedimiento relevante por tokens (≥ umbral) para reusarlo
```
**Golden:** procedimiento "303" se recupera ante "haz el 303". `memory.py:572,595`

## F3.5 · EntityProfile — perfil de pagador  🟠
```
avg_days_late / pays_late: a partir del histórico de cobros del contacto
```
**Golden:** cliente con 3 pagos a +20 días → pays_late=True. `memory.py:357,400`

## F3.6 · to_context_block(task_hint) — inyectar memoria al prompt  🟠
```
selecciona owner + contactos + procedimientos + lecciones RELEVANTES al task_hint → bloque de texto
```
**Golden:** el bloque incluye al titular y procedimientos del dominio de la tarea. `memory.py` (usado en loop.create)

---

# Familia 4 · REFLEXIÓN / APRENDIZAJE — `agent/reflexion.py`

## F4.1 · reflexionar(run) — lección de un fallo  🟠
```
si el run falló: el LLM resume qué salió mal → lección con etiquetas → se guarda (recuperable)
```
**Golden:** un run fallido genera una LessonEntry con tags de la tarea. `reflexion.py:25`

## F4.2 · etiquetas_de_tarea(task) — clasificar para recuperar  🟢
```
extrae tokens significativos (IVA/303/NIF/cobro...) para indexar lecciones/procedimientos
```
**Golden:** "modelo 303 del 2T" → {303, iva, trimestre}. `reflexion.py:45`

---

# Familia 5 · COMPRENSIÓN DE LA BANDEJA (cognición) — `comprension.py`

## F5.1 · comprender(correos, eventos) — cognición, no extracción  ⚠️
```
1. _recopilar correos+eventos → contexto
2. [LLM] entiende los hilos → objetos tipados {tipo, estado, importancia, accion, lugar...}
3. _salvar_objetos: parser TOLERANTE (recupera objetos completos aunque el JSON venga truncado)
4. _normalizar cada objeto (fechas, estados) ; descarta inválidos
5. DEDUP determinista por clave fuerte (deuda→1; evento→fecha,hora; resto→origen/título)
6. persistir + cachear ; si el LLM falla, conservar el último bueno (NUNCA el calendario crudo)
```
**Golden:** "deuda Abogados CEA" emitida 4× → 1 aviso ; deuda no reconocida → importante+requiere_accion. `comprension.py:298,100,164`
**Fallo conocido:** dependía de max_tokens (truncado → no-determinismo); subido + parser tolerante. Re-verificar caso a caso.

## F5.2 · refrescar / refrescar_async / calentar_al_arrancar — fiabilidad de la cognición  🟠
```
se computa en 2º plano y se PERSISTE ; el telar LEE la caché (instantáneo) ; se calienta al arrancar
```
**Golden:** /telar responde al instante con el último bueno aunque el LLM tarde. `comprension.py:361,380,401`

## F5.3 · _salvar_objetos — parser tolerante  🟢
```
recorre el texto conservando cada {...} balanceado ; recupera del array aunque esté truncado/con ruido
```
**Golden:** JSON cortado a la mitad → recupera los objetos completos previos, no None. `comprension.py:100`

---

# Familia 6 · TELAR (tejer el día) — `telar.py`

## F6.1 · tejer_dia — ensamblar los hilos del día  🟠
```
1. fuentes: inbox(comprensión) + eventos + cobros + aprobaciones (deterministas)
2. cada asunto → _hilo_asunto {icono, titulo, porque causal, detalle, accion, enlace}
3. orden por urgencia ; saludo según hora
```
**Golden:** día con deuda+reunión+fiscal → hilos ordenados, la deuda arriba. `telar.py:375`

## F6.2 · _hilo_asunto / _porque_asunto — tarjeta con causa  🟠
```
porque = explicación causal DETERMINISTA por (tipo,estado), DISTINTA del detalle
```
**Golden:** reunión confirmada → porque "confirmada por ambas partes" (no repite el detalle). `telar.py:88,131`

## F6.3 · _hilo_cobro_vencida — cobro con desglose legal  🟢
```
usa cobros/tipos_demora → saldo, etapa, interés BOE, compensación 40€, cita
```
**Golden:** factura vencida → hilo con desglose legal y cita BOE. `telar.py:265`

## F6.4 · _plazos_en_correos / _obligaciones_fiscales — plazos  🟠
```
detecta fechas/plazos en correos + calendario fiscal (ventana N días)
```
**Golden:** correo con "antes del 20/7" → hilo de plazo. `telar.py:199,232`

## F6.5 · fuentes deterministas — inbox/correos/eventos/cobros/aprobaciones  🟠
```
_fuente_correos excluye el correo propio ; _fuente_aprobaciones cuenta pending_approval del store
```
**Golden:** no propone responderte a ti mismo ; el contador de aprobaciones casa con el store. `telar.py:603,627,686,696`

## F6.6 · _buscar_correos(nombre) — fundamentarse en la bandeja  🟠
```
busca en TODO el Gmail al interlocutor para reconciliar (read-only)
```
**Golden:** "reunión con David" → encuentra el hilo y extrae fecha/hora. `telar.py:580`

## F6.7 · _necesita_respuesta (en routine_executors) — no proponer responder a acuses  🟢
```
excluye acuses/Calendar/automáticos del reply-watch
```
**Golden:** "Aceptado: Reunión" → NO propone responder. (fix verificado en sesión previa)

---

# Familia 7 · CACHÉ DEL TELAR — `telar_cache.py`

## F7.1 · get_telar / warm / invalidate — telar instantáneo  🟢
```
get: sirve el último bueno (memoria→disco) al instante y refresca por detrás (async)
warm: calienta al arrancar ; invalidate: tras cambios (aprobar, owner, comprensión)
```
**Golden:** /telar nunca bloquea en llamadas síncronas a Google ; tras invalidate, refresca. `telar_cache.py:97,116,121`
**Pendiente:** que `comprension.refrescar` invalide también esta caché (dup viejo un rato).

---

# Familia 8 · SANEADORES DE SALIDA (voz / seguridad de texto) — `tool_labels.py`

## F8.1 · humanize_user_text — fuera jerga de tools  🟢
```
sustituye nombres de tool / artefactos por lenguaje humano en el texto que ve el usuario
```
**Golden:** "gmail_search → 3 resultados" → "busqué en tu correo". `tool_labels.py:91`

## F8.2 · looks_like_code / safe_user_result — no escupir código  🟢
```
si la "respuesta" parece código → fallback honesto en vez de mostrar el código crudo
```
**Golden:** el 14B devuelve un bloque de código como respuesta → se sustituye por un mensaje honesto. `tool_labels.py:121,126`

## F8.3 · human_label / capability_block — presentarse en humano  🟢
```
nombre humano de cada capacidad ; bloque "esto es lo que sé hacer" sin nombres de tool
```
**Golden:** "¿qué sabes hacer?" → capacidades en humano, sin "gmail_send". `tool_labels.py:137,143`

---

## Resumen de cobertura (honesto) — actualizado RC·Cerebro
`tests/test_cerebro_golden.py` = **30 golden** en el gate (100% CI, sin LM Studio).
- **🟢 con test/verificado AHORA:** smalltalk (F2.1) · parser tolerante (F5.3) · etiquetas (F4.2) ·
  saneadores humanize/looks_like_code/safe_user_result (F8.1/8.2) · capability_block (F8.3) ·
  guardia anti-email-inventado `_recipiente_resuelto`/`_destinatario_claro` (F1.7) · tarjeta de
  aprobación `_describe_for_approval` (F1.8, **arreglado**) · cognición `_normalizar` con guard
  deuda/fraude + ruido (F5) · perfil de pagador EntityProfile (F3.5) · anti-bucle `_is_error_result`/
  `_error_brief`/`_consecutive_tool_errors` (F1.6/F1.9) · **ALG-0.1 contexto** ✅ · **ALG-0.2 reintento** ✅.
  (+ ya tenían: cobro vencido, caché telar, _necesita_respuesta.)
- **🟠 sigue SIN verificación dura (siguiente tanda):** motor del agente e2e (F1.2 bucle, F1.4 reanudar,
  F1.5 answer, F1.10 update_memory), memoria F3.1-3.4/3.6, reflexión F4.1, comprensión F5.1/5.2 e2e,
  telar F6.* (necesitan LM Studio o fakes más elaborados).
- **⚠️ pendiente:** F5.1 no-determinismo histórico de `comprender` (mitigado por F5.3+guard; e2e por verificar).

> "Debería funcionar al 100%" → "funciona, con recibo": 13+ piezas pasaron de 🟠 a 🟢 con test esta tanda.
