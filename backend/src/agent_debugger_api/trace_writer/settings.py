from pydantic_settings import BaseSettings, SettingsConfigDict

from agent_debugger_api.config import PROJECT_ROOT


class WriterSettings(BaseSettings):
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_trace_topic: str = "agentdbg.traces.v1"
    kafka_trace_dlq_topic: str = "agentdbg.traces.v1.dlq"
    kafka_trace_writer_group: str = "agentdbg-trace-writer"
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_user: str = "agentdbg"
    clickhouse_password: str = "agentdbg"
    clickhouse_database: str = "telemetry"
    batch_max_records: int = 1000
    batch_timeout_ms: int = 1000

    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")