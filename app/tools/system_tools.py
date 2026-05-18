"""
系统监控工具集 - 为 AI Agent 提供系统状态查询能力
第一阶段：CPU、内存、磁盘、进程、Docker 状态
第二阶段：日志分析、网络诊断、服务状态
第三阶段：文件系统、systemd 管理、系统信息
"""
import json
import logging
import os
import platform
import subprocess
import psutil
from datetime import datetime
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


# ==================== CPU 工具 ====================

def get_cpu_usage() -> Dict:
    """获取 CPU 使用率"""
    try:
        per_cpu = psutil.cpu_percent(interval=0.5, percpu=True)
        cpu_percent = round(sum(per_cpu) / len(per_cpu), 1) if per_cpu else 0
        freq = psutil.cpu_freq()

        result = {
            "status": "success",
            "tool": "cpu_usage",
            "data": {
                "total_percent": cpu_percent,
                "per_cpu_percent": [round(x, 1) for x in per_cpu],
                "cpu_count": psutil.cpu_count(),
                "cpu_count_logical": psutil.cpu_count(logical=True),
            }
        }

        if freq:
            result["data"]["frequency"] = {
                "current": round(freq.current, 1),
                "min": round(freq.min, 1) if freq.min else None,
                "max": round(freq.max, 1) if freq.max else None,
            }

        logger.info(f"CPU usage retrieved: {cpu_percent}%")
        return result

    except Exception as e:
        logger.error(f"Failed to get CPU usage: {e}", exc_info=True)
        return {"status": "failed", "tool": "cpu_usage", "reason": str(e)}


# ==================== 内存工具 ====================

def get_memory_info() -> Dict:
    """获取内存详细信息（含 swap）"""
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
                    "free": _format_bytes(mem.free),
                    "percent": mem.percent,
                    "buffers": _format_bytes(getattr(mem, 'buffers', 0)),
                    "cached": _format_bytes(getattr(mem, 'cached', 0)),
                },
                "swap": {
                    "total": _format_bytes(swap.total),
                    "used": _format_bytes(swap.used),
                    "free": _format_bytes(swap.free),
                    "percent": swap.percent,
                    "sin": _format_bytes(getattr(swap, 'sin', 0)),
                    "sout": _format_bytes(getattr(swap, 'sout', 0)),
                }
            }
        }

        logger.info(f"Memory info retrieved: {mem.percent}% used")
        return result

    except Exception as e:
        logger.error(f"Failed to get memory info: {e}", exc_info=True)
        return {"status": "failed", "tool": "memory_info", "reason": str(e)}


def get_memory_summary() -> Dict:
    """获取内存摘要（简化版）"""
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
        return {"status": "failed", "tool": "memory_summary", "reason": str(e)}


# ==================== 磁盘工具 ====================

def get_disk_usage(path: str = "/") -> Dict:
    """获取指定路径的磁盘使用情况"""
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
        return {"status": "failed", "tool": "disk_usage", "path": path, "reason": str(e)}


def get_disk_partitions() -> Dict:
    """获取所有磁盘分区信息"""
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
            "data": {"partitions": partition_list, "count": len(partition_list)}
        }
        logger.info(f"Disk partitions retrieved: {len(partition_list)} partitions")
        return result
    except Exception as e:
        logger.error(f"Failed to get disk partitions: {e}", exc_info=True)
        return {"status": "failed", "tool": "disk_partitions", "reason": str(e)}


# ==================== 进程工具 ====================

