from db import get_conn


def get_command_script(platform, bot_instance_id, command):
    """
    白名单解析：优先匹配 (platform, bot_instance_id)，回退到 (*, 0)。
    """
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
            return row[0] if row else None

    finally:
        conn.close()
