import asyncio
import contextlib
import logging
import sys
import os
import pymysql
import uuid

from datetime import datetime
from functools import partial
from telegram import Update

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

from config import (
    BOT_MODE,
    BOT_TOKEN,
    ALLOWED_USERS,
    OPENAI_API_KEY,
    OPENAI_API_URL,
    OPENAI_MODEL,
    BOT_INSTANCE_ID,
    CHAT_PLATFORM,
    DEFAULT_LLM_PROVIDER_ID,
    NODE_ID,
    WEBHOOK_DOMAIN,
    WEBHOOK_LISTEN,
    WEBHOOK_PORT,
    WEBHOOK_SECRET_TOKEN,
    WEBHOOK_URL_PATH,
    ENABLED_TOOLS,
)

from db import bot_instance_exists, mark_chat_first_seen
from monitor import get_system_status, check_alerts
from executor import run_command
from llm import ask_llm

from menu import main_menu, status_menu, cmd_menu, ai_menu, msg_menu
from identity import get_or_create_user, get_or_create_channel

from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=2)

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096
MAIN_MENU_TEXT = "🤖 Linux 运维控制台\n请选择功能："

# 接收消息目录
MSG_DIR = "/opt/tg_bot/messages"

# 确保消息目录存在
os.makedirs(MSG_DIR, exist_ok=True)

# =========================
# 权限
# =========================

def auth(update: Update) -> bool:
    try:
        user = update.effective_user
        if user is None:
            return False
        return user.id in ALLOWED_USERS
    except (AttributeError, TypeError):
        return False


async def reply_long_text(message, text: str):
    if not text:
        return
    for i in range(0, len(text), MAX_MESSAGE_LENGTH):
        await message.reply_text(text[i : i + MAX_MESSAGE_LENGTH])


async def show_main_menu(message):
    await message.reply_text(
        MAIN_MENU_TEXT,
        reply_markup=main_menu()
    )

# =========================
# 获取系统状态文本
# =========================
async def get_system_status_text() -> str:
    loop = asyncio.get_event_loop()
    cpu, mem, disk = await loop.run_in_executor(executor, get_system_status)
    return f"系统状态\n\nCPU: {cpu}%\nMEM: {mem}%\nDISK: {disk}%"


# =========================
# start（首次进入）
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update):
        logger.warning(f"Unauthorized access attempt from user_id={update.effective_user.id if update.effective_user else 'unknown'}")
        return

    logger.info(f"User {update.effective_user.username} (ID: {update.effective_user.id}) started bot")
    
    get_or_create_user(
        CHAT_PLATFORM,
        update.effective_user.id,
        update.effective_user.username,
    )

    get_or_create_channel(CHAT_PLATFORM, update.effective_chat.id)

    mark_chat_first_seen(
        CHAT_PLATFORM,
        str(update.effective_chat.id),
        str(update.effective_user.id),
    )

    await show_main_menu(update.message)


# =========================
# 处理未知命令/消息（Fallback）
# =========================

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """当用户输入不符合预期格式时，显示主菜单用法"""
    if not auth(update):
        logger.warning(f"Unauthorized message from user_id={update.effective_user.id if update.effective_user else 'unknown'}")
        return
    
    # 获取用户输入
    user_input = update.message.text if update.message else ""
    
    logger.info(f"Fallback triggered for user={update.effective_user.username}, input: {user_input[:100]}")
    
    # 复用已有的 show_main_menu 函数
    await show_main_menu(update.message)


