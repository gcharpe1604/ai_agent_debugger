<#
.SYNOPSIS
  Demo of the durable path: POST /api/v1/traces -> Kafka -> trace-writer -> ClickHouse.

.DESCRIPTION
  1. docker compose up -d (Kafka, ClickHouse, Postgres) and wait until healthy.
  2. Apply the Postgres migrations and create a demo user (scripts/create_user.py); its API key
     authenticates the POSTs below.
  3. Start the backend (durable route) and the trace writer in the background.
  4. POST one trace with the key: root run, LLM span, tool span with an ERROR, and its retry.
  5. POST the same batch again (simulated redelivery).
  6. Query ClickHouse in the demo user's project: physical rows vs ClickHouseTraceStore.get_trace,
     get_conflicts, list_runs.
  7. Stop the writer and backend this script started.

  Run from anywhere:  powershell -ExecutionPolicy Bypass -File scripts\demo_durable.ps1
  -NoPause skips the "press Enter" pauses (for unattended runs).
  If the backend is already listening on 8008 it is reused and left running.
  A backend started here gets a random SESSION_SECRET unless one is set in the environment.
  Each run creates a new demo user (demo-<random>@example.com); its email and password are printed.
  Logs go to %TEMP%\agentdbg-demo\.
#>
param([switch]$NoPause)

$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
$Logs = Join-Path $env:TEMP 'agentdbg-demo'
$Uv = (Get-Command uv).Source
$Backend = 'http://127.0.0.1:8008'
$Check = @('run', '--project', 'backend', '--locked', 'python', '-B', 'scripts/demo_durable_check.py')
$Started = @{}
# Restored at the end: this script may run inside the caller's PowerShell session.
$SavedEnv = @{}
foreach ($name in @('AGENT_DEBUGGER_API_KEY', 'SESSION_SECRET', 'CREATE_USER_PASSWORD')) {
    $SavedEnv[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
New-Item -ItemType Directory -Force $Logs | Out-Null
Set-Location $Repo

function Step([int]$n, [string]$title) {
    Write-Host ''
    Write-Host ('=' * 72) -ForegroundColor Cyan
    Write-Host ("Step {0}: {1}" -f $n, $title) -ForegroundColor Cyan
    Write-Host ('=' * 72) -ForegroundColor Cyan
}

function Pause-Demo {
    if (-not $NoPause) { [void](Read-Host 'Press Enter to continue') }
}

function Fail([string]$message) {
    Write-Host "FAILED: $message" -ForegroundColor Red
    Stop-Started
    exit 1
}

function Invoke-Check([string[]]$arguments) {
    # Out-Host: otherwise the helper's printed lines become part of the return value.
    & $Uv @($Check + $arguments) | Out-Host
    return $LASTEXITCODE
}

function Stop-Started {
    foreach ($name in @('writer', 'backend')) {
        $proc = $Started[$name]
        if ($proc -and -not $proc.HasExited) {
            # /T: uv starts python as a child; stop the whole tree.
            & taskkill.exe /PID $proc.Id /T /F | Out-Null
            Write-Host ("  stopped {0} (pid {1})" -f $name, $proc.Id)
        }
        $Started.Remove($name)
    }
}

function Test-Backend {
    try {
        $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "$Backend/api/v1/health"
        return $r.StatusCode -eq 200
    } catch { return $false }
}

function New-Hex([int]$length) {
    -join (1..$length | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) })
}

function Restore-Env {
    foreach ($name in $SavedEnv.Keys) {
        [Environment]::SetEnvironmentVariable($name, $SavedEnv[$name], 'Process')
    }
}

