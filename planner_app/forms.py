import re

from django import forms

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
        fields = ["dia", "inicio", "fin", "titulo", "nota", "categoria", "seguimiento"]


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
        return super().save(commit)


class ConfigForm(forms.ModelForm):
    class Meta:
        model = Config
        fields = ["grilla_desde", "grilla_hasta"]
