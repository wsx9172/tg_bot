import shlex
import subprocess

from db import (
    bot_instance_exists,
    log_command,
    user_can_access_node,
)
from router import get_command_script


def run_command(
    user_db_id,
    channel_db_id,
    bot_id,
    node_id,
    platform,
    command,
    extra_args=None,
):
    if not bot_instance_exists(bot_id):
        log_command(
            user_db_id,
            channel_db_id,
            bot_id,
            node_id,
            command,
            "reject",
            "invalid bot instance",
            args=extra_args,
        )
        return "❌ bot instance not configured"

    if not user_can_access_node(user_db_id, node_id):
        log_command(
            user_db_id,
            channel_db_id,
            bot_id,
            node_id,
            command,
            "reject",
            "node not permitted",
            args=extra_args,
        )
        return "❌ no permission for this node"

    script = get_command_script(platform, bot_id, command)
    if not script:
        log_command(
            user_db_id,
            channel_db_id,
            bot_id,
            node_id,
            command,
            "reject",
            "not allowed",
            args=extra_args,
        )
        return "❌ command not allowed"

    try:
        args = shlex.split(script)
        result = subprocess.check_output(
            args,
            shell=False,
            text=True,
            timeout=20,
            stderr=subprocess.STDOUT,
        )
        log_command(
            user_db_id,
            channel_db_id,
            bot_id,
            node_id,
            command,
            "success",
            result,
            args=extra_args,
        )
        return result
    except subprocess.TimeoutExpired:
        log_command(
            user_db_id,
            channel_db_id,
            bot_id,
            node_id,
            command,
            "fail",
            "timeout",
            args=extra_args,
        )
        return "❌ Command timeout (20s)"
    except Exception as e:
        log_command(
            user_db_id,
            channel_db_id,
            bot_id,
            node_id,
            command,
            "fail",
            str(e),
            args=extra_args,
        )
        return f"❌ {str(e)}"
