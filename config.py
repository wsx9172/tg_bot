import os
import warnings
from pathlib import Path

from dotenv import load_dotenv

# 始终从「本文件所在目录」加载 .env，避免在 Win10 下 cwd 不是项目根时读不到
_ROOT = Path(__file__).resolve().parent
_ENV_FILE = _ROOT / ".env"
if not _ENV_FILE.is_file():
    warnings.warn(
        f"未找到 {_ENV_FILE}（当前工作目录 {os.getcwd()}）。"
        f"请把 .env 放在与 config.py 同级目录，或复制 .env.example 为 .env。",
        stacklevel=1,
    )
load_dotenv(dotenv_path=_ENV_FILE, encoding="utf-8")


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    return int(raw)


# Telegram（支持 TELEGRAM_BOT_TOKEN 或兼容别名 BOT_TOKEN）
BOT_TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN") or ""
).strip()

_allowed = os.getenv("ALLOWED_USERS", "").strip()
ALLOWED_USERS = (
    {int(x.strip()) for x in _allowed.split(",") if x.strip()}
    if _allowed
    else set()
)

# 多平台 / 多 Bot 实例（与 channel.platform、bot_instance.id 对齐）
CHAT_PLATFORM = (os.getenv("CHAT_PLATFORM", "telegram") or "telegram").strip()
BOT_INSTANCE_ID = _int_env("BOT_INSTANCE_ID", 1)

_llm_pid = os.getenv("DEFAULT_LLM_PROVIDER_ID", "").strip()
DEFAULT_LLM_PROVIDER_ID = int(_llm_pid) if _llm_pid else None

# MySQL
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": _int_env("MYSQL_PORT", 3306),
    "user": os.getenv("MYSQL_USER", ""),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "telegram_bot"),
    "charset": "utf8mb4",
    "connect_timeout": _int_env("MYSQL_CONNECT_TIMEOUT", 10),
    "read_timeout": _int_env("MYSQL_READ_TIMEOUT", 30),
    "write_timeout": _int_env("MYSQL_WRITE_TIMEOUT", 30),
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
