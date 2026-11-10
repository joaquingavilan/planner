let S = null, week = mondayOf(new Date());
const modal = new bootstrap.Modal('#accionModal'), form = $('#accionForm');
let cur = null;

const load = safe(async () => { S = await api('GET', `/api/state/?week=${iso(week)}`); render(); });

function render() {
  $('#rango').textContent = `Semana del ${fmtDay(week)} al ${fmtDay(addDays(week, 6))}`;
  const A = S.acciones, hechas = A.filter(a => a.estado === 'hecha').length;
  const r = $('#regla');
  r.className = 'alert py-2 ' + (hechas ? 'alert-success' : 'alert-warning');
  r.innerHTML = hechas
    ? `<b>${hechas}/${A.length || 3}</b> acciones de lanzamiento hechas: el bloque de construir está habilitado.`
    : `<b>Lanzar va primero.</b> Todavía no hiciste ninguna acción de lanzamiento esta semana: sin una, no hay bloque de construir.`;
  $('#lista').innerHTML = A.map((a, i) => `
    <div class="col-md-6 col-xl-4"><div class="card h-100 ${{hecha: 'border-success', no_hecha: 'border-danger', reprogramada: 'border-warning'}[a.estado] || ''}">
      <div class="card-body" data-id="${a.id}">
        <div class="d-flex align-items-start gap-2">
          <div class="flex-grow-1"><div class="text-muted small">${i+1}. Cuando sea <b>${esc(a.cuando) || '…'}</b>, en <b>${esc(a.donde) || '…'}</b>, voy a</div>
            <div class="fs-6 ${a.estado === 'hecha' ? 'text-decoration-line-through text-muted' : ''}">${esc(a.accion)}</div>
            ${a.fecha ? `<span class="badge text-bg-light border mt-1">${fmtDay(parse(a.fecha))}</span>` : ''}
            ${a.notas ? `<div class="small text-muted mt-2">${esc(a.notas)}</div>` : ''}</div>
          <button class="btn btn-sm btn-light" data-edit>Editar</button>
        </div>
        <div class="d-flex flex-wrap gap-1 mt-3">
          ${Object.entries(ESTADOS).filter(([v]) => !(v === '' && pasadaAccion(a))).map(([v, e]) =>
            `<button class="btn btn-sm btn-${a.estado === v ? '' : 'outline-'}${e.c}" data-estado="${v}">${e.i} ${e.t}</button>`).join('')}
        </div>
        ${a.estado === 'reprogramada' && a.nueva_fecha ? `<div class="repro-tag mt-2">↻ Reprogramada para el ${fmtDay(parse(a.nueva_fecha))}</div>` : ''}
        ${a.auto ? '<div class="auto-tag mt-2">Marcada automáticamente al vencer. Corregila si la hiciste.</div>' : ''}
      </div></div></div>`).join('') || '<p class="text-muted">Sin acciones esta semana. Elegí las 3 con «+ Acción» o copiá las de la semana anterior.</p>';
}

$('#lista').addEventListener('click', safe(async ev => {
  const card = ev.target.closest('[data-id]'); if (!card) return;
  const a = S.acciones.find(x => x.id === +card.dataset.id);
  if (ev.target.closest('[data-edit]')) return openModal(a);
  const b = ev.target.closest('[data-estado]');
  if (!b) return;
  if (b.dataset.estado === 'reprogramada') {
    const n = await ReprogModal.open({titulo: a.accion, conHora: false, fecha: a.nueva_fecha});
    if (!n) return;
    await api('POST', `/api/acciones/${a.id}/reprogramar/`, {fecha: n.fecha});
  } else await api('PUT', `/api/acciones/${a.id}/`, {...a, estado: b.dataset.estado});
  load();
}));

function openModal(a) {
  cur = a; $('#accionErr').textContent = '';
  for (const k of ['cuando', 'donde', 'accion', 'fecha', 'notas']) form[k].value = a ? a[k] : '';
  $('#accionDel').classList.toggle('d-none', !a); modal.show();
}
form.addEventListener('submit', async ev => {
  ev.preventDefault();
  const d = Object.fromEntries(['cuando', 'donde', 'accion', 'fecha', 'notas'].map(k => [k, form[k].value.trim()]));
  try {
    if (cur) await api('PUT', `/api/acciones/${cur.id}/`, {...cur, ...d, fecha: d.fecha || ''});
    else await api('POST', '/api/acciones/', {...d, semana: iso(week), orden: S.acciones.length});
    modal.hide(); load();
  } catch (e) { $('#accionErr').textContent = errText(e); }
});
$('#accionDel').onclick = safe(async () => {
  if (!confirm('¿Eliminar esta acción?')) return;
  await api('DELETE', `/api/acciones/${cur.id}/`); modal.hide(); load();
});
$('#nueva').onclick = $('#nueva2').onclick = () => openModal(null);
$('#copiar').onclick = safe(async () => {
  try { const r = await api('POST', '/api/acciones/copiar/', {semana: iso(week)}); toast(`${r.copiadas} acciones copiadas`, 'success'); }
  catch (e) { toast(errText(e)); }
  load();
});
$('#prev').onclick = () => { week = addDays(week, -7); load(); };
$('#next').onclick = () => { week = addDays(week, 7); load(); };
$('#hoy').onclick = () => { week = mondayOf(new Date()); load(); };
load();
