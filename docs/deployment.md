# Deployment (one VM)

`compose.prod.yaml` runs the whole durable stack on one Ubuntu VM: Caddy (HTTPS + UI) → API → Kafka → trace writer → ClickHouse, with PostgreSQL for accounts. Single broker, single node, no replication: a disk loss loses data.

## VM

- Ubuntu 24.04, **4 GB RAM** (2 GB swap added by the setup script), 2 vCPU, 30 GB disk.
- Inbound ports: **22** (SSH), **80** and **443** (Caddy; 80 is needed for the Let's Encrypt challenge and redirects to 443). Nothing else is published; Kafka, ClickHouse, PostgreSQL and the API are reachable only on the compose network.
- A DNS A record for your domain pointing at the VM's public IP.

Measured idle memory (2026-11-24, Docker Desktop): Kafka ~415 MiB, ClickHouse ~110 MiB (capped at 1.2 GiB by `deploy/clickhouse/low-memory.xml`), API ~65 MiB, trace writer ~35 MiB, PostgreSQL ~22 MiB, Caddy ~14 MiB. Each service also has a `mem_limit` in `compose.prod.yaml`.

## First deploy

```bash
git clone https://github.com/gcharpe1604/ai_agent_debugger.git && cd ai_agent_debugger
sudo bash scripts/deploy/vm-setup.sh      # Docker Engine + compose plugin, swap, docker on boot; safe to re-run
# log out and back in so your user can run docker without sudo

cp .env.prod.example .env.prod
nano .env.prod
```

In `.env.prod`:

- `SITE_ADDRESS`: your domain, e.g. `debugger.example.com` (no `https://`).
- Replace every `CHANGE_ME`. `POSTGRES_PASSWORD` must equal the password inside `DATABASE_URL`. Generate values with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`.
- `ALLOW_SIGNUP=false` once your accounts exist (`scripts/create_user.py` still works).
- Leave the Kafka and ClickHouse host names (`kafka:29092`, `clickhouse`) as they are.

```bash
docker compose -f compose.prod.yaml up -d --build
docker compose -f compose.prod.yaml ps        # all healthy, kafka-init "Exited (0)"
```

Open `https://<SITE_ADDRESS>`, register, and copy the API key shown once.

## Sending traces from an agent

In the agent's `.env` (for example `examples/tool_task_agent/.env`):

```
AGENT_DEBUGGER_ENDPOINT=https://<SITE_ADDRESS>/api/v1/traces
AGENT_DEBUGGER_API_KEY=<your key>
```

## Update

```bash
git pull
docker compose -f compose.prod.yaml up -d --build
```

The API runs `alembic upgrade head` each time it starts. Data stays in the named volumes.

## Logs and restarts

```bash
docker compose -f compose.prod.yaml logs -f api trace-writer
docker compose -f compose.prod.yaml logs --tail 100 caddy
docker compose -f compose.prod.yaml restart trace-writer
docker stats --no-stream
```

`docker compose ... down` keeps the data; `down -v` deletes every volume (all traces, users and the TLS certificates).

## Backup

Volumes: `agent-debugger_postgres_data` (users, keys), `agent-debugger_clickhouse_data` (spans), `agent-debugger_kafka_data` (messages not yet written; 7-day retention), `agent-debugger_caddy_data` (certificates). The simplest backup is a VM disk snapshot. For PostgreSQL alone:

```bash
docker compose -f compose.prod.yaml exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > backup.sql
```

## Testing the stack locally

Set `SITE_ADDRESS=localhost`: Caddy then signs its own certificate. Clients must trust Caddy's root CA:

```bash
docker compose -f compose.prod.yaml cp caddy:/data/caddy/pki/authorities/local/root.crt ./caddy-root.crt
export SSL_CERT_FILE=$PWD/caddy-root.crt   # the SDK then verifies https://localhost
```

Browsers show a certificate warning unless that root is trusted. The HSTS header makes a browser remember https for `localhost`.
