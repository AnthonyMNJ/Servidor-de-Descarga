"use strict";
/*
 * Interfaz web del simulador.
 * 1) Envía la configuración al servidor Python (web.py), que ejecuta los hilos de verdad.
 * 2) Recibe la bitácora de operaciones (hilo, operación, estado antes, resultado,
 *    estado después) y la reproduce paso a paso en la página.
 * 3) Muestra el resultado, el estado final del recurso y la línea de tiempo de los hilos.
 */

const $ = (selector) => document.querySelector(selector);

let ESCENARIOS = {};
let reproduccionActual = 0;  // identifica la reproducción en curso (para cancelar la anterior)
let saltar = false;          // "Saltar al final"
let despertar = null;        // corta la espera entre un paso y el siguiente

// ---------------------------------------------------------------- utilidades
function esc(texto) {
  return String(texto ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function formatear(lineas, cap, n) {
  return lineas.map((l) => l.replaceAll("{cap}", cap).replaceAll("{n}", n));
}

function parrafos(lineas) {
  return lineas.map((l) => {
    if (l === "") return '<div class="sep"></div>';
    const vineta = l.startsWith("  •");
    return `<p${vineta ? ' class="vineta"' : ""}>${esc(l.trim())}</p>`;
  }).join("");
}

function numeroCliente(c) {
  return parseInt(String(c).replace(/\D/g, ""), 10) || 0;
}

function esperar(ms) {
  return new Promise((resolver) => {
    const t = setTimeout(resolver, ms);
    despertar = () => { clearTimeout(t); resolver(); };
  });
}

async function api(ruta, datos) {
  const opciones = datos
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos) }
    : {};
  const resp = await fetch(ruta, opciones);
  const json = await resp.json();
  if (!resp.ok) throw new Error(json.error || "Error del servidor");
  return json;
}

function config() {
  const tipo = document.querySelector('input[name="tipo"]:checked').value;
  const sync = document.querySelector('input[name="sync"]:checked').value;
  return {
    escenario: `${tipo}-${sync}`,
    capacidad: Number($("#capacidad").value),
    clientes: Number($("#clientes").value),
  };
}

function validar(c) {
  const ok = (v, a, b) => Number.isInteger(v) && v >= a && v <= b;
  if (!ok(c.capacidad, 1, 10)) return "La capacidad debe ser un número entre 1 y 10.";
  if (!ok(c.clientes, 1, 30)) return "El número de clientes debe estar entre 1 y 30.";
  return null;
}

function mostrarError(texto) {
  const p = $("#mensaje-error");
  p.textContent = texto || "";
  p.hidden = !texto;
}

function bloquear(si) {
  $("#btn-ejecutar").disabled = si;
  $("#btn-comparar").disabled = si;
}

// ---------------------------------------------------- explicación previa
function actualizarExplicacion() {
  const c = config();
  const e = ESCENARIOS[c.escenario];
  if (!e) return;
  let html = `<h3>¿Qué va a pasar? — ${esc(e.titulo)}</h3>` +
    parrafos(formatear(e.antes, c.capacidad, c.clientes));
  if (c.clientes <= c.capacidad) {
    html += `<p class="aviso">Hay ${c.clientes} clientes y ${c.capacidad} lugares: no alcanzan para ` +
      `superar el límite. Aumente el número de clientes para ver el problema.</p>`;
  }
  const caja = $("#que-pasara");
  caja.innerHTML = html;
  caja.className = "explicacion " + (e.con_sync ? "con" : "sin");
}

// ------------------------------------------------ dibujo del recurso
function cajitas(n, max) {
  let h = "";
  for (let i = 0; i < Math.max(n, max); i++) {
    h += `<i class="caja-mini ${i >= max ? "exceso" : i < n ? "lleno" : ""}"></i>`;
  }
  return `<span class="cajitas">${h}</span>`;
}

/** Estado del recurso en una celda de la tabla. */
function htmlEstado(estado, tipo) {
  if (tipo === "basico") {
    const n = estado.conexiones_activas, max = estado.max;
    const exceso = n > max ? ` <span class="etiqueta mal">SOBRECUPO +${n - max}</span>` : "";
    return `<span class="estado ${n > max ? "mal" : ""}">${cajitas(n, max)} <b>${n}/${max}</b>${exceso}</span>`;
  }
  const slots = estado.slots.map((c, i) =>
    `<span class="slot ${c ? "" : "vacio"}" title="Slot ${i}">${c ? esc(c) : "--"}</span>`).join("");
  return `<span class="estado">${slots} <span class="mb">${estado.total_mb} MB</span></span>`;
}

