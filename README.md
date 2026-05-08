# Telegram ChatOps Bot

一个基于 Telegram 的 ChatOps 运维机器人，支持通过菜单或命令执行常用运维操作、查看系统状态、接收告警、调用大模型助手，并把操作记录写入 MySQL。

## 功能

- Telegram webhook 接入
- 用户白名单校验
- `/cmd` 执行预置运维命令
- `/status` 查看 CPU、内存、磁盘状态
- `/ai` 调用大模型问答
- `/msg` 保存消息到本地文件
- 定时系统告警推送
- MySQL 初始化与审计数据存储

## 环境要求

- Python 3.10+
- MySQL 8.x 或兼容版本
- 可公网访问的 HTTPS 域名，例如 `bot.domain.com`
- Telegram Bot Token

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

至少需要配置：

```env
TELEGRAM_BOT_TOKEN=你的 Telegram Bot Token
ALLOWED_USERS=你的 Telegram 用户 ID

WEBHOOK_DOMAIN=bot.domain.com
WEBHOOK_LISTEN=0.0.0.0
WEBHOOK_PORT=33333
WEBHOOK_URL_PATH=tg_webhook_xxx
WEBHOOK_SECRET_TOKEN=可选的随机字符串

MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=你的数据库用户
MYSQL_PASSWORD=你的数据库密码
MYSQL_DATABASE=telegram_bot
```

`WEBHOOK_URL_PATH` 建议使用随机字符串，不需要前导 `/`。如果留空，程序会默认使用 `TELEGRAM_BOT_TOKEN` 作为路径。

## 初始化

执行初始化脚本：

```bash
python init_bot.py
```

脚本会完成：

- 读取 `.env`
- 连接 MySQL
- 执行 `init.sql`
- 调用 Telegram `setWebhook` 注册 webhook

只初始化数据库：

```bash
python init_bot.py --skip-webhook
```

只注册 webhook：

```bash
python init_bot.py --skip-db
```

## 启动

```bash
python main.py
```

程序会监听：

```text
0.0.0.0:33333
```

生产环境建议用 Nginx 或 Caddy 提供 HTTPS，并反向代理到机器人端口。

Nginx 示例：

```nginx
server {
    listen 443 ssl;
    server_name bot.domain.com;

    location /tg_webhook_xxx {
        proxy_pass http://127.0.0.1:33333;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
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

## 常见问题

如果 Telegram 收不到消息，检查：

- 域名 HTTPS 证书是否有效
- Nginx/Caddy 是否正确反代到 `33333`
- `python init_bot.py --skip-db` 是否成功注册 webhook
- `ALLOWED_USERS` 是否包含你的 Telegram 用户 ID
- MySQL 连接配置是否正确
