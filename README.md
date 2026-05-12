# Telegram ChatOps Bot

一个运行在宿主机上的 Telegram ChatOps 运维机器人，支持菜单和命令两种交互方式，可查看宿主机状态、执行白名单命令、接收告警、调用大模型助手，并把操作记录写入 MySQL。

> 说明：本项目会读取宿主机系统状态并执行宿主机命令，不建议用普通 Docker 容器部署 bot 主进程。

## 功能

- Telegram webhook 或 polling 接入
- 用户白名单校验
- `/status` 查看 CPU、内存、磁盘状态
- `/cmd` 执行预置运维命令
- `/ai` 调用大模型问答
- `/msg` 保存消息到本地文件
- 定时系统告警推送
- MySQL 初始化与审计数据存储
- **完整的日志系统**：支持 SQL 日志和业务日志，方便调试和问题排查

## 环境要求

- Python 3.10+
- MySQL 8.x 或兼容版本
- Telegram Bot Token
- webhook 模式需要 HTTPS 域名和反向代理，例如 Caddy 或 Nginx

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 配置

复制环境变量示例：

```bash
cp .env.example .env
```

常用配置：

```env
TELEGRAM_BOT_TOKEN=你的 Telegram Bot Token
BOT_MODE=webhook
ALLOWED_USERS=你的 Telegram 用户 ID

WEBHOOK_DOMAIN=bot.risun.wang
WEBHOOK_LISTEN=0.0.0.0
WEBHOOK_PORT=33333
WEBHOOK_URL_PATH=tg_webhook_xxx
WEBHOOK_SECRET_TOKEN=可选的随机字符串

MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=你的数据库用户
MYSQL_PASSWORD=你的数据库密码
MYSQL_DATABASE=telegram_bot

# 日志配置（新增）
LOG_LEVEL=INFO
LOG_SQL=false
```

`BOT_MODE` 可选：

- `webhook`：通过 HTTPS webhook 接收 Telegram 更新，适合服务器部署。
- `polling`：主动轮询 Telegram 更新，适合本地开发或没有公网 HTTPS 域名的环境。

`WEBHOOK_URL_PATH` 建议使用随机字符串，不需要前导 `/`。如果留空，程序会默认使用 `TELEGRAM_BOT_TOKEN` 作为路径。

### 日志配置说明

项目内置了完整的日志系统，可以通过环境变量进行配置：

#### LOG_LEVEL

控制日志输出级别，可选值：

- `DEBUG`：最详细的日志，包括所有 SQL 语句、参数、内部状态等
- `INFO`：关键业务流程日志（推荐生产环境使用）
- `WARNING`：只记录警告和错误
- `ERROR`：只记录错误

示例：
```env
LOG_LEVEL=DEBUG
```

#### LOG_SQL

是否启用 SQL 日志，记录所有数据库操作：

- `true` 或 `1` 或 `yes`：启用 SQL 日志
- `false` 或其他值：禁用 SQL 日志

示例：
```env
LOG_SQL=true
```

启用后，所有 SQL 语句和参数都会以以下格式输出：
```
2024-01-15 10:30:45 - SQL - DEBUG - SQL: SELECT 1 FROM node WHERE id=%s LIMIT 1 | Params: (1,)
```

#### 日志格式

所有日志统一格式：
```
YYYY-MM-DD HH:MM:SS - 模块名 - 级别 - 消息内容
```

示例输出：
```
2024-01-15 10:30:45 - main - INFO - User admin (ID: 123456) started bot
2024-01-15 10:30:45 - sql - DEBUG - SQL: SELECT id FROM `user` WHERE platform=%s AND external_user_id=%s | Params: ('telegram', '123456')
2024-01-15 10:30:45 - executor - INFO - Executing command: uptime by user=admin
2024-01-15 10:30:45 - monitor - WARNING - Alert triggered: CPU high 92%
```

## 初始化

```bash
python setup_bot.py
```

脚本会完成：

- 读取 `.env`
- 连接 MySQL，数据库没有表时执行 `init.sql`
- 根据 `BOT_MODE` 同步 Telegram webhook 状态

重复执行 `setup_bot.py` 是安全的：如果数据库里已经有表，默认会跳过 `init.sql`。

只初始化数据库，不同步 Telegram webhook 状态：

```bash
python setup_bot.py --skip-webhook
```

只同步 Telegram webhook 状态：

```bash
python setup_bot.py --skip-db
```

重建数据库表：

```bash
python setup_bot.py --reset-db --skip-webhook
```

## 启动

```bash
python main.py
```

如果 `BOT_MODE=polling`，程序会直接启动 polling。

如果 `BOT_MODE=webhook`，程序会监听：

```text
0.0.0.0:33333
```

生产环境建议用 systemd 托管 bot 进程，并用 Caddy 或 Nginx 在宿主机上提供 HTTPS，反向代理到 `127.0.0.1:33333`。

Caddy 示例：

```caddyfile
bot.risun.wang {
    reverse_proxy 127.0.0.1:33333
}
```

## 使用

在 Telegram 中向机器人发送：

```text
/start
```

常用命令：

```text
/status
/cmd uptime
/cmd disk
/cmd mem
/ai 帮我分析这段日志
/msg 保存一段文本
```

## 调试技巧

### 开启详细日志

在 `.env` 文件中设置：

```env
LOG_LEVEL=DEBUG
LOG_SQL=true
```

重启 bot 后，你将看到：
- 所有用户的操作记录
- 所有数据库查询和更新
- 所有命令执行过程
- 所有 API 调用详情

### 查看特定模块日志

如果需要查看特定模块的日志，可以在代码中调整对应 logger 的级别。例如只看数据库操作：

```python
import logging
logging.getLogger('sql').setLevel(logging.DEBUG)
```

### 日志文件输出（可选）

如果需要将日志保存到文件，可以修改 `config.py` 中的日志配置，添加 FileHandler：

```python
file_handler = logging.FileHandler('bot.log', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
logging.getLogger().addHandler(file_handler)
```

## 常见问题

如果 polling 模式收不到消息，执行：

```bash
python setup_bot.py --skip-db
```

这会删除 Telegram 侧已有 webhook。

如果 webhook 模式收不到消息，检查：

- 域名 DNS 是否指向服务器
- 反向代理是否正确转发到 `127.0.0.1:33333`
- `python setup_bot.py --skip-db` 是否成功注册 webhook
- `WEBHOOK_DOMAIN`、`WEBHOOK_URL_PATH` 和 Telegram webhook 注册信息是否一致
- `ALLOWED_USERS` 是否包含你的 Telegram 用户 ID
- MySQL 连接配置是否正确

如果遇到问题，首先检查日志输出，大多数问题都能在日志中找到原因。
