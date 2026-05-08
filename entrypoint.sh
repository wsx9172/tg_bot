#!/bin/sh
set -eu

echo "[entrypoint] start"

if [ "${SKIP_SETUP:-0}" != "1" ]; then
    echo "[entrypoint] running setup"
    python setup_bot.py
else
    echo "[entrypoint] skip setup"
fi

echo "[entrypoint] starting app: $*"

exec "$@"