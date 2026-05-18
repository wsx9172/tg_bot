import psutil
import logging
from app.config import CPU_ALERT, MEM_ALERT, DISK_ALERT, NODE_ID
from app.db import log_status, log_alert

logger = logging.getLogger(__name__)


def get_system_status(log=True):
    cpu = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent

    if log:
        log_status(NODE_ID, cpu, memory, disk)
        logger.debug(f"System status: node={NODE_ID}, cpu={cpu}%, mem={memory}%, disk={disk}%")

    return cpu, memory, disk


def check_alerts():
    cpu, memory, disk = get_system_status(log=False)
    alerts = []

    if cpu > CPU_ALERT:
        msg = f"CPU high {cpu}%"
        alerts.append(msg)
        logger.warning(f"Alert triggered: {msg}")
        log_alert(NODE_ID, "critical", "cpu", msg)

    if memory > MEM_ALERT:
        msg = f"MEM high {memory}%"
        alerts.append(msg)
        logger.warning(f"Alert triggered: {msg}")
        log_alert(NODE_ID, "critical", "memory", msg)

    if disk > DISK_ALERT:
        msg = f"DISK high {disk}%"
        alerts.append(msg)
        logger.warning(f"Alert triggered: {msg}")
        log_alert(NODE_ID, "critical", "disk", msg)

    if alerts:
        logger.info(f"Total {len(alerts)} alert(s) generated")
    
    return alerts
