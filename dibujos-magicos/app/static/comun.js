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

// ---------------------------------------------------------------- sonido
// Un solo sonido a la vez: si empieza un video o una muestra de canción, se pausa lo demás.
document.addEventListener("play", (ev) => {
  for (const m of document.querySelectorAll("audio, video")) if (m !== ev.target && !m.paused) m.pause();
}, true);

// Muestra de canciones: tocar una la hace sonar; tocar la misma otra vez (o "Parar") la detiene.
// Necesita en la página: <audio id="muestra"> y <div id="sonando"> (ver bloqueMuestra()).
function escucharMuestra(m) {
  const a = document.getElementById("muestra");
  if (!m.url || (a.dataset.id === m.id && !a.paused)) { a.pause(); return; }
  a.src = m.url; a.dataset.id = m.id; a.dataset.nombre = m.nombre;
  a.play().catch(() => {});
}
function pararMuestra() { const a = document.getElementById("muestra"); if (a) a.pause(); }
function bloqueMuestra() {
  const a = el("audio", { id: "muestra", preload: "none" });
  const nombre = el("b");
  const caja = el("div", { id: "sonando", class: "sonando oculto", role: "status" },
    el("span", {}, "🎵 Sonando la muestra: ", nombre),
    el("button", { class: "boton claro", type: "button", onclick: pararMuestra }, "⏹ Parar"));
  const actualizar = () => {
    const suena = !a.paused && !a.ended;
    caja.classList.toggle("oculto", !suena);
    nombre.textContent = a.dataset.nombre || "";
  };
  for (const ev of ["play", "playing", "pause", "ended", "emptied"]) a.addEventListener(ev, actualizar);
  return el("div", { class: "bloque-muestra" },
    el("p", { class: "suave pequeno" }, "Toquen una canción para escuchar unos segundos. El video que esté sonando se pausa solo. ",
      el("a", { href: "/canciones" }, "＋ Agregar mis canciones")), a, caja);
}
