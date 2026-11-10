from datetime import date, datetime, time, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from .models import AccionLanzamiento, Bloque, Categoria, Config, Cumplimiento
from .services import cerrar_vencidos

BA = ZoneInfo("America/Argentina/Buenos_Aires")
AHORA = datetime(2026, 11, 11, 12, 0, tzinfo=BA)       # miércoles 12:00
INICIO = datetime(2026, 11, 1, 9, 0, tzinfo=BA)


class CierreTests(TestCase):
    def setUp(self):
        self.cat = Categoria.objects.create(nombre="X")
        cfg = Config.get()
        cfg.inicio_seguimiento = INICIO
        cfg.save()

    def bloque(self, dia, ini="8:00", fin="9:00", seg=True, creado=INICIO):
        h = lambda s: time(*map(int, s.split(":")))
        return Bloque.objects.create(dia=dia, inicio=h(ini), fin=h(fin), titulo="b", categoria=self.cat, seguimiento=seg, creado=creado)

    def test_vence_lo_pasado_y_no_lo_futuro(self):
        lun = self.bloque(0)                      # lun 9/11 ya pasó
        jue = self.bloque(3)                      # jue 12/11 es futuro
        mie_tarde = self.bloque(2, "15:00", "16:00")  # hoy, aún no terminó
        mie_temprano = self.bloque(2, "9:00", "10:00")  # hoy, ya terminó
        n = cerrar_vencidos(AHORA)
        marcados = {(c.bloque_id, c.fecha): c for c in Cumplimiento.objects.all()}
        self.assertIn((lun.id, date(2026, 11, 9)), marcados)
        self.assertIn((mie_temprano.id, date(2026, 11, 11)), marcados)
        self.assertNotIn((jue.id, date(2026, 11, 12)), marcados)
        self.assertNotIn((mie_tarde.id, date(2026, 11, 11)), marcados)
        self.assertTrue(all(c.estado == "no_hecha" and c.auto for c in marcados.values()))
        self.assertEqual(n, len(marcados))
        # semana previa también (el sistema no se abrió): lun 2/11 y mié 4/11 etc.
        self.assertIn((lun.id, date(2026, 11, 2)), marcados)

    def test_idempotente(self):
        self.bloque(0)
        self.assertGreater(cerrar_vencidos(AHORA), 0)
        self.assertEqual(cerrar_vencidos(AHORA), 0)

    def test_no_pisa_estado_manual(self):
        b = self.bloque(0)
        Cumplimiento.objects.create(bloque=b, fecha=date(2026, 11, 9), estado="hecha")
        Cumplimiento.objects.create(bloque=b, fecha=date(2026, 11, 2), estado="reprogramada")
        cerrar_vencidos(AHORA)
        self.assertEqual(Cumplimiento.objects.get(bloque=b, fecha=date(2026, 11, 9)).estado, "hecha")
        self.assertEqual(Cumplimiento.objects.get(bloque=b, fecha=date(2026, 11, 2)).estado, "reprogramada")
        self.assertFalse(Cumplimiento.objects.get(bloque=b, fecha=date(2026, 11, 9)).auto)

    def test_ignora_sin_seguimiento_y_anteriores_a_su_creacion(self):
        self.bloque(0, seg=False)
        nuevo = self.bloque(0, creado=datetime(2026, 11, 9, 18, 0, tzinfo=BA))  # creado luego de la ocurrencia del lun 9
        cerrar_vencidos(AHORA)
        fechas = set(Cumplimiento.objects.filter(bloque=nuevo).values_list("fecha", flat=True))
        self.assertEqual(fechas, set())            # el lun 9 terminó antes de crearse; el lun 16 es futuro
        self.assertFalse(Cumplimiento.objects.filter(bloque__seguimiento=False).exists())

    def test_acciones(self):
        sem_pasada = date(2026, 11, 2)
        sem_actual = date(2026, 11, 9)
        a1 = AccionLanzamiento.objects.create(semana=sem_pasada, accion="a")                          # semana terminada, sin fecha
        a2 = AccionLanzamiento.objects.create(semana=sem_actual, accion="b", fecha=date(2026, 11, 10))  # ayer
        a3 = AccionLanzamiento.objects.create(semana=sem_actual, accion="c", fecha=date(2026, 11, 11))  # hoy
        a4 = AccionLanzamiento.objects.create(semana=sem_actual, accion="d")                          # semana en curso
        a5 = AccionLanzamiento.objects.create(semana=sem_pasada, accion="e", estado="hecha")
        cerrar_vencidos(AHORA)
        est = {a.accion: (a.estado, a.auto) for a in AccionLanzamiento.objects.all()}
        self.assertEqual(est["a"], ("no_hecha", True))
        self.assertEqual(est["b"], ("no_hecha", True))
        self.assertEqual(est["c"], ("", False))
        self.assertEqual(est["d"], ("", False))
        self.assertEqual(est["e"], ("hecha", False))


class ApiTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        get_user_model().objects.create_user("u", password="p")
        self.client.login(username="u", password="p")
        self.cat = Categoria.objects.create(nombre="X")
        self.b = Bloque.objects.create(dia=0, inicio=time(8), fin=time(9), titulo="b", categoria=self.cat, seguimiento=True)

    def post(self, fecha, estado):
        return self.client.post("/api/cumplimientos/", {"bloque": self.b.id, "fecha": fecha, "estado": estado}, content_type="application/json")

    def test_manual_cambia_auto_y_pasado_no_vuelve_a_pendiente(self):
        c = Cumplimiento.objects.create(bloque=self.b, fecha=date(2020, 1, 6), estado="no_hecha", auto=True)  # lunes pasado
        r = self.post("2020-01-06", "hecha"); self.assertEqual(r.status_code, 200, r.content)
        c.refresh_from_db(); self.assertEqual((c.estado, c.auto), ("hecha", False))
        self.assertEqual(self.post("2020-01-06", "").status_code, 400)       # pasado: no puede quedar pendiente
        self.assertEqual(self.post("2020-01-06", "reprogramada").status_code, 200)

    def test_futuro_puede_volver_a_pendiente(self):
        f = (timezone.localdate() + timedelta(days=14)).isoformat()
        self.assertEqual(self.post(f, "reprogramada").status_code, 200)
        self.assertEqual(self.post(f, "").status_code, 200)
        self.assertFalse(Cumplimiento.objects.filter(bloque=self.b).exists())

    def test_state_cierra_al_abrir(self):
        cfg = Config.get(); cfg.inicio_seguimiento = timezone.now() - timedelta(days=10); cfg.save()
        Bloque.objects.filter(pk=self.b.pk).update(creado=timezone.now() - timedelta(days=10))
        r = self.client.get("/api/state/").json()
        self.assertGreaterEqual(r["cerrados"], 1)
        self.assertEqual(self.client.get("/api/state/").json()["cerrados"], 0)
