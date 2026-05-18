import argparse
import logging
import sys
from pathlib import Path
from urllib.parse import urlparse

import pymysql
import requests
from pymysql.constants import CLIENT

from app.config import (
    BOT_MODE,
    BOT_TOKEN,
    MYSQL_CONFIG,
    WEBHOOK_DOMAIN,
    WEBHOOK_SECRET_TOKEN,
    WEBHOOK_URL_PATH,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
DEFAULT_SQL_FILE = ROOT / "init.sql"
TELEGRAM_API_TIMEOUT = 30
PLACEHOLDER_WEBHOOK_DOMAINS = {"bot.domain", "example.com", "localhost"}


def _mysql_server_config() -> dict:
    db_config = dict(MYSQL_CONFIG)
    db_config.pop("database", None)
    return db_config


def _masked_webhook_url(webhook_url: str) -> str:
    if not WEBHOOK_URL_PATH:
        return webhook_url
    return webhook_url.replace(WEBHOOK_URL_PATH, "***", 1)


def count_existing_tables() -> int:
    database = MYSQL_CONFIG["database"]
    connection = pymysql.connect(**_mysql_server_config())

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = %s
                """,
                (database,),
            )
            row = cursor.fetchone()
            return int(row[0] if row else 0)
    finally:
        connection.close()


def execute_init_sql(sql_file: Path) -> None:
    if not sql_file.is_file():
        raise FileNotFoundError(f"SQL file not found: {sql_file}")

    sql = sql_file.read_text(encoding="utf-8")
    db_config = _mysql_server_config()
    db_config["client_flag"] = CLIENT.MULTI_STATEMENTS

    logger.info(
        "Connecting to MySQL %s:%s",
        db_config.get("host"),
        db_config.get("port"),
    )
    connection = pymysql.connect(**db_config)

    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            while cursor.nextset():
                pass
        connection.commit()
    finally:
        connection.close()

    logger.info("Executed %s", sql_file)


def setup_database(sql_file: Path, reset_db: bool) -> None:
    existing_tables = count_existing_tables()
    if existing_tables > 0 and not reset_db:
        logger.info(
            "Database %s already has %s table(s); skipping init.sql. "
            "Use --reset-db to rebuild tables.",
            MYSQL_CONFIG["database"],
            existing_tables,
        )
        return

    if existing_tables > 0 and reset_db:
        logger.warning(
            "Resetting database %s; init.sql may drop and recreate existing tables.",
            MYSQL_CONFIG["database"],
        )

    execute_init_sql(sql_file)


def register_webhook() -> None:
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN / BOT_TOKEN missing")
    if not WEBHOOK_DOMAIN:
        raise ValueError("WEBHOOK_DOMAIN missing")
    if WEBHOOK_DOMAIN in PLACEHOLDER_WEBHOOK_DOMAINS:
        raise ValueError(
            f"WEBHOOK_DOMAIN is still a placeholder: {WEBHOOK_DOMAIN}. "
            "Set it to your real public HTTPS domain in .env."
        )
    if not WEBHOOK_URL_PATH:
        raise ValueError("WEBHOOK_URL_PATH missing")

    webhook_url = f"https://{WEBHOOK_DOMAIN}/{WEBHOOK_URL_PATH}"
    parsed_webhook_url = urlparse(webhook_url)
    if parsed_webhook_url.port and parsed_webhook_url.port not in {80, 88, 443, 8443}:
        raise ValueError(
            "Telegram only accepts webhook URLs on ports 80, 88, 443, or 8443. "
            "Use HTTPS reverse proxy on 443 and proxy to the local bot port."
        )

    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    payload = {"url": webhook_url}
    if WEBHOOK_SECRET_TOKEN:
        payload["secret_token"] = WEBHOOK_SECRET_TOKEN

    logger.info("Registering Telegram webhook: %s", _masked_webhook_url(webhook_url))
    response = requests.post(api_url, data=payload, timeout=TELEGRAM_API_TIMEOUT)

    try:
        result = response.json()
    except ValueError:
        response.raise_for_status()
        raise RuntimeError(f"Telegram returned non-JSON response: {response.text}")

    if response.status_code >= 400:
        description = result.get("description", response.text)
        raise RuntimeError(f"Telegram setWebhook HTTP {response.status_code}: {description}")

    if not result.get("ok"):
        raise RuntimeError(f"Telegram setWebhook failed: {result}")

    logger.info("Telegram webhook registered: %s", result.get("description", "ok"))


def delete_webhook() -> None:
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN / BOT_TOKEN missing")

    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
    logger.info("Deleting Telegram webhook for polling mode")
    response = requests.post(api_url, timeout=TELEGRAM_API_TIMEOUT)

    try:
        result = response.json()
    except ValueError:
        response.raise_for_status()
        raise RuntimeError(f"Telegram returned non-JSON response: {response.text}")

    if response.status_code >= 400:
        description = result.get("description", response.text)
        raise RuntimeError(f"Telegram deleteWebhook HTTP {response.status_code}: {description}")

    if not result.get("ok"):
        raise RuntimeError(f"Telegram deleteWebhook failed: {result}")

    logger.info("Telegram webhook deleted: %s", result.get("description", "ok"))


def sync_telegram_webhook() -> None:
    if BOT_MODE == "webhook":
        register_webhook()
    elif BOT_MODE == "polling":
        delete_webhook()
    else:
        raise ValueError(f"BOT_MODE must be webhook or polling, got {BOT_MODE}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Set up database schema and sync Telegram webhook state."
    )
    parser.add_argument(
        "--sql-file",
        type=Path,
        default=DEFAULT_SQL_FILE,
        help="Path to init.sql. Defaults to ./init.sql.",
    )
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Execute init.sql even when tables already exist. This may erase data.",
    )
    parser.add_argument(
        "--skip-db",
        action="store_true",
        help="Skip database setup.",
    )
    parser.add_argument(
        "--skip-webhook",
        action="store_true",
        help="Skip Telegram webhook sync.",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    args = parse_args()

    try:
        if not args.skip_db:
            setup_database(args.sql_file, args.reset_db)
        if not args.skip_webhook:
            sync_telegram_webhook()
    except Exception:
        logger.exception("Setup failed")
        return 1

    logger.info("Setup completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
