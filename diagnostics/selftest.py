import importlib
import psutil
import platform
import shutil
import time

REQUIRED_MODULES = [
    "permissions",
    "ethics",
    "backup",
    "sandbox",
    "enhancedlogger",
    "command_router",
    "core",
    "main",
]


def run_self_test(logger=None):
    """
    Minimal startup self-test. Checks that critical modules can be imported.
    """
    try:
        for module in REQUIRED_MODULES:
            importlib.import_module(module)
        if logger:
            logger.info("Minimal self-diagnostic passed.", source="SELFTEST")
        return True
    except Exception as e:
        if logger:
            logger.error(f"Minimal self-diagnostic failed: {str(e)}", source="SELFTEST")
        return False


def run_self_tests(command_router=None, input_dir=None, logger=None):
    """
    Runs a full suite of self-tests and returns a list of result strings.
    """
    results = []

    def log_and_append(message, level="info"):
        """Helper to log and add to results simultaneously."""
        results.append(message)
        if logger:
            log_func = getattr(logger, level, logger.info)
            log_func(message, source="SELFTEST")

    log_and_append("[SELFTEST] Starting full self-test suite...")

    # 1. Module Import Checks
    log_and_append("[CHECK] Verifying required modules...")
    for module in REQUIRED_MODULES:
        try:
            importlib.import_module(module)
            log_and_append(f"[✓] Module loaded: {module}", level="debug")
        except Exception as e:
            log_and_append(
                f"[✗] Failed to load module {module}: {str(e)}", level="error"
            )

    # 2. Ethics & Rule Check
    log_and_append("[CHECK] Testing ethics permission logic...")
    try:
        from ethics import EthicsManager

        ethics = EthicsManager()
        if ethics.is_allowed("shutdown"):
            log_and_append("[✓] Rule check: 'shutdown' accepted as expected.")
        else:
            log_and_append(
                "[✗] Rule check: 'shutdown' was denied unexpectedly.", level="warning"
            )
    except Exception as e:
        log_and_append(f"[✗] Ethics system test failed: {str(e)}", level="error")

    # 3. CPU & RAM Usage
    log_and_append("[CHECK] Collecting system diagnostics...")
    try:
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        results.append(f"[✓] CPU Usage: {cpu}%")
        results.append(f"[✓] RAM Usage: {mem.percent}%")
    except Exception as e:
        log_and_append(f"[✗] System resource check failed: {str(e)}", level="error")

    # 4. Platform Summary
    log_and_append("[INFO] Platform: " + platform.platform())

    # 5. Command Router Smoke Test
    if command_router:
        log_and_append("[CHECK] Testing command routing...")
        try:
            # We know the 'status' command exists and takes no arguments.
            response = command_router.route_command("status")
            if "running" in str(response).lower():
                log_and_append("[✓] Command routing functional.")
            else:
                log_and_append(
                    f"[✗] Command router returned unexpected result: {response}",
                    level="warning",
                )
        except Exception as e:
            log_and_append(f"[✗] Command router test failed: {str(e)}", level="error")

    log_and_append("[SELFTEST] Self-test completed.")
    return results
