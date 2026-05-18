import json
import threading
import logging

import pymysql
from dbutils.pooled_db import PooledDB
from app.config import MYSQL_CONFIG, LOG_SQL

_pool = None
_pool_lock = threading.Lock()

# 创建 SQL 日志记录器
sql_logger = logging.getLogger('sql')


class LoggedConnection:
    """包装数据库连接，自动记录所有 SQL 操作"""
    
    def __init__(self, conn):
        self._conn = conn
    
    def cursor(self, *args, **kwargs):
        """返回包装后的 cursor"""
        raw_cursor = self._conn.cursor(*args, **kwargs)
        return LoggedCursor(raw_cursor)
    
    def commit(self):
        result = self._conn.commit()
        sql_logger.debug("Transaction committed")
        return result
    
    def rollback(self):
        result = self._conn.rollback()
        sql_logger.warning("Transaction rolled back")
        return result
    
    def close(self):
        sql_logger.debug("Database connection closed")
        return self._conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class LoggedCursor:
    """包装数据库游标，自动记录所有 SQL 执行"""
    
    def __init__(self, cursor):
        self._cursor = cursor
    
    def execute(self, query, args=None):
        """执行 SQL 并记录日志"""
        if LOG_SQL:
            # 格式化 SQL 用于日志
            if args:
                # 尝试将参数替换到 SQL 中（仅用于日志显示）
                try:
                    formatted_query = query % tuple(args) if isinstance(args, (tuple, list)) else query % args
                    sql_logger.debug(f"SQL: {formatted_query}")
                except:
                    sql_logger.debug(f"SQL: {query} | Params: {args}")
            else:
                sql_logger.debug(f"SQL: {query}")
        
        try:
            result = self._cursor.execute(query, args)
            return result
        except Exception as e:
            if LOG_SQL:
                sql_logger.error(f"SQL Error: {e} | Query: {query[:200]}")
            raise
    
    def executemany(self, query, args_list):
        """批量执行 SQL 并记录日志"""
        if LOG_SQL:
            sql_logger.debug(f"SQL (batch): {query[:200]} | Count: {len(args_list)}")
        
        try:
            result = self._cursor.executemany(query, args_list)
            return result
        except Exception as e:
            if LOG_SQL:
                sql_logger.error(f"SQL Error: {e} | Query: {query[:200]}")
            raise
    
    def fetchone(self):
        result = self._cursor.fetchone()
        if LOG_SQL:
            sql_logger.debug(f"Fetch one: {result}")
        return result
    
    def fetchall(self):
        result = self._cursor.fetchall()
        if LOG_SQL:
            sql_logger.debug(f"Fetch all: {len(result)} rows")
        return result
    
    def fetchmany(self, size=None):
        result = self._cursor.fetchmany(size)
        if LOG_SQL:
            sql_logger.debug(f"Fetch many: {len(result)} rows")
        return result
    
    @property
    def lastrowid(self):
        return self._cursor.lastrowid
    
    @property
    def rowcount(self):
        return self._cursor.rowcount
    
    def close(self):
        return self._cursor.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
    
    def __getattr__(self, name):
        """代理其他属性到原始 cursor"""
        return getattr(self._cursor, name)


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
    """获取包装后的数据库连接，自动记录所有 SQL"""
    raw_conn = _get_pool().connection()
    sql_logger.debug("Database connection acquired from pool")
    return LoggedConnection(raw_conn)


def node_exists(node_id):
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


def log_llm(user_id, channel_id, bot_instance_id, provider_id, prompt, response, session_id=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO llm_log
                (user_id, channel_id, bot_instance_id, provider_id, session_id, prompt, response, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,NOW(6))
                """,
                (user_id, channel_id, bot_instance_id, provider_id, session_id, prompt, response),
            )
        conn.commit()
        sql_logger.info(f"LLM log saved: user={user_id}, session={session_id[:8] if session_id else 'N/A'}..., prompt_len={len(prompt)}, response_len={len(response)}")
    except Exception as e:
        sql_logger.error(f"Failed to log LLM: {e}", exc_info=True)
        raise
    finally:
        conn.close()


def get_recent_llm_messages(user_id, channel_id, bot_instance_id, limit=6):
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
