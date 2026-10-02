# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.6.0 | EXTENSION SLASH COMMANDS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Client-side routing for /skills, /plugins and /<skill> before a prompt is sent.

route(text) -> ("local", output) | ("prompt", prompt_text) | ("passthrough", text)
"""

from core_system.extensions import registry


def _errors(reg, kind):
    return [f"  skipped {e}" for e in reg.errors if e.startswith(kind + "/")]


def _list_skills():
    reg = registry.scan()
    lines = [f"{s.name} — {s.description}" for s in reg.skills.values()]
    if not lines:
        lines = [f"No skills installed. Add {registry.EXTENSIONS_DIR / 'skills' / '<name>' / 'SKILL.md'}"]
    return "\n".join(["SKILLS:", *lines, *_errors(reg, "skills")])


def _list_plugins():
    reg = registry.scan()
    lines = []
    for p in reg.plugins.values():
        state = "approved" if p.approved else "NOT approved"
        net = "on" if p.permissions["network"] else "off"
        tools = ", ".join(t["name"] for t in p.tools)
        lines.append(f"{p.name} v{p.version} [{state}] — {p.description} "
                     f"(network: {net}, files: {p.permissions['files']}; tools: {tools})")
    if not lines:
        lines = [f"No plugins installed. Add {registry.EXTENSIONS_DIR / 'plugins' / '<name>' / 'plugin.json'}"]
    return "\n".join(["PLUGINS:", *lines, *_errors(reg, "plugins")])


def route(text):
    stripped = (text or "").strip()
    if not stripped.startswith("/"):
        return "passthrough", text
    parts = stripped.split(None, 1)
    cmd, rest = parts[0][1:].lower(), parts[1] if len(parts) > 1 else ""
    if cmd == "skills":
        return "local", _list_skills()
    if cmd == "plugins":
        return "local", _list_plugins()
    skill = registry.get_skill(cmd)
    if skill is not None:
        return "prompt", f"[Skill: {skill.name}]\n{skill.body}\n\n[Task]\n{rest.strip()}"
    return "passthrough", text
