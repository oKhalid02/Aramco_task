"""Run a versioned prompt through Claude Code's scripted mode (`claude -p`) on the user's subscription.

Design (Phase 2, D6): prompts live in prompts/pipeline/, outputs are saved to committed files, and the
audit pipeline only ever reads the saved files, so reproducing submission.csv needs no LLM access.
"""

import datetime
import glob
import json
import os
import shutil
import subprocess
from pathlib import Path

MODEL = "claude-opus-5"


def claude_binary() -> str:
    if os.environ.get("CLAUDE_BIN"):
        return os.environ["CLAUDE_BIN"]
    if shutil.which("claude"):
        return shutil.which("claude")
    bundled = sorted(glob.glob(os.path.expanduser(
        "~/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude")))
    if bundled:
        return bundled[-1]
    raise RuntimeError("Claude Code CLI not found: set CLAUDE_BIN or put `claude` on PATH")


def prompt_body(prompt_file: Path) -> str:
    """The prompt file minus its leading <!-- metadata --> comment."""
    text = prompt_file.read_text()
    if text.startswith("<!--"):
        text = text.split("-->", 1)[1]
    return text.strip()


def run(prompt_file: Path, task: str, stdin_text: str, schema: dict, timeout: int = 1800) -> dict:
    cmd = [
        claude_binary(), "-p", task,
        "--system-prompt", prompt_body(prompt_file),
        "--model", MODEL,
        "--tools", "",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--output-format", "json",
        "--json-schema", json.dumps(schema),
    ]
    proc = subprocess.run(cmd, input=stdin_text, capture_output=True, text=True, timeout=timeout)
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"claude -p failed (exit {proc.returncode}): {proc.stdout[-2000:]} {proc.stderr[-2000:]}")
    if out.get("is_error") or out.get("structured_output") is None:
        raise RuntimeError(f"claude -p returned an error: {json.dumps(out)[:2000]}")
    return {
        "meta": {
            "prompt_file": str(prompt_file.relative_to(prompt_file.parents[2])),
            "model": MODEL,
            "models_used": sorted((out.get("modelUsage") or {}).keys()),
            "run_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "estimated_cost_usd": out.get("total_cost_usd"),
            "claude_code_version": subprocess.run([claude_binary(), "--version"], capture_output=True,
                                                  text=True).stdout.strip(),
        },
        "output": out["structured_output"],
    }