function textoEstado(estado, tipo) {
  if (tipo === "basico") return `conexiones_activas = ${estado.conexiones_activas}`;
  return `[${estado.slots.map((c) => c || "--").join("|")}] · ${estado.total_mb} MB`;
}

function estadoInicial(r) {
  return r.tipo === "basico"
    ? { conexiones_activas: 0, max: r.capacidad }
    : { slots: Array(r.capacidad).fill(null), total_mb: 0, max: r.capacidad };
}

function claseEvento(e, r) {
  if (e.pisado_a) return "mal";
  if (e.evento === "entra") {
    const usando = r.tipo === "basico" ? e.despues.conexiones_activas : e.dentro;
    return usando > r.capacidad ? "mal" : "ok";
  }
  return e.evento === "rechazado" ? "aviso" : "info";
}

function etiquetaResultado(e, r) {
  return `<span class="etiqueta ${claseEvento(e, r)}">${esc(e.resultado)}</span>`;
}

/** Panel grande "Estado del recurso ahora". */
function dibujarRecurso(r, estado, evento, mbReales) {
  const cap = r.capacidad;
  let html;
  if (r.tipo === "basico") {
    const n = estado.conexiones_activas;
    let lugares = "";
    for (let i = 0; i < Math.max(n, cap); i++) {
      lugares += `<div class="lugar ${i >= cap ? "exceso" : i < n ? "lleno" : ""}">${i >= cap ? "!" : ""}</div>`;
    }
    html = `<div class="recurso-titulo">Recurso compartido ahora: <code>conexiones_activas</code> ` +
      `(cada cuadro es un lugar del servidor)</div>
      <div class="lugares">${lugares}</div>
      <div class="recurso-num ${n > cap ? "txt-mal" : ""}">${n} / ${cap} conexiones
        ${n > cap ? `<span class="etiqueta mal">¡SOBRECUPO +${n - cap}!</span>` : ""}</div>`;
  } else {
    const dentro = evento ? evento.dentro : 0;
    const slots = estado.slots.map((c, i) => {
      const pisado = evento && evento.pisado_a && evento.slot === i;
      return `<div class="slot-grande ${c ? "ocupado" : ""} ${pisado ? "pisado" : ""}">
        <span>Slot ${i}</span><b>${c ? esc(c) : "libre"}</b>
        ${pisado ? `<span class="txt-mal">¡pisó a ${esc(evento.pisado_a)}!</span>` : ""}</div>`;
    }).join("");
    html = `<div class="recurso-titulo">Recurso compartido ahora: <code>estado_servidor</code></div>
      <div class="slots-grandes">${slots}</div>
      <div class="recurso-datos">
        <div>Total registrado (<code>total_bytes_servidos</code>): <b>${estado.total_mb} MB</b></div>
        <div>MB descargados de verdad hasta ahora: <b>${mbReales} MB</b></div>
        <div>Clientes descargando a la vez: ${cajitas(dentro, cap)}
          <b class="${dentro > cap ? "txt-mal" : ""}">${dentro}/${cap}</b></div>
      </div>`;
  }
  html += evento
    ? `<div class="ultimo">Última operación: <b>Hilo ${evento.hilo_id}</b> (cliente ${esc(evento.cliente)}) ` +
      `solicitó <b>${esc(evento.operacion)}</b> → ${etiquetaResultado(evento, r)}</div>`
    : `<div class="ultimo">Se lanzan ${r.clientes} hilos al mismo tiempo…</div>`;
  $("#recurso-vivo").innerHTML = html;
}

