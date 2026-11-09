let S = null;
const load = safe(async () => { S = await api('GET', '/api/state/'); render(); });

function render() {
  const f = $('#cfgForm');
  f.grilla_desde.innerHTML = Array.from({length: 24}, (_, h) => `<option value="${h}">${String(h).padStart(2,'0')}:00</option>`).join('');
  f.grilla_hasta.innerHTML = Array.from({length: 24}, (_, h) => `<option value="${h+1}">${String(h+1).padStart(2,'0')}:00</option>`).join('');
  f.grilla_desde.value = S.config.grilla_desde; f.grilla_hasta.value = S.config.grilla_hasta;

  $('#cats').innerHTML = S.categorias.map(catRow).join('');

  const por = DIAS.map((n, i) => [n, S.bloques.filter(b => b.dia === i)]);
  $('#horarios').innerHTML = `<div class="table-responsive"><table class="table table-sm align-middle mb-0"><tbody>` +
    por.map(([n, bs]) => `<tr class="table-light"><th colspan="4">${n}</th></tr>` + (bs.map(b => {
      const c = S.categorias.find(c => c.id === b.categoria);
      return `<tr data-id="${b.id}" role="button"><td class="text-nowrap">${b.inicio}–${b.fin}</td><td>${esc(b.titulo)}</td>
        <td><span class="badge" style="background:${c.color};color:${textColor(c.color)};border:1px solid rgba(0,0,0,.15)">${esc(c.nombre)}</span></td>
        <td class="text-end">${b.seguimiento ? '<span title="Con seguimiento">✓</span>' : ''}</td></tr>`;
    }).join('') || `<tr><td colspan="4" class="text-muted small">—</td></tr>`)).join('') + `</tbody></table></div>`;
}

const catRow = c => `<div class="cat-row" data-id="${c?.id ?? ''}">
  <input type="color" class="form-control form-control-color" value="${c?.color ?? '#E9ECEF'}" name="color" title="Color">
  <input class="form-control" name="nombre" value="${esc(c?.nombre ?? '')}" placeholder="Nombre" maxlength="60">
  <input class="form-control" name="orden" type="number" min="0" value="${c?.orden ?? S.categorias.length}" title="Orden">
  <button class="btn btn-outline-primary" data-save>Guardar</button>
  ${c ? '<button class="btn btn-outline-danger" data-del aria-label="Eliminar">✕</button>' : '<button class="btn btn-outline-secondary" data-cancel aria-label="Cancelar">✕</button>'}</div>`;

$('#cfgForm').addEventListener('submit', safe(async ev => {
  ev.preventDefault(); const f = ev.target;
  await api('PUT', '/api/config/', {grilla_desde: +f.grilla_desde.value, grilla_hasta: +f.grilla_hasta.value});
  toast('Rango guardado', 'success'); load();
}));

$('#addCat').onclick = () => $('#cats').insertAdjacentHTML('beforeend', catRow(null));
$('#cats').addEventListener('click', safe(async ev => {
  const row = ev.target.closest('[data-id]'), id = row?.dataset.id;
  if (ev.target.closest('[data-cancel]')) return row.remove();
  if (ev.target.closest('[data-save]')) {
    const q = n => $(`[name=${n}]`, row).value;
    const d = {nombre: q('nombre').trim(), color: q('color'), orden: +q('orden') || 0};
    await api(id ? 'PUT' : 'POST', id ? `/api/categorias/${id}/` : '/api/categorias/', d);
    toast('Categoría guardada', 'success'); return load();
  }
  if (ev.target.closest('[data-del]')) {
    if (!confirm('¿Eliminar la categoría?')) return;
    await api('DELETE', `/api/categorias/${id}/`); load();
  }
}));

const abrir = (bloque) => BloqueModal.open({bloque, categorias: S.categorias, done: load});
$('#addBloque').onclick = () => abrir(null);
$('#horarios').addEventListener('click', ev => {
  const tr = ev.target.closest('tr[data-id]'); if (tr) abrir(S.bloques.find(b => b.id === +tr.dataset.id));
});
load();
