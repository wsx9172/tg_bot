import logging

from openai import OpenAI

from db import get_recent_llm_messages, log_llm

logger = logging.getLogger(__name__)

MEMORY_TURNS = 6
MAX_HISTORY_TEXT_LENGTH = 2000

SYSTEM_PROMPT = """
你是一个面向 Linux 运维和 ChatOps 场景的助手。

你的职责：
- 帮助用户分析系统状态、日志、命令输出、告警和运维问题。
- 回答要简洁、准确、可执行，优先给出排查步骤和安全建议。
- 如果用户询问危险操作，例如删除数据、重启服务、修改防火墙、执行批量命令，要明确提醒风险，并建议先确认影响范围和备份。
- 不要声称自己已经执行了命令；你只能基于用户提供的信息和上下文进行分析。
- 如果上下文不足，先说明缺少的信息，再给出最小可行的下一步。
- 默认使用中文回答，除非用户要求使用其他语言。
""".strip()


def _config_value(config, *names, default=None):
    for name in names:
        value = config.get(name)
        if value:
            return value
    return default


def _trim_text(text, max_length=MAX_HISTORY_TEXT_LENGTH):
    if not text:
        return ""
    text = str(text)
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n...[truncated]"


def _normalize_base_url(api_url):
    if not api_url:
        return None
    api_url = api_url.rstrip("/")
    if api_url.endswith("/chat/completions"):
        return api_url[: -len("/chat/completions")]
    return api_url


def _build_messages(user_id, channel_id, bot_instance_id, prompt):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    try:
        history = get_recent_llm_messages(
            user_id,
            channel_id,
            bot_instance_id,
            limit=MEMORY_TURNS,
        )
    except Exception:
        logger.warning("failed to load llm history", exc_info=True)
        history = []

    for old_prompt, old_response in history:
        if old_prompt:
            messages.append({"role": "user", "content": _trim_text(old_prompt)})
        if old_response:
            messages.append({"role": "assistant", "content": _trim_text(old_response)})

    messages.append({"role": "user", "content": prompt})
    return messages


def ask_llm(
    user_id,
    channel_id,
    bot_instance_id,
    provider_id,
    config,
    prompt,
):
    try:
        api_key = _config_value(config, "api_key", "OPENAI_API_KEY")
        api_url = _config_value(config, "api_url", "OPENAI_API_URL")
        model = _config_value(config, "model", "OPENAI_MODEL", default="deepseek-v4-pro")

        if not api_key:
            return "LLM Error: missing api_key"

        client = OpenAI(
            api_key=api_key,
            base_url=_normalize_base_url(api_url),
        )

        completion = client.chat.completions.create(
            model=model,
            messages=_build_messages(user_id, channel_id, bot_instance_id, prompt),
            timeout=30,
        )

        result = completion.choices[0].message.content

        if not result:
            return "Empty response from API"

        try:
            log_llm(
                user_id,
                channel_id,
                bot_instance_id,
                provider_id,
                prompt,
                result,
            )
        except Exception:
            logger.warning("failed to log llm response", exc_info=True)

        return result

    except Exception as e:
        logger.exception("llm request failed")
        return f"LLM Error: {str(e)}"