function agregarFila(e, i, r) {
  const tr = document.createElement("tr");
  tr.className = "nueva" + (claseEvento(e, r) === "mal" ? " fila-mal" : "");
  const archivo = e.archivo && e.operacion === "PEDIR SLOT" ? `<br><small>${esc(e.archivo)}</small>` : "";
  tr.innerHTML = `
    <td>${i + 1}</td>
    <td>${e.t.toFixed(3)} s</td>
    <td><code>Hilo ${e.hilo_id}</code></td>
    <td>${esc(e.cliente)}</td>
    <td><b>${esc(e.operacion)}</b>${archivo}</td>
    <td>${htmlEstado(e.antes, r.tipo)}</td>
    <td>${etiquetaResultado(e, r)}</td>
    <td>${htmlEstado(e.despues, r.tipo)}</td>`;
  $("#tabla-eventos tbody").appendChild(tr);
  const cont = $("#contenedor-eventos");
  cont.scrollTop = cont.scrollHeight;
}

// ------------------------------------------------ reproducción paso a paso
async function reproducir(r) {
  const mio = ++reproduccionActual;
  saltar = false;
  $("#tabla-eventos tbody").innerHTML = "";
  $("#resultado").hidden = true;
  $("#ejecucion").hidden = false;
  $("#btn-saltar").hidden = false;
  $("#ejecucion").scrollIntoView({ behavior: "smooth", block: "start" });

  let mbReales = 0;
  dibujarRecurso(r, estadoInicial(r), null, 0);
  const pausa = Number($("#velocidad").value);
  if (pausa && !saltar) await esperar(pausa);

  for (let i = 0; i < r.eventos.length; i++) {
    if (mio !== reproduccionActual) return;  // se lanzó otra simulación
    const e = r.eventos[i];
    if (e.evento === "sale") mbReales += e.mb || 0;
    agregarFila(e, i, r);
    dibujarRecurso(r, e.despues, e, mbReales);
    if (pausa && !saltar) await esperar(pausa);
  }
  if (mio !== reproduccionActual) return;
  $("#btn-saltar").hidden = true;
  mostrarResultado(r);
}

// ------------------------------------------------ resultado
function mostrarResultado(r) {
  const cap = r.capacidad;
  const problemas = r.problemas;

  $("#veredicto").innerHTML = problemas.length
    ? `<div class="veredicto mal"><b>✘ PROBLEMA</b><ul>${problemas.map((p) => `<li>${esc(p)}</li>`).join("")}</ul></div>`
    : `<div class="veredicto ok"><b>✔ CORRECTO:</b> el servidor nunca superó su límite de ${cap}.</div>`;

  const m = [
    ["Límite del servidor", cap, false],
    ["Máximo de clientes a la vez", r.pico, r.pico > cap],
    ["Clientes atendidos", r.admitidos, false],
    ["Clientes rechazados", r.rechazados, false],
  ];
  if (r.tipo === "complejo") {
    m.push(["Clientes que pisaron a otro", r.pisados, r.pisados > 0],
      ["MB descargados de verdad", `${r.mb_reales} MB`, false],
      ["MB que registró el servidor", `${r.mb_registrados} MB`, r.mb_registrados !== r.mb_reales]);
  }
  $("#metricas").innerHTML = m.map(([t, v, malo]) =>
    `<div class="metrica ${malo ? "mal" : ""}"><span>${esc(t)}</span><b>${esc(v)}</b></div>`).join("");

  $("#estado-final").innerHTML = htmlEstadoFinal(r);
  $("#linea-tiempo").innerHTML = htmlLineaTiempo(r);
  $("#porque").innerHTML = parrafos(r.porque);
  $("#porque").className = "explicacion " + (problemas.length ? "sin" : "con");

  $("#resultado").hidden = false;
  $("#resultado").scrollIntoView({ behavior: "smooth", block: "start" });
}

function htmlEstadoFinal(r) {
  const ef = r.estado_final;
  let codigo;
  if (r.tipo === "basico") {
    codigo = `conexiones_activas = ${ef.conexiones_activas}    # al terminar debe ser 0\nMAX_CAPACIDAD      = ${ef.max}`;
  } else {
    const slots = ef.slots.map((c, i) =>
      `    ${i}: ${c ? `{"cliente_id": "${c}", ...}` : "None"}`).join(",\n");
    codigo = `estado_servidor = {\n  "slots": {\n${slots}\n  },\n  "total_bytes_servidos": ${ef.total_mb}` +
      `    # MB descargados de verdad: ${r.mb_reales}\n}`;
  }
  return `<div class="estado-final"><pre><code>${esc(codigo)}</code></pre>${htmlEstado(ef, r.tipo)}</div>`;
}

