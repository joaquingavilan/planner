const PX = () => parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--hour'));
let S = null;                       // estado del servidor
let week = mondayOf(new Date());    // lunes visible
let day = new Date();               // día visible en modo "día"
let modo = localStorage.getItem('modo') || (innerWidth < 768 ? 'dia' : 'semana');

// ¿el bloque se muestra en el día i de la semana visible? (las puntuales solo en su fecha)
const enDia = (b, i) => b.dia === i && (!b.fecha || b.fecha === iso(addDays(week, i)));
const fechaCorta = f => { const d = parse(f); return `${DIAS[(d.getDay()+6)%7].slice(0,3).toLowerCase()} ${fmtDay(d)}`; };
const catOf = id => S.categorias.find(c => c.id === id);
const cumpl = (b, fecha) => S.cumplimientos[`${b.id}|${iso(fecha)}`] || {estado: '', auto: false};
const estadoDe = (b, fecha) => cumpl(b, fecha).estado;

async function load() {
  S = await api('GET', `/api/state/?week=${iso(week)}`);
  if (S.cerrados) toast(`${S.cerrados} ${S.cerrados === 1 ? 'actividad vencida pasó' : 'actividades vencidas pasaron'} a «No hecha». Podés corregirlas.`, 'warning');
  render();
}
const reload = safe(load);

function render() {
  const fin = addDays(week, 6);
  $('#rango').textContent = modo === 'dia'
    ? `${DIAS[(day.getDay()+6)%7]} ${fmtDay(day)}`
    : `${fmtDay(week)} – ${fmtDay(fin)} ${fin.getFullYear()}`;
  $$('#modo button').forEach(b => b.classList.toggle('active', b.dataset.modo === modo));
  // estadísticas de la semana
  const seg = S.bloques.filter(b => b.seguimiento).length;
  const cnt = k => Object.values(S.cumplimientos).filter(c => c.estado === k).length;
  $('#stats').textContent = `✓ ${cnt('hecha')} · ✕ ${cnt('no_hecha')} · ↻ ${cnt('reprogramada')} · Lanzamiento ${S.acciones.filter(a => a.estado === 'hecha').length}/${S.acciones.length}`;
  $('#vista').innerHTML = modo === 'dia' ? renderDia() : renderSemana();
}

/* ----- vista semana ----- */
function rango() {
  let d = S.config.grilla_desde * 60, h = S.config.grilla_hasta * 60;
  S.bloques.forEach(b => { d = Math.min(d, Math.floor(mins(b.inicio)/60)*60); h = Math.max(h, Math.ceil(mins(b.fin)/60)*60); });
  return [d, h];
}

function layoutDay(blks) {  // columnas para bloques solapados
  const out = []; let group = [], end = 0;
  const flush = () => { const n = Math.max(...group.map(g => g.col)) + 1; group.forEach(g => out.push({...g, n})); group = []; };
  blks.sort((a, b) => mins(a.inicio) - mins(b.inicio)).forEach(b => {
    if (group.length && mins(b.inicio) >= end) { flush(); end = 0; }
    const used = group.filter(g => mins(g.b.fin) > mins(b.inicio)).map(g => g.col);
    let col = 0; while (used.includes(col)) col++;
    group.push({b, col}); end = Math.max(end, mins(b.fin));
  });
  if (group.length) flush();
  return out;
}

function renderSemana() {
  const [d0, d1] = rango(), px = PX(), hoy = iso(new Date());
  const heads = DIAS.map((n, i) => { const f = addDays(week, i);
    return `<div class="wk-head ${iso(f) === hoy ? 'today' : ''}" data-dia="${i}">${n.slice(0,3)}<small>${fmtDay(f)}</small></div>`; }).join('');
  const hours = Array.from({length: (d1-d0)/60}, (_, i) => `<div>${String((d0/60)+i).padStart(2,'0')}:00</div>`).join('');
  const cols = DIAS.map((_, i) => {
    const f = addDays(week, i);
    const blks = layoutDay(S.bloques.filter(b => enDia(b, i))).map(({b, col, n}) => blockEl(b, f, d0, px, col, n)).join('');
    return `<div class="wk-col ${iso(f) === hoy ? 'today' : ''}" data-dia="${i}" style="height:${(d1-d0)/60*px}px">${blks}</div>`;
  }).join('');
  return `<div class="wk-wrap"><div class="wk"><div></div>${heads}<div class="wk-hours">${hours}</div>${cols}</div></div>`;
}

