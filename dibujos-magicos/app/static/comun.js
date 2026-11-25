// Funciones compartidas por todas las páginas
async function api(ruta, opciones = {}) {
  const r = await fetch(ruta, opciones);
  let datos = null;
  try { datos = await r.json(); } catch (e) { /* sin cuerpo */ }
  if (!r.ok) throw new Error((datos && datos.error) || `Algo salió mal (${r.status}).`);
  return datos;
}
function apiJSON(ruta, metodo, cuerpo) {
  return api(ruta, { method: metodo, headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) });
}
function el(etiqueta, attrs = {}, ...hijos) {
  const e = document.createElement(etiqueta);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (k.startsWith("aria-")) e.setAttribute(k, String(v));
    else if (v !== false && v != null) e.setAttribute(k, v === true ? "" : v);
  }
  for (const h of hijos.flat()) if (h != null) e.append(h.nodeType ? h : document.createTextNode(h));
  return e;
}
const ESTADOS = { procesando: "Preparando…", revisar: "Revisar", listo: "Listo", error: "Hubo un problema" };
function guardarLocal(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
function leerLocal(k, def) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : def; } catch (e) { return def; } }
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));
