from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from .models import AccionLanzamiento, Bloque, Config, Cumplimiento, Estado


def ocurrencia_fin(fecha, bloque):
    """Datetime (aware, hora local) en que termina la ocurrencia de `bloque` en `fecha`."""
    return timezone.make_aware(datetime.combine(fecha, bloque.fin))


def ya_vencio(fecha, bloque, now=None):
    return ocurrencia_fin(fecha, bloque) <= (now or timezone.now())


@transaction.atomic
def cerrar_vencidos(now=None):
    """Pasa a «No hecha» (auto) lo pendiente cuyo horario ya terminó. Se invoca al abrir la app.

    - Bloques con seguimiento: cada ocurrencia (bloque + fecha) vencida sin estado.
      Solo cuentan ocurrencias que terminan después de que el bloque fue creado.
    - Acciones de lanzamiento: pendientes con fecha pasada, o sin fecha y con la semana terminada.
    Un estado cargado a mano nunca se pisa. Devuelve cuántos registros se cerraron.
    """
    now = now or timezone.now()
    hoy = timezone.localtime(now).date()
    cfg = Config.get()
    desde = cfg.ultimo_cierre or timezone.localtime(cfg.inicio_seguimiento).date()

    bloques = list(Bloque.objects.filter(seguimiento=True))
    existentes = set(Cumplimiento.objects.filter(fecha__gte=desde, fecha__lte=hoy).values_list("bloque_id", "fecha"))
    nuevos = []
    d = desde
    while d <= hoy:
        for b in bloques:
            if b.dia == d.weekday() and (b.id, d) not in existentes:
                fin = ocurrencia_fin(d, b)
                if b.creado < fin <= now:
                    nuevos.append(Cumplimiento(bloque=b, fecha=d, estado=Estado.NO_HECHA, auto=True))
        d += timedelta(days=1)
    Cumplimiento.objects.bulk_create(nuevos, ignore_conflicts=True)

    acc = AccionLanzamiento.objects.filter(estado="")
    n_acc = acc.filter(fecha__lt=hoy).update(estado=Estado.NO_HECHA, auto=True, actualizado=now)
    n_acc += acc.filter(fecha__isnull=True, semana__lt=hoy - timedelta(days=6)).update(
        estado=Estado.NO_HECHA, auto=True, actualizado=now)

    cfg.ultimo_cierre = hoy
    cfg.save(update_fields=["ultimo_cierre"])
    return len(nuevos) + n_acc