def get_top_processes(limit: int = 10, sort_by: str = "cpu") -> Dict:
    """获取占用资源最多的进程"""
    try:
        limit = max(1, min(50, limit))
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'status']):
            try:
                pinfo = proc.as_dict(attrs=['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'status'])
                if pinfo['name']:
                    processes.append(pinfo)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        key = 'memory_percent' if sort_by == "memory" else 'cpu_percent'
        processes.sort(key=lambda x: x.get(key) or 0, reverse=True)
        top_procs = processes[:limit]

        result = {
            "status": "success",
            "tool": "top_processes",
            "data": {
                "sort_by": sort_by,
                "processes": top_procs,
                "total_processes": len(processes),
                "showing": len(top_procs),
            }
        }
        logger.info(f"Top {limit} processes by {sort_by} retrieved")
        return result
    except Exception as e:
        logger.error(f"Failed to get top processes: {e}", exc_info=True)
        return {"status": "failed", "tool": "top_processes", "reason": str(e)}


def get_process_info(pid: int) -> Dict:
    """获取指定进程的详细信息"""
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
                "memory_percent": round(proc.memory_percent(), 2),
                "memory_rss": _format_bytes(proc.memory_info().rss),
                "memory_vms": _format_bytes(proc.memory_info().vms),
                "threads": proc.num_threads(),
                "open_files": len(proc.open_files()),
                "connections": len(proc.net_connections()),
            }
            try:
                info["cmdline"] = " ".join(proc.cmdline())
            except Exception:
                info["cmdline"] = ""

        logger.info(f"Process info retrieved for PID {pid}")
        return {"status": "success", "tool": "process_info", "data": info}

    except psutil.NoSuchProcess:
        return {"status": "failed", "tool": "process_info", "pid": pid, "reason": f"Process {pid} not found"}
    except Exception as e:
        logger.error(f"Failed to get process info for PID {pid}: {e}", exc_info=True)
        return {"status": "failed", "tool": "process_info", "pid": pid, "reason": str(e)}


# ==================== Docker 工具 ====================

def _run_docker(args: list, timeout: int = 10) -> subprocess.CompletedProcess:
    """安全执行 docker 命令，统一超时和错误处理"""
    return subprocess.run(
        ["docker"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def get_docker_status() -> Dict:
    """获取 Docker 服务运行状态和容器统计"""
    try:
        result = _run_docker(["info"], timeout=5)
        if result.returncode != 0:
            return {"status": "failed", "tool": "docker_status", "reason": "Docker is not running or not accessible"}

        containers_result = _run_docker(["ps", "-a", "--format", "{{.Status}}"], timeout=5)
        statuses = [s for s in containers_result.stdout.strip().split('\n') if s]

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
        return {"status": "failed", "tool": "docker_status", "reason": "Docker command not found"}
    except subprocess.TimeoutExpired:
        return {"status": "failed", "tool": "docker_status", "reason": "Docker command timeout"}
    except Exception as e:
        logger.error(f"Failed to get Docker status: {e}", exc_info=True)
        return {"status": "failed", "tool": "docker_status", "reason": str(e)}


def get_docker_containers(limit: int = 10) -> Dict:
    """获取 Docker 容器列表"""
    try:
        result = _run_docker(
            ["ps", "-a", "--format", "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}"],
            timeout=5,
        )
        if result.returncode != 0:
            return {"status": "failed", "tool": "docker_containers", "reason": "Failed to list containers"}

        containers = []
        for line in result.stdout.strip().split('\n')[:limit]:
            if line:
                parts = line.split('\t')
                if len(parts) >= 3:
                    containers.append({
                        "id": parts[0][:12],
                        "name": parts[1],
                        "status": parts[2],
                        "ports": parts[3] if len(parts) > 3 else "",
                    })

        logger.info(f"Docker containers retrieved: {len(containers)}")
        return {"status": "success", "tool": "docker_containers", "data": {"containers": containers, "count": len(containers)}}

    except Exception as e:
        logger.error(f"Failed to get Docker containers: {e}", exc_info=True)
        return {"status": "failed", "tool": "docker_containers", "reason": str(e)}


def get_docker_container_details(container_id_or_name: str) -> Dict:
    """获取 Docker 容器详细信息（资源使用、重启次数、最近日志）"""
    try:
        inspect_result = _run_docker(["inspect", container_id_or_name], timeout=10)
        if inspect_result.returncode != 0:
            return {
                "status": "failed",
                "tool": "docker_container_details",
                "reason": f"Container '{container_id_or_name}' not found or docker command failed",
            }

        inspect_data = json.loads(inspect_result.stdout)[0]

        # 获取容器资源统计
        stats_result = _run_docker(
            ["stats", container_id_or_name, "--no-stream", "--format",
             "{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}"],
            timeout=10,
        )
        cpu_percent = "N/A"
        mem_usage = "N/A"
        mem_percent = "N/A"
        if stats_result.returncode == 0 and stats_result.stdout.strip():
            parts = stats_result.stdout.strip().split('|')
            if len(parts) >= 3:
                cpu_percent = parts[0]
                mem_usage = parts[1]
                mem_percent = parts[2]

        # 获取最近日志
        logs_result = _run_docker(["logs", "--tail", "20", container_id_or_name], timeout=10)
        logs = logs_result.stdout[-1000:] if logs_result.stdout else ""

        state = inspect_data.get('State', {})
        host_config = inspect_data.get('HostConfig', {})

        container_info = {
            "id": inspect_data.get('Id', '')[:12],
            "name": inspect_data.get('Name', '').lstrip('/'),
            "status": state.get('Status', 'unknown'),
            "started_at": state.get('StartedAt', 'N/A'),
            "restart_count": state.get('RestartCount', 0),
            "exit_code": state.get('ExitCode', 'N/A'),
            "health": state.get('Health', {}).get('Status', 'N/A'),
            "resources": {
                "cpu_percent": cpu_percent,
                "memory_usage": mem_usage,
                "memory_percent": mem_percent,
                "memory_limit": host_config.get('Memory', 0),
            },
            "recent_logs": logs,
        }

        logger.info(f"Docker container details retrieved: {container_id_or_name}")
        return {"status": "success", "tool": "docker_container_details", "data": container_info}

    except Exception as e:
        logger.error(f"Failed to get Docker container details: {e}", exc_info=True)
        return {"status": "failed", "tool": "docker_container_details", "reason": str(e)}


# ==================== 系统健康诊断 ====================

def get_system_health_summary() -> Dict:
    """系统健康快速诊断，一次性获取所有核心指标（推荐第一调用）"""
    try:
        per_cpu = psutil.cpu_percent(interval=0.5, percpu=True)
        cpu_percent = round(sum(per_cpu) / len(per_cpu), 1) if per_cpu else 0

        mem = psutil.virtual_memory()
        mem_percent = mem.percent
        mem_used_gb = mem.used / (1024 ** 3)
        mem_total_gb = mem.total / (1024 ** 3)

        load_avg = psutil.getloadavg()

        # Top 3 进程
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
            {"pid": p['pid'], "name": p['name'],
             "cpu_percent": round(p['cpu_percent'], 1),
             "memory_percent": round(p['memory_percent'] or 0, 1)}
            for p in processes[:3]
        ]

        # Docker 状态
        docker_status = "unknown"
        try:
            dr = _run_docker(["info"], timeout=5)
            docker_status = "running" if dr.returncode == 0 else "stopped"
        except Exception:
            docker_status = "not_installed"

        # 异常检测
        anomalies = []
        if cpu_percent > 80:
            anomalies.append(f"CPU 使用率过高: {cpu_percent}%")
        if mem_percent > 85:
            anomalies.append(f"内存使用率过高: {mem_percent}%")
        if load_avg[0] > psutil.cpu_count():
            anomalies.append(f"系统负载过高: {load_avg[0]:.2f} (CPU数: {psutil.cpu_count()})")

        # 健康评分
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
                "cpu": {"usage_percent": cpu_percent},
                "memory": {"usage_percent": mem_percent, "used_gb": round(mem_used_gb, 2), "total_gb": round(mem_total_gb, 2)},
                "load_average": {
                    "load1": round(load_avg[0], 2), "load5": round(load_avg[1], 2), "load15": round(load_avg[2], 2),
                    "cpu_count": psutil.cpu_count(),
                },
                "top_processes": top_3,
                "docker_status": docker_status,
                "anomalies": anomalies,
            }
        }
        logger.info(f"System health summary generated: score={health_score}")
        return result

    except Exception as e:
        logger.error(f"Failed to get system health summary: {e}", exc_info=True)
        return {"status": "failed", "tool": "system_health_summary", "reason": str(e)}