/** Gráfico de cuántos clientes usan el servidor a la vez + una fila por hilo. */
function htmlLineaTiempo(r) {
  const ev = r.eventos;
  if (!ev.length) return "<p>No hubo operaciones.</p>";
  const tMax = Math.max(...ev.map((e) => e.t)) * 1.03;
  const pct = (t) => `${((t / tMax) * 100).toFixed(2)}%`;
  const cap = r.capacidad;

  // --- gráfico de ocupación (escalera) ---
  const cambios = ev.filter((e) => e.evento === "entra" || e.evento === "sale")
    .slice().sort((a, b) => a.t - b.t);
  const yMax = Math.max(cap, r.pico) + 1;
  const y = (v) => (100 - (v / yMax) * 100).toFixed(2);
  const x = (t) => ((t / tMax) * 1000).toFixed(1);
  let actual = 0, puntos = `0,100`;
  for (const e of cambios) {
    puntos += ` ${x(e.t)},${y(actual)}`;
    actual += e.evento === "entra" ? 1 : -1;
    puntos += ` ${x(e.t)},${y(actual)}`;
  }
  puntos += ` 1000,${y(actual)} 1000,100`;
  const grafico = `
    <div class="lt-fila">
      <div class="lt-nombre">A la vez<small>máx. ${r.pico} / límite ${cap}</small></div>
      <div class="lt-pista grafico">
        <svg viewBox="0 0 1000 100" preserveAspectRatio="none" aria-label="Clientes usando el servidor a la vez">
          <rect x="0" y="0" width="1000" height="${y(cap)}" fill="var(--mal-fondo)"></rect>
          <polygon points="${puntos}" fill="var(--info)" fill-opacity=".35" stroke="var(--info)"
                   stroke-width="2" vector-effect="non-scaling-stroke"></polygon>
          <line x1="0" x2="1000" y1="${y(cap)}" y2="${y(cap)}" stroke="var(--mal)" stroke-width="2"
                stroke-dasharray="6 4" vector-effect="non-scaling-stroke"></line>
        </svg>
        <span class="lt-limite" style="top:calc(${y(cap)}% - 16px)">límite ${cap}</span>
      </div>
    </div>`;

  // --- una fila por cliente / hilo ---
  const porCliente = new Map();
  for (const e of ev) {
    if (!porCliente.has(e.cliente)) porCliente.set(e.cliente, []);
    porCliente.get(e.cliente).push(e);
  }
  const clientes = [...porCliente.keys()].sort((a, b) => numeroCliente(a) - numeroCliente(b));
  const seg = (a, b, clase, titulo) =>
    `<div class="seg ${clase}" style="left:${pct(a)};width:${pct(Math.max(b - a, tMax * 0.004))}" title="${esc(titulo)}"></div>`;

  let filas = "";
  for (const c of clientes) {
    const lista = porCliente.get(c);
    const pedir = lista.find((e) => e.operacion === "CONECTAR" || e.operacion === "PEDIR SLOT");
    const soltar = lista.find((e) => e.operacion === "DESCONECTAR" || e.operacion === "LIBERAR SLOT");
    let barras = "";
    if (pedir) {
      barras += seg(pedir.t_solicitud, pedir.t, "pidiendo",
        `Pidiendo entrar (${pedir.t_solicitud.toFixed(3)} s → ${pedir.t.toFixed(3)} s)`);
      if (pedir.evento === "rechazado") {
        barras += `<div class="marca-rechazo" style="left:${pct(pedir.t)}" title="Rechazado">✕</div>`;
      } else if (soltar) {
        barras += seg(pedir.t, soltar.t_solicitud, pedir.pisado_a ? "usando mal" : "usando",
          pedir.pisado_a ? `Descargando (pisó a ${pedir.pisado_a})` : "Descargando");
        barras += seg(soltar.t_solicitud, soltar.t, "saliendo", "Liberando su lugar");
      }
    }
    const hilo = pedir ? `Hilo ${pedir.hilo_id}` : "";
    filas += `<div class="lt-fila"><div class="lt-nombre">Cliente ${esc(c)}<small>${hilo}</small></div>` +
      `<div class="lt-pista">${barras}</div></div>`;
  }

  let eje = "";
  for (let k = 0; k <= 4; k++) {
    const t = (tMax * k) / 4;
    eje += `<span style="left:${pct(t)}">${t.toFixed(2)} s</span>`;
  }

  return `<div class="lt">${grafico}${filas}
      <div class="lt-fila"><div></div><div class="lt-eje">${eje}</div></div>
    </div>
    <div class="leyenda">
      <span><i style="background:repeating-linear-gradient(45deg,var(--aviso),var(--aviso) 4px,transparent 4px,transparent 7px)"></i>Pidiendo entrar / esperando turno</span>
      <span><i style="background:var(--ok)"></i>Descargando</span>
      <span><i style="background:var(--mal)"></i>Descargando en un slot pisado</span>
      <span><i style="background:var(--info)"></i>Liberando su lugar</span>
      <span><b class="txt-mal">✕</b> Rechazado</span>
      <span><i style="background:var(--mal-fondo)"></i>Zona de sobrecupo (arriba del límite)</span>
    </div>`;
}

