import psutil
from enhancedlogger import EnhancedLogger

logger = EnhancedLogger()


def get_cpu_usage():
    return psutil.cpu_percent(interval=1)


def get_ram_usage():
    mem = psutil.virtual_memory()
    return mem.percent


def log_resource_usage():
    cpu = get_cpu_usage()
    ram = get_ram_usage()
    logger.log(
        f"System resource check: CPU usage = {cpu}%, RAM usage = {ram}%", level="info"
    )
    return cpu, ram
