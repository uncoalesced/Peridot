import threading
import psutil
import time
from enhancedlogger import EnhancedLogger

logger = EnhancedLogger()
refresh_interval = 10  # seconds


def monitor_resources(stop_event):
    while not stop_event.is_set():
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        logger.info(f"CPU usage: {cpu:.1f}% | RAM usage: {ram:.1f}%", source="RESOURCE")
        print(f">iCould: CPU: {cpu:.1f}% | RAM: {ram:.1f}%")
        time.sleep(refresh_interval)
