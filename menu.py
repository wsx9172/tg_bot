from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 系统状态", callback_data="menu:status")],
        [InlineKeyboardButton("⚙️ 命令执行", callback_data="menu:cmd")],
        [InlineKeyboardButton("🧠 AI助手", callback_data="menu:ai")]
    ])


def status_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 刷新状态", callback_data="menu:status")],
        [InlineKeyboardButton("⬅️ 返回主菜单", callback_data="menu:back")]
    ])


def cmd_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 使用说明", callback_data="menu:cmd_help")],
        [InlineKeyboardButton("⬅️ 返回主菜单", callback_data="menu:back")]
    ])


def ai_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 使用说明", callback_data="menu:ai_help")],
        [InlineKeyboardButton("⬅️ 返回主菜单", callback_data="menu:back")]
    ])
