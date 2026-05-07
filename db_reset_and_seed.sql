-- =============================================================================
-- 1) 清空所有表（按你的 bot_mysql.sql 结构，表间未声明外键，顺序任意）
--    执行前请确认库名，必要时: USE telegram_bot;
-- =============================================================================

SET FOREIGN_KEY_CHECKS = 0;

TRUNCATE TABLE `alert_log`;
TRUNCATE TABLE `command_log`;
TRUNCATE TABLE `llm_log`;
TRUNCATE TABLE `status_log`;
TRUNCATE TABLE `chat_state`;
TRUNCATE TABLE `command_allow`;
TRUNCATE TABLE `channel`;
TRUNCATE TABLE `user`;
TRUNCATE TABLE `llm_provider`;
TRUNCATE TABLE `bot_instance`;
TRUNCATE TABLE `node`;

SET FOREIGN_KEY_CHECKS = 1;

-- =============================================================================
-- 2) 必要初始化数据（与 main.py 中 BOT_ID=1、默认 node_id=1 及 /cmd 白名单一致）
--    请按实际环境修改 node.ip、bot_instance、command_allow.script
-- =============================================================================

-- 节点：executor.node_exists() 要求存在；config 里 NODE_ID 默认应对应此 id
INSERT INTO `node` (`id`, `name`, `ip`, `status`, `created_at`)
VALUES (1, 'default', '127.0.0.1', 'unknown', NOW(6));

-- Bot 实例：与代码里 BOT_ID = 1 对齐（审计/扩展用）
INSERT INTO `bot_instance` (`id`, `name`, `type`, `platform`, `enabled`, `created_at`)
VALUES (1, 'default-ops', 'ops', 'telegram', 1, NOW(6));

-- 命令白名单：script 会被 shlex 拆成 argv，禁止写 shell 元字符拼接用户输入
-- Linux 常见路径；若 Bot 跑在 Windows，请改为对应可执行文件或批处理思路（仍建议 argv 列表语义）
INSERT INTO `command_allow` (`command`, `script`, `enabled`, `created_at`) VALUES
('uptime', 'uptime', 1, NOW(6)),
('disk', 'df -h /', 1, NOW(6)),
('mem', 'free -h', 1, NOW(6)),
('docker', 'docker ps', 1, NOW(6));

-- 可选：LLM 提供方，便于以后把 provider_id 从 NULL 迁到具体行
INSERT INTO `llm_provider` (`name`, `type`, `config`, `enabled`, `created_at`)
VALUES ('default-openai', 'openai', '{}', 1, NOW(6));

-- 自增游标与显式 id=1 已写入时保持一致（无则省略）
ALTER TABLE `node` AUTO_INCREMENT = 2;
ALTER TABLE `bot_instance` AUTO_INCREMENT = 2;
ALTER TABLE `command_allow` AUTO_INCREMENT = 5;
ALTER TABLE `llm_provider` AUTO_INCREMENT = 2;
