# diagnostics.py

import os
import sys
import platform
import time
import shutil
import importlib.util
import psutil
from pathlib import Path
from integrity_checker import run_integrity_check

REQUIRED_MODULES = ["psutil", "platform", "shutil", "time", "pathlib"]


def run_self_test(logger):
    logger.info("Running system diagnostics...", source="DIAGNOSTICS")

    try:
        results = []

        # 1. Check OS platform
        os_info = platform.platform()
        results.append(f"Platform detected: {os_info}")
        logger.info(f"[OK] Platform: {os_info}", source="DIAGNOSTICS")

        # 2. Check Python version
        python_version = sys.version
        results.append(f"Python version: {python_version}")
        logger.info(f"[OK] Python version: {python_version}", source="DIAGNOSTICS")

        # 3. Check free disk space
        total, used, free = shutil.disk_usage(os.getcwd())
        free_gb = free / (1024**3)
        results.append(f"Free disk space: {free_gb:.2f} GB")
        if free_gb < 1:
            logger.warning(
                "[WARN] Low disk space (<1GB). Consider cleaning up.",
                source="DIAGNOSTICS",
            )
        else:
            logger.info("[OK] Disk space check passed", source="DIAGNOSTICS")

        # 4. Check file write access
        try:
            test_path = Path("diagnostic_test.tmp")
            test_path.write_text("test", encoding="utf-8")
            test_path.unlink()
            logger.info("[OK] Write access check passed", source="DIAGNOSTICS")
        except Exception as e:
            logger.error(f"[FAIL] Write test failed: {str(e)}", source="DIAGNOSTICS")
            return False

        # 5. Check for PYTHONUTF8
        if os.getenv("PYTHONUTF8") != "1":
            logger.warning(
                "[WARN] PYTHONUTF8 is not enabled. Unicode characters may not display correctly.",
                source="DIAGNOSTICS",
            )
        else:
            logger.info("[OK] PYTHONUTF8 is enabled", source="DIAGNOSTICS")

        # 6. Basic performance loop
        start = time.time()
        for _ in range(1000000):
            _ = 1 + 1
        end = time.time()
        logger.info(
            f"[OK] Basic loop completed in {(end - start):.4f}s", source="DIAGNOSTICS"
        )

        # 7. RAM and CPU Usage
        ram = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=1)
        logger.info(f"[OK] RAM usage: {ram.percent:.1f}%", source="RESOURCE")
        logger.info(f"[OK] CPU usage: {cpu:.1f}%", source="RESOURCE")

        # 8. CPU temperature (where available)
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    for entry in entries:
                        logger.info(
                            f"[OK] CPU Temp ({name}): {entry.current}°C",
                            source="RESOURCE",
                        )
            else:
                logger.warning(
                    "[WARN] No CPU temperature sensors found.", source="RESOURCE"
                )
        except Exception as e:
            logger.warning(
                f"[WARN] CPU temperature check failed: {str(e)}", source="RESOURCE"
            )

        # 9. Python dependency check
        missing = []
        for module in REQUIRED_MODULES:
            if importlib.util.find_spec(module) is None:
                missing.append(module)
        if missing:
            logger.error(
                f"[FAIL] Missing Python modules: {', '.join(missing)}",
                source="DEPENDENCY",
            )
            return False
        else:
            logger.info(
                "[OK] All required Python modules are present", source="DEPENDENCY"
            )

        # 10. File Integrity
        integrity_results = run_integrity_check(logger)
        for line in integrity_results:
            logger.info(line, source="INTEGRITY")

        # Done
        logger.info(
            "All diagnostic checks completed successfully.", source="DIAGNOSTICS"
        )
        return True

    except Exception as e:
        logger.error(f"[FAIL] Self-diagnostics failed: {str(e)}", source="DIAGNOSTICS")
        return False