function New-Secret {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function Post-Batch([string]$body, [string]$label) {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
    $r = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$Backend/api/v1/traces" `
        -ContentType 'application/json' -Body $bytes `
        -Headers @{ Authorization = "Bearer $env:AGENT_DEBUGGER_API_KEY" }
    Write-Host ("  {0}: HTTP {1} {2}" -f $label, $r.StatusCode, $r.Content)
    if ($r.StatusCode -ne 202) { Fail "$label was not accepted" }
}

try {
    # ------------------------------------------------------------------
    Step 1 'Start Kafka, ClickHouse and Postgres (docker compose)'
    & docker compose up -d postgres kafka kafka-init clickhouse
    if ($LASTEXITCODE -ne 0) { Fail 'docker compose up failed (is Docker Desktop running?)' }
    $deadline = (Get-Date).AddSeconds(180)
    foreach ($c in @('agent-debugger-postgres', 'agent-debugger-kafka', 'agent-debugger-clickhouse')) {
        do {
            $health = (& docker inspect -f '{{.State.Health.Status}}' $c).Trim()
            if ($health -eq 'healthy') { break }
            if ((Get-Date) -gt $deadline) { Fail "$c is '$health' after 180 s" }
            Start-Sleep -Seconds 2
        } while ($true)
        Write-Host "  $c healthy"
    }
    do {
        $state = (& docker inspect -f '{{.State.Status}} {{.State.ExitCode}}' agent-debugger-kafka-init).Trim()
        if ($state -eq 'exited 0') { break }
        if ($state -like 'exited*') { Fail "kafka-init failed: $state" }
        if ((Get-Date) -gt $deadline) { Fail "kafka-init still '$state' after 180 s" }
        Start-Sleep -Seconds 2
    } while ($true)
    Write-Host '  kafka-init exited 0 (topics agentdbg.traces.v1 and .dlq exist)'
    Pause-Demo

    # ------------------------------------------------------------------
    Step 2 'Apply the Postgres migrations and create a demo user'
    & $Uv run --project backend --locked alembic -c backend/alembic.ini upgrade head
    if ($LASTEXITCODE -ne 0) { Fail 'alembic upgrade head failed' }
    $email = "demo-$(New-Hex 8)@example.com"
    $env:CREATE_USER_PASSWORD = New-Secret
    $key = & $Uv run --project backend --locked python -B scripts/create_user.py --email $email --name 'Demo user'
    if ($LASTEXITCODE -ne 0) { Fail 'scripts/create_user.py failed' }
    $env:AGENT_DEBUGGER_API_KEY = "$key".Trim()
    Write-Host "  user $email, password $env:CREATE_USER_PASSWORD (demo only)"
    Write-Host ("  API key {0}... (create_user.py shows it once; kept in this script's environment)" -f $env:AGENT_DEBUGGER_API_KEY.Substring(0, 12))
    Pause-Demo

    # ------------------------------------------------------------------
    Step 3 'Start the backend (POST /api/v1/traces) and the trace writer'
    if (Test-Backend) {
        Write-Host "  backend already running at ${Backend}: reusing it (it will be left running)"
    } else {
        if (-not $env:SESSION_SECRET) { $env:SESSION_SECRET = New-Secret }
        $Started['backend'] = Start-Process -FilePath $Uv -PassThru -WindowStyle Hidden -WorkingDirectory $Repo `
            -ArgumentList @('run', '--project', 'backend', '--locked', 'uvicorn', 'agent_debugger_api.main:app',
                            '--host', '127.0.0.1', '--port', '8008', '--workers', '1', '--no-proxy-headers') `
            -RedirectStandardOutput "$Logs\backend.out.log" -RedirectStandardError "$Logs\backend.err.log"
        $deadline = (Get-Date).AddSeconds(60)
        while (-not (Test-Backend)) {
            if ($Started['backend'].HasExited) { Fail "backend exited; see $Logs\backend.err.log" }
            if ((Get-Date) -gt $deadline) { Fail "backend not ready after 60 s; see $Logs\backend.err.log" }
            Start-Sleep -Seconds 1
        }
        Write-Host ("  backend ready at {0} (pid {1}); GET /api/v1/health -> 200" -f $Backend, $Started['backend'].Id)
    }
    $Started['writer'] = Start-Process -FilePath $Uv -PassThru -WindowStyle Hidden -WorkingDirectory $Repo `
        -ArgumentList @('run', '--project', 'backend', '--locked', 'python', '-B', '-m', 'agent_debugger_api.trace_writer') `
        -RedirectStandardOutput "$Logs\writer.out.log" -RedirectStandardError "$Logs\writer.err.log"
    Write-Host ("  trace writer started (pid {0}); it creates the ClickHouse schema on startup" -f $Started['writer'].Id)
    if ((Invoke-Check @('wait-schema', '60')) -ne 0) { Fail "writer did not create the schema; see $Logs\writer.err.log" }
    Pause-Demo

    # ------------------------------------------------------------------
    Step 4 'POST one trace with the API key: run -> LLM call -> tool call (ERROR) -> retried tool call (OK)'
    $traceId = New-Hex 32
    $root = New-Hex 16; $llm = New-Hex 16; $tool1 = New-Hex 16; $tool2 = New-Hex 16
    $t0 = [int64][DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() * 1000000
    $ms = [int64]1000000
    $batch = [ordered]@{
        protocol_version = '1'
        spans = @(
            [ordered]@{ trace_id = $traceId; span_id = $root; name = 'support_agent.run'; operation_type = 'run'
                start_time = $t0; end_time = $t0 + 1900 * $ms; status = @{ code = 'OK' }
                service_name = 'support_agent'; execution_mode = 'controlled'
                attributes = [ordered]@{ 'user.question' = 'Where is order 1042?'; 'agent.max_steps' = 5 } },
            [ordered]@{ trace_id = $traceId; span_id = $llm; parent_span_id = $root; name = 'llm.plan'; operation_type = 'model'
                start_time = $t0 + 10 * $ms; end_time = $t0 + 610 * $ms; status = @{ code = 'OK' }
                service_name = 'support_agent'; model = 'gpt-4o-mini'; provider = 'openai'
                input_tokens = 412; output_tokens = 58; total_tokens = 470; cost = '0.000097' },
            [ordered]@{ trace_id = $traceId; span_id = $tool1; parent_span_id = $root; name = 'tool.lookup_order'; operation_type = 'tool'
                start_time = $t0 + 620 * $ms; end_time = $t0 + 1120 * $ms
                status = [ordered]@{ code = 'ERROR'; description = 'orders API timed out after 500 ms' }
                error_type = 'TimeoutError'; service_name = 'support_agent'; attempt = 1
                events = @([ordered]@{ name = 'exception'; time = $t0 + 1119 * $ms; attributes = [ordered]@{ 'exception.type' = 'TimeoutError' } }) },
            [ordered]@{ trace_id = $traceId; span_id = $tool2; parent_span_id = $root; name = 'tool.lookup_order'; operation_type = 'tool'
                start_time = $t0 + 1150 * $ms; end_time = $t0 + 1880 * $ms; status = @{ code = 'OK' }
                service_name = 'support_agent'; attempt = 2; retry_of_span_id = $tool1
                links = @([ordered]@{ trace_id = $traceId; span_id = $tool1; relation = 'retry_of' }) }
        )
    }
    $body = $batch | ConvertTo-Json -Depth 10 -Compress
    Write-Host "  trace_id $traceId"
    Write-Host "    $root  support_agent.run    run    OK"
    Write-Host "    $llm  llm.plan             model  OK     gpt-4o-mini, 412/58 tokens"
    Write-Host "    $tool1  tool.lookup_order    tool   ERROR  TimeoutError (attempt 1)"
    Write-Host "    $tool2  tool.lookup_order    tool   OK     retry of $tool1 (attempt 2)"
    Post-Batch $body 'first delivery '
    Pause-Demo

    # ------------------------------------------------------------------
    Step 5 'POST the same batch again (simulated redelivery: client retry after a lost 202)'
    Post-Batch $body 'second delivery'
    Write-Host '  Kafka now holds every span twice; the writer inserts both copies.'
    Pause-Demo

    # ------------------------------------------------------------------
    Step 6 "Query ClickHouse in the demo user's project: physical rows vs logical spans, conflicts, run list"
    if ((Invoke-Check @('wait-caught-up', '60')) -ne 0) { Fail "writer did not catch up; see $Logs\writer.err.log" }
    if ((Invoke-Check @('report', $traceId)) -ne 0) { Fail 'unexpected ClickHouse result (see report above)' }
    Pause-Demo

    # ------------------------------------------------------------------
    Step 7 'Stop the trace writer and backend'
    # The writer has committed every message (step 6), so stopping it loses nothing.
    Stop-Started
    if (-not (Test-Backend)) { Write-Host "  $Backend no longer answers" }
    Write-Host ''
    Write-Host 'Demo finished. Kafka, ClickHouse and Postgres are still running (docker compose stop to stop them).' -ForegroundColor Green
    exit 0
} finally {
    Stop-Started   # also on Ctrl+C or an unexpected error
    Restore-Env
}
