"""Sovereign Invocation Relay (v1.6.0).

A tiny background process that starts server.py on demand for cloud agents
(via the MCP bridge) and exits it after an idle timeout so the GPU is free
when Peridot is not in use. Entry point: core_system/invocation/relay.py.
"""
