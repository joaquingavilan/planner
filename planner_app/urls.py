from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.semana, name="semana"),
    path("lanzamiento/", views.lanzamiento, name="lanzamiento"),
    path("configuracion/", views.configuracion, name="configuracion"),
    path("api/state/", views.api_state),
    path("api/categorias/", views.categorias),
    path("api/categorias/<int:pk>/", views.categorias),
    path("api/bloques/", views.bloques),
    path("api/bloques/<int:pk>/", views.bloques),
    path("api/cumplimientos/", views.cumplimiento),
    path("api/acciones/", views.acciones),
    path("api/acciones/<int:pk>/", views.acciones),
    path("api/acciones/copiar/", views.copiar_acciones),
    path("api/acciones/<int:pk>/reprogramar/", views.reprogramar_accion),
    path("api/config/", views.config),
    path("login/", auth_views.LoginView.as_view(template_name="planner/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("healthz", views.healthz),
    path("manifest.webmanifest", views.manifest),
    path("sw.js", views.service_worker),
]
