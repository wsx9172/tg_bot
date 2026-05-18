"""
LLM 工具模块包

提供 LLM Agent 可用的各种工具定义和执行函数。

导出分类：
1. 工具集合（推荐）：SYSTEM_TOOLS, SYSTEM_TOOL_SCHEMAS
2. 搜索工具：SEARCH_TOOL_SCHEMA, web_search
3. 独立诊断函数（高级用法）：get_system_health_summary 等
"""

# ==================== 搜索工具 ====================
from app.tools.search_tools import SEARCH_TOOL_SCHEMA, web_search

# ==================== 系统工具集合（推荐使用）====================
from app.tools.system_tools import (
    SYSTEM_TOOLS,           # 工具注册表字典 {name: function}
    SYSTEM_TOOL_SCHEMAS,    # 工具 Schema 列表（用于构建 tools 参数）
)

# ==================== 独立诊断函数（可选，高级用法）====================
# 注意：通常不需要直接导入这些函数，通过 SYSTEM_TOOLS 调用即可
# 仅在需要单独测试或直接调用时才使用
from app.tools.system_tools import (
    get_system_health_summary,
    get_system_info,
    get_io_stats,
    get_load_average,
    get_network_connections,
    get_network_interfaces,
    get_directory_size,
    get_large_files,
    get_docker_container_details,
    get_systemd_service_status,
    read_log_tail,
    get_journalctl_logs,
)

__all__ = [
    # 搜索工具
    "SEARCH_TOOL_SCHEMA",
    "web_search",

    # 系统工具集合（主要接口）
    "SYSTEM_TOOLS",
    "SYSTEM_TOOL_SCHEMAS",

    # 独立诊断函数（高级用法，可选）
    "get_system_health_summary",
    "get_system_info",
    "get_io_stats",
    "get_load_average",
    "get_network_connections",
    "get_network_interfaces",
    "get_directory_size",
    "get_large_files",
    "get_docker_container_details",
    "get_systemd_service_status",
    "read_log_tail",
    "get_journalctl_logs",
]