def get_io_stats() -> Dict:
    """磁盘 I/O 性能诊断"""
    try:
        io_counters = psutil.disk_io_counters(perdisk=True)
        disk_stats = {}
        for disk_name, counters in io_counters.items():
            disk_stats[disk_name] = {
                "read_bytes_mb": round(counters.read_bytes / (1024 ** 2), 2),
                "write_bytes_mb": round(counters.write_bytes / (1024 ** 2), 2),
                "read_count": counters.read_count,
                "write_count": counters.write_count,
                "read_time_ms": counters.read_time,
                "write_time_ms": counters.write_time,
                "busy_time_ms": counters.busy_time,
            }

        total_io = psutil.disk_io_counters()
        result = {
            "status": "success",
            "tool": "io_stats",
            "data": {
                "total": {
                    "read_mb": round(total_io.read_bytes / (1024 ** 2), 2) if total_io else 0,
                    "write_mb": round(total_io.write_bytes / (1024 ** 2), 2) if total_io else 0,
                    "read_count": total_io.read_count if total_io else 0,
                    "write_count": total_io.write_count if total_io else 0,
                },
                "per_disk": disk_stats,
            }
        }
        logger.info(f"IO stats retrieved for {len(disk_stats)} disks")
        return result
    except Exception as e:
        logger.error(f"Failed to get IO stats: {e}", exc_info=True)
        return {"status": "failed", "tool": "io_stats", "reason": str(e)}


