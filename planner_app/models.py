from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


class Estado(models.TextChoices):
    HECHA = "hecha", "Hecha"
    NO_HECHA = "no_hecha", "No hecha"
    REPROGRAMADA = "reprogramada", "Reprogramada"


class Categoria(models.Model):
    nombre = models.CharField(max_length=60, unique=True)
    color = models.CharField(max_length=7, default="#E9ECEF")  # fondo, #RRGGBB
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["orden", "nombre"]

    def __str__(self):
        return self.nombre


class Bloque(models.Model):
    """Actividad recurrente semanal (plantilla), o puntual si tiene `fecha` (p. ej. una reprogramación)."""

    dia = models.PositiveSmallIntegerField(choices=list(enumerate(DIAS)))  # 0 = lunes
    inicio = models.TimeField()
    fin = models.TimeField()
    titulo = models.CharField(max_length=120)
    nota = models.CharField(max_length=300, blank=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="bloques")
    seguimiento = models.BooleanField(default=False, help_text="Permite marcar hecha / no hecha")
    creado = models.DateTimeField(default=timezone.now, editable=False)  # no se vencen ocurrencias anteriores
    fecha = models.DateField(null=True, blank=True, help_text="Solo para actividades puntuales (no recurrentes)")

    class Meta:
        ordering = ["dia", "inicio"]

    def clean(self):
        if self.inicio and self.fin and self.fin <= self.inicio:
            raise ValidationError({"fin": "El fin debe ser posterior al inicio."})

    def save(self, *args, **kwargs):
        if self.fecha:
            self.dia = self.fecha.weekday()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{DIAS[self.dia]} {self.inicio:%H:%M} {self.titulo}"


class Cumplimiento(models.Model):
    """Estado de un bloque en una fecha concreta. Sin fila = pendiente."""

    bloque = models.ForeignKey(Bloque, on_delete=models.CASCADE, related_name="cumplimientos")
    fecha = models.DateField()
    estado = models.CharField(max_length=12, choices=Estado.choices)
    auto = models.BooleanField(default=False, help_text="Marcada por el sistema al vencer el horario")
    actualizado = models.DateTimeField(auto_now=True)
    nueva = models.ForeignKey(Bloque, null=True, blank=True, on_delete=models.SET_NULL, related_name="origenes",
                              help_text="Si está reprogramada: la actividad puntual creada para la nueva fecha")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["bloque", "fecha"], name="uniq_bloque_fecha")]


class AccionLanzamiento(models.Model):
    """'Cuando sea ___, en ___, voy a ___' — acciones de lanzamiento de una semana."""

    semana = models.DateField(db_index=True, help_text="Lunes de la semana")
    cuando = models.CharField(max_length=120, blank=True)
    donde = models.CharField(max_length=120, blank=True)
    accion = models.CharField(max_length=300)
    fecha = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=12, choices=Estado.choices, blank=True)
    auto = models.BooleanField(default=False)
    actualizado = models.DateTimeField(auto_now=True)
    nueva = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="origenes")
    notas = models.TextField(blank=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["semana", "orden", "id"]

    def clean(self):
        if self.semana and self.semana.weekday() != 0:
            raise ValidationError({"semana": "Debe ser un lunes."})


class Config(models.Model):
    """Singleton: rango visible de la grilla."""

    grilla_desde = models.PositiveSmallIntegerField(default=7)
    grilla_hasta = models.PositiveSmallIntegerField(default=22)
    inicio_seguimiento = models.DateTimeField(default=timezone.now, editable=False)
    ultimo_cierre = models.DateField(null=True, blank=True, editable=False)  # último día revisado por cerrar_vencidos

    def clean(self):
        if not (0 <= self.grilla_desde <= 23 and 1 <= self.grilla_hasta <= 24):
            raise ValidationError("Horas fuera de rango.")
        if self.grilla_hasta <= self.grilla_desde:
            raise ValidationError({"grilla_hasta": "Debe ser mayor que 'desde'."})

    @classmethod
    def get(cls):
        return cls.objects.get_or_create(pk=1)[0]
