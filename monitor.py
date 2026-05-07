import psutil
from config import CPU_ALERT, MEM_ALERT, DISK_ALERT, NODE_ID
from db import log_status, log_alert


def get_system_status(log=True):
    cpu = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent

    if log:
        log_status(NODE_ID, cpu, memory, disk)

    return cpu, memory, disk


def check_alerts():
    cpu, memory, disk = get_system_status(log=False)

    alerts = []

    if cpu > CPU_ALERT:
        msg = f"CPU high {cpu}%"
        alerts.append(msg)
        log_alert(NODE_ID, "critical", "cpu", msg)

    if memory > MEM_ALERT:
        msg = f"MEM high {memory}%"
        alerts.append(msg)
        log_alert(NODE_ID, "critical", "memory", msg)

    if disk > DISK_ALERT:
        msg = f"DISK high {disk}%"
        alerts.append(msg)
        log_alert(NODE_ID, "critical", "disk", msg)

    return alerts
