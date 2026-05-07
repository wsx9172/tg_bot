import shlex
import subprocess

from db import log_command, node_exists
from router import get_command_script


def run_command(user_id, channel_id, bot_id, node_id, command):
    if not node_exists(node_id):
        log_command(
            user_id, channel_id, bot_id, node_id, command, "reject", "invalid node"
        )
        return "❌ node not found"

    script = get_command_script(command)
    if not script:
        log_command(user_id, channel_id, bot_id, node_id, command, "reject", "not allowed")
        return "❌ command not allowed"
    
    try:
        # ✅ 使用列表，避免shell=True
        args = shlex.split(script)
        result = subprocess.check_output(
            args,
            shell=False,  # 关键修复
            text=True,
            timeout=20,
            stderr=subprocess.STDOUT,
        )
        log_command(user_id, channel_id, bot_id, node_id, command, "success", result)
        return result
    except subprocess.TimeoutExpired:
        log_command(user_id, channel_id, bot_id, node_id, command, "fail", "timeout")
        return "❌ Command timeout (20s)"
    except Exception as e:
        log_command(user_id, channel_id, bot_id, node_id, command, "fail", str(e))
        return f"❌ {str(e)}"