function blockEl(b, f, d0, px, col, n) {
  const c = catOf(b.categoria), {estado: e, auto, nueva} = b.seguimiento ? cumpl(b, f) : {estado: ''};
  const top = (mins(b.inicio) - d0) / 60 * px, h = Math.max((mins(b.fin) - mins(b.inicio)) / 60 * px, 14);
  return `<div class="blk ${e === 'hecha' ? 'done' : e === 'no_hecha' ? 'skip' : e === 'reprogramada' ? 'repro' : ''}" data-id="${b.id}" data-fecha="${iso(f)}"
    title="${esc(b.titulo)} ${b.inicio}–${b.fin}${b.nota ? ' · ' + esc(b.nota) : ''}${S.origenes[b.id] ? ' · reprogramada desde el ' + fechaCorta(S.origenes[b.id]) : ''}${nueva ? ' · reprogramada para el ' + fechaCorta(nueva.fecha) + ' ' + nueva.inicio : ''}"
    style="top:${top}px;height:${h}px;left:calc(${col/n*100}% + 1px);width:calc(${100/n}% - 2px);background:${c.color};color:${textColor(c.color)}">
    <div class="t"><b>${S.origenes[b.id] ? '↻ ' : ''}${esc(b.titulo)}</b>${h > 40 ? `<span class="n">${b.inicio}–${b.fin}</span>` : ''}</div>${b.seguimiento ? stBtn(e, false, auto).replace('<button', h < 26 ? `<button style="width:${h-4}px;height:${h-4}px;font-size:9px"` : '<button') : ''}</div>`;
}

/* ----- vista día ----- */
function renderDia() {
  const i = (day.getDay() + 6) % 7, f = day;
  if (iso(mondayOf(f)) !== iso(week)) return '';   // se recarga al cambiar de semana
  const items = S.bloques.filter(b => enDia(b, i)).sort((a, b) => mins(a.inicio) - mins(b.inicio)).map(b => {
    const c = catOf(b.categoria), {estado: e, auto, nueva} = b.seguimiento ? cumpl(b, f) : {estado: ''};
    return `<div class="day-card" data-id="${b.id}" data-fecha="${iso(f)}" style="border-color:${c.color === '#FFFFFF' ? '#ced4da' : c.color}">
      <div class="day-time">${b.inicio}–${b.fin}</div>
      <div class="flex-grow-1 ${e === 'hecha' || e === 'reprogramada' ? 'text-decoration-line-through text-muted' : ''}"><b>${esc(b.titulo)}</b>
        <span class="badge ms-1" style="background:${c.color};color:${textColor(c.color)};border:1px solid rgba(0,0,0,.15)">${esc(c.nombre)}</span>
        ${b.nota ? `<div class="small text-muted">${esc(b.nota)}</div>` : ''}
        ${S.origenes[b.id] ? `<div class="repro-tag">↻ Reprogramada desde el ${fechaCorta(S.origenes[b.id])}</div>` : ''}
        ${nueva ? `<div class="repro-tag">↻ Reprogramada para el ${fechaCorta(nueva.fecha)} · ${nueva.inicio}–${nueva.fin}</div>` : ''}
        ${auto ? '<div class="auto-tag">Marcada automáticamente al vencer. Tocá el círculo si la hiciste.</div>' : ''}</div>
      ${b.seguimiento ? stBtn(e, true, auto) : ''}</div>`;
  }).join('') || '<p class="text-muted">Nada planificado este día.</p>';
  const acc = S.acciones.filter(a => a.fecha === iso(f)).map(a => `<div class="day-card" data-accion="${a.id}" style="border-color:#C2410C">
      <div class="day-time">Lanzamiento</div><div class="flex-grow-1"><b>${esc(a.accion)}</b>
      <div class="small text-muted">${esc([a.cuando, a.donde].filter(Boolean).join(' · '))}</div></div>${stBtn(a.estado, true, a.auto)}</div>`).join('');
  const hoy = iso(new Date());
  const strip = DIAS.map((n, k) => { const d = addDays(week, k);
    return `<button class="chip ${iso(d) === iso(day) ? 'on' : ''} ${iso(d) === hoy ? 'hoy' : ''}" data-chip="${k}">${n.slice(0,3)}<b>${d.getDate()}</b></button>`; }).join('');
  return `<div class="strip mb-3">${strip}</div><div class="vstack gap-2 day-list">${acc}${items}</div>`;
}

