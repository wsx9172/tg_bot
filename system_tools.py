"""
系统监控工具集 - 为 AI Agent 提供系统状态查询能力
第一阶段：CPU、内存、磁盘、进程、Docker 状态
第二阶段：日志分析、网络诊断、服务状态
"""
import psutil
import subprocess
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# ==================== CPU 工具 ====================

def get_cpu_usage() -> Dict:
    """
    获取 CPU 使用率
    
    Returns:
        CPU 使用率字典
    """
    try:
        # 获取总体使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 获取每核使用率
        per_cpu = psutil.cpu_percent(interval=1, percpu=True)
        
        # 获取 CPU 频率
        freq = psutil.cpu_freq()
        
        result = {
            "status": "success",
            "tool": "cpu_usage",
            "data": {
                "total_percent": cpu_percent,
                "per_cpu_percent": per_cpu,
                "cpu_count": psutil.cpu_count(),
                "cpu_count_logical": psutil.cpu_count(logical=True),
            }
        }
        
        if freq:
            result["data"]["frequency"] = {
                "current": freq.current,
                "min": freq.min,
                "max": freq.max
            }
        
        logger.info(f"CPU usage retrieved: {cpu_percent}%")
        return result
        
    except Exception as e:
        logger.error(f"Failed to get CPU usage: {e}", exc_info=True)
        return {
            "status": "failed",
            "tool": "cpu_usage",
            "reason": str(e)
        }


# ==================== 内存工具 ====================

def get_memory_info() -> Dict:
    """
    获取内存详细信息
    
    Returns:
        内存信息字典
    """
    try:
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        result = {
            "status": "success",
            "tool": "memory_info",
            "data": {
                "virtual": {
                    "total": _format_bytes(mem.total),
                    "available": _format_bytes(mem.available),
                    "used": _format_bytes(mem.used),
                    "percent": mem.percent,
                },
                "swap": {
                    "total": _format_bytes(swap.total),
                    "used": _format_bytes(swap.used),
                    "free": _format_bytes(swap.free),
                    "percent": swap.percent,
                }
            }
        }
        
        logger.info(f"Memory info retrieved: {mem.percent}% used")
        return result
        
    except Exception as e:
        logger.error(f"Failed to get memory info: {e}", exc_info=True)
        return {
            "status": "failed",
            "tool": "memory_info",
            "reason": str(e)
        }


def get_memory_summary() -> Dict:
    """
    获取内存摘要（简化版，类似 free 命令）
    
    Returns:
        内存摘要字典
    """
    try:
        mem = psutil.virtual_memory()
        
        result = {
            "status": "success",
            "tool": "memory_summary",
            "data": {
                "total": _format_bytes(mem.total),
                "used": _format_bytes(mem.used),
                "free": _format_bytes(mem.free),
                "available": _format_bytes(mem.available),
                "usage_percent": mem.percent,
            }
        }
        
        logger.debug("Memory summary retrieved")
        return result
        
    except Exception as e:
        logger.error(f"Failed to get memory summary: {e}", exc_info=True)
        return {
            "status": "failed",
            "tool": "memory_summary",
            "reason": str(e)
        }


# ==================== 磁盘工具 ====================

def get_disk_usage(path: str = "/") -> Dict:
    """
    获取磁盘使用情况
    
    Args:
        path: 要检查的路径，默认根目录
    
    Returns:
        磁盘使用信息字典
    """
    try:
        disk = psutil.disk_usage(path)
        
        result = {
            "status": "success",
            "tool": "disk_usage",
            "data": {
                "path": path,
                "total": _format_bytes(disk.total),
                "used": _format_bytes(disk.used),
                "free": _format_bytes(disk.free),
                "percent": disk.percent,
            }
        }
        
        logger.info(f"Disk usage for {path}: {disk.percent}%")
        return result
        
    except Exception as e:
        logger.error(f"Failed to get disk usage for {path}: {e}", exc_info=True)
        return {
            "status": "failed",
            "tool": "disk_usage",
            "path": path,
            "reason": str(e)
        }


