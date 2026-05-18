# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Telegram ChatOps bot for Linux server operations. Runs on the host machine (not containerized), reads system state, executes whitelisted commands, receives alerts, and calls LLM with tool-use capabilities. All operations are audited to MySQL.

## Commands

```bash
# Install
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# Initialize database + sync webhook
python setup_bot.py

# DB only (skip webhook sync)
python setup_bot.py --skip-webhook

# Rebuild DB tables
python setup_bot.py --reset-db --skip-webhook

# Delete Telegram webhook (for switching webhook→polling)
python setup_bot.py --skip-db

# Start the bot
python main.py
```

There is no test suite or linting configuration in this project.

## Architecture

```
main.py          — Bot entry point: handlers, callback router, alert loop, polling/webhook startup
config.py        — All env-var loading, logging config (console + rotating file), constants
db.py            — MySQL connection pool (DBUtils), logged cursors, all query functions
executor.py      — Command execution: validates bot instance → node permission → whitelist → subprocess
router.py        — Command whitelist lookup from command_allow table (platform/bot_id scoped)
identity.py      — get-or-create user and channel records in MySQL
monitor.py       — psutil-based CPU/mem/disk gathering, alert threshold checks
menu.py          — Telegram inline keyboard markup builders
llm.py           — LLM orchestration: message building, multi-round tool calling, tool dispatch, logging
setup_bot.py     — DB init (runs init.sql), Telegram webhook register/delete
tools/
  __init__.py    — Public API surface for the tools package
  search_tools.py — web_search tool: schema + search engine HTTP call
  system_tools.py — 13 system diagnostic tools (CPU, mem, disk, processes, Docker, I/O, load)
```

## Key Design Decisions

- **Multi-round tool calling** (`llm.py`): Up to `MAX_TOOL_CALL_ROUNDS` (default 5) rounds. The final round sets `tool_choice="none"` to force a text response. A budget instruction is injected each round telling the model how many rounds remain. Tool results are truncated to `MAX_TOOL_CONTENT` (default 4000 chars) to prevent context overflow.

- **Tool system** (`tools/`): Two categories — `search` (web search via search engine) and `system` (13 psutil/Docker diagnostic functions). Enabled via the `ENABLED_TOOLS` env var (comma-separated: `search,system`). Each tool has a detailed Chinese-language schema description guiding the LLM on when and how to use it. `get_system_health_summary` is the recommended first-call tool.

- **Command whitelist** (`router.py`): Commands are resolved from `command_allow` table with scoping — exact `(platform, bot_instance_id)` match first, then fallback to `(*, 0)`. Scripts are `shlex.split` and executed via `subprocess.check_output` with 20s timeout.

- **Node permission model** (`db.py:user_can_access_node`): Admin users can access any existing node. Non-admin users can only access nodes bound in `user_node`, or all nodes if they have zero bindings (convenience for single-machine deployments).

- **DB connection pooling** (`db.py`): Uses DBUtils `PooledDB` with mincached=0 (lazy connection). All connections/cursors are wrapped in logging proxies. When `LOG_SQL=true`, every query is logged.

- **Two bot modes**: `webhook` (production — listens on `WEBHOOK_LISTEN:WEBHOOK_PORT`, expects reverse proxy with HTTPS) and `polling` (development — `app.run_polling()`). `setup_bot.py` syncs the Telegram webhook URL accordingly.

- **Alert loop** (`main.py:alert_loop`): Runs every 60s, checks CPU/mem/disk thresholds via `psutil`, sends Telegram messages to all `ALLOWED_USERS` if thresholds exceeded.

- **Session tracking** (`llm.py`): Each LLM conversation gets a UUID `session_id` that links multi-turn tool-call rounds in `llm_log`, enabling conversation history reconstruction.

## Logging

Logs go to both console and `./log/bot.log` with rotation (10MB max, 10 backups). SQL logs go to `./log/sql.log` when `LOG_SQL=true`. The log directory is auto-created on startup. Log level controlled by `LOG_LEVEL` env var.
