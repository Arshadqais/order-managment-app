# Deploy on the office computer

This setup runs the Support Desk on the admin's computer. Docker stores the SQLite database locally in the `fat-support_database` volume. Caddy provides HTTPS, and an optional worker sends completion SMS messages.

## 1. Prepare the computer and hostname

- On Windows, install and start Docker Desktop with WSL 2. On Linux, install Docker Engine with the Compose plugin. Check with `docker compose version`.
- Set a public DNS name such as `support.yourcompany.com` to the office's public IP. Give the office computer a fixed LAN address and forward TCP ports 80 and 443 to it. Allow those two ports through the computer firewall.
- If the office connection uses CGNAT or inbound ports are blocked, ask the office network admin or ISP for a reachable address before using this setup.

## 2. Start the app

Open PowerShell or a terminal in the downloaded repository. Copy `.env.example` to `.env` and set `SUPPORT_HOST` to your actual DNS name. Generate a secret with Docker and put the output in `.env` as `DJANGO_SECRET_KEY`. Keep this value private and stable across updates.

```sh
docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_urlsafe(48))"
docker compose up -d --build
docker compose logs -f web proxy
```

Once the web logs show Waitress serving, press Ctrl+C to exit the log view, then create the admin login:

```sh
docker compose exec web python manage.py createsuperuser
```

Open the HTTPS link from a phone on mobile data to confirm public access. Submit a test complaint and verify that it appears in the admin queue. An admin can create employee accounts through **Manage accounts**.

| User | Path on your HTTPS hostname |
| --- | --- |
| Customer | `/` |
| Employee | `/employee/login/` |
| Admin | `/admin/login/` |

## 3. Enable completion SMS

Enter your Twilio account SID, auth token and approved sender in `.env`. Run:

```sh
docker compose --profile sms up -d
docker compose logs -f sms
```

The worker checks the local database every minute. Use a test complaint with your own phone number to verify delivery before sharing the customer link. Twilio must permit SMS to your destination. The office computer needs outbound HTTPS access to `api.twilio.com`.

## 4. Maintain the office deployment

- Keep the computer and Docker running, and disable sleep while the complaint link should be available. On Windows, configure Docker Desktop to start when the deployment account signs in.
- After updating the repository, rerun `docker compose up -d --build`. If SMS is enabled, include `--profile sms`. Database migrations run at startup.
- Back up the SQLite file before updates. The following uses SQLite's online backup API and copies a consistent snapshot to your current folder. Store it privately and verify periodically that it restores.

```sh
docker compose exec -T web python -c "import sqlite3; src=sqlite3.connect('/data/support.sqlite3'); dst=sqlite3.connect('/tmp/support-backup.sqlite3'); src.backup(dst); dst.close(); src.close()"
docker compose cp web:/tmp/support-backup.sqlite3 ./support-backup.sqlite3
```

The database survives ordinary container restarts and `docker compose down`. The `docker compose down --volumes` command deletes the local database volume and certificate storage. For an existing SQLite database, stop the deployment before importing a verified backup into the database volume.

### If the Docker build reports a certificate verification error

If your office uses a TLS-inspecting proxy, obtain its approved PEM CA bundle from IT. Pass it to BuildKit for the dependency installation step, then start the existing image:

```sh
docker build --secret id=pip_ca,src=office-ca.pem -t fat-support:local .
docker compose up -d --no-build
```

Keep the CA file outside the repository if possible and adjust the path in the command. BuildKit mounts it only during installation.
