import json
import threading

import pymysql
from dbutils.pooled_db import PooledDB
from config import MYSQL_CONFIG

_pool = None
_pool_lock = threading.Lock()


def _get_pool():
    """延迟创建连接池，避免 import 时 MySQL 未启动即崩溃；mincached=0 不在初始化时建连。"""
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is None:
            _pool = PooledDB(
                creator=pymysql,
                maxconnections=10,
                mincached=0,
                maxcached=5,
                blocking=True,
                ping=1,
                **MYSQL_CONFIG,
            )
        return _pool


def get_conn():
    return _get_pool().connection()


def node_exists(node_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM node WHERE id=%s LIMIT 1", (node_id,))
            return cur.fetchone() is not None
    finally:
        conn.close()


def bot_instance_exists(bot_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM bot_instance WHERE id=%s AND enabled=1 LIMIT 1",
                (bot_id,),
            )
            return cur.fetchone() is not None
    finally:
        conn.close()


def user_can_access_node(user_db_id, node_id):
    """
    admin：任意已存在节点。
    非 admin：在 user_node 中有绑定则仅允许绑定节点；无任何绑定时允许全部节点（便于单机部署）。
    """
    if not node_exists(node_id):
        return False
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT role FROM `user` WHERE id=%s LIMIT 1", (user_db_id,))
            row = cur.fetchone()
            if not row:
                return False
            role = row[0]
            if role == "admin":
                return True
            cur.execute(
                "SELECT 1 FROM user_node WHERE user_id=%s AND node_id=%s LIMIT 1",
                (user_db_id, node_id),
            )
            if cur.fetchone():
                return True
            cur.execute("SELECT COUNT(*) AS c FROM user_node WHERE user_id=%s", (user_db_id,))
            cnt = cur.fetchone()[0]
            return cnt == 0
    finally:
        conn.close()


def log_command(
    user_id, channel_id, bot_id, node_id, command, status, result, args=None
):
    conn = get_conn()
    args_str = None
    if args is not None:
        args_str = json.dumps(args, ensure_ascii=False)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO command_log
                (user_id, channel_id, bot_id, node_id, command, args, status, result, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW(6))
                """,
                (
                    user_id,
                    channel_id,
                    bot_id,
                    node_id,
                    command,
                    args_str,
                    status,
                    result,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def log_status(node_id, cpu, memory, disk):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO status_log
                (node_id, cpu, memory, disk, created_at)
                VALUES (%s,%s,%s,%s,NOW(6))
                """,
                (node_id, cpu, memory, disk),
            )
        conn.commit()
    finally:
        conn.close()


def log_alert(node_id, level, alert_type, message):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO alert_log
                (node_id, level, type, message, created_at)
                VALUES (%s,%s,%s,%s,NOW(6))
                """,
                (node_id, level, alert_type, message),
            )
        conn.commit()
    finally:
        conn.close()


def log_llm(user_id, channel_id, bot_instance_id, provider_id, prompt, response):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO llm_log
                (user_id, channel_id, bot_instance_id, provider_id, prompt, response, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,NOW(6))
                """,
                (user_id, channel_id, bot_instance_id, provider_id, prompt, response),
            )
        conn.commit()
    finally:
        conn.close()


def mark_chat_first_seen(platform, external_chat_id, external_user_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT IGNORE INTO chat_state
                (platform, external_chat_id, external_user_id, first_seen)
                VALUES (%s,%s,%s,NOW(6))
                """,
                (platform, str(external_chat_id), str(external_user_id)),
            )
        conn.commit()
    finally:
        conn.close()


def is_new_chat(platform, external_chat_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM chat_state WHERE platform=%s AND external_chat_id=%s LIMIT 1",
                (platform, str(external_chat_id)),
            )
            return cur.fetchone() is None
    finally:
        conn.close()