def get_load_average() -> Dict:
    """系统负载分析"""
    try:
        load_avg = psutil.getloadavg()
        cpu_count = psutil.cpu_count()

        ratios = {
            "load1_ratio": round(load_avg[0] / cpu_count, 2),
            "load5_ratio": round(load_avg[1] / cpu_count, 2),
            "load15_ratio": round(load_avg[2] / cpu_count, 2),
        }

        if load_avg[0] > cpu_count * 1.5:
            status, message = "critical", f"系统严重过载！当前负载 {load_avg[0]:.2f} 远超 CPU 核心数 {cpu_count}"
        elif load_avg[0] > cpu_count:
            status, message = "warning", f"系统轻度过载，负载 {load_avg[0]:.2f} 超过 CPU 核心数 {cpu_count}"
        elif load_avg[0] < cpu_count * 0.7:
            status, message = "healthy", f"系统负载正常 ({load_avg[0]:.2f}/{cpu_count})"
        else:
            status, message = "normal", f"系统负载适中 ({load_avg[0]:.2f}/{cpu_count})"

        result = {
            "status": "success",
            "tool": "load_average",
            "data": {
                "load_average": {"load1": round(load_avg[0], 2), "load5": round(load_avg[1], 2), "load15": round(load_avg[2], 2)},
                "cpu_count": cpu_count,
                "ratios": ratios,
                "assessment": {"status": status, "message": message},
            }
        }
        logger.info(f"Load average retrieved: {load_avg[0]:.2f}/{cpu_count}")
        return result
    except Exception as e:
        logger.error(f"Failed to get load average: {e}", exc_info=True)
        return {"status": "failed", "tool": "load_average", "reason": str(e)}


# ==================== 网络诊断工具 ====================

def get_network_connections(state: str = "all") -> Dict:
    """获取网络连接列表（类似 ss/netstat）

    Args:
        state: 连接状态过滤 — "listening", "established", "all"
    """
    try:
        raw_connections = psutil.net_connections(kind='inet')

        state_filter = state.lower()
        connections = []
        for conn in raw_connections:
            if state_filter == "listening" and conn.status != "LISTEN":
                continue
            if state_filter == "established" and conn.status != "ESTABLISHED":
                continue

            connections.append({
                "proto": "tcp" if conn.type.name == "SOCK_STREAM" else "udp",
                "local": f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "",
                "remote": f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "*:*",
                "status": conn.status,
                "pid": conn.pid,
            })

        # 统计
        listening = sum(1 for c in connections if c["status"] == "LISTEN")
        established = sum(1 for c in connections if c["status"] == "ESTABLISHED")

        result = {
            "status": "success",
            "tool": "network_connections",
            "data": {
                "connections": connections[:50],
                "total": len(connections),
                "listening": listening,
                "established": established,
                "filter": state_filter,
            }
        }
        logger.info(f"Network connections retrieved: {len(connections)} (filter={state_filter})")
        return result
    except Exception as e:
        logger.error(f"Failed to get network connections: {e}", exc_info=True)
        return {"status": "failed", "tool": "network_connections", "reason": str(e)}


def get_network_interfaces() -> Dict:
    """获取网卡信息（IP 地址、流量统计）"""
    try:
        addresses = psutil.net_if_addrs()
        io_counters = psutil.net_io_counters(pernic=True)

        interfaces = {}
        for iface_name, addrs in addresses.items():
            iface_info = {"addresses": [], "io_stats": {}}
            for addr in addrs:
                iface_info["addresses"].append({
                    "family": str(addr.family),
                    "address": addr.address,
                    "netmask": addr.netmask or "",
                    "broadcast": addr.broadcast or "",
                })

            if iface_name in io_counters:
                io = io_counters[iface_name]
                iface_info["io_stats"] = {
                    "sent_mb": round(io.bytes_sent / (1024 ** 2), 2),
                    "received_mb": round(io.bytes_recv / (1024 ** 2), 2),
                    "packets_sent": io.packets_sent,
                    "packets_recv": io.packets_recv,
                    "errors_in": io.errin,
                    "errors_out": io.errout,
                    "dropped_in": io.dropin,
                    "dropped_out": io.dropout,
                }

            interfaces[iface_name] = iface_info

        result = {
            "status": "success",
            "tool": "network_interfaces",
            "data": {"interfaces": interfaces, "count": len(interfaces)}
        }
        logger.info(f"Network interfaces retrieved: {len(interfaces)} interfaces")
        return result
    except Exception as e:
        logger.error(f"Failed to get network interfaces: {e}", exc_info=True)
        return {"status": "failed", "tool": "network_interfaces", "reason": str(e)}


# ==================== 系统信息工具 ====================