def get_disk_partitions() -> Dict:
    """
    获取所有磁盘分区信息
    
    Returns:
        分区信息列表
    """
    try:
        partitions = psutil.disk_partitions(all=False)
        partition_list = []
        
        for partition in partitions:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                partition_list.append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "total": _format_bytes(usage.total),
                    "used": _format_bytes(usage.used),
                    "free": _format_bytes(usage.free),
                    "percent": usage.percent,
                })
            except PermissionError:
                continue
        
        result = {
            "status": "success",
            "tool": "disk_partitions",
            "data": {
                "partitions": partition_list,
                "count": len(partition_list)
            }
        }
        
        logger.info(f"Disk partitions retrieved: {len(partition_list)} partitions")
        return result
        
    except Exception as e:
        logger.error(f"Failed to get disk partitions: {e}", exc_info=True)
        return {
            "status": "failed",
            "tool": "disk_partitions",
            "reason": str(e)
        }


# ==================== 进程工具 ====================

def get_top_processes(limit: int = 10, sort_by: str = "cpu") -> Dict:
    """
    获取占用资源最多的进程（替代 top 命令）
    
    Args:
        limit: 返回的进程数量，默认 10
        sort_by: 排序方式，"cpu" 或 "memory"
    
    Returns:
        进程列表
    """
    try:
        limit = max(1, min(50, limit))  # 限制范围 1-50
        
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'status']):
            try:
                pinfo = proc.as_dict(attrs=['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'status'])
                if pinfo['name']:  # 跳过空名称
                    processes.append(pinfo)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # 排序
        if sort_by == "memory":
            processes.sort(key=lambda x: x.get('memory_percent') or 0, reverse=True)
        else:  # 默认按 CPU
            processes.sort(key=lambda x: x.get('cpu_percent') or 0, reverse=True)
        
        # 取前 N 个
        top_procs = processes[:limit]
        
        result = {
            "status": "success",
            "tool": "top_processes",
            "data": {
                "sort_by": sort_by,
                "processes": top_procs,
                "total_processes": len(processes),
                "showing": len(top_procs)
            }
        }
        
        logger.info(f"Top {limit} processes by {sort_by} retrieved")
        return result
        
    except Exception as e:
        logger.error(f"Failed to get top processes: {e}", exc_info=True)
        return {
            "status": "failed",
            "tool": "top_processes",
            "reason": str(e)
        }


def get_process_info(pid: int) -> Dict:
    """
    获取指定进程的详细信息
    
    Args:
        pid: 进程 ID
    
    Returns:
        进程详细信息
    """
    try:
        proc = psutil.Process(pid)
        
        with proc.oneshot():
            info = {
                "pid": proc.pid,
                "name": proc.name(),
                "status": proc.status(),
                "username": proc.username(),
                "create_time": datetime.fromtimestamp(proc.create_time()).strftime('%Y-%m-%d %H:%M:%S'),
                "cpu_percent": proc.cpu_percent(interval=0.1),
                "memory_percent": proc.memory_percent(),
                "memory_info": _format_bytes(proc.memory_info().rss),
                "threads": proc.num_threads(),
                "open_files": len(proc.open_files()),
                "connections": len(proc.connections()),
            }
            
            # 命令行
            try:
                info["cmdline"] = " ".join(proc.cmdline())
            except:
                info["cmdline"] = ""
        
        result = {
            "status": "success",
            "tool": "process_info",
            "data": info
        }
        
        logger.info(f"Process info retrieved for PID {pid}")
        return result
        
    except psutil.NoSuchProcess:
        return {
            "status": "failed",
            "tool": "process_info",
            "pid": pid,
            "reason": f"Process {pid} not found"
        }
    except Exception as e:
        logger.error(f"Failed to get process info for PID {pid}: {e}", exc_info=True)
        return {
            "status": "failed",
            "tool": "process_info",
            "pid": pid,
            "reason": str(e)
        }


# ==================== Docker 工具 ====================

def get_docker_status() -> Dict:
    """
    获取 Docker 状态（容器数量、运行状态等）
    
    Returns:
        Docker 状态信息
    """
    try:
        # 检查 docker 命令是否可用
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return {
                "status": "failed",
                "tool": "docker_status",
                "reason": "Docker is not running or not accessible"
            }
        
        # 获取容器统计
        containers_result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        statuses = containers_result.stdout.strip().split('\n') if containers_result.stdout.strip() else []
        
        running = sum(1 for s in statuses if 'Up' in s)
        stopped = sum(1 for s in statuses if 'Exited' in s)
        total = len(statuses)
        
        result = {
            "status": "success",
            "tool": "docker_status",
            "data": {
                "total_containers": total,
                "running": running,
                "stopped": stopped,
                "paused": total - running - stopped,
            }
        }
        
        logger.info(f"Docker status retrieved: {running}/{total} running")
        return result
        
    except FileNotFoundError:
        return {
            "status": "failed",
            "tool": "docker_status",
            "reason": "Docker command not found"
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "failed",
            "tool": "docker_status",
            "reason": "Docker command timeout"
        }
    except Exception as e:
        logger.error(f"Failed to get Docker status: {e}", exc_info=True)
        return {
            "status": "failed",
            "tool": "docker_status",
            "reason": str(e)
        }


def get_docker_containers(limit: int = 10) -> Dict:
    """
    获取 Docker 容器列表
    
    Args:
        limit: 返回的容器数量
    
    Returns:
        容器列表
    """
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return {
                "status": "failed",
                "tool": "docker_containers",
                "reason": "Failed to list containers"
            }
        
        containers = []
        for line in result.stdout.strip().split('\n')[:limit]:
            if line:
                parts = line.split('\t')
                if len(parts) >= 3:
                    containers.append({
                        "id": parts[0][:12],
                        "name": parts[1],
                        "status": parts[2],
                        "ports": parts[3] if len(parts) > 3 else ""
                    })
        
        result = {
            "status": "success",
            "tool": "docker_containers",
            "data": {
                "containers": containers,
                "count": len(containers)
            }
        }
        
        logger.info(f"Docker containers retrieved: {len(containers)}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Docker containers: {e}", exc_info=True)
        return {
            "status": "failed",
            "tool": "docker_containers",
            "reason": str(e)
        }


# ==================== 辅助函数 ====================

def _format_bytes(bytes_value: int) -> str:
    """格式化字节数为可读字符串"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"


# ==================== 工具 Schema 定义 ====================

CPU_USAGE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_cpu_usage",
        "description": "获取 CPU 使用率信息，包括总体使用率、每核使用率和 CPU 频率。",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

MEMORY_INFO_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_memory_info",
        "description": "获取详细内存信息，包括虚拟内存和交换空间的使用情况。",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

MEMORY_SUMMARY_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_memory_summary",
        "description": "获取内存摘要信息（类似 free 命令）。",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

DISK_USAGE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_disk_usage",
        "description": "获取磁盘使用情况，可指定路径，默认为根目录。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要检查的路径，默认为 '/'",
                    "default": "/"
                }
            },
            "required": []
        }
    }
}

DISK_PARTITIONS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_disk_partitions",
        "description": "获取所有磁盘分区信息。",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

TOP_PROCESSES_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_top_processes",
        "description": "获取占用资源最多的进程列表（类似 top 命令），可指定数量和排序方式。",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "返回的进程数量，默认10",
                    "default": 10
                },
                "sort_by": {
                    "type": "string",
                    "description": "排序方式，'cpu' 或 'memory'，默认为 'cpu'",
                    "default": "cpu"
                }
            },
            "required": []
        }
    }
}

PROCESS_INFO_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_process_info",
        "description": "获取指定进程的详细信息。",
        "parameters": {
            "type": "object",
            "properties": {
                "pid": {
                    "type": "integer",
                    "description": "进程 ID"
                }
            },
            "required": ["pid"]
        }
    }
}

DOCKER_STATUS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_docker_status",
        "description": "获取 Docker 服务状态和容器统计信息。",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

DOCKER_CONTAINERS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_docker_containers",
        "description": "获取 Docker 容器列表。",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "返回的容器数量，默认10",
                    "default": 10
                }
            },
            "required": []
        }
    }
}

# 合并所有系统工具 schema
SYSTEM_TOOL_SCHEMAS = [
    CPU_USAGE_TOOL_SCHEMA,
    MEMORY_INFO_TOOL_SCHEMA,
    MEMORY_SUMMARY_TOOL_SCHEMA,
    DISK_USAGE_TOOL_SCHEMA,
    DISK_PARTITIONS_TOOL_SCHEMA,
    TOP_PROCESSES_TOOL_SCHEMA,
    PROCESS_INFO_TOOL_SCHEMA,
    DOCKER_STATUS_TOOL_SCHEMA,
    DOCKER_CONTAINERS_TOOL_SCHEMA,
]


# ==================== 工具注册表 ====================

SYSTEM_TOOLS = {
    "get_cpu_usage": get_cpu_usage,
    "get_memory_info": get_memory_info,
    "get_memory_summary": get_memory_summary,
    "get_disk_usage": get_disk_usage,
    "get_disk_partitions": get_disk_partitions,
    "get_top_processes": get_top_processes,
    "get_process_info": get_process_info,
    "get_docker_status": get_docker_status,
    "get_docker_containers": get_docker_containers,
}
