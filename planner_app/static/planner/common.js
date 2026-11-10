/* utilidades compartidas */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const DIAS = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'];
const MESES = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];

const iso = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
const parse = s => { const [y,m,d] = s.split('-').map(Number); return new Date(y, m-1, d); };
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate()+n); return x; };
const mondayOf = d => addDays(d, -((d.getDay()+6) % 7));
const mins = hhmm => { const [h,m] = hhmm.split(':').map(Number); return h*60+m; };
const hhmm = m => `${String(Math.floor(m/60)).padStart(2,'0')}:${String(m%60).padStart(2,'0')}`;
const fmtDay = d => `${d.getDate()} ${MESES[d.getMonth()]}`;

function textColor(hex) {
  const n = parseInt(hex.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
  return (0.299*r + 0.587*g + 0.114*b) > 150 ? '#212529' : '#fff';
}

async function api(method, url, data) {
  const r = await fetch(url, {
    method,
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': $('meta[name=csrf]').content},
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  if (r.redirected && r.url.includes('/login/')) { location.href = '/login/'; throw new Error('login'); }
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error('api'), {errors: j.errors || {__all__: ['Error inesperado']}});
  return j;
}
const errText = e => Object.entries(e.errors || {}).map(([k, v]) => (k === '__all__' ? '' : k + ': ') + v.join(' ')).join(' · ');

function toast(msg, kind = 'danger') {
  const el = document.createElement('div');
  el.className = `toast align-items-center text-bg-${kind} border-0`;
  el.innerHTML = `<div class="d-flex"><div class="toast-body">${esc(msg)}</div><button class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
  $('#toasts').append(el);
  const t = new bootstrap.Toast(el, {delay: 4000}); t.show(); el.addEventListener('hidden.bs.toast', () => el.remove());
}
const safe = fn => async (...a) => { try { return await fn(...a); } catch (e) { if (e.errors) toast(errText(e)); else throw e; } };

const pasadoBloque = (fechaIso, b) => { const [y, m, d] = fechaIso.split('-').map(Number), [h, mi] = b.fin.split(':').map(Number); return new Date(y, m-1, d, h, mi) <= new Date(); };
const pasadaAccion = a => { const hoy0 = parse(iso(new Date())); return (a.fecha ? parse(a.fecha) : addDays(parse(a.semana), 6)) < hoy0; };

/* ---------- estados: '' (pendiente) · hecha · no_hecha · reprogramada ---------- */
const ESTADOS = {
  '':           {t: 'Pendiente',    i: '',  c: 'secondary'},
  hecha:        {t: 'Hecha',        i: '✓', c: 'success'},
  no_hecha:     {t: 'No hecha',     i: '✕', c: 'danger'},
  reprogramada: {t: 'Reprogramada', i: '↻', c: 'warning'},
};
const stBtn = (estado, big = false, auto = false) =>
  `<button type="button" class="st ${estado} ${big ? 'st-lg' : ''}" data-st="${estado}" title="${ESTADOS[estado].t}${auto ? ' (automático)' : ''}">${ESTADOS[estado].i}</button>`;

/* menú flotante para elegir estado; resuelve con el estado elegido o undefined si se cancela.
   Si la actividad ya pasó (pasado=true) no se ofrece «Pendiente»: el sistema la volvería a cerrar. */
function pickEstado(anchor, {actual = '', pasado = false} = {}) {
  return new Promise(resolve => {
    $('#estadoMenu')?.remove();
    const opts = Object.keys(ESTADOS).filter(k => !(pasado && k === ''));
    const m = document.createElement('div'); m.id = 'estadoMenu'; m.className = 'estado-menu';
    m.innerHTML = opts.map(k => `<button class="btn btn-sm btn-${actual === k ? '' : 'outline-'}${ESTADOS[k].c}" data-v="${k}">${ESTADOS[k].i} ${ESTADOS[k].t}</button>`).join('');
    const close = v => { m.remove(); back.remove(); resolve(v); };
    const back = document.createElement('div'); back.className = 'estado-back'; back.onclick = () => close(undefined);
    m.onclick = e => { const b = e.target.closest('[data-v]'); if (b) close(b.dataset.v); };
    document.body.append(back, m);
    if (innerWidth >= 768) {  // popover junto al botón; en celular queda como hoja inferior (CSS)
      const r = anchor.getBoundingClientRect();
      m.style.top = Math.min(r.bottom + 6, innerHeight - m.offsetHeight - 8) + 'px';
      m.style.left = Math.max(8, Math.min(r.left - m.offsetWidth + r.width, innerWidth - m.offsetWidth - 8)) + 'px';
    }
  });
}

/* ---------- modal de bloque (alta / edición) ---------- */
const BloqueModal = (() => {
  const el = $('#bloqueModal'), form = $('#bloqueForm'), modal = new bootstrap.Modal(el);
  let cur = null, onSave = null;
  $('#diasChecks').innerHTML = DIAS.map((d, i) =>
    `<input type="checkbox" class="btn-check" id="dc${i}" value="${i}"><label class="btn btn-outline-secondary btn-sm" for="dc${i}">${d.slice(0,3)}</label>`).join('');
  form.dia.innerHTML = DIAS.map((d, i) => `<option value="${i}">${d}</option>`).join('');

  function open({bloque, dia = 0, inicio = '09:00', fin = '10:00', categorias, done}) {
    cur = bloque; onSave = done;
    $('#bloqueTitulo').textContent = bloque ? 'Editar actividad' : 'Nueva actividad';
    form.categoria.innerHTML = categorias.map(c => `<option value="${c.id}">${esc(c.nombre)}</option>`).join('');
    const b = bloque || {titulo: '', nota: '', categoria: categorias[0]?.id, seguimiento: false, dia, inicio, fin};
    form.titulo.value = b.titulo; form.nota.value = b.nota; form.categoria.value = b.categoria;
    form.inicio.value = b.inicio; form.fin.value = b.fin; form.seguimiento.checked = b.seguimiento; form.dia.value = b.dia;
    const puntual = !!bloque?.fecha;   // actividad puntual (p. ej. una reprogramación): se edita por fecha, no por día de la semana
    form.fecha.value = bloque?.fecha || '';
    $('#diasMulti').classList.toggle('d-none', !!bloque); $('#diaUno').classList.toggle('d-none', !bloque || puntual);
    $('#fechaUno').classList.toggle('d-none', !puntual);
    $$('#diasChecks input').forEach(c => c.checked = !bloque && +c.value === b.dia);
    $('#bloqueDel').classList.toggle('d-none', !bloque); $('#bloqueErr').textContent = '';
    modal.show(); setTimeout(() => form.titulo.focus(), 300);
  }

  form.addEventListener('submit', async ev => {
    ev.preventDefault();
    const data = {titulo: form.titulo.value.trim(), nota: form.nota.value.trim(), categoria: form.categoria.value,
      inicio: form.inicio.value, fin: form.fin.value, seguimiento: form.seguimiento.checked};
    try {
      if (cur) await api('PUT', `/api/bloques/${cur.id}/`, {...data, dia: form.dia.value, fecha: cur.fecha ? form.fecha.value : ''});
      else {
        const dias = $$('#diasChecks input:checked').map(c => +c.value);
        if (!dias.length) { $('#bloqueErr').textContent = 'Elegí al menos un día.'; return; }
        await api('POST', '/api/bloques/', {...data, dias});
      }
      modal.hide(); onSave && onSave();
    } catch (e) { $('#bloqueErr').textContent = errText(e); }
  });
  $('#bloqueDel').addEventListener('click', async () => {
    if (!confirm('¿Eliminar esta actividad?')) return;
    await safe(() => api('DELETE', `/api/bloques/${cur.id}/`))(); modal.hide(); onSave && onSave();
  });
  return {open};
})();


/* ---------- modal de reprogramación: resuelve {fecha, inicio, fin} o undefined si se cancela ---------- */
const ReprogModal = (() => {
  const el = $('#reprogModal'), form = $('#reprogForm'), modal = new bootstrap.Modal(el);
  let done = null, conHora = true;
  const hoy = () => iso(new Date());

  form.querySelectorAll('[data-dias]').forEach(b => b.onclick = () => { form.fecha.value = iso(addDays(new Date(), +b.dataset.dias)); });
  el.addEventListener('hidden.bs.modal', () => { const d = done; done = null; d && d(undefined); });
  form.addEventListener('submit', ev => {
    ev.preventDefault();
    const v = {fecha: form.fecha.value, inicio: form.inicio.value, fin: form.fin.value};
    const err = !v.fecha ? 'Elegí una fecha.'
      : v.fecha < hoy() ? 'La fecha no puede ser pasada.'
      : conHora && (!v.inicio || !v.fin) ? 'Indicá el horario.'
      : conHora && v.fin <= v.inicio ? 'El fin debe ser posterior al inicio.'
      : conHora && new Date(`${v.fecha}T${v.fin}`) <= new Date() ? 'La nueva fecha y hora tienen que estar en el futuro.' : '';
    if (err) { $('#reprogErr').textContent = err; return; }
    const d = done; done = null; modal.hide(); d && d(v);
  });

  /* titulo: nombre de la actividad · fecha/inicio/fin: valores iniciales · conHora=false para acciones (solo día) */
  return {open({titulo, fecha, inicio = '09:00', fin = '10:00', conHora: ch = true}) {
    conHora = ch; $('#reprogErr').textContent = '';
    $('#reprogTitulo').textContent = titulo;
    form.fecha.min = hoy(); form.fecha.value = fecha || iso(addDays(new Date(), 1));
    form.inicio.value = inicio; form.fin.value = fin;
    $('#reprogHoras').classList.toggle('d-none', !ch);
    $('#reprogAyuda').textContent = ch ? 'Se agrega una actividad en ese día y horario.' : 'Se agrega la acción en la semana de esa fecha.';
    return new Promise(res => { done = res; modal.show(); });
  }};
})();