def get_system_info() -> Dict:
    """获取系统基本信息（内核、OS、主机名、运行时间）"""
    try:
        uname = platform.uname()
        boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime('%Y-%m-%d %H:%M:%S')

        uptime_seconds = psutil.boot_time()
        now = datetime.now().timestamp()
        uptime_delta = now - uptime_seconds
        days = int(uptime_delta // 86400)
        hours = int((uptime_delta % 86400) // 3600)
        minutes = int((uptime_delta % 3600) // 60)

        distro = ""
        try:
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release") as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME="):
                            distro = line.split("=", 1)[1].strip().strip('"')
                            break
        except Exception:
            pass

        result = {
            "status": "success",
            "tool": "system_info",
            "data": {
                "hostname": uname.node,
                "kernel": uname.release,
                "kernel_version": uname.version,
                "arch": uname.machine,
                "os": uname.system,
                "distro": distro,
                "boot_time": boot_time,
                "uptime": f"{days}d {hours}h {minutes}m",
                "uptime_seconds": int(uptime_delta),
                "python_version": platform.python_version(),
            }
        }
        logger.info(f"System info retrieved: {uname.node} ({uname.release})")
        return result
    except Exception as e:
        logger.error(f"Failed to get system info: {e}", exc_info=True)
        return {"status": "failed", "tool": "system_info", "reason": str(e)}


# ==================== systemd 服务工具 ====================

def get_systemd_service_status(service_name: str = "", state: str = "") -> Dict:
    """查询 systemd 服务状态

    Args:
        service_name: 服务名称（为空则列出所有 service 单元）
        state: 状态过滤 — "active", "failed", "inactive", ""=全部
    """
    try:
        if service_name:
            # 查询单个服务
            cmd = ["systemctl", "status", service_name, "--no-pager", "-l"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            # 即使用 exit code 非 0，stdout 通常也包含有用信息
            output = result.stdout[:2000]

            # 提取关键行
            active_line = ""
            loaded_line = ""
            for line in output.split('\n'):
                stripped = line.strip()
                if stripped.startswith("Active:"):
                    active_line = stripped
                elif stripped.startswith("Loaded:"):
                    loaded_line = stripped

            return {
                "status": "success",
                "tool": "systemd_service_status",
                "data": {
                    "service_name": service_name,
                    "loaded": loaded_line,
                    "active": active_line,
                    "is_active": "active (running)" in output or "active (exited)" in output,
                    "raw_output": output[-1500:],
                }
            }
        else:
            # 列出所有 service 单元
            cmd = ["systemctl", "list-units", "--type=service", "--no-pager", "--no-legend"]
            if state:
                cmd += ["--state=" + state]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            services = []
            for line in result.stdout.strip().split('\n')[:30]:
                parts = line.split()
                if len(parts) >= 4:
                    services.append({
                        "name": parts[0],
                        "load": parts[1],
                        "active": parts[2],
                        "sub": parts[3],
                        "description": " ".join(parts[4:]) if len(parts) > 4 else "",
                    })

            result_data = {
                "status": "success",
                "tool": "systemd_service_status",
                "data": {
                    "services": services,
                    "count": len(services),
                    "state_filter": state or "all",
                }
            }
            logger.info(f"Systemd services retrieved: {len(services)} services")
            return result_data

    except FileNotFoundError:
        return {"status": "failed", "tool": "systemd_service_status", "reason": "systemctl command not found (not a systemd system?)"}
    except subprocess.TimeoutExpired:
        return {"status": "failed", "tool": "systemd_service_status", "reason": "systemctl command timeout"}
    except Exception as e:
        logger.error(f"Failed to get systemd service status: {e}", exc_info=True)
        return {"status": "failed", "tool": "systemd_service_status", "reason": str(e)}


# ==================== 文件系统工具 ====================

def get_directory_size(path: str, max_depth: int = 2) -> Dict:
    """计算目录大小（类似 du -sh）

    Args:
        path: 目标路径
        max_depth: 递归深度，默认 2（防止遍历过深）
    """
    try:
        target = Path(path)
        if not target.exists():
            return {"status": "failed", "tool": "directory_size", "reason": f"Path not found: {path}"}

        max_depth = max(1, min(5, max_depth))

        def _dir_size(p: Path, depth: int) -> dict:
            result = {"path": str(p), "size_bytes": 0, "children": []}
            try:
                for child in p.iterdir():
                    if child.is_file():
                        try:
                            size = child.stat().st_size
                            result["size_bytes"] += size
                        except OSError:
                            pass
                    elif child.is_dir() and not child.is_symlink() and depth < max_depth:
                        child_info = _dir_size(child, depth + 1)
                        result["size_bytes"] += child_info["size_bytes"]
                        result["children"].append(child_info)
            except PermissionError:
                pass

            result["size_human"] = _format_bytes(result["size_bytes"])
            result["children"].sort(key=lambda x: x["size_bytes"], reverse=True)
            result["children"] = result["children"][:20]
            return result

        tree = _dir_size(target, 0)
        tree["max_depth"] = max_depth

        logger.info(f"Directory size calculated for {path}: {tree['size_human']}")
        return {"status": "success", "tool": "directory_size", "data": tree}

    except Exception as e:
        logger.error(f"Failed to get directory size: {e}", exc_info=True)
        return {"status": "failed", "tool": "directory_size", "reason": str(e)}


def get_large_files(path: str, limit: int = 20) -> Dict:
    """查找目录下最大的文件

    Args:
        path: 搜索路径
        limit: 返回文件数量
    """
    try:
        target = Path(path)
        if not target.exists():
            return {"status": "failed", "tool": "large_files", "reason": f"Path not found: {path}"}

        limit = max(1, min(100, limit))
        large_files = []

        for dirpath, dirnames, filenames in os.walk(str(target)):
            # 跳过虚拟文件系统
            dirnames[:] = [d for d in dirnames if not d.startswith('.') and d not in ('/proc', '/sys', '/dev')]
            if '/proc' in dirpath or '/sys' in dirpath or '/dev' in dirpath:
                continue

            for fname in filenames:
                try:
                    fpath = os.path.join(dirpath, fname)
                    size = os.path.getsize(fpath)
                    if size > 10 * 1024 * 1024:  # 只记录 > 10MB 的文件
                        large_files.append({"path": fpath, "size_bytes": size, "size_human": _format_bytes(size)})
                except OSError:
                    continue

            if len(large_files) > limit * 5:
                break

        large_files.sort(key=lambda x: x["size_bytes"], reverse=True)
        result = {
            "status": "success",
            "tool": "large_files",
            "data": {
                "files": large_files[:limit],
                "count": len(large_files[:limit]),
                "search_path": path,
            }
        }
        logger.info(f"Large files found: {len(large_files[:limit])} files in {path}")
        return result
    except Exception as e:
        logger.error(f"Failed to find large files: {e}", exc_info=True)
        return {"status": "failed", "tool": "large_files", "reason": str(e)}


# ==================== 日志工具 ====================

def read_log_tail(file_path: str, lines: int = 50, grep_pattern: str = "") -> Dict:
    """读取日志文件的最后 N 行

    Args:
        file_path: 日志文件路径
        lines: 读取行数（默认 50，最大 200）
        grep_pattern: 可选的过滤关键词
    """
    try:
        target = Path(file_path)
        if not target.exists():
            return {"status": "failed", "tool": "read_log_tail", "reason": f"File not found: {file_path}"}
        if not target.is_file():
            return {"status": "failed", "tool": "read_log_tail", "reason": f"Not a regular file: {file_path}"}

        lines = max(1, min(200, lines))

        with open(target, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
            tail_lines = all_lines[-lines:]

        if grep_pattern:
            tail_lines = [l for l in tail_lines if grep_pattern.lower() in l.lower()]

        content = "".join(tail_lines)

        result = {
            "status": "success",
            "tool": "read_log_tail",
            "data": {
                "file_path": file_path,
                "total_lines_in_file": len(all_lines),
                "returned_lines": len(tail_lines),
                "grep_pattern": grep_pattern or None,
                "content": content[:3000],
            }
        }
        logger.info(f"Log tail read: {file_path} ({len(tail_lines)} lines)")
        return result
    except Exception as e:
        logger.error(f"Failed to read log tail: {e}", exc_info=True)
        return {"status": "failed", "tool": "read_log_tail", "reason": str(e)}


def get_journalctl_logs(unit: str, lines: int = 50, since: str = "") -> Dict:
    """查询 systemd journal 日志

    Args:
        unit: systemd 单元名称（如 "bot.service", "nginx.service"）
        lines: 返回行数（默认 50，最大 200）
        since: 时间范围（如 "10min ago", "1 hour ago", "today"），空=不限制
    """
    try:
        lines = max(1, min(200, lines))
        cmd = ["journalctl", "-u", unit, "--no-pager", "-n", str(lines)]
        if since:
            cmd += ["--since", since]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            return {"status": "failed", "tool": "journalctl_logs", "reason": result.stderr.strip() or "journalctl command failed"}

        output = result.stdout[-3000:]

        return {
            "status": "success",
            "tool": "journalctl_logs",
            "data": {
                "unit": unit,
                "lines": lines,
                "since": since or None,
                "content": output,
            }
        }
    except FileNotFoundError:
        return {"status": "failed", "tool": "journalctl_logs", "reason": "journalctl command not found (not a systemd system?)"}
    except subprocess.TimeoutExpired:
        return {"status": "failed", "tool": "journalctl_logs", "reason": "journalctl command timeout"}
    except Exception as e:
        logger.error(f"Failed to get journalctl logs: {e}", exc_info=True)
        return {"status": "failed", "tool": "journalctl_logs", "reason": str(e)}


# ==================== 辅助函数 ====================

def _format_bytes(bytes_value: int) -> str:
    """格式化字节数为可读字符串"""
    if bytes_value < 0:
        return "0 B"
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
        "description": "获取 CPU 使用率，返回总体/每核使用率及频率信息。用于 CPU 瓶颈排查、单核打满检测。",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }
}

MEMORY_INFO_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_memory_info",
        "description": "详细内存分析（含 swap、buffers/cache），用于 OOM 排查、swap 异常诊断、内存泄漏调查。日常监控建议用 get_memory_summary。",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }
}

