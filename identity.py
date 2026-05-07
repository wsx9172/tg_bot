from db import get_conn


# =========================
# 获取或创建 user
# =========================

def get_or_create_user(platform, external_user_id, name=None):
    conn = get_conn()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM `user`
                WHERE platform=%s AND external_user_id=%s
            """, (platform, str(external_user_id)))

            row = cur.fetchone()

            if row:
                return row[0]

            cur.execute("""
                INSERT INTO `user`(platform, external_user_id, name)
                VALUES (%s,%s,%s)
            """, (platform, str(external_user_id), name))

            conn.commit()
            return cur.lastrowid

    finally:
        conn.close()


# =========================
# 获取 channel
# =========================

def get_or_create_channel(platform, external_id, name=None):
    conn = get_conn()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM `channel`
                WHERE platform=%s AND external_id=%s
            """, (platform, str(external_id)))

            row = cur.fetchone()

            if row:
                return row[0]

            cur.execute("""
                INSERT INTO `channel`(platform, external_id, name)
                VALUES (%s,%s,%s)
            """, (platform, str(external_id), name))

            conn.commit()
            return cur.lastrowid

    finally:
        conn.close()
