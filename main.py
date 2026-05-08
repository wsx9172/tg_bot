import asyncio
import logging
import sys
import os
import pymysql

from datetime import datetime
from functools import partial
from telegram import Update

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

from config import (
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
        await message.reply_text("")
        return
    for i in range(0, len(text), MAX_MESSAGE_LENGTH):
        await message.reply_text(text[i : i + MAX_MESSAGE_LENGTH])

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
        return

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

    await update.message.reply_text(
        "🤖 Linux 运维控制台\n请选择功能：",
        reply_markup=main_menu()
    )


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
        return

    data = query.data

    try:
        # =========================
        # 返回主菜单
        # =========================
        if data == "menu:back":
            await query.message.edit_text(
                "🤖 Linux 运维控制台\n请选择功能：",
                reply_markup=main_menu()
            )

        # =========================
        # 系统状态
        # =========================
        elif data == "menu:status":
            await query.message.edit_text(
                await get_system_status_text(),
                reply_markup=status_menu()
            )

        # =========================
        # 命令页面
        # =========================
        elif data == "menu:cmd":
            await query.message.edit_text(
                "⚙️ 命令执行模块\n\n"
                "使用方式：\n/cmd uptime\n/cmd disk\n/cmd mem",
                reply_markup=cmd_menu()
            )

        # =========================
        # AI页面
        # =========================
        elif data == "menu:ai":
            await query.message.edit_text(
                "🧠 AI助手模块\n\n使用方式：\n/ai 你的问题",
                reply_markup=ai_menu()
            )

        # =========================
        # 接收消息页面
        # =========================
        elif data == "menu:msg":
            await query.message.edit_text(
                "💬 接收消息模块\n\n使用方式：\n/msg 你的消息",
                reply_markup=msg_menu()
            )

        # =========================
        # 命令说明
        # =========================
        elif data == "menu:cmd_help":
            await query.message.reply_text(
                "可用命令：\n"
                "- uptime\n- disk\n- mem\n- docker"
            )

        # =========================
        # AI说明
        # =========================
        elif data == "menu:ai_help":
            await query.message.reply_text(
                "AI功能说明：\n输入 /ai + 问题 即可调用大模型"
            )

    except Exception:
        logger.exception("callback handler error")


# =========================
# 命令接口
# =========================

async def cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update):
        return

    if not context.args:
        await update.message.reply_text("用法：/cmd uptime")
        return

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
            context.args[0],
            extra,
        ),
    )

    await reply_long_text(update.message, result)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update):
        return

    await update.message.reply_text(await get_system_status_text())


async def ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update):
        return

    prompt = " ".join(context.args)

    if not prompt:
        await update.message.reply_text("用法：/ai 问题")
        return

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
        },
        prompt,
    )

    await reply_long_text(update.message, result)

async def msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """接收消息并保存到文件"""
    if not auth(update):
        return
    
    # 获取用户输入
    content = " ".join(context.args)
    if not content:
        await update.message.reply_text("用法：/msg <内容>\n例如：/msg this is a token")
        return
    
    try:
        # 生成文件名：msg_2024-12-14_10-30-45-123456.txt
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
        filename = f"msg_{timestamp}.txt"
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
        
        logger.info(f"Message saved: {filepath}")
    
    except Exception as e:
        await update.message.reply_text(f"❌ 保存失败: {e}")
        logger.error(f"Failed to save message: {e}")

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
                tasks = [
                    app.bot.send_message(uid, "\n".join(alerts))
                    for uid in ALLOWED_USERS
                ]
                await asyncio.gather(*tasks)
        except Exception:
            logger.exception("alert loop error")
        
        await asyncio.sleep(60)

async def post_init(app):
    asyncio.create_task(alert_loop(app))


# =========================
# main
# =========================

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("Bot starting")

    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN / BOT_TOKEN missing")
        sys.exit(1)

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
            .build()
        )

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("cmd", cmd))
        app.add_handler(CommandHandler("status", status))
        app.add_handler(CommandHandler("ai", ai))
        app.add_handler(CommandHandler("msg", msg))

        app.add_handler(CallbackQueryHandler(button_handler))

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
