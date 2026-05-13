<div align="center">

# PERIDOT KERNEL | SECURITY POLICY

### Threat Model & Defense Architecture — v1.4.0-stable

*Defense-in-Depth. Local-First. Air-Gapped by Design.*

</div>

---

# `> THREAT MODEL`

Peridot is a sovereign AI kernel engineered to operate strictly on local hardware.

The architecture assumes the following threat landscape:

---

## The Host OS Is Trusted

Peridot assumes the physical machine and operating system remain under the direct control of the operator.

The kernel is designed for:
- local execution
- local administration
- local authority

without dependence on remote infrastructure.

---

## The User Is Sovereign

The human operating the terminal is considered the administrator.

Peridot does not impose:
- remote policy enforcement
- hidden moderation layers
- cloud-managed restrictions
- external execution control

The operator retains authority over runtime behavior.

---

## Local Processes May Be Malicious

Peridot assumes other local processes may attempt to:
- hijack the inference API
- siphon VRAM resources
- exfiltrate contextual memory
- abuse subprocess execution
- interfere with runtime orchestration

This includes:
- compromised browser tabs
- malware
- unauthorized scripts
- hostile local applications

The security architecture is engineered accordingly.

---

# `> ACTIVE DEFENSES`

## v1.3.2-beta

Peridot implements a strict defense-in-depth architecture designed to protect:
- host hardware
- local inference execution
- runtime integrity
- contextual privacy

---

## Air-Gapped Operation

The inference server binds exclusively to:

```text
127.0.0.1
```

External network traffic is not accepted.

The runtime is intentionally isolated from public network exposure.

---

## Sovereign Telemetry Suppression

Global environment variables:

```text
HF_HUB_OFFLINE
TRANSFORMERS_OFFLINE
```

force external libraries into offline operation.

This architecture:
- suppresses upstream telemetry
- blocks silent synchronization
- prevents remote model fetches
- enforces deterministic local execution

The runtime does not phone home.

---

## Cryptographic Handshake Authentication

Peridot uses a localized, untracked:

```text
.env
```

configuration for API authentication.

The Neural Engine:

```text
server.py
```

returns:

```text
403 FORBIDDEN
```

for any request lacking the required:

```text
Authorization: Bearer
```

authentication header.

No unauthenticated internal or external request is permitted to access inference execution.

---

## Zero Disk-Footprint Memory Layer

The primary:

```text
l1_cache
```

operates entirely within volatile ephemeral RAM.

Contextual memory is not serialized to disk unless explicitly routed into the encrypted Vector Store architecture.

The runtime prioritizes:
- transient memory handling
- reduced forensic residue
- minimal persistent exposure

during standard operation.

---

## Application-Layer Input Sanitization

All prompts are sanitized through:

```text
core_system/security.py
```

before inference execution begins.

Sanitization routines scan for:
- shell injection payloads
- arbitrary code execution attempts
- subprocess abuse
- unsafe execution directives

including patterns such as:

```python
os.system()
```

and related execution vectors.

---

## Subprocess Whitelisting

The Folding@Home WebSocket integration operates under strict directive whitelisting.

The Medical Research subsystem only accepts approved JSON state directives:

```text
pause
fold
```

No arbitrary subprocess execution is permitted through the research orchestration layer.

---

## Path Traversal Protection

Core routing logic explicitly blocks access to:
- sensitive operating system directories
- protected system paths
- cryptographic material
- privileged runtime locations

Examples include:

```text
/etc/
C:\Windows\
```

Path traversal attempts are rejected before filesystem interaction occurs.

---

# `> REPORTING A VULNERABILITY`

If you discover vulnerabilities involving:
- arbitrary code execution
- VRAM hijacking
- authentication bypass
- unauthorized API access
- telemetry leakage
- sandbox escape
- privilege escalation

do **NOT** open a public GitHub issue.

Instead, report the vulnerability privately to:

```text
uncoalesced@gmail.com
```

Include:
- reproduction steps
- affected subsystem
- proof-of-concept details
- environment information where applicable

The uncoalesced collective will:
- acknowledge reports within 48 hours
- validate findings
- coordinate remediation
- prepare patches before public disclosure

Responsible disclosure is expected.

---

<div align="center">

`PERIDOT SECURITY POLICY` · `v1.3.2-beta`

**Engineered by uncoalesced**

*Air-Gapped Execution.*  
*Defense-in-Depth Security.*  
*Local Sovereignty.*

</div>