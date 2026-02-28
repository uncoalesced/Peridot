import os

input_path = r"D:\iCould\input"
os.makedirs(input_path, exist_ok=True)

tasks = {
    "status.task": "status",
    "diagnostic.task": "run_diagnostic",
    "log_summary.task": "summarize_log",
    "json_summary.task": "summarize_json",
    "restart.task": "restart",
    "shutdown.task": "shutdown",
    "what_is_icould.task": "what is icould",
    "invalid.task": "foobar_command",  # Test how system handles unknown command
}

for filename, content in tasks.items():
    file_path = os.path.join(input_path, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

print("Test .task files created in input folder.")
