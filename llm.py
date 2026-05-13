import logging
import json
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps
from datetime import datetime
import requests
from openai import OpenAI

from db import get_recent_llm_messages, log_llm
from system_tools import SYSTEM_TOOLS, SYSTEM_TOOL_SCHEMAS
from config import SEARCH_BASE_URL

logger = logging.getLogger(__name__)

def log_openai_api_call(call_label="API Call"):
    """
    通用 LLM API 调用日志装饰器（安全版）

    只记录：
    - 请求：model / messages长度 / tools数量 / tool_choice
    - 响应：content / tool_calls数量 / token信息（如有）

    不依赖任何 SDK 结构，避免 JSON 序列化错误
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):

            # ========== 安全提取请求信息 ==========
            model = kwargs.get("model") or (args[1] if len(args) > 1 else "unknown")
            messages = kwargs.get("messages") or (args[2] if len(args) > 2 else [])
            tools = kwargs.get("tools") or (args[3] if len(args) > 3 else [])
            tool_choice = kwargs.get("tool_choice", "auto")
            timeout = kwargs.get("timeout", 30)

            request_summary = {
                "label": call_label,
                "model": str(model),
                "messages_count": len(messages),
                "tools_count": len(tools),
                "tool_choice": tool_choice,
                "timeout": timeout,
            }

            logger.info(f"LLM Request: {json.dumps(request_summary, ensure_ascii=False)}")

            # ========== 调用 ==========
            try:
                completion = func(*args, **kwargs)

                # ========== 安全提取响应 ==========
                choices = getattr(completion, "choices", [])

                response_summary = {
                    "label": call_label,
                    "choices_count": len(choices),
                }

                # 提取第一个结果（通常够用）
                if choices:
                    msg = getattr(choices[0], "message", None)

                    if msg:
                        response_summary["content"] = getattr(msg, "content", None)

                        tool_calls = getattr(msg, "tool_calls", None)
                        if tool_calls:
                            response_summary["tool_calls_count"] = len(tool_calls)
                        else:
                            response_summary["tool_calls_count"] = 0

                # token信息（可选）
                usage = getattr(completion, "usage", None)
                if usage:
                    response_summary["tokens"] = {
                        "prompt": getattr(usage, "prompt_tokens", None),
                        "completion": getattr(usage, "completion_tokens", None),
                        "total": getattr(usage, "total_tokens", None),
                    }

                logger.info(f"LLM Response: {json.dumps(response_summary, ensure_ascii=False)}")

                return completion

            except Exception as e:
                logger.error(f"LLM API call failed ({call_label}): {e}", exc_info=True)
                raise

        return wrapper
    return decorator


MEMORY_TURNS = 5 # LLM 回复中包含的最近消息数量
MAX_HISTORY_TEXT_LENGTH = 2000 # 单条消息最大字符数
MAX_TOOL_CONTENT = 4000  # 工具返回内容最大字符数
MAX_SNIPPET_LENGTH = 300  # 搜索结果摘要最大长度
MAX_TOOL_CALL_ROUNDS = 5  # 工具调用最大轮次，防止无限循环

SYSTEM_PROMPT = """
You are skilled in Linux operations, Docker, networking, backend systems, ChatOps, and troubleshooting.
You can also answer general questions normally.

Guidelines:

* Prefer practical and technical answers for system/programming/infrastructure topics
* Use tools when real-time or system information is needed
* Reply in Chinese by default

Output Style Requirements:

* Responses must be optimized for plain-text chat interfaces
* Do NOT use Markdown tables and headings like | or # or ## unless the user asks for 
* Do NOT use fenced code blocks unless explicitly requested
* Prefer short paragraphs and simple bullet lists
* Use Unicode symbols sparingly for readability (such as •, →, ✓)
* Avoid overly long responses unless the user asks for detailed explanations

Behavior Rules:

* Never claim commands or operations were executed unless tool results confirm it
* Base technical conclusions on tool output or user-provided information
* Warn users before dangerous operations
""".strip()


def _get_current_time_message() -> str:
    """
    生成包含当前系统时间的状态消息
    
    将时间作为系统状态信息注入，帮助模型了解当前时间上下文，减少因训练数据截止导致的幻觉。
    此消息应作为独立的 system message 添加到消息列表中。
    
    Returns:
        包含当前时间的系统状态消息字符串
    """
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
    
    time_message = (
        f"SysCurrent systemtem time: {current_time}. "
        "Use for time-aware responses."
    )
    
    return time_message


# 定义搜索工具的 schema
SEARCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "在互联网上搜索实时信息、技术文档、最新资讯等。当用户询问需要最新信息的问题时使用此工具。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词或问题，应该简洁明确"
                },
                "num_results": {
                    "type": "integer",
                    "description": "返回结果数量，默认3条，最多5条",
                    "default": 3,
                    "minimum": 1,
                    "maximum": 5
                }
            },
            "required": ["query"]
        }
    }
}


def _build_tools_list(enabled_tools: set) -> List[Dict]:
    """
    根据配置集合动态构建工具列表
    
    支持通过配置集合灵活控制哪些工具对 LLM 可用。这种设计便于未来扩展更多工具类型。
    
    Args:
        enabled_tools: 启用的工具类型集合，如 {"search", "system"}
    
    Returns:
        包含所有已启用工具的 schema 列表
    
    Examples:
        >>> _build_tools_list({"search", "system"})  # 启用搜索和系统工具
        >>> _build_tools_list({"search"})  # 仅启用搜索工具
        >>> _build_tools_list(set())  # 禁用所有工具
    """
    tools = []
    
    # 如果启用系统工具，添加系统工具 schemas
    if "system" in enabled_tools:
        tools.extend(SYSTEM_TOOL_SCHEMAS)
        logger.debug(f"Added {len(SYSTEM_TOOL_SCHEMAS)} system tool schemas")
    
    # 如果启用搜索功能，将搜索工具放在最前面（优先级更高）
    if "search" in enabled_tools:
        tools.insert(0, SEARCH_TOOL_SCHEMA)
        logger.debug("Added search tool schema")
    
    logger.info(f"Built tools list with {len(tools)} tools (enabled: {enabled_tools})")
    return tools


def _config_value(config, *names, default=None):
    """
    从配置字典中按优先级获取配置值
    
    依次尝试多个可能的键名，返回第一个非空值。用于兼容不同版本的配置项命名。
    
    Args:
        config: 配置字典对象
        *names: 要查找的键名列表（按优先级排序）
        default: 默认返回值，当所有键都不存在时返回
    
    Returns:
        找到的第一个非空配置值，或默认值
    """
    for name in names:
        value = config.get(name)
        if value:
            return value
    return default


def _trim_text(text, max_length=MAX_HISTORY_TEXT_LENGTH):
    """
    截断文本到指定长度，防止超出上下文限制
    
    Args:
        text: 需要截断的文本内容
        max_length: 最大允许长度（默认使用全局常量）
    
    Returns:
        截断后的文本，如果超长则添加省略标记
    """
    if not text:
        return ""
    text = str(text)
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n...[truncated]"


def _normalize_base_url(api_url):
    """
    规范化 API 基础 URL
    
    移除末尾的斜杠和 /chat/completions 路径后缀，确保 URL 格式统一。
    
    Args:
        api_url: 原始 API URL 地址
    
    Returns:
        规范化后的基础 URL，如果输入为空则返回 None
    """
    if not api_url:
        return None
    api_url = api_url.rstrip("/")
    if api_url.endswith("/chat/completions"):
        return api_url[: -len("/chat/completions")]
    return api_url


def _truncate_tool_content(content: str, max_length: int = MAX_TOOL_CONTENT) -> str:
    """截断工具返回内容，防止超出 LLM Context"""
    if not content:
        return ""
    
    content_str = str(content)
    if len(content_str) <= max_length:
        return content_str
    
    # 保留开头和结尾
    half = max_length // 2
    return content_str[:half] + "\n...[content truncated due to length]...\n" + content_str[-half:]


def _sanitize_snippet(snippet: str, max_length: int = MAX_SNIPPET_LENGTH) -> str:
    """清洗和截断搜索结果摘要，防止 Prompt Injection"""
    if not snippet:
        return ""
    
    # 移除潜在的脚本标签和危险 HTML
    snippet = snippet.replace("<script>", "").replace("</script>", "")
    snippet = snippet.replace("<iframe>", "").replace("</iframe>", "")
    
    # 截断
    if len(snippet) > max_length:
        snippet = snippet[:max_length] + "..."
    
    return snippet.strip()


def _web_search(query: str, num_results: int = 3) -> Dict:
    """
    
    通过搜索引擎执行搜索，返回结构化的搜索结果。
    
    Args:
        query: 搜索关键词
        num_results: 返回结果数量（1-5）
    
    Returns:
        搜索结果字典，包含状态、查询词、来源和结果列表
    """
    logger.info(f"Executing web search with search engine: query='{query}', num_results={num_results}")
    
    # 限制结果数量范围
    num_results = max(1, min(5, num_results))
    
    try:
        # 构建 search engine API 请求 URL
        search_url = f"{SEARCH_BASE_URL}/search"
        
        # 准备请求参数
        params = {
            "q": query,
            "format": "json",
            "pageno": 1,
            "categories": "general",
            "language": "zh-CN"
        }
        
        logger.debug(f"Sending request to search engine: url={search_url}, params={params}")
        
        # 发送 HTTP GET 请求，设置超时
        response = requests.get(search_url, params=params, timeout=10)
        response.raise_for_status()
        
        # 解析 JSON 响应
        data = response.json()
        
        results_list = []
        # 提取搜索结果
        for result in data.get("results", [])[:num_results]:
            title = result.get("title", "")
            snippet = result.get("content", "") or result.get("snippet", "")
            link = result.get("url", "")
            
            # 清洗和截断摘要
            snippet = _sanitize_snippet(snippet)
            
            results_list.append({
                "title": title[:200] if title else "",
                "snippet": snippet,
                "link": link
            })
        
        results = {
            "status": "success",
            "query": query,
            "results_count": len(results_list),
            "results": results_list
        }
        
        logger.info(f"search engine search completed: found {len(results['results'])} results")
        return results
        
    except requests.exceptions.Timeout:
        error_msg = "Request timeout"
        logger.error(f"search engine search timeout: {error_msg}")
        return {
            "status": "failed",
            "reason": f"Search timeout after 10 seconds",
            "query": query,
            "results": []
        }
        
    except requests.exceptions.ConnectionError as e:
        error_msg = str(e)
        logger.error(f"search engine connection error: {error_msg}", exc_info=True)
        return {
            "status": "failed",
            "reason": f"Connection error: Cannot reach search engine server at {SEARCH_BASE_URL}",
            "query": query,
            "results": []
        }
        
    except requests.exceptions.HTTPError as e:
        error_msg = str(e)
        logger.error(f"search engine HTTP error: {error_msg}", exc_info=True)
        return {
            "status": "failed",
            "reason": f"HTTP error: {response.status_code} - {error_msg}",
            "query": query,
            "results": []
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"search engine search failed: {error_msg}", exc_info=True)
        return {
            "status": "failed",
            "reason": f"Search failed: {error_msg}",
            "query": query,
            "results": []
        }


def _tool_call_to_dict(tool_call) -> Dict:
    """
    将 tool_call 对象转换为字典，确保跨 SDK 兼容性
    
    Args:
        tool_call: OpenAI SDK 的 tool_call 对象
    
    Returns:
        标准化的字典格式
    """
    return {
        "id": getattr(tool_call, 'id', ''),
        "type": "function",
        "function": {
            "name": getattr(tool_call.function, 'name', ''),
            "arguments": getattr(tool_call.function, 'arguments', '{}')
        }
    }


def _execute_single_tool(tool_call) -> Dict:
    """
    执行单个工具调用
    
    Args:
        tool_call: 单个工具调用对象
    
    Returns:
        包含 tool_call_id 和 content 的字典
    """
    function_name = tool_call.function.name
    function_args = tool_call.function.arguments
    
    logger.info(f"Tool call detected: function={function_name}, args={function_args}")
    
    # 根据工具名称分发执行：网络搜索、系统工具或未知工具
    if function_name == "web_search":
        try:
            args = json.loads(function_args)
            query = args.get("query", "")
            num_results = args.get("num_results", 3)
            
            if not query:
                logger.warning("Web search called with empty query")
                return {
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({
                        "status": "failed",
                        "reason": "Empty search query",
                        "results": []
                    }, ensure_ascii=False)
                }
            
            # 执行搜索
            search_result = _web_search(query, num_results)
            
            # 截断过长的搜索结果，防止超出 context
            result_json = json.dumps(search_result, ensure_ascii=False, indent=2)
            truncated_result = _truncate_tool_content(result_json)
            
            logger.info(f"Tool execution completed: {function_name}, status={search_result.get('status')}")
            return {
                "tool_call_id": tool_call.id,
                "content": truncated_result
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse tool arguments: {e}")
            return {
                "tool_call_id": tool_call.id,
                "content": json.dumps({
                    "status": "failed",
                    "reason": f"Invalid arguments: {str(e)}",
                    "results": []
                }, ensure_ascii=False)
            }
        except Exception as e:
            logger.error(f"Tool execution failed: {e}", exc_info=True)
            return {
                "tool_call_id": tool_call.id,
                "content": json.dumps({
                    "status": "failed",
                    "reason": f"Execution error: {str(e)}",
                    "results": []
                }, ensure_ascii=False)
            }
    
    elif function_name in SYSTEM_TOOLS:
        # 执行系统工具
        try:
            args = json.loads(function_args)
            
            # 根据函数名动态调用，传递相应参数
            if function_name == "get_disk_usage":
                path = args.get("path", "/")
                tool_result = SYSTEM_TOOLS[function_name](path=path)
            elif function_name == "get_top_processes":
                limit = args.get("limit", 10)
                sort_by = args.get("sort_by", "cpu")
                tool_result = SYSTEM_TOOLS[function_name](limit=limit, sort_by=sort_by)
            elif function_name == "get_process_info":
                pid = args.get("pid")
                tool_result = SYSTEM_TOOLS[function_name](pid=pid)
            elif function_name == "get_docker_containers":
                limit = args.get("limit", 10)
                tool_result = SYSTEM_TOOLS[function_name](limit=limit)
            else:
                # 无参数函数
                tool_result = SYSTEM_TOOLS[function_name]()
            
            # 截断过长的工具结果
            result_json = json.dumps(tool_result, ensure_ascii=False, indent=2)
            truncated_result = _truncate_tool_content(result_json)
            
            logger.info(f"System tool execution completed: {function_name}, status={tool_result.get('status')}")
            return {
                "tool_call_id": tool_call.id,
                "content": truncated_result
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse system tool arguments: {e}")
            return {
                "tool_call_id": tool_call.id,
                "content": json.dumps({
                    "status": "failed",
                    "reason": f"Invalid arguments: {str(e)}",
                    "results": []
                }, ensure_ascii=False)
            }
        except Exception as e:
            logger.error(f"System tool execution failed: {e}", exc_info=True)
            return {
                "tool_call_id": tool_call.id,
                "content": json.dumps({
                    "status": "failed",
                    "reason": f"Execution error: {str(e)}",
                    "results": []
                }, ensure_ascii=False)
            }
    
    else:
        logger.warning(f"Unknown tool function: {function_name}")
        return {
            "tool_call_id": tool_call.id,
            "content": json.dumps({
                "status": "failed",
                    "reason": f"Unknown function: {function_name}",
                    "results": []
                }, ensure_ascii=False)
        }


def _handle_tool_calls(tool_calls: List, messages: List[Dict]) -> List[Dict]:
    """
    处理模型的工具调用请求（使用线程池并行执行）
    
    使用 ThreadPoolExecutor 并行执行多个工具调用，提高响应速度。
    所有工具调用完成后，按原始顺序将结果添加到消息历史中。
    
    Args:
        tool_calls: 模型返回的工具调用列表
        messages: 当前消息历史
    
    Returns:
        更新后的消息历史
    """
    # 将工具调用添加到消息历史
    messages.append({
        "role": "assistant",
        "tool_calls": [_tool_call_to_dict(tc) for tc in tool_calls]
    })
    
    # 使用线程池并行执行所有工具调用
    tool_results = {}
    max_workers = min(len(tool_calls), 5)  # 最多5个并发线程
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有工具调用任务
        future_to_tool_call = {
            executor.submit(_execute_single_tool, tc): tc 
            for tc in tool_calls
        }
        
        # 收集执行结果
        for future in as_completed(future_to_tool_call):
            tool_call = future_to_tool_call[future]
            try:
                result = future.result()
                tool_results[tool_call.id] = result
            except Exception as e:
                logger.error(f"Tool execution exception: {e}", exc_info=True)
                tool_results[tool_call.id] = {
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({
                        "status": "failed",
                        "reason": f"Unexpected error: {str(e)}",
                        "results": []
                    }, ensure_ascii=False)
                }
    
    # 按原始顺序添加工具响应到消息历史
    for tool_call in tool_calls:
        result = tool_results.get(tool_call.id)
        if result:
            messages.append({
                "role": "tool",
                "tool_call_id": result["tool_call_id"],
                "content": result["content"]
            })
    
    return messages


@log_openai_api_call()
def _call_llm(client, model, messages, tools, tool_choice="auto"):
    """
    调用 LLM API
    
    Args:
        client: OpenAI 客户端实例
        model: 模型名称
        messages: 消息历史列表
        tools: 可用工具列表
        tool_choice: 工具选择方式
    
    Returns:
        API 响应对象
    """
    return client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        timeout=30,
    )


def _build_messages(user_id, channel_id, bot_instance_id, prompt):
    """
    构建 LLM 对话消息历史
    
    从数据库加载最近的对话历史，并与当前用户输入组合成完整的消息列表。
    消息结构：
    1. System message: 固定的角色定义和规则（SYSTEM_PROMPT）
    2. System message: 动态的系统状态（当前时间）
    3. Historical messages: 历史对话记录
    4. User message: 当前用户问题
    
    Args:
        user_id: 用户唯一标识符
        channel_id: 频道标识符
        bot_instance_id: Bot 实例标识符
        prompt: 当前用户的问题或指令
    
    Returns:
        包含系统提示、系统状态、历史对话和当前问题的完整消息列表
    """
    # 构建消息列表：先添加固定的系统提示
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        # 注入当前系统时间作为独立的 system message（系统状态）
        {"role": "system", "content": _get_current_time_message()}
    ]

    try:
        history = get_recent_llm_messages(
            user_id,
            channel_id,
            bot_instance_id,
            limit=MEMORY_TURNS,
        )
        logger.debug(f"Loaded {len(history)} history messages for user={user_id}")
    except Exception:
        logger.warning("failed to load llm history", exc_info=True)
        history = []

    for old_prompt, old_response in history:
        if old_prompt:
            messages.append({"role": "user", "content": _trim_text(old_prompt)})
        if old_response:
            messages.append({"role": "assistant", "content": _trim_text(old_response)})

    messages.append({"role": "user", "content": prompt})
    logger.debug(f"Built messages with {len(messages)} turns for user={user_id}")
    return messages


def ask_llm(
    user_id,
    channel_id,
    bot_instance_id,
    provider_id,
    config,
    prompt,
    session_id=None,
):
    """
    向 LLM 发起对话请求并获取回复。
    Args:
        user_id: 用户 ID
        channel_id: 频道 ID
        bot_instance_id: Bot 实例 ID
        provider_id: Provider ID
        config: 配置字典
        prompt: 用户输入
        session_id: 会话 ID（用于关联同一对话的多轮调用，如未提供则自动生成）
    """
    logger.info(
        f"LLM request started: "
        f"user={user_id}, provider={provider_id}, prompt_len={len(prompt)}"
    )
    try:
        # =========================
        # 生成或验证 session_id
        # =========================
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())
        
        logger.debug(f"Session ID: {session_id}")

        # =========================
        # 读取配置
        # =========================
        api_key = _config_value(config, "api_key", "OPENAI_API_KEY")
        api_url = _config_value(config, "api_url", "OPENAI_API_URL")
        model = _config_value(
            config,
            "model",
            "OPENAI_MODEL",
            default="deepseek-v4-pro",
        )

        enabled_tools = _config_value(
            config,
            "enabled_tools",
            "ENABLED_TOOLS",
            default={"search", "system"},
        )

        if not api_key:
            logger.error("LLM Error: missing api_key")
            return "LLM Error: missing api_key"

        logger.debug(
            f"Calling LLM API: "
            f"model={model}, "
            f"base_url={_normalize_base_url(api_url)}, "
            f"enabled_tools={enabled_tools}"
        )

        # =========================
        # 初始化 OpenAI Client
        # =========================
        client = OpenAI(
            api_key=api_key,
            base_url=_normalize_base_url(api_url),
        )

        # =========================
        # 构建初始消息
        # =========================
        messages = _build_messages(
            user_id,
            channel_id,
            bot_instance_id,
            prompt,
        )

        # =========================
        # 构建工具列表
        # =========================
        tools = _build_tools_list(enabled_tools)

        # 最终结果
        result = None

        # =========================
        # 多轮 Tool Calling
        # =========================
        for round_num in range(1, MAX_TOOL_CALL_ROUNDS + 1):

            is_final_round = (
                round_num == MAX_TOOL_CALL_ROUNDS
            )

            remaining_rounds = (
                MAX_TOOL_CALL_ROUNDS - round_num
            )

            logger.info(
                f"LLM API call round "
                f"{round_num}/{MAX_TOOL_CALL_ROUNDS}"
            )

            # =========================
            # 当前轮使用的 tools 配置
            #
            # 最后一轮：
            # - 禁止工具调用
            # - 即使模型继续返回 tool_calls
            #   也绝不执行
            # =========================
            if is_final_round:
                active_tools = None
                tool_choice = "none"

                # 给模型一个“软提示”
                # 但真正的控制权在客户端
                final_instruction = {
                    "role": "system",
                    "content": (
                        "Tool call budget exhausted. You must now answer directly, using only the information already gathered, do not call tools anymore."
                    ),
                }
                request_messages = messages + [final_instruction]
            else:
                active_tools = tools
                tool_choice = "auto"
                # 告诉模型还剩多少轮
                budget_instruction = {
                    "role": "system",
                    "content": (
                        f"Tool Call Budget: "
                        f"{remaining_rounds} tool call round(s) remaining "
                        f"after this round."
                    ),
                }
                request_messages = messages + [budget_instruction]
            # =========================
            # 调用 LLM
            # =========================
            completion = _call_llm(
                client=client,
                model=model,
                messages=request_messages,
                tools=active_tools,
                tool_choice=tool_choice,
            )

            choice = completion.choices[0]
            message = choice.message

            content = (message.content or "").strip()
            tool_calls = message.tool_calls or []
            finish_reason = getattr(choice, "finish_reason", None)

            logger.info(
                "LLM Response: "
                f"finish_reason={finish_reason}, "
                f"tool_calls={len(tool_calls)}, "
                f"content_len={len(content)}"
            )

            # =========================
            # 记录每轮 LLM 调用日志（带 session_id）
            # =========================
            try:
                # 构建日志标识，区分中间调用和最终响应
                log_prefix = f"[Session:{session_id[:8]}...][Round {round_num}/{MAX_TOOL_CALL_ROUNDS}]"
                
                # 如果有工具调用，记录工具信息
                if tool_calls:
                    tool_names = [tc.function.name for tc in tool_calls]
                    log_prompt = f"{log_prefix} Tool call requested: {', '.join(tool_names)}"
                    log_response = f"{log_prefix} Executing tools..."
                elif content:
                    # 最终文本响应（有内容）
                    log_prompt = f"{log_prefix}: {prompt}"
                    log_response = content
                else:
                    # 空响应
                    log_prompt = f"{log_prefix} Empty response"
                    log_response = f"{log_prefix} No content generated"
                
                log_llm(
                    user_id,
                    channel_id,
                    bot_instance_id,
                    provider_id,
                    log_prompt,
                    log_response,
                    session_id=session_id,
                )
            except Exception:
                logger.warning(
                    f"failed to log llm round {round_num}",
                    exc_info=True,
                )

            # ==================================================
            # FINAL MODE
            #
            # 到达最大轮次后：
            # - 完全忽略 tool_calls
            # - 只接受 content
            # - 不再进行任何 Tool Calling
            #
            # 这是整个 Agent 最重要的“硬拦截”
            # ==================================================
            if is_final_round:
                if content:
                    result = content
                else:
                    # 最后一轮依然没有返回正常结果，直接返回固定内容
                    logger.warning(
                        "Final round returned empty content. "
                        "Using fallback response."
                    )
                    result = (
                        "抱歉，我暂时无法生成完整回答。\n\n"
                        "可能原因：\n"
                        "1. 模型持续请求工具调用\n"
                        "2. 模型未正确生成最终文本\n"
                        "3. 当前模型对 Tool Calling 支持不稳定\n\n"
                        "建议稍后重试或更换模型。"
                    )
                break

            # ==================================================
            # NORMAL MODE
            # ==================================================

            # 模型请求工具调用
            if tool_calls:
                logger.info(
                    f"Round {round_num}: "
                    f"executing {len(tool_calls)} tool call(s)"
                )
                messages = _handle_tool_calls(
                    tool_calls,
                    messages,
                )
                continue
            # 模型直接给出了文本回复
            if content:
                logger.info(
                    f"Round {round_num}: "
                    f"received final text response"
                )
                result = content
                break

            # 没有 tool_calls
            # 也没有 content
            logger.warning(
                f"Round {round_num}: "
                f"empty response from model"
            )
            result = "Empty response from model"
            break
        # =========================
        # 最终兜底
        # =========================
        if not result:
            result = "LLM returned no result"

        logger.info(
            f"LLM response received: "
            f"user={user_id}, "
            f"response_len={len(result)}"
        )

        # 注意：每轮 LLM 调用已在循环内部记录到数据库
        # 此处不再重复记录最终响应，避免数据冗余
        return result
    except Exception as e:
        logger.exception(
            f"llm request failed: "
            f"user={user_id}, error={e}"
        )
        return f"LLM Error: {str(e)}"