# =========================
# callback router（统一入口）
# =========================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if not query:
        return

    try:
        await query.answer()
    except Exception:
        logger.warning("callback answer failed", exc_info=True)
        return

    if not auth(update):
        logger.warning(f"Unauthorized callback from user_id={update.effective_user.id if update.effective_user else 'unknown'}")
        return

    data = query.data
    logger.debug(f"Callback received: {data} from user={update.effective_user.username}")

    try:
        # =========================
        # 返回主菜单
        # =========================
        if data == "menu:back":
            await query.message.edit_text(
                MAIN_MENU_TEXT,
                reply_markup=main_menu()
            )

        # =========================
        # 系统状态
        # =========================
        elif data == "menu:status":
            logger.debug(f"User {update.effective_user.username} requested system status")
            await query.message.edit_text(
                await get_system_status_text(),
                reply_markup=status_menu()
            )

        # =========================
        # 命令页面
        # =========================
        elif data == "menu:cmd":
            logger.debug(f"User {update.effective_user.username} opened command menu")
            await query.message.edit_text(
                "⚙️ 命令执行模块\n\n"
                "使用方式：\n/cmd uptime\n/cmd disk\n/cmd mem",
                reply_markup=cmd_menu()
            )

        # =========================
        # AI页面
        # =========================
        elif data == "menu:ai":
            logger.debug(f"User {update.effective_user.username} opened AI menu")
            await query.message.edit_text(
                "🧠 AI助手模块\n\n使用方式：\n/ai 你的问题",
                reply_markup=ai_menu()
            )

        # =========================
        # 接收消息页面
        # =========================
        elif data == "menu:msg":
            logger.debug(f"User {update.effective_user.username} opened message menu")
            await query.message.edit_text(
                "💬 接收消息模块\n\n使用方式：\n/msg 你的消息",
                reply_markup=msg_menu()
            )

        # =========================
        # 命令说明
        # =========================
        elif data == "menu:cmd_help":
            logger.debug(f"User {update.effective_user.username} requested command help")
            await query.message.reply_text(
                "可用命令：\n"
                "- uptime\n- disk\n- mem\n- docker"
            )

        # =========================
        # AI说明
        # =========================
        elif data == "menu:ai_help":
            logger.debug(f"User {update.effective_user.username} requested AI help")
            await query.message.reply_text(
                "AI功能说明：\n输入 /ai + 问题 即可调用大模型"
            )

        else:
            logger.warning(f"Unknown callback: {data} from user={update.effective_user.username}")

    except Exception:
        logger.exception("callback handler error")


# =========================
# 命令接口
# =========================

async def cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update):
        logger.warning(f"Unauthorized /cmd from user_id={update.effective_user.id if update.effective_user else 'unknown'}")
        return

    if not context.args:
        await update.message.reply_text("用法：/cmd uptime")
        return

    command = context.args[0]
    logger.info(f"Executing command: {command} by user={update.effective_user.username}")

    user_db_id = get_or_create_user(
        CHAT_PLATFORM,
        update.effective_user.id,
        update.effective_user.username,
    )
    channel_db_id = get_or_create_channel(
        CHAT_PLATFORM,
        update.effective_chat.id,
    )
    extra = list(context.args[1:]) if len(context.args) > 1 else None

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        executor,
        partial(
            run_command,
            user_db_id,
            channel_db_id,
            BOT_INSTANCE_ID,
            NODE_ID,
            CHAT_PLATFORM,
            command,
            extra,
        ),
    )

    logger.info(f"Command {command} executed successfully, result length: {len(result)}")
    await reply_long_text(update.message, result)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update):
        logger.warning(f"Unauthorized /status from user_id={update.effective_user.id if update.effective_user else 'unknown'}")
        return

    logger.info(f"User {update.effective_user.username} requested status via /status command")
    await update.message.reply_text(await get_system_status_text())


async def ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update):
        logger.warning(f"Unauthorized /ai from user_id={update.effective_user.id if update.effective_user else 'unknown'}")
        return

    prompt = " ".join(context.args)

    if not prompt:
        await update.message.reply_text("用法：/ai 问题")
        return

    logger.info(f"AI request from user={update.effective_user.username}, prompt length: {len(prompt)}")

    user_db_id = get_or_create_user(
        CHAT_PLATFORM,
        update.effective_user.id,
        update.effective_user.username,
    )
    channel_db_id = get_or_create_channel(
        CHAT_PLATFORM,
        update.effective_chat.id,
    )

    result = ask_llm(
        user_db_id,
        channel_db_id,
        BOT_INSTANCE_ID,
        DEFAULT_LLM_PROVIDER_ID,
        {
            "api_key": OPENAI_API_KEY,
            "api_url": OPENAI_API_URL,
            "model": OPENAI_MODEL,
            "enabled_tools": ENABLED_TOOLS,  # 传递工具配置集合
        },
        prompt,
        session_id=None,  # 让 ask_llm 自动生成 session_id
    )

    logger.info(f"AI response generated for user={update.effective_user.username}, response length: {len(result)}")
    await reply_long_text(update.message, result)
    
async def msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """接收消息并保存到文件"""
    if not auth(update):
        logger.warning(f"Unauthorized /msg from user_id={update.effective_user.id if update.effective_user else 'unknown'}")
        return
    
    # 获取用户输入
    content = " ".join(context.args)
    if not content:
        await update.message.reply_text("用法：/msg <内容>\n例如：/msg this is a token")
        return
    
    try:
        # 生成文件名：msg_2024-12-14_10-30-45-123456_ab12cd34.txt
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
        filename = f"msg_{timestamp}_{uuid.uuid4().hex[:8]}.txt"
        filepath = os.path.join(MSG_DIR, filename)
        
        # 写入文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 返回成功信息
        await update.message.reply_text(
            f"✅ 消息已保存\n\n"
            f"文件: {filename}\n"
            f"内容: {content}"
        )
        
        logger.info(f"Message saved: {filepath} by user={update.effective_user.username}")
    
    except Exception as e:
        await update.message.reply_text(f"❌ 保存失败: {e}")
        logger.error(f"Failed to save message: {e}", exc_info=True)