/* ----- eventos ----- */
const open = (bloque, extra = {}) => BloqueModal.open({bloque, categorias: S.categorias, done: reload, ...extra});

$('#vista').addEventListener('click', safe(async ev => {
  const st = ev.target.closest('.st');
  const card = ev.target.closest('[data-id]'), acc = ev.target.closest('[data-accion]');
  if (st && acc) {
    const a = S.acciones.find(x => x.id === +acc.dataset.accion);
    const v = await pickEstado(st, {actual: a.estado, pasado: pasadaAccion(a)});
    if (v === undefined || v === a.estado) return;
    if (v === 'reprogramada') {
      const n = await ReprogModal.open({titulo: a.accion, conHora: false, fecha: a.nueva_fecha});
      if (!n) return;
      await api('POST', `/api/acciones/${a.id}/reprogramar/`, {fecha: n.fecha}); return load();
    }
    await api('PUT', `/api/acciones/${a.id}/`, {...a, estado: v}); return load();
  }
  if (st && card) {
    const b = S.bloques.find(x => x.id === +card.dataset.id);
    const v = await pickEstado(st, {actual: st.dataset.st, pasado: pasadoBloque(card.dataset.fecha, b)});
    if (v === undefined || v === st.dataset.st) return;
    let nueva;
    if (v === 'reprogramada') {   // hay que decir para cuándo: se agrega la actividad en ese día
      const prev = S.cumplimientos[`${b.id}|${card.dataset.fecha}`]?.nueva;
      nueva = await ReprogModal.open({titulo: `${b.titulo} · ${b.inicio}–${b.fin}`, ...(prev || {inicio: b.inicio, fin: b.fin})});
      if (!nueva) return;
    }
    await api('POST', '/api/cumplimientos/', {bloque: b.id, fecha: card.dataset.fecha, estado: v, nueva});
    return load();
  }
  if (card) return open(S.bloques.find(b => b.id === +card.dataset.id));
  const chip = ev.target.closest('[data-chip]');
  if (chip) { day = addDays(week, +chip.dataset.chip); return render(); }
  const head = ev.target.closest('.wk-head');
  if (head) { day = addDays(week, +head.dataset.dia); return setModo('dia'); }
  const col = ev.target.closest('.wk-col');
  if (col) {   // clic en hueco: nueva actividad en ese horario (a 15')
    const y = ev.clientY - col.getBoundingClientRect().top, [d0] = rango();
    const m = d0 + Math.floor(y / PX() * 4) * 15;
    open(null, {dia: +col.dataset.dia, inicio: hhmm(m), fin: hhmm(Math.min(m + 60, 23*60+59))});
  }
}));

function setModo(m) { modo = m; localStorage.setItem('modo', m); render(); }
$('#modo').addEventListener('click', ev => { const b = ev.target.closest('button'); if (b) setModo(b.dataset.modo); });
function go(dd) {  // dd: días a mover (±1 en día, ±7 en semana) o null = hoy
  if (dd === null) day = new Date(); else day = addDays(modo === 'dia' ? day : week, dd);
  const w = mondayOf(day), cambia = iso(w) !== iso(week); week = w;
  cambia ? reload() : render();
}
$('#prev').onclick = () => go(modo === 'dia' ? -1 : -7);
$('#next').onclick = () => go(modo === 'dia' ? 1 : 7);
$('#hoy').onclick = () => go(null);
$('#nuevo').onclick = $('#nuevo2').onclick = () => open(null, {dia: (day.getDay()+6)%7});
reload();

/* swipe horizontal en vista día */
let tx = null;
$('#vista').addEventListener('touchstart', e => { tx = modo === 'dia' ? [e.touches[0].clientX, e.touches[0].clientY] : null; }, {passive: true});
$('#vista').addEventListener('touchend', e => {
  if (!tx) return; const dx = e.changedTouches[0].clientX - tx[0], dy = e.changedTouches[0].clientY - tx[1]; tx = null;
  if (Math.abs(dx) > 70 && Math.abs(dx) > 2 * Math.abs(dy)) go(dx < 0 ? 1 : -1);
});
