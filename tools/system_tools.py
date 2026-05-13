"""
系统监控工具集 - 为 AI Agent 提供系统状态查询能力
第一阶段：CPU、内存、磁盘、进程、Docker 状态
第二阶段：日志分析、网络诊断、服务状态
"""
import psutil
import subprocess
import logging
from typing import Dict, List
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


# ==================== 新增诊断工具 ====================

def get_system_health_summary() -> Dict:
    """
    【用途】系统健康快速诊断，一次性获取核心指标
    【适用场景】
    - 服务器卡顿排查
    - 日常健康检查
    - AI 快速判断系统状态
    - 避免多次工具调用导致的循环
    
    【返回信息用途】
    - CPU/内存/负载综合评估
    - Top 3 异常进程定位
    - Docker 服务状态确认
    
    【优先级】⭐⭐⭐⭐⭐ 推荐作为第一诊断工具
    """
    try:
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 内存摘要
        mem = psutil.virtual_memory()
        mem_percent = mem.percent
        mem_used_gb = mem.used / (1024**3)
        mem_total_gb = mem.total / (1024**3)
        
        # 系统负载
        load_avg = psutil.getloadavg()
        
        # Top 3 进程（按 CPU）
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                pinfo = proc.info
                if pinfo['cpu_percent'] is not None and pinfo['cpu_percent'] > 0:
                    processes.append(pinfo)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
        top_3 = [
            {
                "pid": p['pid'],
                "name": p['name'],
                "cpu_percent": round(p['cpu_percent'], 1),
                "memory_percent": round(p['memory_percent'], 1) if p['memory_percent'] else 0
            }
            for p in processes[:3]
        ]
        
        # Docker 状态
        docker_status = "unknown"
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=5
            )
            docker_status = "running" if result.returncode == 0 else "stopped"
        except:
            docker_status = "not_installed"
        
        # 异常检测
        anomalies = []
        if cpu_percent > 80:
            anomalies.append(f"CPU 使用率过高: {cpu_percent}%")
        if mem_percent > 85:
            anomalies.append(f"内存使用率过高: {mem_percent}%")
        if load_avg[0] > psutil.cpu_count():
            anomalies.append(f"系统负载过高: {load_avg[0]:.2f} (CPU数: {psutil.cpu_count()})")
        
        health_score = 100
        if cpu_percent > 80:
            health_score -= 30
        elif cpu_percent > 60:
            health_score -= 10
        
        if mem_percent > 85:
            health_score -= 30
        elif mem_percent > 70:
            health_score -= 10
        
        if load_avg[0] > psutil.cpu_count() * 1.5:
            health_score -= 20
        elif load_avg[0] > psutil.cpu_count():
            health_score -= 10
        
        health_score = max(0, health_score)
        
        result = {
            "status": "success",
            "tool": "system_health_summary",
            "data": {
                "health_score": health_score,
                "health_level": "healthy" if health_score >= 80 else ("warning" if health_score >= 50 else "critical"),
                "cpu": {
                    "usage_percent": cpu_percent
                },
                "memory": {
                    "usage_percent": mem_percent,
                    "used_gb": round(mem_used_gb, 2),
                    "total_gb": round(mem_total_gb, 2)
                },
                "load_average": {
                    "load1": round(load_avg[0], 2),
                    "load5": round(load_avg[1], 2),
                    "load15": round(load_avg[2], 2),
                    "cpu_count": psutil.cpu_count()
                },
                "top_processes": top_3,
                "docker_status": docker_status,
                "anomalies": anomalies
            }
        }
        
        logger.info(f"System health summary generated: score={health_score}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to get system health summary: {e}", exc_info=True)
        return {
            "status": "failed",
            "tool": "system_health_summary",
            "reason": str(e)
        }


