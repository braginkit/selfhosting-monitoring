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
- `.env.local.test` - committed test profile defaults (safe values only).

Parsing is done via `pydantic-settings`:

- runtime: `.env.base + .env`
- tests: `.env.base + .env.local.test`
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
cp .env.example .env
# update targets.yml with your private service endpoints
```

## Run with Docker

```bash
docker compose pull
docker compose up -d
docker compose logs -f monitor-worker matrix-bot
```

To pin a specific release, set `MONITOR_IMAGE` in `.env` to a version tag
for example `ghcr.io/braginkit/selfhosting-monitoring:v0.1.0`.

## Tests

```bash
pytest -q
```

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
