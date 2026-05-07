from db import get_conn


def get_command_script(command):
    conn = get_conn()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT script FROM command_allow
                WHERE command=%s AND enabled=1
            """, (command,))

            row = cur.fetchone()
            return row[0] if row else None

    finally:
        conn.close()
