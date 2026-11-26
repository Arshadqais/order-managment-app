# Future Advanced Technologies Support Desk

Customers submit IT complaints from a mobile-friendly public page and can attach one JPEG, PNG or WebP image up to 5 MB. Only signed-in staff who can access the complaint can see the photo. Attachments are stored in SQLite and included in database backups. Admins review incoming complaints and choose remote/office support or an on-site visit. Every employee can see open complaints and record the work they completed. The admin history can be filtered by employee username and completion dates, displayed in Pakistan time.

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

For a ready-to-run office setup with HTTPS, a local SQLite volume, and optional SMS, see the [Docker deployment guide](deploy/README.md). For 24/7 intake independent of the office computers, see the [cloud deployment guide](deploy/CLOUD.md).

Host the Django WSGI app (`support.wsgi:application`) behind an HTTPS reverse proxy using a production WSGI server. Set `DJANGO_SECRET_KEY` to a strong random value in your host's secret settings. Set `DJANGO_ALLOWED_HOSTS` to the public hostname, with comma-separated values for multiple hosts. Leave `DJANGO_DEBUG` unset. Run migrations and `python manage.py collectstatic --noinput`, then configure the proxy to serve `staticfiles/` at `/static/`. Set `DJANGO_TRUST_HTTPS_PROXY=1` only when the trusted proxy strips and replaces the incoming `X-Forwarded-Proto` header.

The app uses SQLite. Use a single deployment instance with a persistent volume, point `DJANGO_DB_PATH` to the database file on that volume, and configure regular SQLite backups. Keep the volume and backups private because they contain customer contact details and work records. Public submissions and sign-ins are rate-limited using the client address seen by Django. If deployed behind a proxy, configure client-aware rate limits at the edge. Share the public HTTPS root URL with customers after deployment.

## Keep the database on the admin's computer

Run the app on the admin's computer or a dedicated office machine managed by the admin. By default Django creates `support.sqlite3` in the checkout when you run migrations. For regular office use, place the database in a private folder outside the checkout so replacing the code will preserve complaint history. Set the same `DJANGO_DB_PATH` for migrations and for the running app.

For example, in Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$env:LOCALAPPDATA\FATSupport" | Out-Null
$env:DJANGO_DB_PATH = "$env:LOCALAPPDATA\FATSupport\support.sqlite3"
python manage.py migrate
```

Set this path in the production service's environment when configuring it to start on boot. If the app already has data, use a SQLite backup to move the existing database to the new path before switching the service. Keep a separate, private backup and periodically verify that it can be restored.

For phones on the office network, configure an internal HTTPS hostname. For customers using mobile data or another network, configure a public HTTPS hostname routed to the web app on the office machine. Keep the database file private in either setup. The office machine and its network connection must be available whenever customers need to submit complaints.

## Send customers an SMS when work is completed

Run `python manage.py migrate` after updating the app. Each newly completed complaint queues one SMS with its reference number. The existing software workflow saves completion and queues the SMS together. Pakistani mobile numbers in `03XXXXXXXXX` format and international numbers with a country code are supported. Existing completed complaints are not queued retroactively.

Configure `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_FROM_NUMBER` in the office machine's private service environment. Use a Twilio sender approved for your destination and verify the account can send to Pakistani mobile numbers, including any applicable geographic permissions or sender registration. Keep credentials outside Git. The SMS job needs outbound HTTPS access to `api.twilio.com`.

Run `python manage.py send_completion_sms` once to process the queue. For automatic sending, schedule it to run every minute using Windows Task Scheduler or the office machine's service scheduler. Use the same Django settings and `DJANGO_DB_PATH` as the web app, and configure a single job instance so runs do not overlap. The job processes up to 50 queued notifications per run.

The admin can view the SMS status on each completed complaint. Provider acceptance confirms submission, and handset delivery requires checking the provider's message logs. A rejected, unconfirmed, or interrupted send is not retried automatically. Check the provider logs before attempting any resend to avoid sending duplicate messages.

## Send customers an email when work is completed

New complaints require a customer email address, a UAE phone number, and a property or office number. Existing complaints still open and complete normally. A complaint without an email address has no completion email queued.

Run `python manage.py migrate` when updating a local installation. Configure `EMAIL_HOST`, `EMAIL_PORT` (default `587`), `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` and `DEFAULT_FROM_EMAIL` in the deployment environment for an SMTP provider supporting STARTTLS. Use the provider's verified sender address and keep credentials private.

For Docker Compose, place the settings in `.env` and run `docker compose --profile email up -d --build`. If you also use SMS, include `--profile sms` before `up`. The email worker checks the local database once a minute. For a native installation, schedule `python manage.py send_completion_email` once a minute using the same database settings as the app.

The admin can see the email status in each completed complaint. Acceptance means the SMTP server accepted the message. If a send is unconfirmed, consult the provider logs before any resend.
