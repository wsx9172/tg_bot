#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
强制发送测试告警（无需系统真的触发告警）
支持自定义参数：python3 test_alert.py "自定义告警内容"
"""
import asyncio
import logging
import sys
from pathlib import Path

# 将项目根目录加入 Python 路径，支持从任意目录运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telegram.ext import Application
from app.config import BOT_TOKEN, ALLOWED_USERS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def send_test_alert(custom_message=None):
    """强制发送测试告警消息"""
    
    # 初始化Bot
    app = Application.builder().token(BOT_TOKEN).build()
    
    print("="*60)
    print("🧪 主动发送消息")
    print("="*60)
    
    # 构造测试告警消息
    if custom_message:
        message_text = custom_message
        print(f"\n📝 自定义消息内容:")
    else:
        message_text = "此内容为测试"
        print(f"\n📊 测试告警内容:")
    
    print(f"  {message_text}")
    
    if not ALLOWED_USERS:
        print("\n❌ 错误: ALLOWED_USERS 为空")
        print("   请在 .env 中配置: ALLOWED_USERS=123456,789012")
        return
    
    # 发送到所有允许的用户
    print(f"\n📨 发送到 {len(ALLOWED_USERS)} 个用户...")
    
    success_count = 0
    fail_count = 0
    
    for uid in ALLOWED_USERS:
        try:
            # ✅ 自定义参数不加前缀，默认参数加前缀
            if custom_message:
                msg = message_text
            else:
                msg = f"🚨 告警测试\n\n{message_text}"
            
            await app.bot.send_message(uid, msg)
            print(f"  ✅ 用户 {uid} 发送成功")
            success_count += 1
        except Exception as e:
            print(f"  ❌ 用户 {uid} 发送失败: {e}")
            fail_count += 1
    
    print("\n" + "="*60)
    print(f"📈 发送结果: 成功 {success_count} 条, 失败 {fail_count} 条")
    print("="*60)

if __name__ == "__main__":
    custom_msg = None
    if len(sys.argv) > 1:
        custom_msg = sys.argv[1]
        print(f"📌 使用自定义参数: {custom_msg}\n")
    
    asyncio.run(send_test_alert(custom_msg))