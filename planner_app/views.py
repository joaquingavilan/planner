import json
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q
from django.db.models import ProtectedError
from django.contrib.auth.decorators import login_not_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import AccionForm, BloqueForm, CategoriaForm, ConfigForm, CumplimientoForm, ReprogForm
from .services import cerrar_vencidos, ya_vencio
from .models import DIAS, AccionLanzamiento, Bloque, Categoria, Config, Cumplimiento, Estado


# ---------- páginas ----------
def semana(request):
    return render(request, "planner/semana.html", {"nav": "semana"})


def lanzamiento(request):
    return render(request, "planner/lanzamiento.html", {"nav": "lanzamiento"})


def configuracion(request):
    return render(request, "planner/configuracion.html", {"nav": "configuracion"})


# ---------- helpers ----------
def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def parse_week(raw):
    try:
        return monday(date.fromisoformat(raw))
    except (TypeError, ValueError):
        return monday(date.today())


def body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return {}


def errors(form):
    return JsonResponse({"errors": {k: [e["message"] for e in v] for k, v in form.errors.get_json_data().items()}}, status=400)


def ser_cat(c):
    return {"id": c.id, "nombre": c.nombre, "color": c.color, "orden": c.orden}


def ser_bloque(b):
    return {"id": b.id, "dia": b.dia, "inicio": b.inicio.strftime("%H:%M"), "fin": b.fin.strftime("%H:%M"),
            "titulo": b.titulo, "nota": b.nota, "categoria": b.categoria_id, "seguimiento": b.seguimiento,
            "fecha": b.fecha.isoformat() if b.fecha else ""}


def ser_accion(a):
    return {"id": a.id, "semana": a.semana.isoformat(), "cuando": a.cuando, "donde": a.donde, "accion": a.accion,
            "fecha": a.fecha.isoformat() if a.fecha else "", "estado": a.estado, "auto": a.auto,
            "nueva_fecha": a.nueva.fecha.isoformat() if a.nueva_id and a.nueva.fecha else "", "notas": a.notas, "orden": a.orden}


def crud(request, pk, Model, Form, ser, data=None):
    """POST crea, PUT edita, DELETE borra."""
    data = body(request) if data is None else data
    if request.method == "DELETE":
        try:
            Model.objects.filter(pk=pk).delete()
        except ProtectedError:
            return JsonResponse({"errors": {"__all__": ["Tiene elementos asociados; reasignalos o borralos primero."]}}, status=409)
        return JsonResponse({"ok": True})
    obj = Model.objects.filter(pk=pk).first() if pk else None
    form = Form(data, instance=obj)
    if not form.is_valid():
        return errors(form)
    return JsonResponse(ser(form.save()), status=200 if pk else 201)


# ---------- API ----------
@require_http_methods(["GET"])
def api_state(request):
    cerrados = cerrar_vencidos()  # el cierre ocurre solo al abrir/recargar, sin procesos en segundo plano
    semana = parse_week(request.GET.get("week"))
    fechas = [semana + timedelta(days=i) for i in range(7)]
    cfg = Config.get()
    bloques = list(Bloque.objects.filter(Q(fecha__isnull=True) | Q(fecha__in=fechas)))   # plantilla + puntuales de la semana
    cumpls = list(Cumplimiento.objects.filter(fecha__in=fechas).select_related("nueva"))
    puntuales = [b.id for b in bloques if b.fecha]
    return JsonResponse({
        "semana": semana.isoformat(),
        "cerrados": cerrados,
        "dias": DIAS,
        "config": {"grilla_desde": cfg.grilla_desde, "grilla_hasta": cfg.grilla_hasta},
        "categorias": [ser_cat(c) for c in Categoria.objects.all()],
        "bloques": [ser_bloque(b) for b in bloques],
        "cumplimientos": {f"{c.bloque_id}|{c.fecha.isoformat()}": {
            "estado": c.estado, "auto": c.auto,
            "nueva": ({"fecha": c.nueva.fecha.isoformat(), "inicio": c.nueva.inicio.strftime("%H:%M"),
                       "fin": c.nueva.fin.strftime("%H:%M")} if c.nueva_id else None)} for c in cumpls},
        # puntual -> fecha de la ocurrencia original de la que viene (para rotularla «reprogramada desde»)
        "origenes": {str(n): f.isoformat() for n, f in
                     Cumplimiento.objects.filter(nueva__in=puntuales).values_list("nueva_id", "fecha")},
        "acciones": [ser_accion(a) for a in AccionLanzamiento.objects.filter(semana=semana).select_related("nueva")],
    })


@require_http_methods(["POST", "PUT", "DELETE"])
def categorias(request, pk=None):
    return crud(request, pk, Categoria, CategoriaForm, ser_cat)


@require_http_methods(["POST", "PUT", "DELETE"])
def bloques(request, pk=None):
    data = body(request)
    dias = data.get("dias")
    if request.method == "POST" and isinstance(dias, list) and dias:  # alta en varios días a la vez
        creados = []
        with transaction.atomic():
            for d in dias:
                f = BloqueForm({**data, "dia": d})
                if not f.is_valid():
                    transaction.set_rollback(True)
                    return errors(f)
                creados.append(ser_bloque(f.save()))
        return JsonResponse({"creados": creados}, status=201)
    return crud(request, pk, Bloque, BloqueForm, ser_bloque, data)


def desligar(c):
    """Quita la actividad puntual creada por una reprogramación (si todavía no tiene estado propio)."""
    n = c.nueva
    if n:
        c.nueva = None
        c.save(update_fields=["nueva"])
        if not n.cumplimientos.exists():
            n.delete()


