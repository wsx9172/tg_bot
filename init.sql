-- =============================================================================
-- 从零初始化：建库（若不存在）→ 删表重建 → 种子数据
-- 用法（与 .env 中 MYSQL_DATABASE 一致，默认 telegram_bot）：
--   mysql -h HOST -u USER -p < init.sql
-- 若库已存在且仅想重建表结构+数据：直接执行本文件即可（各表 DROP IF EXISTS）。
-- 若要从服务器上彻底删掉该库再建，取消注释下面两行（危险，确认环境后再用）：
-- DROP DATABASE IF EXISTS `telegram_bot`;
-- CREATE DATABASE `telegram_bot` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- =============================================================================

CREATE DATABASE IF NOT EXISTS `telegram_bot` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `telegram_bot`;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ---------------------------------------------------------------------------
-- 机器人实例
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS `bot_instance`;
CREATE TABLE `bot_instance` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键，对应环境变量 BOT_INSTANCE_ID',
  `name` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '展示名',
  `type` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'ops/alert/ai/hybrid',
  `platform` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'telegram/wechat/feishu/dingtalk/web',
  `external_ref` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '平台侧 Bot 标识（如 @username、appId）',
  `config` text COLLATE utf8mb4_unicode_ci COMMENT '扩展 JSON（端点、特性开关等）',
  `enabled` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_bot_platform` (`platform`,`enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Bot 实例（多进程/多账号）';

DROP TABLE IF EXISTS `user_node`;
DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `platform` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `external_user_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `role` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'viewer' COMMENT 'admin=全部节点; 非admin见 user_node 与应用层策略',
  `enabled` tinyint(1) NOT NULL DEFAULT '1',
  `metadata` text COLLATE utf8mb4_unicode_ci COMMENT '扩展 JSON',
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_platform_ext` (`platform`,`external_user_id`),
  KEY `idx_user_role` (`role`,`enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='跨平台用户';

CREATE TABLE `user_node` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL COMMENT 'user.id',
  `node_id` bigint NOT NULL COMMENT 'node.id',
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_node` (`user_id`,`node_id`),
  KEY `idx_user_node_user` (`user_id`),
  KEY `idx_user_node_node` (`node_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户-节点授权（多机隔离）';

DROP TABLE IF EXISTS `channel`;
CREATE TABLE `channel` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `platform` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `external_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'chat_id/room_id 等',
  `name` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `bot_instance_id` bigint DEFAULT NULL COMMENT '可选：绑定默认处理该会话的 Bot 实例',
  `metadata` text COLLATE utf8mb4_unicode_ci COMMENT '扩展 JSON',
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_channel_platform_ext` (`platform`,`external_id`),
  KEY `idx_channel_bot` (`bot_instance_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='消息渠道（多平台）';

DROP TABLE IF EXISTS `chat_state`;
CREATE TABLE `chat_state` (
  `platform` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `external_chat_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `external_user_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '首次触发用户',
  `first_seen` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`platform`,`external_chat_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话首次记录';

DROP TABLE IF EXISTS `node`;
CREATE TABLE `node` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ip` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `region` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `labels` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '逗号分隔或约定格式',
  `status` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT 'unknown',
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_node_region` (`region`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='受控机器';

DROP TABLE IF EXISTS `command_allow`;
CREATE TABLE `command_allow` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `platform` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '*' COMMENT '* 表示任意平台',
  `bot_instance_id` bigint NOT NULL DEFAULT '0' COMMENT '0 表示任意 Bot 实例',
  `command` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `script` text COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'argv 语义，供 shlex.split',
  `enabled` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_allow_scope` (`platform`,`bot_instance_id`,`command`),
  KEY `idx_allow_lookup` (`command`,`enabled`,`platform`,`bot_instance_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='命令白名单（按平台/实例覆盖）';

DROP TABLE IF EXISTS `command_log`;
CREATE TABLE `command_log` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL COMMENT 'user.id（内部用户主键）',
  `channel_id` bigint NOT NULL COMMENT 'channel.id',
  `bot_id` bigint DEFAULT NULL COMMENT 'bot_instance.id',
  `node_id` bigint DEFAULT NULL,
  `command` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `args` text COLLATE utf8mb4_unicode_ci COMMENT '其余参数 JSON 数组字符串',
  `status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `result` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_cl_user_time` (`user_id`,`created_at`),
  KEY `idx_cl_node_time` (`node_id`,`created_at`),
  KEY `idx_cl_bot_time` (`bot_id`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='命令审计';

DROP TABLE IF EXISTS `status_log`;
CREATE TABLE `status_log` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `node_id` bigint NOT NULL,
  `cpu` double DEFAULT NULL,
  `memory` double DEFAULT NULL,
  `disk` double DEFAULT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_status_node_time` (`node_id`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='采集指标';

DROP TABLE IF EXISTS `alert_log`;
CREATE TABLE `alert_log` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `node_id` bigint DEFAULT NULL,
  `type` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `level` varchar(16) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `message` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_alert_node_time` (`node_id`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='告警';

DROP TABLE IF EXISTS `llm_provider`;
CREATE TABLE `llm_provider` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `type` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `config` text COLLATE utf8mb4_unicode_ci,
  `enabled` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='LLM 提供方';

DROP TABLE IF EXISTS `llm_log`;
CREATE TABLE `llm_log` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint DEFAULT NULL COMMENT 'user.id',
  `channel_id` bigint DEFAULT NULL COMMENT 'channel.id',
  `bot_instance_id` bigint DEFAULT NULL COMMENT 'bot_instance.id',
  `provider_id` bigint DEFAULT NULL,
  `session_id` varchar(64) DEFAULT NULL COMMENT '会话ID，用于关联同一对话的多轮调用',
  `prompt` text COLLATE utf8mb4_unicode_ci,
  `response` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_llm_user_time` (`user_id`,`created_at`),
  KEY `idx_llm_bot_time` (`bot_instance_id`,`created_at`),
  KEY `idx_llm_session` (`session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='LLM 审计';

SET FOREIGN_KEY_CHECKS = 1;

-- =============================================================================
-- 种子数据（NODE_ID=1、BOT_INSTANCE_ID=1 与 .env 默认一致）
-- =============================================================================

INSERT INTO `node` (`id`, `name`, `ip`, `region`, `labels`, `status`, `created_at`)
VALUES (1, 'default', '127.0.0.1', NULL, NULL, 'unknown', NOW(6));

INSERT INTO `bot_instance` (`id`, `name`, `type`, `platform`, `external_ref`, `config`, `enabled`, `created_at`)
VALUES (1, 'default-ops', 'ops', 'telegram', NULL, NULL, 1, NOW(6));

INSERT INTO `command_allow`
  (`platform`, `bot_instance_id`, `command`, `script`, `enabled`, `created_at`)
VALUES
  ('*', 0, 'uptime', 'uptime', 1, NOW(6)),
  ('*', 0, 'disk', 'df -h /', 1, NOW(6)),
  ('*', 0, 'mem', 'free -h', 1, NOW(6)),
  ('*', 0, 'docker', 'docker ps', 1, NOW(6));

INSERT INTO `llm_provider` (`name`, `type`, `config`, `enabled`, `created_at`)
VALUES ('default-openai', 'openai', '{}', 1, NOW(6));

ALTER TABLE `node` AUTO_INCREMENT = 2;
ALTER TABLE `bot_instance` AUTO_INCREMENT = 2;
ALTER TABLE `command_allow` AUTO_INCREMENT = 10;
ALTER TABLE `llm_provider` AUTO_INCREMENT = 2;
