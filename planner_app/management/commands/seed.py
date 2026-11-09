from datetime import time

from django.core.management.base import BaseCommand

from planner_app.models import Bloque, Categoria

CATS = [  # nombre, color
    ("Arranque", "#1E3A5F"), ("Lanzamiento", "#C2410C"), ("Gestiones CRM", "#C7D2FE"),
    ("Desarrollo CRM", "#FDE7D3"), ("Bici", "#CCEFE9"), ("Trabajo", "#E9ECEF"), ("Descanso/Libre", "#FFFFFF"),
]
T = lambda s: time(*map(int, s.split(":")))
LV = range(5)
# (días, inicio, fin, título, nota, categoría, seguimiento)
BLOQUES = [
    (LV, "8:00", "8:15", "Arranque", "Elegí tu acción de lanzamiento del día y anotala.", "Arranque", True),
    (LV, "8:15", "12:00", "Trabajo", "Una tarea a la vez. Lo que aparece y no es urgente va a la lista, no a la cabeza.", "Trabajo", False),
    (LV, "12:00", "13:00", "Almuerzo y pausa real", "Lejos de la pantalla.", "Descanso/Libre", False),
    (LV, "13:00", "17:15", "Trabajo", "Si tenés un hueco libre, usalo para tu acción de lanzamiento del día.", "Trabajo", False),
    (LV, "17:15", "17:30", "Cierre", "Anotá qué hiciste y qué queda para mañana. Vaciá la cabeza.", "Arranque", True),
    (LV, "17:30", "18:30", "Descanso de verdad", "Sin trabajo ni emprendimiento.", "Descanso/Libre", False),
    ((0, 2, 4), "18:30", "19:30", "Bici", "Ropa lista desde la mañana", "Bici", True),
    ((1,), "18:30", "19:30", "Lanzamiento", "Contactar clientes", "Lanzamiento", True),
    ((3,), "18:30", "19:30", "Lanzamiento", "Mostrar, cotizar, cerrar", "Lanzamiento", True),
    (LV, "19:30", "20:30", "Cena", "", "Descanso/Libre", False),
    ((0, 2), "20:30", "21:15", "Construir", "Solo bloqueantes. Corte 21:15", "Desarrollo CRM", True),
    ((1, 3), "20:30", "21:15", "Libre", "", "Descanso/Libre", False),
    ((4,), "20:30", "21:15", "Libre: amigos, planes", "", "Descanso/Libre", False),
    ((5,), "9:00", "10:30", "Bici larga", "", "Bici", True),
    ((6,), "19:00", "19:20", "Planificar la semana", "Elegir las 3 acciones de lanzamiento y ponerles día y hora.", "Arranque", True),
]


class Command(BaseCommand):
    help = "Carga categorías y horarios del plan semanal original (solo si no hay datos)."

    def handle(self, *args, **opts):
        if Bloque.objects.exists():
            return self.stdout.write("Ya hay bloques; no se hace nada.")
        cats = {n: Categoria.objects.get_or_create(nombre=n, defaults={"color": c, "orden": i})[0]
                for i, (n, c) in enumerate(CATS)}
        Bloque.objects.bulk_create([
            Bloque(dia=d, inicio=T(i), fin=T(f), titulo=t, nota=n, categoria=cats[c], seguimiento=s)
            for dias, i, f, t, n, c, s in BLOQUES for d in dias])
        self.stdout.write(self.style.SUCCESS("Plan cargado."))
