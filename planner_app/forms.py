import re

from datetime import datetime

from django import forms
from django.utils import timezone

from .models import AccionLanzamiento, Bloque, Categoria, Config, Cumplimiento


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nombre", "color", "orden"]

    def clean_color(self):
        c = self.cleaned_data["color"]
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", c):
            raise forms.ValidationError("Color inválido (#RRGGBB).")
        return c.upper()


class BloqueForm(forms.ModelForm):
    class Meta:
        model = Bloque
        fields = ["dia", "inicio", "fin", "titulo", "nota", "categoria", "seguimiento", "fecha"]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["dia"].required = False

    def clean(self):
        c = super().clean()
        if c.get("fecha"):
            c["dia"] = c["fecha"].weekday()
        elif c.get("dia") in (None, ""):
            self.add_error("dia", "Elegí un día.")
        return c


class CumplimientoForm(forms.ModelForm):
    class Meta:
        model = Cumplimiento
        fields = ["bloque", "fecha", "estado"]

    def validate_unique(self):  # la unicidad (bloque, fecha) se resuelve con update_or_create en la vista
        pass

    def validate_constraints(self):
        pass


class AccionForm(forms.ModelForm):
    class Meta:
        model = AccionLanzamiento
        fields = ["semana", "cuando", "donde", "accion", "fecha", "estado", "notas", "orden"]

    def save(self, commit=True):
        if "estado" in self.changed_data:  # un cambio manual deja de ser «automático»
            self.instance.auto = False
            n = self.instance.nueva
            if n and self.instance.estado != "reprogramada":  # deshace la reprogramación si la copia sigue pendiente
                self.instance.nueva = None
                if not n.estado:
                    n.delete()
        return super().save(commit)


class ConfigForm(forms.ModelForm):
    class Meta:
        model = Config
        fields = ["grilla_desde", "grilla_hasta"]


class ReprogForm(forms.Form):
    """Nueva fecha y horario de una actividad reprogramada (debe quedar en el futuro)."""

    fecha = forms.DateField()
    inicio = forms.TimeField()
    fin = forms.TimeField()

    def clean(self):
        c = super().clean()
        if self.errors:
            return c
        if c["fin"] <= c["inicio"]:
            raise forms.ValidationError("El fin debe ser posterior al inicio.")
        if timezone.make_aware(datetime.combine(c["fecha"], c["fin"])) <= timezone.now():
            raise forms.ValidationError("La nueva fecha y hora tienen que estar en el futuro.")
        return c
