# Future Advanced Technologies Support Desk

Customers submit IT complaints from a mobile-friendly public page. Admins review incoming complaints and choose remote/office support or an on-site visit. Every employee can see open complaints and record the work they completed. The admin history can be filtered by employee username and completion dates, displayed in Pakistan time.

## Run locally

Use Python 3.12 from the repository directory.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export DJANGO_DEBUG=1
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

- `/` is the customer complaint form.
- `/admin/login/` is the admin sign-in. Use **Manage accounts** to add staff accounts. For an employee, create an active user with **Staff status** and **Superuser status** both unchecked.
- `/employee/login/` is the employee sign-in. Share each employee's credentials securely.
- `/desk/` is the complaint queue. Select **Work history** from the admin portal to look up completed work.

Run the automated workflow checks with `python manage.py test`.

## Deploy

Host the Django WSGI app (`support.wsgi:application`) behind an HTTPS reverse proxy using a production WSGI server. Set `DJANGO_SECRET_KEY` to a strong random value in your host's secret settings. Set `DJANGO_ALLOWED_HOSTS` to the public hostname, with comma-separated values for multiple hosts. Leave `DJANGO_DEBUG` unset. Run migrations and `python manage.py collectstatic --noinput`, then configure the proxy to serve `staticfiles/` at `/static/`. Set `DJANGO_TRUST_HTTPS_PROXY=1` only when the trusted proxy strips and replaces the incoming `X-Forwarded-Proto` header.

The app uses SQLite. Use a single deployment instance with a persistent volume, point `DJANGO_DB_PATH` to the database file on that volume, and configure regular SQLite backups. Keep the volume and backups private because they contain customer contact details and work records. Public submissions and sign-ins are rate-limited using the client address seen by Django. If deployed behind a proxy, configure client-aware rate limits at the edge. Share the public HTTPS root URL with customers after deployment.
