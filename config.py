import os
import logging
from pathlib import Path

from dotenv import load_dotenv

# 始终从「本文件所在目录」加载 .env，避免在 Win10 下 cwd 不是项目根时读不到
_ROOT = Path(__file__).resolve().parent
_ENV_FILE = _ROOT / ".env"
if not _ENV_FILE.is_file():
    print(
        f"警告: 未找到 {_ENV_FILE}（当前工作目录 {os.getcwd()}）。"
        f"请把 .env 放在与 config.py 同级目录，或复制 .env.example 为 .env。"
    )
load_dotenv(dotenv_path=_ENV_FILE, encoding="utf-8")


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    return int(raw)


# =========================
# 日志配置
# =========================

# 日志级别配置（可通过环境变量覆盖）
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_SQL = os.getenv("LOG_SQL", "false").lower() in ("true", "1", "yes")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 日志文件配置
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log")
LOG_FILE = os.path.join(LOG_DIR, "bot.log")
LOG_MAX_BYTES = 10 * 1024 * 1024  # 单个日志文件最大zize
LOG_BACKUP_COUNT = 10  # 保留日志文件数量

# 自动创建 log 目录
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# 配置根日志记录器（同时输出到控制台和文件）
root_logger = logging.getLogger()
root_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

# 清除已有的 handler（防止重复添加）
root_logger.handlers.clear()

# 控制台 handler
console_handler = logging.StreamHandler()
console_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
console_handler.setFormatter(
    logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
)
root_logger.addHandler(console_handler)

# 文件 handler（带滚动策略）
from logging.handlers import RotatingFileHandler
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=LOG_MAX_BYTES,
    backupCount=LOG_BACKUP_COUNT,
    encoding='utf-8'
)
file_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
file_handler.setFormatter(
    logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
)
root_logger.addHandler(file_handler)

# SQL 日志专用配置
if LOG_SQL:
    # 设置 pymysql 日志级别为 DEBUG 以捕获所有 SQL
    logging.getLogger('pymysql').setLevel(logging.DEBUG)
    
    # 创建自定义 handler 来格式化 SQL 日志
    sql_logger = logging.getLogger('sql')
    sql_logger.setLevel(logging.DEBUG)
    
    # 防止日志重复
    sql_logger.propagate = False
    
    # SQL 控制台 handler
    sql_console_handler = logging.StreamHandler()
    sql_console_handler.setLevel(logging.DEBUG)
    sql_console_handler.setFormatter(
        logging.Formatter(
            '%(asctime)s - SQL - %(levelname)s - %(message)s',
            datefmt=LOG_DATE_FORMAT
        )
    )
    sql_logger.addHandler(sql_console_handler)
    
    # SQL 文件 handler（带滚动策略）
    sql_file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "sql.log"),
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    sql_file_handler.setLevel(logging.DEBUG)
    sql_file_handler.setFormatter(
        logging.Formatter(
            '%(asctime)s - SQL - %(levelname)s - %(message)s',
            datefmt=LOG_DATE_FORMAT
        )
    )
    sql_logger.addHandler(sql_file_handler)


# Telegram（支持 TELEGRAM_BOT_TOKEN 或兼容别名 BOT_TOKEN）
BOT_TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN") or ""
).strip()
BOT_MODE = (os.getenv("BOT_MODE") or "polling").strip().lower()

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

WEBHOOK_DOMAIN = os.getenv("WEBHOOK_DOMAIN", "").strip()
WEBHOOK_LISTEN = (os.getenv("WEBHOOK_LISTEN") or "0.0.0.0").strip()
WEBHOOK_PORT = _int_env("WEBHOOK_PORT", 33333)
WEBHOOK_URL_PATH = (os.getenv("WEBHOOK_URL_PATH") or BOT_TOKEN).strip().lstrip("/")
WEBHOOK_SECRET_TOKEN = (os.getenv("WEBHOOK_SECRET_TOKEN", "") or "").strip() or None

CPU_ALERT = _int_env("CPU_ALERT", 85)
MEM_ALERT = _int_env("MEM_ALERT", 85)
DISK_ALERT = _int_env("DISK_ALERT", 90)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_URL = os.getenv(
    "OPENAI_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-v4-pro")

# LLM 搜索功能配置
ENABLE_SEARCH = os.getenv("ENABLE_SEARCH", "true").lower() in ("true", "1", "yes")

# LLM 工具调用配置（使用集合管理，便于扩展）
# 可选值: "search", "system"
# 示例: ENABLED_TOOLS="search,system" 或 ENABLED_TOOLS="search" 或 ENABLED_TOOLS=""
ENABLED_TOOLS = {tool.strip().lower() for tool in os.getenv("ENABLED_TOOLS", "search,system").split(",") if tool.strip()}

# search engine 搜索引擎配置
SEARCH_BASE_URL = os.getenv("SEARCH_BASE_URL").strip().rstrip("/")

# =========================
# LLM 对话历史与工具调用限制配置
# =========================
MEMORY_TURNS = int(os.getenv("MEMORY_TURNS", "5"))
MAX_HISTORY_TEXT_LENGTH = int(os.getenv("MAX_HISTORY_TEXT_LENGTH", "2000"))
MAX_TOOL_CONTENT = int(os.getenv("MAX_TOOL_CONTENT", "4000"))
MAX_SNIPPET_LENGTH = int(os.getenv("MAX_SNIPPET_LENGTH", "300"))
MAX_TOOL_CALL_ROUNDS = int(os.getenv("MAX_TOOL_CALL_ROUNDS", "5"))
