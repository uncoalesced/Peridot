"""
Peridot Sovereign Kernel | Architectural Integrity Auditor
Engineered by uncoalesced.

Calculates cryptographic drift between the local runtime and the remote upstream repository.
"""

import subprocess
import sys
import os
from pathlib import Path

# Force Windows console to process ANSI escape sequences
if os.name == 'nt':
    os.system("")

# ANSI Formatting
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

def run_git_command(command, fail_silently=False):
    """Executes a git command and returns the decoded output."""
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            cwd=Path(__file__).parent.parent
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if not fail_silently:
            print(f"{RED}[ERROR] Git execution failed: {e.stderr.strip()}{RESET}")
        return None

def verify_git_environment():
    """Ensures the environment is a valid Git repository."""
    if not run_git_command(["git", "rev-parse", "--is-inside-work-tree"], fail_silently=True):
        print(f"{RED}[FATAL] Target directory is not a Git repository. Integrity check aborted.{RESET}")
        sys.exit(1)

def check_local_drift():
    """Identifies files that have been altered locally and are not committed."""
    print(f"\n{CYAN}[1/3] Scanning Local Subsystem Drift...{RESET}")
    status = run_git_command(["git", "status", "--porcelain"])
    
    if not status:
        print(f"{GREEN}[OK] Local working directory is clean. No unauthorized modifications detected.{RESET}")
        return

    print(f"{YELLOW}[WARN] Local drift detected. The following files are modified, untracked, or missing:{RESET}")
    for line in status.split('\n'):
        state = line[:2]
        file_path = line[3:]
        if 'M' in state:
            print(f"  - [MODIFIED] {file_path}")
        elif 'D' in state:
            print(f"  - [MISSING]  {file_path}")
        elif '??' in state:
            print(f"  - [UNTRACKED] {file_path}")

def check_upstream_sync():
    """Fetches remote metadata and compares HEAD to origin/main."""
    print(f"\n{CYAN}[2/3] Fetching Remote Telemetry (origin/main)...{RESET}")
    run_git_command(["git", "fetch", "origin", "main"])

    # Calculate commit differential
    local_hash = run_git_command(["git", "rev-parse", "HEAD"])
    remote_hash = run_git_command(["git", "rev-parse", "origin/main"])

    if local_hash == remote_hash:
        print(f"{GREEN}[OK] System is fully synchronized with upstream repository.{RESET}")
        return

    print(f"{YELLOW}[WARN] Architectural desynchronization detected.{RESET}")
    
    # Check if behind, ahead, or diverged
    status = run_git_command(["git", "rev-list", "--left-right", "--count", "HEAD...origin/main"])
    ahead = 0
    behind = 0
    if status:
        ahead, behind = status.split()
        ahead = int(ahead)
        behind = int(behind)
        if behind > 0:
            print(f"  - [OUTDATED] System is behind by {behind} commits. Update required.")
        if ahead > 0:
            print(f"  - [AHEAD] System contains {ahead} unpublished local commits.")

    # Show exactly which files changed remotely
    if behind > 0:
        print(f"\n{CYAN}[3/3] Pending Upstream Updates:{RESET}")
        diff = run_git_command(["git", "diff", "--name-status", "HEAD..origin/main"])
        for line in diff.split('\n'):
            if line:
                action, file = line.split('\t', 1)
                action_str = "UPDATED" if action == 'M' else "ADDED" if action == 'A' else "DELETED"
                print(f"  - [{action_str}] {file}")

def main():
    print(f"{CYAN}===================================================={RESET}")
    print(f"{CYAN} PERIDOT KERNEL INTEGRITY AUDITOR{RESET}")
    print(f"{CYAN}===================================================={RESET}")
    
    verify_git_environment()
    check_local_drift()
    check_upstream_sync()
    
    print(f"\n{CYAN}===================================================={RESET}")
    print(f"{CYAN} AUDIT COMPLETE.{RESET}")

if __name__ == "__main__":
    main()