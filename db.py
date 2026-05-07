import pymysql
from dbutils.pooled_db import PooledDB
from config import MYSQL_CONFIG


# =========================
# 连接池（新增核心）
# =========================

POOL = PooledDB(
    creator=pymysql,
    maxconnections=10,
    mincached=2,
    maxcached=5,
    blocking=True,
    ping=1,
    **MYSQL_CONFIG
)


def get_conn():
    return POOL.connection()


def node_exists(node_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM node WHERE id=%s LIMIT 1", (node_id,))
            return cur.fetchone() is not None
    finally:
        conn.close()


# =========================
# command log
# =========================
def log_command(user_id, channel_id, bot_id, node_id, command, status, result):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO command_log
                (user_id, channel_id, bot_id, node_id, command, status, result, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,NOW(6))
            """, (user_id, channel_id, bot_id, node_id, command, status, result))
        conn.commit()
    finally:
        conn.close()

# =========================
# status log
# =========================

def log_status(node_id, cpu, memory, disk):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO status_log
                (node_id, cpu, memory, disk, created_at)
                VALUES (%s,%s,%s,%s,NOW(6))
            """, (node_id, cpu, memory, disk))
        conn.commit()
    finally:
        conn.close()


# =========================
# alert log
# =========================

def log_alert(node_id, level, alert_type, message):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO alert_log
                (node_id, level, type, message, created_at)
                VALUES (%s,%s,%s,%s,NOW(6))
            """, (node_id, level, alert_type, message))
        conn.commit()
    finally:
        conn.close()


# =========================
# llm log
# =========================

def log_llm(user_id, channel_id, provider_id, prompt, response):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO llm_log
                (user_id, channel_id, provider_id, prompt, response, created_at)
                VALUES (%s,%s,%s,%s,%s,NOW(6))
            """, (user_id, channel_id, provider_id, prompt, response))
        conn.commit()
    finally:
        conn.close()


# =========================
# chat state
# =========================

def is_new_chat(chat_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT chat_id FROM chat_state WHERE chat_id=%s",
                (chat_id,)
            )
            return cur.fetchone() is None
    finally:
        conn.close()


def mark_chat(chat_id, user_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO chat_state(chat_id, user_id, first_seen)
                VALUES (%s,%s,NOW())
            """, (chat_id, user_id))
        conn.commit()
    finally:
        conn.close()
