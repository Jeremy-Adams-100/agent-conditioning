#!/usr/bin/env python3
"""Minimal MCP server exposing search_sessions tool over stdio.

Launched as a subprocess by Claude Code via --mcp-config.
Reads the SQLite database path from the SESSIONS_DB environment variable.

Protocol: JSON-RPC 2.0 over stdio with Content-Length framing (MCP standard).
"""

import json
import os
import sys
from pathlib import Path

from auto_compact.db import init_db, search_sessions


def read_message():
    """Read a JSON-RPC message with Content-Length header from stdin."""
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        decoded = line.decode("utf-8")
        if decoded.strip() == "":
            break
        if ":" in decoded:
            key, value = decoded.split(":", 1)
            headers[key.strip()] = value.strip()

    content_length = int(headers.get("Content-Length", 0))
    if content_length == 0:
        return None

    body = sys.stdin.buffer.read(content_length)
    return json.loads(body)


def write_message(msg):
    """Write a JSON-RPC message with Content-Length header to stdout."""
    body = json.dumps(msg).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n"
    sys.stdout.buffer.write(header.encode("utf-8"))
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


def main():
    db_path = os.environ.get("SESSIONS_DB", "")
    if db_path:
        db_path = Path(db_path)
    else:
        db_path = Path.home() / ".local" / "share" / "auto-compact" / "sessions.db"

    conn = init_db(db_path)

    while True:
        msg = read_message()
        if msg is None:
            break

        method = msg.get("method", "")
        msg_id = msg.get("id")

        if method == "initialize":
            write_message({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "sessions-search", "version": "1.0.0"},
                },
            })

        elif method == "notifications/initialized":
            pass  # Notification — no response

        elif method == "tools/list":
            write_message({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": [
                        {
                            "name": "search_sessions",
                            "description": (
                                "Search past session summaries for historical context. "
                                "Use when the current session summary doesn't contain "
                                "information you need, or when the user references past "
                                "work not in your current state."
                            ),
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "Natural language search query.",
                                    },
                                    "limit": {
                                        "type": "integer",
                                        "description": "Maximum results to return (default 5).",
                                        "default": 5,
                                    },
                                },
                                "required": ["query"],
                            },
                        }
                    ],
                },
            })

        elif method == "tools/call":
            params = msg.get("params", {})
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            if tool_name == "search_sessions":
                query = arguments.get("query", "")
                limit = min(arguments.get("limit", 5), 20)
                try:
                    results = search_sessions(conn, query, limit)
                except Exception:
                    results = []

                if results:
                    text = "\n\n---\n\n".join(
                        f"Session {r['id']} (depth {r['depth']}, {r['created_at']}):\n"
                        f"{r['summary_xml']}"
                        for r in results
                    )
                else:
                    text = "No matching sessions found."

                write_message({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": text}],
                    },
                })
            else:
                write_message({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                })

        elif msg_id is not None:
            # Unknown method with an ID — return error
            write_message({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"},
            })

    conn.close()


if __name__ == "__main__":
    main()
