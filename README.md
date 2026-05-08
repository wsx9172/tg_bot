# Telegram ChatOps Bot

一个基于 Telegram 的 ChatOps 运维机器人，支持菜单和命令两种交互方式，可执行预置运维命令、查看系统状态、接收告警、调用大模型助手，并把操作记录写入 MySQL。

## 功能

- Telegram webhook 或 polling 接入
- 用户白名单校验
- `/cmd` 执行预置运维命令
- `/status` 查看 CPU、内存、磁盘状态
- `/ai` 调用大模型问答
- `/msg` 保存消息到本地文件
- 定时系统告警推送
- MySQL 初始化与审计数据存储

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

MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_ROOT_PASSWORD=你的 MySQL root 密码
MYSQL_USER=tg_bot
MYSQL_PASSWORD=你的数据库密码
MYSQL_DATABASE=telegram_bot
```

`BOT_MODE` 可选：

- `webhook`：通过 HTTPS webhook 接收 Telegram 更新，适合服务器部署。
- `polling`：主动轮询 Telegram 更新，适合本地开发或没有公网 HTTPS 域名的环境。

`WEBHOOK_URL_PATH` 建议使用随机字符串，不需要前导 `/`。如果留空，程序会默认使用 `TELEGRAM_BOT_TOKEN` 作为路径。

## Docker Compose

Compose 会启动三个容器：

- `bot`：运行 Telegram bot
- `caddy`：自动申请/续期 HTTPS 证书，并反向代理到 bot 的 `33333` 端口
- `mysql`：运行 MySQL 8，存储 bot 数据

Caddy 不需要手动挂载证书，但需要确保：

- `WEBHOOK_DOMAIN` 已解析到这台服务器
- 服务器公网 `80` 和 `443` 端口可访问

启动：

```bash
docker compose up -d --build
```

`bot` 镜像使用 `entrypoint.sh` 启动。容器启动时会先执行：

```bash
python setup_bot.py
```

然后再执行默认命令：

```bash
python main.py
```

因此修改 `.env`、`Caddyfile` 或代码后，通常重新执行 `docker compose up -d --build` 即可。

查看日志：

```bash
docker compose logs -f bot caddy mysql
```

停止服务：

```bash
docker compose down
```

MySQL 数据和 Caddy 证书数据会保存到 Docker volumes：

- `mysql_data`
- `caddy_data`
- `caddy_config`

## 手动初始化

一般不需要手动执行，因为 `entrypoint.sh` 会自动执行 setup。

如果只想手动同步数据库和 Telegram webhook 状态：

```bash
docker compose run --rm bot python setup_bot.py
```

如果想跳过容器启动时的 setup：

```bash
SKIP_SETUP=1 docker compose up -d --build
```

## 本地运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python setup_bot.py
python main.py
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python setup_bot.py
python main.py
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

如果 polling 模式收不到消息，执行：

```bash
python setup_bot.py --skip-db
```

这会删除 Telegram 侧已有 webhook。

如果 webhook 模式收不到消息，检查：

- 域名 DNS 是否指向服务器
- 服务器 `80` / `443` 是否开放给 Caddy
- `docker compose logs -f caddy` 中是否有证书申请错误
- `WEBHOOK_DOMAIN`、`WEBHOOK_URL_PATH` 和 Telegram webhook 注册信息是否一致
- `ALLOWED_USERS` 是否包含你的 Telegram 用户 ID
- MySQL 连接配置是否正确