// ------------------------------------------------ comparación
async function compararTodo() {
  const c = config();
  const error = validar(c);
  mostrarError(error);
  if (error) return;
  bloquear(true);
  try {
    const datos = await api("/api/comparar", { capacidad: c.capacidad, clientes: c.clientes });
    const cap = datos.capacidad;
    const filas = datos.resultados.map((r) => {
      const complejo = r.tipo === "complejo";
      const mbMal = complejo && r.mb_registrados !== r.mb_reales;
      return `<tr class="${r.problemas.length ? "fila-mal" : ""}">
        <td><b>${esc(r.titulo)}</b></td>
        <td class="${r.pico > cap ? "txt-mal" : ""}"><b>${r.pico}</b> / ${cap}</td>
        <td>${r.admitidos}</td>
        <td>${r.rechazados}</td>
        <td class="${r.pisados ? "txt-mal" : ""}">${complejo ? r.pisados : "-"}</td>
        <td class="${mbMal ? "txt-mal" : ""}">${complejo ? `${r.mb_registrados} / ${r.mb_reales}` : "-"}</td>
        <td><code>${esc(textoEstado(r.estado_final, r.tipo))}</code></td>
        <td>${r.problemas.length ? '<span class="etiqueta mal">✘ PROBLEMA</span>' : '<span class="etiqueta ok">✔ CORRECTO</span>'}</td>
      </tr>`;
    }).join("");
    $("#tabla-comparacion").innerHTML = `
      <p>Se ejecutaron los 4 escenarios con capacidad <b>${cap}</b> y <b>${datos.clientes}</b> clientes.</p>
      <div class="tabla-scroll"><table>
        <thead><tr><th>Escenario</th><th>Máx. a la vez / límite</th><th>Atendidos</th><th>Rechazados</th>
          <th>Pisados</th><th>MB registrados / reales</th><th>Estado final del recurso</th><th>Resultado</th></tr></thead>
        <tbody>${filas}</tbody>
      </table></div>
      <div class="explicacion con" style="margin-top:14px">
        <p><b>Conclusión:</b> sin control, varios clientes ocupan el servidor al mismo tiempo y se supera
        el límite (o se pierden datos). Con Lock, el límite se respeta siempre: los que sobran son
        rechazados en lugar de sobrecargar el servidor.</p>
      </div>`;
    $("#comparacion").hidden = false;
    $("#comparacion").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    mostrarError(err.message);
  } finally {
    bloquear(false);
  }
}

// ------------------------------------------------ inicio
async function ejecutar(evento) {
  evento.preventDefault();
  const c = config();
  const error = validar(c);
  mostrarError(error);
  if (error) return;
  bloquear(true);
  try {
    const r = await api("/api/simular", c);
    bloquear(false);
    await reproducir(r);
  } catch (err) {
    mostrarError(err.message);
  } finally {
    bloquear(false);
  }
}

async function iniciar() {
  try {
    const datos = await api("/api/escenarios");
    ESCENARIOS = datos.escenarios;
  } catch (err) {
    mostrarError("No se pudo conectar con el servidor Python. ¿Está ejecutándose web.py?");
    return;
  }
  actualizarExplicacion();
  $("#form-config").addEventListener("submit", ejecutar);
  $("#form-config").addEventListener("input", actualizarExplicacion);
  $("#btn-comparar").addEventListener("click", compararTodo);
  $("#btn-saltar").addEventListener("click", () => { saltar = true; if (despertar) despertar(); });
}

iniciar();
