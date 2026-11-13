// Runs in the page that holds one SVG frame; returns the measurements as an object.
// Options arrive as window.__measureOpts = { minTarget, tol }.
(() => {
  const opts = Object.assign({ minTarget: 44, tol: 0.5 }, window.__measureOpts || {});
  const svg = document.querySelector("svg");
  const bad = document.querySelector("parsererror");
  if (bad) return { canvas: "?", texts: 0, targets: 0, states: 0, findings: [{ kind: "xml", msg: bad.textContent.replace(/\s+/g, " ").replace(/^This page contains the following errors: ?/, "").replace(/ ?Below is a rendering.*/, "") }] };
  const NOT_DRAWN = "defs, symbol, clipPath, mask, pattern, marker";
  const r1 = (n) => Math.round(n * 10) / 10;

  // Clones keep their ids (so #id CSS still matches) and also carry data-oid; lookups by id
  // skip placed copies so an id names the original, or the placed instance through resolve().
  const byId = (id) => [...svg.querySelectorAll("[id]")].find((e) => e.id === id && !(e.parentElement && e.parentElement.closest("[data-use]")));

  // Place each <use> as a <g> holding a clone of its target, so every instance is measured. A <symbol> becomes a nested <svg>
  // with the symbol's attributes (viewBox, preserveAspectRatio, inherited style) and the <use>'s size, as the browser renders it.
  const SVG_NS = "http://www.w3.org/2000/svg";
  const placeSymbol = (symbol, u) => {
    const inner = document.createElementNS(SVG_NS, "svg");
    for (const a of symbol.getAttributeNames()) inner.setAttribute(a, symbol.getAttribute(a));
    for (const a of ["width", "height"]) inner.setAttribute(a, u.getAttribute(a) || symbol.getAttribute(a) || "100%");
    inner.append(...symbol.childNodes);
    return inner;
  };
  for (let round = 0; round < 20; round++) {
    const uses = [...svg.querySelectorAll("use")].filter((u) => !u.closest(NOT_DRAWN));
    if (!uses.length) break;
    for (const u of uses) {
      const id = (u.getAttribute("href") || u.getAttribute("xlink:href") || "").replace(/^#/, "");
      const src = id && byId(id);
      const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      if (src) {
        const clone = src.cloneNode(true);
        for (const el of [clone, ...clone.querySelectorAll("[id]")]) {
          if (el.hasAttribute("id")) el.setAttribute("data-oid", el.getAttribute("id"));
        }
        g.append(src.localName === "symbol" ? placeSymbol(clone, u) : clone);
      }
      const x = u.getAttribute("x") || 0, y = u.getAttribute("y") || 0;
      g.setAttribute("transform", `${u.getAttribute("transform") || ""} translate(${x} ${y})`);
      for (const a of u.getAttributeNames()) {
        if (a === "id" || a.startsWith("data-")) g.setAttribute(a, u.getAttribute(a));
      }
      // A nested placed copy is found by data-in through its data-oid, as its parts are.
      if (u.hasAttribute("id")) g.setAttribute("data-oid", u.getAttribute("id"));
      g.setAttribute("data-use", id);
      for (const a of ["class", "style", "fill", "stroke", "visibility", "opacity"]) {
        if (u.hasAttribute(a)) g.setAttribute(a, u.getAttribute(a));
      }
      u.replaceWith(g);
    }
  }

  // A shape's box in the frame's user space (viewBox units), optionally grown by half its stroke.
  const box = (el, withStroke) => {
    let b;
    try { b = el.getBBox(); } catch (e) { return null; }
    const sm = el.getScreenCTM();
    if (!sm) return null;
    const m = svg.getScreenCTM().inverse().multiply(sm);
    const pad = withStroke && getComputedStyle(el).stroke !== "none"
      ? (parseFloat(getComputedStyle(el).strokeWidth) || 0) / 2 : 0;
    const pts = [[b.x - pad, b.y - pad], [b.x + b.width + pad, b.y - pad],
      [b.x - pad, b.y + b.height + pad], [b.x + b.width + pad, b.y + b.height + pad]]
      .map(([x, y]) => [m.a * x + m.c * y + m.e, m.b * x + m.d * y + m.f]);
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const x0 = Math.min(...xs), y0 = Math.min(...ys);
    return { x: x0, y: y0, w: Math.max(...xs) - x0, h: Math.max(...ys) - y0 };
  };
  const empty = (b) => !b || (b.w === 0 && b.h === 0);
  const hidden = (el) => { const s = getComputedStyle(el); return s.visibility === "hidden" || s.display === "none"; };
  const label = (el) => {
    const t = el.textContent.replace(/\s+/g, " ").trim();
    return `"${t.length > 28 ? t.slice(0, 27) + "…" : t}"`;
  };
  // data-in="id": the nearest placed instance that holds the id (walking out through nested <use> wrappers; within one,
  // its own part first, then the parts placed inside it, shallowest first), else the original element.
  const wrapperOf = (e) => e.parentElement && e.parentElement.closest("[data-use]");
  const depth = (e, w) => { let n = 0; for (let p = wrapperOf(e); p && p !== w; p = wrapperOf(p)) n++; return n; };
  const resolve = (el, id) => {
    for (let w = el.closest("[data-use]"); w; w = wrapperOf(w)) {
      if (w.getAttribute("data-oid") === id || w.id === id) return w;
      const hits = [...w.querySelectorAll("[data-oid]")].filter((e) => e.getAttribute("data-oid") === id);
      if (hits.length) return hits.map((e) => [depth(e, w), e]).sort((a, b) => a[0] - b[0])[0][1];
    }
    return byId(id);
  };

  const findings = [];
  const add = (kind, msg) => findings.push({ kind, msg });

  const vb = svg.viewBox.baseVal;
  const canvas = vb && vb.width ? { x: vb.x, y: vb.y, w: vb.width, h: vb.height }
    : { x: 0, y: 0, w: svg.width.baseVal.value, h: svg.height.baseVal.value };

  // Text against its container (data-in="<id>") and the canvas.
  const texts = [...svg.querySelectorAll("text")].filter((t) => !t.closest(NOT_DRAWN));
  const boxes = [];
  for (const t of texts) {
    const tb = box(t, false);
    if (empty(tb)) { add("text", `${label(t)} has no box (display:none or empty)`); continue; }
    if (!hidden(t)) boxes.push({ t, tb });
    if (tb.x < canvas.x - opts.tol || tb.y < canvas.y - opts.tol ||
        tb.x + tb.w > canvas.x + canvas.w + opts.tol || tb.y + tb.h > canvas.y + canvas.h + opts.tol) {
      add("canvas", `${label(t)} leaves the canvas: x ${r1(tb.x)}–${r1(tb.x + tb.w)}, y ${r1(tb.y)}–${r1(tb.y + tb.h)}, canvas ${canvas.w}×${canvas.h}`);
    }
    const id = t.getAttribute("data-in");
    if (!id) continue;
    const c = resolve(t, id);
    const cb = c && box(c, false);
    if (empty(cb)) { add("container", `${label(t)}: data-in="${id}" matches no drawn element`); continue; }
    const over = {
      left: cb.x - tb.x, right: tb.x + tb.w - (cb.x + cb.w),
      top: cb.y - tb.y, bottom: tb.y + tb.h - (cb.y + cb.h),
    };
    const sides = Object.entries(over).filter(([, v]) => v > opts.tol).map(([k, v]) => `${k} +${r1(v)}`);
    if (sides.length) {
      add("overflow", `${label(t)} exceeds #${id}: ${sides.join(", ")} (text ${r1(tb.w)}×${r1(tb.h)}, box ${r1(cb.w)}×${r1(cb.h)})`);
    }
  }

  // Overlap between the text boxes that are visible together.
  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i].tb, b = boxes[j].tb;
      const w = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
      const h = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
      if (w > 2 * opts.tol && h > 2 * opts.tol) {
        add("overlap", `${label(boxes[i].t)} × ${label(boxes[j].t)}: ${r1(w)}×${r1(h)}`);
      }
    }
  }

  // Interactive targets (data-target, optional value = minimum) against the platform minimum.
  const targets = [...svg.querySelectorAll("[data-target]")].filter((e) => !e.closest(NOT_DRAWN));
  for (const el of targets) {
    const b = box(el, false);
    const min = parseFloat(el.getAttribute("data-target")) || opts.minTarget;
    const name = el.getAttribute("data-oid") || el.id || label(el);
    if (empty(b)) { add("target", `${name} has no box`); continue; }
    if (b.w < min - opts.tol || b.h < min - opts.tol) {
      add("target", `${name} is ${r1(b.w)}×${r1(b.h)}, minimum ${min}×${min}`);
    }
  }

  // Element state sheets: every state layer keeps the same outer box as the first one.
  const sheets = [...svg.querySelectorAll("[data-states]")].filter((e) => !e.closest(NOT_DRAWN));
  const SHAPES = "rect, circle, ellipse, path, line, polyline, polygon, text, image";
  for (const sheet of sheets) {
    const name = sheet.getAttribute("data-states");
    const layers = [...sheet.querySelectorAll("[data-state]")];
    const outer = layers.map((layer) => {
      const parts = [...layer.querySelectorAll(SHAPES)]
        .filter((e) => !e.closest("[data-overlay]"))
        .map((e) => box(e, true)).filter((b) => !empty(b));
      if (!parts.length) return { state: layer.getAttribute("data-state"), b: null };
      const x0 = Math.min(...parts.map((p) => p.x)), y0 = Math.min(...parts.map((p) => p.y));
      const x1 = Math.max(...parts.map((p) => p.x + p.w)), y1 = Math.max(...parts.map((p) => p.y + p.h));
      return { state: layer.getAttribute("data-state"), b: { x: x0, y: y0, w: x1 - x0, h: y1 - y0 } };
    });
    const base = outer.find((o) => o.b);
    for (const o of outer) {
      if (!o.b) { add("state", `${name} ${o.state}: no box (hide layers with visibility="hidden", not display:none)`); continue; }
      const d = { x: o.b.x - base.b.x, y: o.b.y - base.b.y, w: o.b.w - base.b.w, h: o.b.h - base.b.h };
      if (Object.values(d).some((v) => Math.abs(v) > opts.tol)) {
        add("state", `${name} ${o.state} vs ${base.state}: Δx ${r1(d.x)}, Δy ${r1(d.y)}, Δw ${r1(d.w)}, Δh ${r1(d.h)} (box ${r1(o.b.w)}×${r1(o.b.h)})`);
      }
    }
  }

  return { canvas: `${canvas.w}×${canvas.h}`, texts: texts.length, targets: targets.length, states: sheets.length, findings };
})()