# =========================
# 告警
# =========================
async def alert_loop(app):
    loop = asyncio.get_event_loop()
    while True:
        try:
            # ✅ 在线程池中执行CPU密集操作
            alerts = await loop.run_in_executor(executor, check_alerts)
            if alerts:
                logger.warning(f"Alerts triggered: {len(alerts)} alerts")
                tasks = [
                    app.bot.send_message(uid, "\n".join(alerts))
                    for uid in ALLOWED_USERS
                ]
                await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("alert loop cancelled")
            raise
        except Exception:
            logger.exception("alert loop error")
        
        await asyncio.sleep(60)

async def post_init(app):
    app.bot_data["alert_task"] = asyncio.create_task(alert_loop(app))


async def post_shutdown(app):
    task = app.bot_data.pop("alert_task", None)
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    executor.shutdown(wait=False, cancel_futures=True)


# =========================
# main
# =========================

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("=" * 50)
    logger.info("Bot starting...")
    logger.info(f"BOT_MODE: {BOT_MODE}")
    logger.info(f"CHAT_PLATFORM: {CHAT_PLATFORM}")
    logger.info(f"BOT_INSTANCE_ID: {BOT_INSTANCE_ID}")
    logger.info(f"NODE_ID: {NODE_ID}")
    logger.info(f"ALLOWED_USERS: {ALLOWED_USERS}")
    logger.info(f"LOG_LEVEL: {os.getenv('LOG_LEVEL', 'INFO')}")
    logger.info(f"LOG_SQL: {os.getenv('LOG_SQL', 'false')}")
    logger.info("=" * 50)

    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN / BOT_TOKEN missing")
        sys.exit(1)

    if BOT_MODE not in {"webhook", "polling"}:
        logger.error("BOT_MODE must be webhook or polling, got %s", BOT_MODE)
        sys.exit(1)

    if BOT_MODE == "webhook":
        if not WEBHOOK_DOMAIN:
            logger.error("WEBHOOK_DOMAIN missing")
            sys.exit(1)

        if not WEBHOOK_URL_PATH:
            logger.error("WEBHOOK_URL_PATH missing")
            sys.exit(1)

    try:
        if not bot_instance_exists(BOT_INSTANCE_ID):
            logger.warning(
                "BOT_INSTANCE_ID=%s missing or disabled in bot_instance; "
                "run init.sql or insert a bot_instance row so audit and allowlists align",
                BOT_INSTANCE_ID,
            )
    except pymysql.err.OperationalError as e:
        logger.error(
            "无法连接 MySQL（%s）。请确认 mysqld 已启动，且 .env 中 "
            "MYSQL_HOST / MYSQL_PORT / MYSQL_USER / MYSQL_PASSWORD / MYSQL_DATABASE 正确。",
            e,
        )
        sys.exit(1)

    try:
        app = (
            Application.builder()
            .token(BOT_TOKEN)
            .post_init(post_init)
            .post_shutdown(post_shutdown)
            .build()
        )

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("cmd", cmd))
        app.add_handler(CommandHandler("status", status))
        app.add_handler(CommandHandler("ai", ai))
        app.add_handler(CommandHandler("msg", msg))

        # Fallback 1：处理所有非命令的文本消息
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_command))
        
        # Fallback 2：处理所有未知命令（以 / 开头但未注册的命令）
        app.add_handler(MessageHandler(filters.Regex(r'^/'), unknown_command))

        app.add_handler(CallbackQueryHandler(button_handler))

        if BOT_MODE == "polling":
            logger.info("Bot initialized; polling started")
            app.run_polling()
        else:
            webhook_url = f"https://{WEBHOOK_DOMAIN}/{WEBHOOK_URL_PATH}"

            logger.info(
                "Bot initialized; webhook starting on %s:%s -> %s",
                WEBHOOK_LISTEN,
                WEBHOOK_PORT,
                webhook_url,
            )

            app.run_webhook(
                listen=WEBHOOK_LISTEN,
                port=WEBHOOK_PORT,
                url_path=WEBHOOK_URL_PATH,
                webhook_url=webhook_url,
                secret_token=WEBHOOK_SECRET_TOKEN,
            )

    except Exception:
        logger.exception("fatal error starting bot")
        sys.exit(1)


if __name__ == "__main__":
    main()
