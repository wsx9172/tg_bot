"""
搜索工具模块

提供网络搜索功能，用于 LLM Agent 获取实时信息。
"""

import logging
from typing import Dict
import requests

from app.config import SEARCH_BASE_URL, MAX_SNIPPET_LENGTH

logger = logging.getLogger(__name__)


# =========================
# 搜索工具 Schema 定义
# =========================

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


# =========================
# 辅助函数
# =========================

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


# =========================
# 搜索工具执行函数
# =========================

def web_search(query: str, num_results: int = 3) -> Dict:
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
