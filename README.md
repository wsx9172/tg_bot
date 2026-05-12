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

# LLM 搜索功能配置（新增）
ENABLE_SEARCH=true
```

`BOT_MODE` 可选：

- `webhook`：通过 HTTPS webhook 接收 Telegram 更新，适合服务器部署。
- `polling`：主动轮询 Telegram 更新，适合本地开发或没有公网 HTTPS 域名的环境。

`WEBHOOK_URL_PATH` 建议使用随机字符串，不需要前导 `/`。如果留空，程序会默认使用 `TELEGRAM_BOT_TOKEN` 作为路径。

### LLM 搜索功能说明

项目支持 AI 助手调用网络搜索工具，获取实时信息和技术文档。

#### ENABLE_SEARCH

是否启用搜索功能：

- `true` 或 `1` 或 `yes`：启用搜索功能（默认）
- `false` 或其他值：禁用搜索功能

示例：
```env
ENABLE_SEARCH=true
```

#### 搜索引擎

项目使用 **DuckDuckGo Search** 作为搜索引擎：

- ✅ **完全免费**：无需 API Key
- ✅ **隐私保护**：不追踪用户
- ✅ **易于使用**：安装依赖即可使用
- ⚠️ **注意**：有速率限制，建议合理设置搜索频率

安装依赖：
```bash
pip install duckduckgo-search
```

或使用 requirements.txt：
```bash
pip install -r requirements.txt
```

#### 工作原理

1. **智能判断**：模型会自动判断是否需要搜索（例如询问最新技术、实时信息等）
2. **工具调用**：如果需要搜索，模型会调用 `web_search` 工具
3. **执行搜索**：系统通过 DuckDuckGo 执行网络搜索并获取结果
4. **生成回答**：模型结合搜索结果生成最终回答

示例对话：
```
用户：Kubernetes 最新版本有什么新特性？
AI：[调用搜索工具] → [获取最新信息] → [生成回答]
```

### 日志配置说明

项目内置了完整的日志系统，支持控制台和文件双输出，并配置了合理的滚动策略。

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
- `false` 或其他值：禁用 SQL 日志（默认）

示例：
```env
LOG_SQL=true
```

#### 日志文件配置

**自动创建目录**：
- 程序启动时自动创建 `./log` 目录
- 无需手动创建，如果目录不存在会自动生成

**日志文件位置**：
- 主日志文件：`./log/bot.log`
- SQL 日志文件：`./log/sql.log`（仅当 `LOG_SQL=true` 时生成）

**滚动策略**：
- **文件大小限制**：单个日志文件最大 10MB
- **备份数量**：保留最近 5 个备份文件
- **自动轮转**：当日志文件超过 10MB 时，自动创建新文件
- **文件命名**：
  - `bot.log` - 当前日志
  - `bot.log.1` - 最近的备份
  - `bot.log.2` - 次近的备份
  - ...以此类推

**编码格式**：UTF-8，支持中文日志

**输出方式**：
- ✅ **控制台输出**：实时显示在终端
- ✅ **文件输出**：持久化保存到磁盘
- 两者独立配置，互不影响

#### 日志目录结构

```
bot/
├── log/                  # 日志目录（自动创建）
│   ├── bot.log          # 主日志文件
│   ├── bot.log.1        # 备份文件 1
│   ├── bot.log.2        # 备份文件 2
│   ├── ...
│   ├── sql.log          # SQL 日志文件（可选）
│   └── sql.log.1        # SQL 备份文件
├── config.py
├── main.py
└── ...
```

#### 查看日志

**实时查看**：
```bash
# Linux/macOS
tail -f log/bot.log

# Windows PowerShell
Get-Content log/bot.log -Wait -Tail 50
```

**查看历史日志**：
```bash
# 查看最近的 100 行
tail -n 100 log/bot.log

# 搜索特定关键词
grep "ERROR" log/bot.log
grep "user_id=123456" log/bot.log
```

**清理旧日志**：
- 系统自动管理，超过 5 个备份的文件会被自动删除
- 如需手动清理：`rm log/bot.log.*`

#### 调试技巧

1. **开发环境**：设置 `LOG_LEVEL=DEBUG` 获取最详细信息
2. **生产环境**：设置 `LOG_LEVEL=INFO` 平衡性能和可观测性
3. **SQL 调试**：临时设置 `LOG_SQL=true` 排查数据库问题
4. **日志分析**：定期检查 `log/` 目录，分析错误模式

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