MEMORY_SUMMARY_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_memory_summary",
        "description": "快速内存概览（类似 free -h），返回 total/used/free/available 及使用百分比。推荐作为第一内存诊断工具。",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }
}

DISK_USAGE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_disk_usage",
        "description": "获取指定路径的磁盘使用情况。默认检查根目录 /，可传入 path 参数检查特定挂载点。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要检查的路径，默认为 /"}
            },
            "required": []
        }
    }
}

DISK_PARTITIONS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_disk_partitions",
        "description": "获取所有磁盘分区布局和挂载信息（设备、挂载点、文件系统类型、容量使用）。用于多磁盘环境容量分析。",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }
}

TOP_PROCESSES_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_top_processes",
        "description": "获取 CPU 或内存占用最高的进程列表（类似 top）。默认返回 Top 10，可调整 limit 和 sort_by。发现异常进程后使用 get_process_info 深入分析。",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "返回的进程数量，默认 10，最大 50"},
                "sort_by": {"type": "string", "description": "排序方式：'cpu' 或 'memory'，默认 'cpu'"}
            },
            "required": []
        }
    }
}

PROCESS_INFO_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_process_info",
        "description": "获取指定 PID 的进程详细信息（命令行、内存 RSS/VMS、线程数、打开文件数、网络连接数）。必须先通过 get_top_processes 定位目标 PID，不要对 PID=1 调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "pid": {"type": "integer", "description": "进程 ID（不能是 1）"}
            },
            "required": ["pid"]
        }
    }
}

