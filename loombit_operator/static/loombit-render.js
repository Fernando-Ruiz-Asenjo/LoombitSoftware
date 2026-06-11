/*
 * loombit-render.js — LD-1 de «Loombit Decide»: el renderer de la UI generativa GOBERNADA.
 *
 * Pinta una *spec* JSON (validada en el backend por ui_spec.py) desde un vocabulario CERRADO.
 * GARANTÍA DE SEGURIDAD (Ley Fundacional aplicada a la pantalla): este renderer NUNCA usa
 * innerHTML, NUNCA eval, NUNCA inserta HTML del LLM. Todo texto se pinta con `textContent` y la
 * estructura se construye con `createElement`. Un tipo desconocido NO se pinta (se ignora con aviso):
 * el LLM no puede colar interfaz fuera del vocabulario aunque el backend fallara.
 *
 * API:  LoombitRender.renderSpec(spec, mountEl, { onResolve })
 *   - onResolve(decisionId, optionId): callback al pulsar una opción de un decision_card.
 */
(function (global) {
  "use strict";

  var ALLOWED = {
    decision_card: true,
    resumen: true,
    eleccion: true,
    borrador_preview: true,
    cola: true,
  };

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = String(text); // SIEMPRE textContent, nunca innerHTML
    return node;
  }

  function renderDecisionCard(spec, handlers) {
    var card = el("div", "lb-decision-card");
    card.setAttribute("data-kind", String(spec.kind || "generico"));
    card.appendChild(el("h3", "lb-title", spec.title || ""));
    if (spec.why) card.appendChild(el("p", "lb-why", spec.why));
    if (spec.detail) card.appendChild(el("p", "lb-detail", spec.detail));

    var meta = el("div", "lb-meta");
    if (spec.risk) meta.appendChild(el("span", "lb-risk lb-risk-" + spec.risk, "riesgo " + spec.risk));
    if (spec.reversible === false) meta.appendChild(el("span", "lb-irreversible", "no reversible"));
    else if (spec.reversible === true) meta.appendChild(el("span", "lb-reversible", "reversible"));
    if (meta.childNodes.length) card.appendChild(meta);

    if (Array.isArray(spec.badges)) {
      var badges = el("div", "lb-badges");
      spec.badges.forEach(function (b) {
        badges.appendChild(el("span", "lb-badge", b));
      });
      card.appendChild(badges);
    }

    var opts = el("div", "lb-options");
    (spec.options || []).forEach(function (o) {
      var btn = el("button", "lb-option lb-option-" + (o.kind || "aprobar"), o.label || o.id);
      btn.type = "button";
      btn.setAttribute("data-option-id", String(o.id));
      btn.addEventListener("click", function () {
        if (handlers && typeof handlers.onResolve === "function") {
          handlers.onResolve(String(spec.id || ""), String(o.id));
        }
      });
      opts.appendChild(btn);
    });
    card.appendChild(opts);
    return card;
  }

  function renderResumen(spec) {
    var box = el("div", "lb-resumen");
    if (spec.title) box.appendChild(el("h3", "lb-title", spec.title));
    if (Array.isArray(spec.lines)) {
      var ul = el("ul", "lb-lines");
      spec.lines.forEach(function (line) {
        ul.appendChild(el("li", null, line));
      });
      box.appendChild(ul);
    }
    return box;
  }

  function renderEleccion(spec, handlers) {
    var box = el("div", "lb-eleccion");
    box.appendChild(el("p", "lb-prompt", spec.prompt || ""));
    var opts = el("div", "lb-options");
    (spec.options || []).forEach(function (o) {
      var btn = el("button", "lb-option", o.label || o.id);
      btn.type = "button";
      btn.setAttribute("data-option-id", String(o.id));
      btn.addEventListener("click", function () {
        if (handlers && typeof handlers.onChoose === "function") {
          handlers.onChoose(String(spec.id || ""), String(o.id));
        }
      });
      opts.appendChild(btn);
    });
    box.appendChild(opts);
    return box;
  }

  function renderBorradorPreview(spec) {
    var box = el("div", "lb-borrador");
    if (spec.to) box.appendChild(el("div", "lb-borrador-to", "Para: " + spec.to));
    if (spec.subject) box.appendChild(el("div", "lb-borrador-subject", spec.subject));
    box.appendChild(el("pre", "lb-borrador-body", spec.body || "")); // <pre> + textContent: texto plano
    return box;
  }

  function renderCola(spec, handlers) {
    var box = el("div", "lb-cola");
    if (spec.title) box.appendChild(el("h2", "lb-cola-title", spec.title));
    var list = el("div", "lb-cola-items");
    (spec.items || []).forEach(function (item) {
      var node = renderComponent(item, handlers);
      if (node) list.appendChild(node);
    });
    box.appendChild(list);
    return box;
  }

  function renderComponent(spec, handlers) {
    if (!spec || typeof spec !== "object" || !ALLOWED[spec.type]) {
      if (global.console) console.warn("loombit-render: tipo no permitido, ignorado:", spec && spec.type);
      return null; // fuera del vocabulario → no se pinta
    }
    switch (spec.type) {
      case "decision_card":
        return renderDecisionCard(spec, handlers);
      case "resumen":
        return renderResumen(spec);
      case "eleccion":
        return renderEleccion(spec, handlers);
      case "borrador_preview":
        return renderBorradorPreview(spec);
      case "cola":
        return renderCola(spec, handlers);
      default:
        return null;
    }
  }

  function renderSpec(spec, mountEl, handlers) {
    if (!mountEl) return;
    while (mountEl.firstChild) mountEl.removeChild(mountEl.firstChild);
    var node = renderComponent(spec, handlers || {});
    if (node) mountEl.appendChild(node);
  }

  global.LoombitRender = { renderSpec: renderSpec, renderComponent: renderComponent };
})(typeof window !== "undefined" ? window : this);
