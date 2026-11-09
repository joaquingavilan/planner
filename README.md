# Mi semana

Planificador semanal (Django + PostgreSQL + JS vanilla + Bootstrap 5).

## Arranque
```bash
docker compose up -d db            # o usá tu Postgres (variables POSTGRES_*)
pip install -r requirements.txt
python manage.py migrate
python manage.py seed              # carga categorías y horarios del plan original
python manage.py runserver
```
- **Semana**: grilla (o vista Día), clic en un hueco crea actividad, ✓/✕ en las que tienen seguimiento.
- **Lanzamiento**: las 3 acciones «Cuando sea… en… voy a…» por semana, con hecha / no hecha.
- **Configuración**: rango horario de la grilla, ABM de categorías y de horarios.

## PWA
- Instalable (manifest + iconos + service worker en `/sw.js`). En Android/Chrome: «Instalar app»; en iOS: Compartir → «Agregar a inicio».
- Funciona offline en **modo lectura**: el shell y la última semana consultada quedan en caché. Los cambios requieren conexión (se avisa con un cartel).
- Para instalarla en el celu necesita HTTPS (o `localhost`): publicala detrás de un proxy con certificado.

## Deploy en Railway
1. Subí esta carpeta a un repo de GitHub (`git init && git add . && git commit`).
2. Railway → **New Project → Deploy from GitHub repo**. Detecta el `Dockerfile` y `railway.json` (healthcheck en `/healthz`).
3. En el mismo proyecto: **+ New → Database → PostgreSQL**.
4. En el servicio de la app → **Variables**:
   | Variable | Valor |
   |---|---|
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
   | `DJANGO_SECRET_KEY` | `python -c "import secrets;print(secrets.token_urlsafe(50))"` |
   | `APP_USERNAME` | tu usuario (por defecto `joaquin`) |
   | `APP_PASSWORD` | una clave larga (obligatoria; se re-aplica en cada deploy) |
5. **Settings → Networking → Generate Domain**. Railway inyecta `RAILWAY_PUBLIC_DOMAIN`, que se usa para CSRF/HTTPS.
6. Abrí la URL, ingresá, y en el celu «Instalar app».

Cada deploy corre `migrate`, `seed` (solo si la base está vacía) y `ensure_user`. Para cambiar la clave, cambiá `APP_PASSWORD` y redeployá.
Los datos viven en el Postgres de Railway; hacé backups desde su pestaña de la base.