DOCKER_STATUS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_docker_status",
        "description": "Docker 服务健康检查，返回运行中/停止/暂停的容器数量统计。推荐作为 Docker 问题的第一诊断工具。",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }
}

DOCKER_CONTAINERS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_docker_containers",
        "description": "获取 Docker 容器列表（ID、名称、状态、端口映射）。发现异常容器后使用 get_docker_container_details 获取详细信息和日志。",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "返回的容器数量，默认 10"}
            },
            "required": []
        }
    }
}

SYSTEM_HEALTH_SUMMARY_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_system_health_summary",
        "description": "系统健康快速诊断 ⭐ 一次调用获取 CPU/内存/负载/Top3进程/Docker状态/健康评分/异常告警。80% 的运维问题可通过此工具定位，强烈推荐作为第一个调用的诊断工具。",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }
}

IO_STATS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_io_stats",
        "description": "磁盘 I/O 性能诊断，返回每块磁盘的读写吞吐量(MB/s)、IOPS、读写耗时。用于排查 CPU 不高但响应慢的 IO wait 瓶颈。",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }
}

LOAD_AVERAGE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_load_average",
        "description": "系统负载分析，返回 load1/load5/load15 及与 CPU 核心数对比，自动评估系统过载状态（healthy/warning/critical）。Linux 核心运维指标。",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }
}

DOCKER_CONTAINER_DETAILS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_docker_container_details",
        "description": "Docker 容器深度诊断：CPU/MEM 精确使用量、重启次数、健康检查状态、退出码、最近 20 行日志。必须先通过 get_docker_containers 定位目标容器。",
        "parameters": {
            "type": "object",
            "properties": {
                "container_id_or_name": {"type": "string", "description": "容器 ID 或名称（必须先通过其他工具定位）"}
            },
            "required": ["container_id_or_name"]
        }
    }
}

# ==================== 新增工具 Schema ====================

NETWORK_CONNECTIONS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_network_connections",
        "description": "获取网络连接列表（类似 ss -tunlp），返回监听端口、已建立连接及其关联进程 PID。用于端口占用排查、异常连接检测、服务监听确认。",
        "parameters": {
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "description": "连接状态过滤：'listening'（仅监听端口）、'established'（仅已建立连接）、'all'（全部），默认 'all'"
                }
            },
            "required": []
        }
    }
}

NETWORK_INTERFACES_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_network_interfaces",
        "description": "获取所有网卡信息：IP 地址、子网掩码、MAC 地址、收发流量统计(MB)、错误/丢包计数。用于网络故障排查和流量分析。",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }
}

SYSTEM_INFO_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_system_info",
        "description": "获取系统基本信息：主机名、内核版本、OS 发行版、架构、启动时间、运行时长。每次会话建议先调用此工具了解环境上下文。",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }
}

