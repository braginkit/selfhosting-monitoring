# selfhosting-monitoring

Python 3.13 monitoring service for the SelfHosting stack. It checks subsystem health,
sends alerts by SMTP, and falls back to Matrix when SMTP is unavailable.

## Runtime model

- `monitor-worker`: runs health checks and alert policy.
- `matrix-bot`: sends queued fallback notifications to Matrix.
- `redis`: stores incident state and matrix outbox queue.

## Environment

Files:

- `.env.base` - full variable contract (`KEY=`), public and safe.
- `.env` - runtime secrets and local values (gitignored).
- `.env.test.base` - committed test profile defaults (safe values only).
- `deploy/monitoring.env.prod.example` - production values template for the server
  (copy to `~/monitoring/.env` and replace `CHANGE_ME`; no secrets in git).

Parsing is done via `pydantic-settings`:

- runtime: `.env.base + .env`
- tests: `.env.base + .env.test.base`
- process environment variables always override file values.
- alert transport order is configurable via `MONITOR_ALERT_CHANNEL_PRIORITY`
  (example: `smtp,matrix_outbox`).

## Local dev setup

```bash
pyenv install 3.13.3
pyenv local 3.13.3
python -m venv .venv
source .venv/bin/activate
pip install poetry
poetry config virtualenvs.create false
poetry install
# create .env from .env.base and fill secret values
# update targets.yml with your private service endpoints
```

## Run with Docker

```bash
docker compose pull
docker compose up -d
docker compose logs -f monitor-worker matrix-bot
```

Production note: `monitor-worker` pins `*.bragin.crazedns.ru` check targets to LAN IP
`192.168.1.75` via `extra_hosts` to avoid WAN/hairpin resolution during HTTP/SMTP
checks from inside the container.

Production note: copy `targets.yml.example` to `targets.yml` on the server before
first deploy (placeholder `example.invalid` URLs will cause permanent false alarms).

Production note: `docker-compose.yml` bind-mounts `./targets.yml` into the container
(`/app/targets.yml`). Without the mount, the worker uses `targets.yml` baked into the
GHCR image at build time.

Production note: alert emails must include `Date` and `Message-ID` headers
(`SmtpNotifier` sets them). Without them, `amavis` flags `BAD-HEADER`, bounces
may leave via direct MX and fail with Spamhaus PBL on WAN IP.

Production note: `MONITOR_SMTP_FROM` must match the iCloud relay account configured
on the mail stack so Postfix uses `smtp.mail.me.com` sender-dependent relay
(see `infra/mail/README.md` in the SelfHosting repo).

Until a new GHCR image is published, `docker-compose.yml` bind-mounts
`patches/smtp_notifier.py` over the image module (adds `Date` / `Message-ID`).
After release, remove the patch mount and rely on the image build.

### SMTP delivery tracking (Matrix escalation)

When an alert is accepted by local Postfix via SMTP, the worker stores the
`Message-ID` in Redis and, on each poll cycle, reads docker-mailserver logs from
`/var/log/mail` (volume `mail_mail_logs`). If delivery bounces (for example
Spamhaus PBL / iCloud path) or is not confirmed within `MONITOR_SMTP_DELIVERY_TIMEOUT_SECONDS`,
a follow-up alert is enqueued for `matrix-bot` with `[ESCALATION]` and context that
email delivery failed after an SMTP attempt.

Requires `mail_logs` external volume mount (see `docker-compose.yml`).

### GHCR auth via GitHub App (system setup)

For private GHCR images, prefer GitHub App auth over long-lived PAT tokens.

1. Create a GitHub App:
   - Repository permissions: `Packages: Read-only`, `Contents: Read-only`
   - Install it on `braginkit/selfhosting-monitoring`
   - Generate a private key (`.pem`)
2. On server, place key at a protected path, for example:
   - `~/.config/selfhosting/gh-app-private-key.pem`
   - `chmod 600 ~/.config/selfhosting/gh-app-private-key.pem`
3. Run login script:

```bash
cd ~/monitoring
chmod +x scripts/ghcr-login-github-app.sh
GH_APP_ID="<app_id>" \
GH_APP_INSTALLATION_ID="<installation_id>" \
GH_APP_PRIVATE_KEY_PATH="$HOME/.config/selfhosting/gh-app-private-key.pem" \
scripts/ghcr-login-github-app.sh
```

4. Validate pull path:

```bash
docker pull ghcr.io/braginkit/selfhosting-monitoring:latest
docker compose pull
docker compose up -d
```

To pin a specific release, set `MONITOR_IMAGE` in `.env` to a version tag
for example `ghcr.io/braginkit/selfhosting-monitoring:v0.1.0`.

### Production notification routing (current state)

- SMTP notifications use mail credentials from the local mail stack.
- Matrix notifications use `@monitorbot` and are routed to a dedicated personal
  alerts room (invited user: `@nebragin`).
- `MONITOR_ALERT_CHANNEL_PRIORITY=smtp,matrix_outbox` keeps SMTP first and
  Matrix outbox as fallback.

## Tests

```bash
poetry install
poetry run pytest
# or: pytest -q (requires Python 3.13)
```

Coverage target: 80% (`pyproject.toml`). Key suites:

- `tests/unit/test_alert_pipeline.py` — threshold, SMTP→Matrix fallback, recovery
- `tests/unit/test_mail_log.py` / `test_delivery_tracker.py` — SMTP log parsing and Matrix escalation
- `tests/unit/test_smtp_notifier.py` — headers (`Date`, `Message-ID`), SMTP errors
- `tests/unit/test_targets.py` — YAML fixtures and `targets.yml.example` sanity
- `tests/fixtures/targets.test.yml` — test profile targets for `MONITOR_TARGETS_FILE`

## Quality checks

```bash
make precommit-install
make precommit-run
make check
make ci
```

## Image build and publish

- CI workflow builds and pushes image to GHCR:
  - `.github/workflows/build-and-push.yml`
- Published image:
  - `ghcr.io/braginkit/selfhosting-monitoring`
- Tags strategy:
  - `latest` on `master`
  - `v*` tags on release tags
  - short commit SHA tags for traceability

## Matrix bot scope

Current bot only sends messages from outbox and does not react to incoming
messages. Architecture keeps the sender isolated so command handlers can be
added later without breaking worker logic.
