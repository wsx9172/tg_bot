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
    ContextTypes
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
    ENABLE_SEARCH,
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
            "enable_search": str(ENABLE_SEARCH),
        },
        prompt,
    )

    logger.info(f"AI response generated for user={update.effective_user.username}, response length: {len(result)}")
    await reply_long_text(update.message, result)