SYSTEMD_SERVICE_STATUS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_systemd_service_status",
        "description": "查询 systemd 服务状态。不传 service_name 则列出所有 service 单元；传入 service_name 则查询单个服务的 Active/Loaded 状态和最近日志。用于服务故障排查和状态确认。",
        "parameters": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "服务名称（如 'bot.service', 'nginx.service'），为空则列出全部"},
                "state": {"type": "string", "description": "状态过滤：'active', 'failed', 'inactive'，仅列出全部时生效"}
            },
            "required": []
        }
    }
}

DIRECTORY_SIZE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_directory_size",
        "description": "计算目录大小（类似 du -sh），递归显示子目录大小并排序。用于磁盘空间占用排查，定位哪些目录消耗了最多空间。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "目标路径（必填）"},
                "max_depth": {"type": "integer", "description": "递归深度，默认 2，最大 5。值越大越慢"}
            },
            "required": ["path"]
        }
    }
}

LARGE_FILES_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_large_files",
        "description": "查找目录下最大的文件（>10MB），按大小降序排列。用于快速定位占用磁盘空间的大文件（日志、备份、core dump 等）。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "搜索路径（必填）"},
                "limit": {"type": "integer", "description": "返回文件数量，默认 20，最大 100"}
            },
            "required": ["path"]
        }
    }
}

READ_LOG_TAIL_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_log_tail",
        "description": "读取日志文件最后 N 行，支持关键词过滤（类似 tail -N | grep）。用于查看应用日志、错误日志、访问日志等。",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "日志文件路径（必填）"},
                "lines": {"type": "integer", "description": "读取行数，默认 50，最大 200"},
                "grep_pattern": {"type": "string", "description": "可选过滤关键词（不区分大小写）"}
            },
            "required": ["file_path"]
        }
    }
}

JOURNALCTL_LOGS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_journalctl_logs",
        "description": "查询 systemd journal 日志，按 unit 和时间范围过滤。用于排查 systemd 服务（如 bot.service, nginx.service）的运行日志和启动失败原因。",
        "parameters": {
            "type": "object",
            "properties": {
                "unit": {"type": "string", "description": "systemd 单元名称（必填，如 'bot.service', 'nginx.service'）"},
                "lines": {"type": "integer", "description": "返回行数，默认 50，最大 200"},
                "since": {"type": "string", "description": "时间范围，如 '10min ago', '1 hour ago', 'today', 'yesterday'"}
            },
            "required": ["unit"]
        }
    }
}

# ==================== 合并所有工具 Schema ====================

SYSTEM_TOOL_SCHEMAS = [
    SYSTEM_HEALTH_SUMMARY_TOOL_SCHEMA,
    SYSTEM_INFO_TOOL_SCHEMA,
    CPU_USAGE_TOOL_SCHEMA,
    MEMORY_SUMMARY_TOOL_SCHEMA,
    MEMORY_INFO_TOOL_SCHEMA,
    LOAD_AVERAGE_TOOL_SCHEMA,
    IO_STATS_TOOL_SCHEMA,
    DISK_USAGE_TOOL_SCHEMA,
    DISK_PARTITIONS_TOOL_SCHEMA,
    DIRECTORY_SIZE_TOOL_SCHEMA,
    LARGE_FILES_TOOL_SCHEMA,
    TOP_PROCESSES_TOOL_SCHEMA,
    PROCESS_INFO_TOOL_SCHEMA,
    NETWORK_CONNECTIONS_TOOL_SCHEMA,
    NETWORK_INTERFACES_TOOL_SCHEMA,
    DOCKER_STATUS_TOOL_SCHEMA,
    DOCKER_CONTAINERS_TOOL_SCHEMA,
    DOCKER_CONTAINER_DETAILS_TOOL_SCHEMA,
    SYSTEMD_SERVICE_STATUS_TOOL_SCHEMA,
    READ_LOG_TAIL_TOOL_SCHEMA,
    JOURNALCTL_LOGS_TOOL_SCHEMA,
]

# ==================== 工具注册表 ====================

SYSTEM_TOOLS = {
    # 系统健康（优先推荐）
    "get_system_health_summary": get_system_health_summary,
    "get_system_info": get_system_info,

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
    "get_directory_size": get_directory_size,
    "get_large_files": get_large_files,

    # 进程
    "get_top_processes": get_top_processes,
    "get_process_info": get_process_info,

    # 网络
    "get_network_connections": get_network_connections,
    "get_network_interfaces": get_network_interfaces,

    # Docker
    "get_docker_status": get_docker_status,
    "get_docker_containers": get_docker_containers,
    "get_docker_container_details": get_docker_container_details,

    # systemd
    "get_systemd_service_status": get_systemd_service_status,

    # 日志
    "read_log_tail": read_log_tail,
    "get_journalctl_logs": get_journalctl_logs,
}
