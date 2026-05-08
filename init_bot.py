import argparse
import logging
import sys
from pathlib import Path

import pymysql
import requests
from pymysql.constants import CLIENT

from config import (
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


def _masked_webhook_url(webhook_url: str) -> str:
    if not WEBHOOK_URL_PATH:
        return webhook_url
    return webhook_url.replace(WEBHOOK_URL_PATH, "***", 1)


def execute_init_sql(sql_file: Path) -> None:
    if not sql_file.is_file():
        raise FileNotFoundError(f"SQL file not found: {sql_file}")

    sql = sql_file.read_text(encoding="utf-8")
    db_config = dict(MYSQL_CONFIG)
    db_config.pop("database", None)
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


def register_webhook() -> None:
    if not BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN / BOT_TOKEN missing")
    if not WEBHOOK_DOMAIN:
        raise ValueError("WEBHOOK_DOMAIN missing")
    if not WEBHOOK_URL_PATH:
        raise ValueError("WEBHOOK_URL_PATH missing")

    webhook_url = f"https://{WEBHOOK_DOMAIN}/{WEBHOOK_URL_PATH}"
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    payload = {"url": webhook_url}
    if WEBHOOK_SECRET_TOKEN:
        payload["secret_token"] = WEBHOOK_SECRET_TOKEN

    logger.info("Registering Telegram webhook: %s", _masked_webhook_url(webhook_url))
    response = requests.post(api_url, data=payload, timeout=TELEGRAM_API_TIMEOUT)
    response.raise_for_status()

    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(f"Telegram setWebhook failed: {result}")

    logger.info("Telegram webhook registered: %s", result.get("description", "ok"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize database schema and register Telegram webhook."
    )
    parser.add_argument(
        "--sql-file",
        type=Path,
        default=DEFAULT_SQL_FILE,
        help="Path to init.sql. Defaults to ./init.sql.",
    )
    parser.add_argument(
        "--skip-db",
        action="store_true",
        help="Skip executing init.sql.",
    )
    parser.add_argument(
        "--skip-webhook",
        action="store_true",
        help="Skip Telegram setWebhook registration.",
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
            execute_init_sql(args.sql_file)
        if not args.skip_webhook:
            register_webhook()
    except Exception:
        logger.exception("Initialization failed")
        return 1

    logger.info("Initialization completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
