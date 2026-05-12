import logging
from db import get_conn

logger = logging.getLogger(__name__)


def get_command_script(platform, bot_instance_id, command):
    """
    白名单解析：优先匹配 (platform, bot_instance_id)，回退到 (*, 0)。
    """
    logger.debug(f"Looking up command script: platform={platform}, bot_instance_id={bot_instance_id}, command={command}")
    
    conn = get_conn()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT script FROM command_allow
                WHERE command=%s AND enabled=1
                  AND (platform IN ('*', %s))
                  AND (bot_instance_id IN (0, %s))
                ORDER BY
                  (platform = %s) DESC,
                  (bot_instance_id = %s) DESC
                LIMIT 1
                """,
                (command, platform, bot_instance_id, platform, bot_instance_id),
            )
            row = cur.fetchone()
            
            if row:
                logger.debug(f"Command {command} found with script: {row[0]}")
                return row[0]
            else:
                logger.warning(f"Command {command} not found in allow list")
                return None

    finally:
        conn.close()
