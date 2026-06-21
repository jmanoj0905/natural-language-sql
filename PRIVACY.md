# Privacy Statement — Natural Language SQL Engine

## What runs where

All services — backend API, frontend, and (with the default provider) the AI model — run in local Docker containers on your own machine. Nothing is phoned home to the project maintainers, and there is no telemetry of any kind.

## AI providers

### Local / Ollama (default)

The default provider is [Ollama](https://ollama.com) running inside a container on your machine. When you use this provider:

- Your database schema, your questions, and the generated SQL never leave your machine.
- Inference happens entirely locally.

### Cloud providers (OpenAI, Google Gemini, Groq)

These are opt-in. When you select a cloud provider in Settings:

- Your **question**, the **relevant portion of your database schema** (retrieved by the hybrid RAG pipeline), and the **generated SQL context** are sent to that provider's API.
- No other data (database passwords, API keys, row data from query results) is included in the prompt sent to the cloud provider.
- Each cloud provider's own privacy policy governs what they do with that data.

You can switch back to Local/Ollama at any time from the Settings panel to stop sending data externally.

## Credential storage

**Database passwords** and **cloud API keys** are Fernet-encrypted before being written to disk. They are stored in the `~/.nlsql` directory on the host machine, mounted into the Docker stack as the `nlsql_data` volume.

- Passwords and API keys are **never logged** — they are redacted in all structured log output.
- Passwords and API keys are **never returned in API responses** — the API returns masked values (e.g., `********`) rather than the actual secrets.
- The encryption key itself is auto-generated on first launch and persisted in `~/.nlsql/.encryption_key`. To survive a full container wipe, back this file up, or set `DB_ENCRYPTION_KEY` explicitly in `.env`.

The following configuration values are stored as **plaintext** (they are not sensitive secrets): provider name, model name, and Ollama URL.

## What is NOT encrypted

Row data returned by your database queries, schema metadata, and query history are held in memory for the duration of your session and are not written to disk by this application.

## No telemetry

This application does not collect, transmit, or aggregate usage data, error reports, analytics events, or any other telemetry. There are no third-party tracking scripts.

## Summary table

| Data | Sent externally? | Encrypted at rest? | Logged? |
|------|------------------|--------------------|---------|
| Database schema (RAG slice) | Only when using a cloud provider, to that provider | No | No |
| Your question | Only when using a cloud provider, to that provider | No | No |
| Generated SQL | Only when using a cloud provider, to that provider | No | No |
| Database passwords | Never | Yes (Fernet) | No (redacted) |
| Cloud API keys | Used to authenticate to the selected provider; not part of the prompt payload | Yes (Fernet) | No (redacted) |
| Query results (row data) | Never | No (in-memory only) | No |
| Telemetry / analytics | Never | N/A | N/A |
