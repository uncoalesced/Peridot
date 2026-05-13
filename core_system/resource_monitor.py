# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

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
