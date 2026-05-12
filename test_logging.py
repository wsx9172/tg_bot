"""
测试日志配置脚本
运行此脚本验证日志文件是否正确创建和写入
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入配置（会自动创建 log 目录）
from config import LOG_DIR, LOG_FILE, LOG_LEVEL, LOG_SQL

print("=" * 60)
print("日志配置测试")
print("=" * 60)

# 检查 log 目录
print(f"\n1. 日志目录: {LOG_DIR}")
print(f"   是否存在: {os.path.exists(LOG_DIR)}")
print(f"   绝对路径: {os.path.abspath(LOG_DIR)}")

# 检查日志文件
print(f"\n2. 主日志文件: {LOG_FILE}")
print(f"   是否存在: {os.path.exists(LOG_FILE)}")

if LOG_SQL:
    sql_log_file = os.path.join(LOG_DIR, "sql.log")
    print(f"\n3. SQL 日志文件: {sql_log_file}")
    print(f"   是否启用: {LOG_SQL}")

# 测试日志写入
print(f"\n4. 测试日志写入...")
import logging

logger = logging.getLogger(__name__)
logger.info("这是一条测试日志 - INFO 级别")
logger.debug("这是一条测试日志 - DEBUG 级别")
logger.warning("这是一条测试日志 - WARNING 级别")

# 验证文件是否生成
print(f"\n5. 验证日志文件...")
if os.path.exists(LOG_FILE):
    file_size = os.path.getsize(LOG_FILE)
    print(f"   ✅ 日志文件已创建")
    print(f"   文件大小: {file_size} bytes")
    
    # 读取最后几行
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        print(f"   日志行数: {len(lines)}")
        print(f"\n   最新日志内容:")
        for line in lines[-3:]:
            print(f"   {line.strip()}")
else:
    print(f"   ❌ 日志文件未创建")

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)
print(f"\n提示: 可以查看 {LOG_FILE} 文件确认日志输出")
