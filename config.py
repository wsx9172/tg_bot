import os

from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    return int(raw)


# Telegram
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

_allowed = os.getenv("ALLOWED_USERS", "").strip()
ALLOWED_USERS = (
    {int(x.strip()) for x in _allowed.split(",") if x.strip()}
    if _allowed
    else set()
)

# MySQL
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": _int_env("MYSQL_PORT", 3306),
    "user": os.getenv("MYSQL_USER", ""),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "telegram_bot"),
    "charset": "utf8mb4",
}

NODE_ID = _int_env("NODE_ID", 1)

CPU_ALERT = _int_env("CPU_ALERT", 85)
MEM_ALERT = _int_env("MEM_ALERT", 85)
DISK_ALERT = _int_env("DISK_ALERT", 90)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_URL = os.getenv(
    "OPENAI_API_URL", "https://api.openai.com/v1/chat/completions"
)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
