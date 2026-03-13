# Security Policy

## Threat Model
Peridot is a Sovereign AI Kernel designed to run strictly on local hardware. We assume the following regarding the threat landscape:
* **The Host OS is Trusted:** Peridot assumes the machine it runs on is under the user's control.
* **The User is Authorized:** The human operating the terminal is the administrator.
* **Local Processes May Be Malicious:** Other scripts, malware, or browser tabs running on the same machine may attempt to hijack the LLM or siphon GPU resources.

## Active Defenses (v1.2.2+)
Peridot employs a Defense-in-Depth architecture to protect the host machine:
1. **Air-Gapped Operation:** The server binds strictly to `127.0.0.1`. It will not accept external network traffic.
2. **Ephemeral API Authentication:** API keys are generated cryptographically in RAM (`os.environ`) at boot and evaporate on shutdown, completely mitigating CWE-312 (Clear-text storage).
3. **Application-Layer Input Sanitization:** All prompts are scrubbed for code-execution payloads (e.g., `os.system`, `<script>`) before inference.
4. **Subprocess Whitelisting:** The Medical Research (Folding@Home) WebSocket integration is hardcoded to exclusively accept `pause` and `unpause` directives.
5. **Path Traversal Blocks:** Core logic strictly prohibits reading from sensitive directories (`/etc/`, `C:\Windows\`) or accessing cryptographic material (`.ssh/`, `.env`).

## Reporting a Vulnerability
If you discover a vulnerability that allows for arbitrary code execution, VRAM hijacking, or API auth bypass, do NOT open a public GitHub issue.

Please email the vulnerability details to uncoalesced@gmail.com We will acknowledge the report within 48 hours and coordinate a patch before public disclosure.