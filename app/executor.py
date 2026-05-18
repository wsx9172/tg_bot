import shlex
import subprocess
import logging

from app.db import (
    bot_instance_exists,
    log_command,
    user_can_access_node,
)
from app.router import get_command_script

logger = logging.getLogger(__name__)


def run_command(
    user_db_id,
    channel_db_id,
    bot_id,
    node_id,
    platform,
    command,
    extra_args=None,
):
    logger.info(f"Running command: {command} for user={user_db_id}, node={node_id}")
    
    if not bot_instance_exists(bot_id):
        logger.warning(f"Command rejected: invalid bot instance {bot_id}")
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
        logger.warning(f"Command rejected: user {user_db_id} has no permission for node {node_id}")
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
        logger.warning(f"Command rejected: {command} not allowed")
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

    logger.debug(f"Executing script: {script}")
    try:
        args = shlex.split(script)
        result = subprocess.check_output(
            args,
            shell=False,
            text=True,
            timeout=20,
            stderr=subprocess.STDOUT,
        )
        logger.info(f"Command {command} executed successfully, output length: {len(result)}")
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
        logger.error(f"Command {command} timed out after 20s")
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
        logger.error(f"Command {command} failed: {e}", exc_info=True)
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
