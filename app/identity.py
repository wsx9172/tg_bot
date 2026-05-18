import logging
from app.db import get_conn

logger = logging.getLogger(__name__)


# =========================
# 获取或创建 user
# =========================

def get_or_create_user(platform, external_user_id, name=None):
    logger.debug(f"Getting or creating user: platform={platform}, external_user_id={external_user_id}")
    
    conn = get_conn()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM `user`
                WHERE platform=%s AND external_user_id=%s
            """, (platform, str(external_user_id)))

            row = cur.fetchone()

            if row:
                logger.debug(f"User found: id={row[0]}")
                return row[0]

            cur.execute("""
                INSERT INTO `user`(platform, external_user_id, name)
                VALUES (%s,%s,%s)
            """, (platform, str(external_user_id), name))

            conn.commit()
            user_id = cur.lastrowid
            logger.info(f"New user created: id={user_id}, platform={platform}, external_user_id={external_user_id}")
            return user_id

    finally:
        conn.close()


# =========================
# 获取 channel
# =========================

def get_or_create_channel(platform, external_id, name=None):
    logger.debug(f"Getting or creating channel: platform={platform}, external_id={external_id}")
    
    conn = get_conn()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM `channel`
                WHERE platform=%s AND external_id=%s
            """, (platform, str(external_id)))

            row = cur.fetchone()

            if row:
                logger.debug(f"Channel found: id={row[0]}")
                return row[0]

            cur.execute("""
                INSERT INTO `channel`(platform, external_id, name)
                VALUES (%s,%s,%s)
            """, (platform, str(external_id), name))

            conn.commit()
            channel_id = cur.lastrowid
            logger.info(f"New channel created: id={channel_id}, platform={platform}, external_id={external_id}")
            return channel_id

    finally:
        conn.close()
