import json
import threading
import logging

import pymysql
from dbutils.pooled_db import PooledDB
from config import MYSQL_CONFIG, LOG_SQL

_pool = None
_pool_lock = threading.Lock()

# 创建 SQL 日志记录器
sql_logger = logging.getLogger('sql')


def _log_sql(sql, params=None):
    """记录 SQL 语句和参数"""
    if LOG_SQL:
        if params:
            sql_logger.debug(f"SQL: {sql} | Params: {params}")
        else:
            sql_logger.debug(f"SQL: {sql}")


def _get_pool():
    """延迟创建连接池，避免 import 时 MySQL 未启动即崩溃；mincached=0 不在初始化时建连。"""
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is None:
            sql_logger.info("Initializing database connection pool...")
            _pool = PooledDB(
                creator=pymysql,
                maxconnections=10,
                mincached=0,
                maxcached=5,
                blocking=True,
                ping=1,
                **MYSQL_CONFIG,
            )
            sql_logger.info("Database connection pool initialized successfully")
        return _pool


def get_conn():
    conn = _get_pool().connection()
    sql_logger.debug("Database connection acquired from pool")
    return conn


def node_exists(node_id):
    _log_sql("SELECT 1 FROM node WHERE id=%s LIMIT 1", (node_id,))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM node WHERE id=%s LIMIT 1", (node_id,))
            result = cur.fetchone() is not None
            sql_logger.debug(f"node_exists({node_id}) = {result}")
            return result
    finally:
        conn.close()


def bot_instance_exists(bot_id):
    _log_sql(
        "SELECT 1 FROM bot_instance WHERE id=%s AND enabled=1 LIMIT 1",
        (bot_id,),
    )
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM bot_instance WHERE id=%s AND enabled=1 LIMIT 1",
                (bot_id,),
            )
            result = cur.fetchone() is not None
            sql_logger.debug(f"bot_instance_exists({bot_id}) = {result}")
            return result
    finally:
        conn.close()


def user_can_access_node(user_db_id, node_id):
    """
    admin：任意已存在节点。
    非 admin：在 user_node 中有绑定则仅允许绑定节点；无任何绑定时允许全部节点（便于单机部署）。
    """
    if not node_exists(node_id):
        return False
    
    _log_sql("SELECT role FROM `user` WHERE id=%s LIMIT 1", (user_db_id,))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT role FROM `user` WHERE id=%s LIMIT 1", (user_db_id,))
            row = cur.fetchone()
            if not row:
                sql_logger.warning(f"user_can_access_node: User {user_db_id} not found")
                return False
            role = row[0]
            if role == "admin":
                sql_logger.debug(f"user_can_access_node: User {user_db_id} is admin, access granted")
                return True
            cur.execute(
                "SELECT 1 FROM user_node WHERE user_id=%s AND node_id=%s LIMIT 1",
                (user_db_id, node_id),
            )
            if cur.fetchone():
                sql_logger.debug(f"user_can_access_node: User {user_db_id} has binding to node {node_id}")
                return True
            cur.execute("SELECT COUNT(*) AS c FROM user_node WHERE user_id=%s", (user_db_id,))
            cnt = cur.fetchone()[0]
            result = cnt == 0
            sql_logger.debug(f"user_can_access_node: User {user_db_id} has {cnt} bindings, access={result}")
            return result
    finally:
        conn.close()


def log_command(
    user_id, channel_id, bot_id, node_id, command, status, result, args=None
):
    args_str = None
    if args is not None:
        args_str = json.dumps(args, ensure_ascii=False)
    
    _log_sql(
        "INSERT INTO command_log ... VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW(6))",
        (user_id, channel_id, bot_id, node_id, command, args_str, status, result),
    )
    
    conn = get_conn()
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
        sql_logger.info(f"Command logged: user={user_id}, command={command}, status={status}")
    except Exception as e:
        sql_logger.error(f"Failed to log command: {e}", exc_info=True)
        raise
    finally:
        conn.close()


def log_status(node_id, cpu, memory, disk):
    _log_sql(
        "INSERT INTO status_log ... VALUES (%s,%s,%s,%s,NOW(6))",
        (node_id, cpu, memory, disk),
    )
    
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
        sql_logger.debug(f"Status logged: node={node_id}, cpu={cpu}%, mem={memory}%, disk={disk}%")
    except Exception as e:
        sql_logger.error(f"Failed to log status: {e}", exc_info=True)
        raise
    finally:
        conn.close()


def log_alert(node_id, level, alert_type, message):
    _log_sql(
        "INSERT INTO alert_log ... VALUES (%s,%s,%s,%s,NOW(6))",
        (node_id, level, alert_type, message),
    )
    
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
        sql_logger.warning(f"Alert logged: node={node_id}, level={level}, type={alert_type}, msg={message}")
    except Exception as e:
        sql_logger.error(f"Failed to log alert: {e}", exc_info=True)
        raise
    finally:
        conn.close()


def log_llm(user_id, channel_id, bot_instance_id, provider_id, prompt, response):
    _log_sql(
        "INSERT INTO llm_log ... VALUES (%s,%s,%s,%s,%s,%s,NOW(6))",
        (user_id, channel_id, bot_instance_id, provider_id, prompt[:50] + "...", response[:50] + "..."),
    )
    
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
        sql_logger.info(f"LLM log saved: user={user_id}, prompt_len={len(prompt)}, response_len={len(response)}")
    except Exception as e:
        sql_logger.error(f"Failed to log LLM: {e}", exc_info=True)
        raise
    finally:
        conn.close()


def get_recent_llm_messages(user_id, channel_id, bot_instance_id, limit=6):
    _log_sql(
        "SELECT prompt, response FROM llm_log WHERE user_id=%s AND channel_id=%s AND bot_instance_id=%s ORDER BY created_at DESC LIMIT %s",
        (user_id, channel_id, bot_instance_id, limit),
    )
    
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT prompt, response
                FROM llm_log
                WHERE user_id=%s
                  AND channel_id=%s
                  AND bot_instance_id=%s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (user_id, channel_id, bot_instance_id, limit),
            )
            rows = cur.fetchall()
            sql_logger.debug(f"Retrieved {len(rows)} recent LLM messages for user={user_id}")
            return list(reversed(rows))
    finally:
        conn.close()


def mark_chat_first_seen(platform, external_chat_id, external_user_id):
    _log_sql(
        "INSERT IGNORE INTO chat_state ... VALUES (%s,%s,%s,NOW(6))",
        (platform, str(external_chat_id), str(external_user_id)),
    )
    
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
        sql_logger.debug(f"Chat first seen marked: platform={platform}, chat={external_chat_id}, user={external_user_id}")
    except Exception as e:
        sql_logger.error(f"Failed to mark chat first seen: {e}", exc_info=True)
        raise
    finally:
        conn.close()


def is_new_chat(platform, external_chat_id):
    _log_sql(
        "SELECT 1 FROM chat_state WHERE platform=%s AND external_chat_id=%s LIMIT 1",
        (platform, str(external_chat_id)),
    )
    
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM chat_state WHERE platform=%s AND external_chat_id=%s LIMIT 1",
                (platform, str(external_chat_id)),
            )
            result = cur.fetchone() is None
            sql_logger.debug(f"is_new_chat(platform={platform}, chat={external_chat_id}) = {result}")
            return result
    finally:
        conn.close()