@require_http_methods(["POST"])
def cumplimiento(request):
    """Fija el estado manual de un bloque en una fecha.

    - estado vacío: vuelve a pendiente (solo si aún no venció).
    - «reprogramada»: exige `nueva` {fecha, inicio, fin} y crea (o mueve) la actividad puntual de ese día.
    """
    data = body(request)
    b = Bloque.objects.filter(pk=data.get("bloque")).first()
    try:
        fecha = date.fromisoformat(data.get("fecha", ""))
    except ValueError:
        fecha = None
    if not b or not fecha:
        return JsonResponse({"errors": {"__all__": ["Datos inválidos."]}}, status=400)
    estado = data.get("estado") or ""

    if not estado:
        if ya_vencio(fecha, b):
            return JsonResponse({"errors": {"__all__": ["Una actividad que ya pasó no puede quedar pendiente."]}}, status=400)
        for c in Cumplimiento.objects.filter(bloque=b, fecha=fecha):
            desligar(c)
            c.delete()
        return JsonResponse({"ok": True})

    if estado not in Estado.values:
        return JsonResponse({"errors": {"estado": ["Estado inválido."]}}, status=400)

    with transaction.atomic():
        if estado == Estado.REPROGRAMADA:
            rf = ReprogForm(data.get("nueva") or {})
            if not rf.is_valid():
                return errors(rf)
            n = rf.cleaned_data
            c, _ = Cumplimiento.objects.update_or_create(bloque=b, fecha=fecha, defaults={"estado": estado, "auto": False})
            if c.nueva:   # ya estaba reprogramada: se mueve la actividad existente
                p = c.nueva
                p.fecha, p.inicio, p.fin = n["fecha"], n["inicio"], n["fin"]
                p.save()
            else:
                c.nueva = Bloque.objects.create(
                    fecha=n["fecha"], dia=n["fecha"].weekday(), inicio=n["inicio"], fin=n["fin"], titulo=b.titulo, nota=b.nota,
                    categoria=b.categoria, seguimiento=True)
                c.save(update_fields=["nueva"])
        else:
            c, _ = Cumplimiento.objects.update_or_create(bloque=b, fecha=fecha, defaults={"estado": estado, "auto": False})
            desligar(c)
    return JsonResponse({"ok": True})


@require_http_methods(["POST"])
def reprogramar_accion(request, pk):
    """Marca la acción como reprogramada y crea su copia pendiente en la semana de la nueva fecha."""
    a = get_object_or_404(AccionLanzamiento, pk=pk)
    try:
        f = date.fromisoformat(body(request).get("fecha", ""))
    except ValueError:
        return JsonResponse({"errors": {"fecha": ["Fecha inválida."]}}, status=400)
    if f < timezone.localdate():
        return JsonResponse({"errors": {"fecha": ["La nueva fecha no puede ser pasada."]}}, status=400)
    with transaction.atomic():
        a.estado, a.auto = Estado.REPROGRAMADA, False
        if a.nueva:
            a.nueva.fecha, a.nueva.semana = f, monday(f)
            a.nueva.save()
        else:
            a.nueva = AccionLanzamiento.objects.create(semana=monday(f), cuando=a.cuando, donde=a.donde, accion=a.accion,
                                                       fecha=f, notas=a.notas, orden=a.orden)
        a.save()
    return JsonResponse({"ok": True})


@require_http_methods(["POST", "PUT", "DELETE"])
def acciones(request, pk=None):
    return crud(request, pk, AccionLanzamiento, AccionForm, ser_accion)


@require_http_methods(["POST"])
def copiar_acciones(request):
    """Copia las acciones de la semana anterior (como pendientes)."""
    destino = parse_week(body(request).get("semana"))
    if AccionLanzamiento.objects.filter(semana=destino).exists():
        return JsonResponse({"errors": {"__all__": ["Esta semana ya tiene acciones."]}}, status=409)
    previas = AccionLanzamiento.objects.filter(semana=destino - timedelta(days=7))
    AccionLanzamiento.objects.bulk_create([
        AccionLanzamiento(semana=destino, cuando=a.cuando, donde=a.donde, accion=a.accion, orden=a.orden) for a in previas])
    return JsonResponse({"copiadas": previas.count()}, status=201)


@require_http_methods(["PUT"])
def config(request):
    form = ConfigForm(body(request), instance=Config.get())
    if not form.is_valid():
        return errors(form)
    form.save()
    return JsonResponse({"ok": True})


# ---------- PWA ----------
@login_not_required
def manifest(request):
    return render(request, "planner/manifest.webmanifest", content_type="application/manifest+json")


@login_not_required
def service_worker(request):
    from django.conf import settings
    version = max((p.stat().st_mtime for p in (settings.BASE_DIR / "planner_app/static/planner").glob("*.[jc]s*")), default=0)
    assets = ["planner/vendor/bootstrap.min.css", "planner/vendor/bootstrap.bundle.min.js", "planner/style.css", "planner/common.js",
              "planner/semana.js", "planner/lanzamiento.js", "planner/config.js", "planner/icons/icon-192.png"]
    resp = render(request, "planner/sw.js", {"version": int(version), "assets": assets}, content_type="application/javascript")
    resp["Service-Worker-Allowed"] = "/"
    resp["Cache-Control"] = "no-cache"
    return resp


@login_not_required
def healthz(request):
    return HttpResponse("ok")
