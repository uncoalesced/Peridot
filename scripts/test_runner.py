def run_tests():
    modules = ["permissions", "ethics", "backup", "sandbox", "enhancedlogger"]
    all_passed = True

    for module in modules:
        try:
            __import__(module)
            print(f"[✓] {module} module loaded successfully.")
        except Exception as e:
            print(f"[✗] Failed to load {module}: {str(e)}")
            all_passed = False

    return all_passed
