# Cloud deployment for 24/7 complaint intake

Run the existing Docker Compose package on a company-approved Linux cloud server with a static public IP and encrypted persistent storage. Keep the server running continuously. Choose the region and retention period with the team responsible for customer data. Use sample complaints until the company approves the environment for real customer information.

## Bring the site online

1. Install Docker Engine and the Compose plugin on the cloud server. Keep SSH restricted to the deployment operator. Allow public TCP 80 and 443 in the provider firewall for Caddy.
2. Point your public support hostname at the server's static IP. Only add an IPv6 record if the server is reachable on IPv6.
3. Copy the deployment package to the server. Run the commands from the folder containing `compose.yaml`.

   ```sh
   umask 077
   cp -n .env.example .env
   docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

4. Set `SUPPORT_HOST` to your hostname and `DJANGO_SECRET_KEY` to that generated key in `.env`. Keep the file private and preserve it across updates.
5. Start the site, then create the admin account once the web service is running.

   ```sh
   docker compose up -d --build
   docker compose logs --tail=50 web proxy
   docker compose exec web python manage.py createsuperuser
   ```

6. Open the HTTPS site from another network. Submit a test complaint with sample data, verify it appears in the admin queue, complete it through an employee account, and check the admin work history.

Share the root URL with customers. Give staff only the relevant login URLs, `/admin/login/` and `/employee/login/`. Each staff member uses an individual account.

## Protect and preserve the data

- Django runs behind Caddy with debug mode off. The database and application port are private to the server. Caddy provides public HTTPS.
- Keep Docker's `fat-support_database` volume on encrypted persistent host storage. SQLite data lives in that volume. Maintain encrypted off-server backups with access restricted to the deployment operator, and test recovery on a separate instance. See [the backup command](README.md#4-maintain-the-office-deployment).
- Monitor the public form with an external HTTPS availability check. Review storage space and backup results. A single server can still have outages during maintenance or provider incidents.
- Use the [SMS instructions](README.md#3-enable-completion-sms) if needed. Verify delivery using a test number before enabling customer use.
