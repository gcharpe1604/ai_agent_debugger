<#
.SYNOPSIS
  Runs the trace-writer tests for a demo, verbosely, against the compose Kafka and ClickHouse.

.DESCRIPTION
  1. The crash test alone (clickhouse-span-record.md §6 test 2): the writer dies
     between the ClickHouse insert and the Kafka commit, restarts, and no span is
     lost or shown twice.
  2. All writer tests: real Kafka (§6 tests 2, 14-16), ClickHouse storage, and the
     consumer loop, parse and content-hash unit tests.

  CLICKHOUSE_REQUIRED=1 and KAFKA_REQUIRED=1 are set, so a missing service fails
  the run instead of skipping tests. Start the services first:
      docker compose up -d kafka kafka-init clickhouse
  Run:  powershell -ExecutionPolicy Bypass -File scripts\demo_tests.ps1

  Expected log lines that are not failures:
    "insert failed, retrying ... ConnectionError: clickhouse is down"  (the ClickHouse-down retry test)
    "Topic ...dlq.missing not found in cluster metadata"             (§6 test 16, missing DLQ topic)
#>
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path (Split-Path -Parent $PSScriptRoot) 'backend')
$env:CLICKHOUSE_REQUIRED = '1'
$env:KAFKA_REQUIRED = '1'

function Run-Tests([string]$title, [string[]]$tests) {
    Write-Host ''
    Write-Host ('=' * 72) -ForegroundColor Cyan
    Write-Host $title -ForegroundColor Cyan
    Write-Host ('=' * 72) -ForegroundColor Cyan
    & uv run --locked python -B -m unittest -v @tests
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $title" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Run-Tests '1. Crash after insert, before commit (section 6 test 2)' @(
    'tests.trace_writer.test_writer_kafka.WriterKafkaTests.test_crash_after_insert_before_commit_loses_nothing_and_stays_one_logical_row'
)
Run-Tests '2. All trace-writer tests' @(
    'tests.trace_writer.test_writer_kafka',
    'tests.trace_writer.test_consumer_loop',
    'tests.trace_writer.test_consumer_parse',
    'tests.trace_writer.test_content_hash',
    'tests.clickhouse.test_writer'
)
Write-Host ''
Write-Host 'All writer tests passed.' -ForegroundColor Green
exit 0