def get_io_stats() -> Dict:
    """
    【用途】磁盘 I/O 性能诊断，检测 IO wait 瓶颈
    【适用场景】
    - 服务器响应慢但 CPU 不高
    - 数据库查询缓慢
    - 文件读写性能问题
    - 判断是否 IO wait 导致系统卡顿
    
    【返回信息用途】
    - 识别磁盘读写瓶颈
    - 计算 IO wait 占比
    - 定位高 IOPS 设备
    
    【关键指标】
    - read/write throughput (MB/s)
    - IOPS (每秒操作次数)
    - await (平均等待时间 ms)
    """
    try:
        # 磁盘 I/O 统计
        io_counters = psutil.disk_io_counters(perdisk=True)
        
        disk_stats = {}
        for disk_name, counters in io_counters.items():
            read_mb = counters.read_bytes / (1024**2)
            write_mb = counters.write_bytes / (1024**2)
            
            disk_stats[disk_name] = {
                "read_bytes_mb": round(read_mb, 2),
                "write_bytes_mb": round(write_mb, 2),
                "read_count": counters.read_count,
                "write_count": counters.write_count,
                "read_time_ms": counters.read_time,
                "write_time_ms": counters.write_time,
                "busy_time_ms": counters.busy_time
            }
        
        # 总体统计
        total_io = psutil.disk_io_counters()
        total_read_mb = total_io.read_bytes / (1024**2) if total_io else 0
        total_write_mb = total_io.write_bytes / (1024**2) if total_io else 0
        
        result = {
            "status": "success",
            "tool": "io_stats",
            "data": {
                "total": {
                    "read_mb": round(total_read_mb, 2),
                    "write_mb": round(total_write_mb, 2),
                    "read_count": total_io.read_count if total_io else 0,
                    "write_count": total_io.write_count if total_io else 0
                },
                "per_disk": disk_stats
            }
        }
        
        logger.info(f"IO stats retrieved for {len(disk_stats)} disks")
        return result
        
    except Exception as e:
        logger.error(f"Failed to get IO stats: {e}", exc_info=True)
        return {
            "status": "failed",
            "tool": "io_stats",
            "reason": str(e)
        }


def get_load_average() -> Dict:
    """
    【用途】系统负载分析，判断系统整体压力
    【适用场景】
    - 判断系统是否过载
    - 长期性能趋势分析
    - 容量规划参考
    
    【返回信息用途】
    - load1/load5/load15 对比 CPU 核心数
    - 判断短期/中期/长期负载趋势
    - 识别负载突增或持续高压
    
    【诊断规则】
    - load > CPU数 × 1.5: 严重过载
    - load > CPU数: 轻度过载
    - load < CPU数 × 0.7: 健康
    """
    try:
        load_avg = psutil.getloadavg()
        cpu_count = psutil.cpu_count()
        
        # 计算负载比例
        load_ratios = {
            "load1_ratio": round(load_avg[0] / cpu_count, 2),
            "load5_ratio": round(load_avg[1] / cpu_count, 2),
            "load15_ratio": round(load_avg[2] / cpu_count, 2)
        }
        
        # 负载评估
        if load_avg[0] > cpu_count * 1.5:
            status = "critical"
            message = f"系统严重过载！当前负载 {load_avg[0]:.2f} 远超 CPU 核心数 {cpu_count}"
        elif load_avg[0] > cpu_count:
            status = "warning"
            message = f"系统轻度过载，负载 {load_avg[0]:.2f} 超过 CPU 核心数 {cpu_count}"
        elif load_avg[0] < cpu_count * 0.7:
            status = "healthy"
            message = f"系统负载正常 ({load_avg[0]:.2f}/{cpu_count})"
        else:
            status = "normal"
            message = f"系统负载适中 ({load_avg[0]:.2f}/{cpu_count})"
        
        result = {
            "status": "success",
            "tool": "load_average",
            "data": {
                "load_average": {
                    "load1": round(load_avg[0], 2),
                    "load5": round(load_avg[1], 2),
                    "load15": round(load_avg[2], 2)
                },
                "cpu_count": cpu_count,
                "ratios": load_ratios,
                "assessment": {
                    "status": status,
                    "message": message
                }
            }
        }
        
        logger.info(f"Load average retrieved: {load_avg[0]:.2f}/{cpu_count}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to get load average: {e}", exc_info=True)
        return {
            "status": "failed",
            "tool": "load_average",
            "reason": str(e)
        }


