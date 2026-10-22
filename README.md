# AI Agent Debugger

A developer-focused platform for debugging AI agent executions through structured execution traces.

The project aims to help developers understand how an AI agent reached a particular result by capturing and visualizing model calls, tool calls, retrieved context, state changes, and other execution steps.

## Run the current integration

[Start FastAPI/React and execute the four live agents with uv](docs/local-development.md). Real provider calls emit SDK spans; local memory storage is explicitly temporary. `refund-agent` is excluded.

## Project Status

🚧 **In Development**

The project is currently in the planning and initial development phase.

## Planned Tech Stack

* **Backend:** Python, FastAPI
* **Database:** PostgreSQL, JSONB
* **Frontend:** React, JavaScript
* **Deployment:** Docker

## Documentation

Detailed architecture, protocols, and development documentation will be added under the [`docs/`](./docs/) directory as the project evolves.

## License

Licensed under the [Apache License 2.0](./LICENSE).