def get_docker_container_details(container_id_or_name: str) -> Dict:
    """
    【用途】Docker 容器深度诊断，获取详细资源使用和日志
    【适用场景】
    - 容器异常退出排查
    - 容器资源争抢分析
    - 容器健康检查失败调查
    - 需要查看容器日志
    
    【返回信息用途】
    - 容器 CPU/MEM 精确使用量
    - 重启次数（判断稳定性）
    - 健康检查状态
    - 最近日志（定位错误原因）
    
    【重要提示】仅在已知具体容器 ID 或名称时使用
    """
    try:
        # 获取容器详细信息
        cmd_inspect = f"docker inspect {container_id_or_name}"
        result_inspect = subprocess.run(
            cmd_inspect.split(),
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result_inspect.returncode != 0:
            return {
                "status": "failed",
                "tool": "docker_container_details",
                "reason": f"Container '{container_id_or_name}' not found or docker command failed"
            }
        
        import json
        inspect_data = json.loads(result_inspect.stdout)[0]
        
        # 获取容器统计信息
        cmd_stats = f"docker stats {container_id_or_name} --no-stream --format '{{{{.CPUPerc}}}}|{{{{.MemUsage}}}}|{{{{.MemPerc}}}}'"
        result_stats = subprocess.run(
            cmd_stats.split(),
            capture_output=True,
            text=True,
            timeout=10
        )
        
        cpu_percent = "N/A"
        mem_usage = "N/A"
        mem_percent = "N/A"
        
        if result_stats.returncode == 0:
            parts = result_stats.stdout.strip().split('|')
            if len(parts) >= 3:
                cpu_percent = parts[0]
                mem_usage = parts[1]
                mem_percent = parts[2]
        
        # 获取最近日志
        cmd_logs = f"docker logs --tail 20 {container_id_or_name}"
        result_logs = subprocess.run(
            cmd_logs.split(),
            capture_output=True,
            text=True,
            timeout=10
        )
        
        logs = result_logs.stdout[-1000:] if result_logs.stdout else ""  # 限制日志长度
        
        # 提取关键信息
        state = inspect_data.get('State', {})
        host_config = inspect_data.get('HostConfig', {})
        
        container_info = {
            "id": inspect_data.get('Id', '')[:12],
            "name": inspect_data.get('Name', '').lstrip('/'),
            "status": state.get('Status', 'unknown'),
            "created": state.get('StartedAt', 'N/A'),
            "restart_count": state.get('RestartCount', 0),
            "exit_code": state.get('ExitCode', 'N/A'),
            "health": state.get('Health', {}).get('Status', 'N/A'),
            "resources": {
                "cpu_percent": cpu_percent,
                "memory_usage": mem_usage,
                "memory_percent": mem_percent,
                "memory_limit": host_config.get('Memory', 0)
            },
            "recent_logs": logs
        }
        
        result = {
            "status": "success",
            "tool": "docker_container_details",
            "data": container_info
        }
        
        logger.info(f"Docker container details retrieved: {container_id_or_name}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Docker container details: {e}", exc_info=True)
        return {
            "status": "failed",
            "tool": "docker_container_details",
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
        "description": """【用途】系统性能诊断，判断CPU是否存在瓶颈或异常负载

【适用场景】
- 服务器卡顿排查
- 容器CPU争抢分析
- 高负载问题定位
- 单核打满检测

【返回信息用途】
- 总体CPU使用率：判断整体压力
- 每核使用率：识别单核瓶颈
- CPU频率：确认降频/睿频状态

【建议】配合 get_system_health_summary 使用，快速定位问题""",
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
        "description": """【用途】详细内存分析，用于排查内存泄漏和swap异常

【适用场景】
- 内存泄漏深度排查
- Swap交换空间异常分析
- 缓存/缓冲占用过高调查
- OOM (Out of Memory) 问题诊断

【返回信息用途】
- 虚拟内存详细信息：total/used/free/available
- 交换空间状态：是否频繁swap导致性能下降
- 缓存/缓冲占比：判断是否可回收

【注意】日常监控建议使用 get_memory_summary，此工具用于深度分析""",
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
        "description": """【用途】快速内存概览，用于健康检查和AI摘要

【适用场景】
- 日常健康检查
- AI快速判断内存状态
- 内存告警触发
- 避免多次工具调用

【返回信息用途】
- 类似 free 命令的简洁输出
- 内存使用百分比
- 可用内存估算

【优先级】⭐⭐⭐⭐ 推荐作为第一内存诊断工具""",
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
        "description": """【用途】磁盘空间使用诊断，判断存储是否充足

【适用场景】
- 磁盘空间告警
- 日志文件膨胀排查
- Docker镜像/容器占用分析
- 分区容量规划

【返回信息用途】
- 指定路径的总容量/已用/可用
- 使用百分比
- inode使用情况

【建议】默认检查根目录 '/'，如需检查特定路径请传入 path 参数""",
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
        "description": """【用途】获取所有磁盘分区布局和挂载信息

【适用场景】
- 多磁盘环境容量分配分析
- 挂载点配置验证
- LVM/RAID结构查看
- 新磁盘识别

【返回信息用途】
- 所有分区的设备名、挂载点、文件系统类型
- 各分区容量和使用情况

【注意】日常诊断较少使用，主要用于复杂存储环境分析""",
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
        "description": """【用途】获取资源占用最高的进程列表，定位异常进程

【适用场景】
- CPU飙高时定位元凶进程
- 内存泄漏进程识别
- 僵尸进程检测
- 资源争抢分析

【返回信息用途】
- 按CPU或内存排序的进程列表
- 每个进程的PID、名称、资源占用百分比
- 为后续 get_process_info 提供目标PID

【重要提示】
- 默认返回Top 10进程，可按需调整limit
- 发现异常进程后，可使用 get_process_info(pid=X) 深入分析
- 不要直接对PID=1调用get_process_info（无意义）""",
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
        "description": """【用途】获取指定进程的详细信息，用于深度分析

【适用场景】
- 仅在 get_top_processes 已定位异常进程后使用
- 用户明确要求分析某个特定PID
- 需要查看进程的线程数、打开文件数、启动时间等详细信息

【返回信息用途】
- 进程完整命令行
- 内存RSS/VSS详细数据
- 线程数、文件描述符数
- 进程启动时间和运行时长

【重要约束】
⚠️ 禁止直接对PID=1调用（init/systemd进程，无诊断价值）
⚠️ 必须先通过 top_processes 定位目标，或使用明确指定的PID
⚠️ 不要盲目遍历所有进程""",
        "parameters": {
            "type": "object",
            "properties": {
                "pid": {
                    "type": "integer",
                    "description": "进程 ID（必须是具体有意义的PID，不能是1）"
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
        "description": """【用途】Docker服务健康检查，快速判断容器整体状态

【适用场景】
- 判断容器是否异常退出或资源紧张
- 快速评估服务健康状态
- Docker守护进程可用性检查
- 容器数量统计

【返回信息用途】
- Docker服务是否运行
- 运行中/停止/暂停的容器数量
- 总容器数和镜像数
- 适合AI快速判断是否需要进一步调查

【优先级】⭐⭐⭐⭐ 推荐作为Docker问题的第一诊断工具""",
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
        "description": """【用途】获取Docker容器列表和基本信息

【适用场景】
- 查看所有容器运行状态
- 识别异常退出的容器
- 端口映射冲突排查
- 容器命名规范检查

【返回信息用途】
- 容器ID、名称、状态、端口映射
- 帮助定位具体需要深入分析的容器

【后续操作】发现异常容器后，使用 get_docker_container_details(container_id) 获取详细信息和日志""",
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

# 新增工具 Schema
SYSTEM_HEALTH_SUMMARY_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_system_health_summary",
        "description": """【用途】系统健康快速诊断，一次性获取核心指标（强烈推荐）

【适用场景】
- 服务器卡顿初步排查
- 日常健康检查
- AI快速判断系统状态
- 避免多次工具调用导致的循环

【返回信息用途】
- CPU/内存/负载综合评估
- Top 3异常进程自动定位
- Docker服务状态确认
- 健康评分（0-100）和异常告警

【优先级】⭐⭐⭐⭐⭐ 推荐作为第一诊断工具，80%的问题可通过此工具定位

【关键优势】一次调用替代多次单独查询，显著降低Tool Loop风险""",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

IO_STATS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_io_stats",
        "description": """【用途】磁盘I/O性能诊断，检测IO wait瓶颈

【适用场景】
- 服务器响应慢但CPU不高（疑似IO wait）
- 数据库查询缓慢
- 文件读写性能问题
- 判断是否磁盘瓶颈导致系统卡顿

【返回信息用途】
- 磁盘读写吞吐量（MB/s）
- IOPS（每秒操作次数）
- 平均等待时间（await ms）
- 每块磁盘的详细统计

【关键价值】解决"CPU 72%但不知原因"的问题，识别真正的IO wait瓶颈""",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

LOAD_AVERAGE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_load_average",
        "description": """【用途】系统负载分析，判断系统整体压力（Linux核心指标）

【适用场景】
- 判断系统是否过载
- 长期性能趋势分析
- 容量规划参考
- 负载突增或持续高压识别

【返回信息用途】
- load1/load5/load15 三维度负载
- 负载与CPU核心数对比
- 自动评估系统状态（healthy/warning/critical）

【诊断规则】
- load > CPU数 × 1.5: 严重过载
- load > CPU数: 轻度过载  
- load < CPU数 × 0.7: 健康

【重要性】这是Linux系统诊断的核心指标，必须掌握""",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

DOCKER_CONTAINER_DETAILS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_docker_container_details",
        "description": """【用途】Docker容器深度诊断，获取详细资源使用和日志

【适用场景】
- 容器异常退出排查
- 容器资源争抢分析
- 容器健康检查失败调查
- 需要查看容器最近日志

【返回信息用途】
- 容器CPU/MEM精确使用量
- 重启次数（判断稳定性）
- 健康检查状态
- 最近20行日志（定位错误原因）
- 退出码和启动时间

【重要约束】
⚠️ 仅在已知具体容器ID或名称时使用
⚠️ 先通过 get_docker_containers 或 get_docker_status 定位目标容器
⚠️ 不要盲目遍历所有容器""",
        "parameters": {
            "type": "object",
            "properties": {
                "container_id_or_name": {
                    "type": "string",
                    "description": "容器ID或名称（必须先通过其他工具定位）"
                }
            },
            "required": ["container_id_or_name"]
        }
    }
}

# 合并所有系统工具 schema
SYSTEM_TOOL_SCHEMAS = [
    SYSTEM_HEALTH_SUMMARY_TOOL_SCHEMA,  # ⭐ 优先推荐
    CPU_USAGE_TOOL_SCHEMA,
    MEMORY_SUMMARY_TOOL_SCHEMA,
    MEMORY_INFO_TOOL_SCHEMA,
    LOAD_AVERAGE_TOOL_SCHEMA,
    IO_STATS_TOOL_SCHEMA,
    DISK_USAGE_TOOL_SCHEMA,
    DISK_PARTITIONS_TOOL_SCHEMA,
    TOP_PROCESSES_TOOL_SCHEMA,
    PROCESS_INFO_TOOL_SCHEMA,
    DOCKER_STATUS_TOOL_SCHEMA,
    DOCKER_CONTAINERS_TOOL_SCHEMA,
    DOCKER_CONTAINER_DETAILS_TOOL_SCHEMA,
]

# ==================== 工具注册表 ====================

SYSTEM_TOOLS = {
    # ⭐ 核心诊断工具（优先推荐）
    "get_system_health_summary": get_system_health_summary,
    
    # CPU/内存/负载
    "get_cpu_usage": get_cpu_usage,
    "get_memory_summary": get_memory_summary,
    "get_memory_info": get_memory_info,
    "get_load_average": get_load_average,
    
    # I/O 诊断
    "get_io_stats": get_io_stats,
    
    # 磁盘
    "get_disk_usage": get_disk_usage,
    "get_disk_partitions": get_disk_partitions,
    
    # 进程
    "get_top_processes": get_top_processes,
    "get_process_info": get_process_info,
    
    # Docker
    "get_docker_status": get_docker_status,
    "get_docker_containers": get_docker_containers,
    "get_docker_container_details": get_docker_container_details,
}
