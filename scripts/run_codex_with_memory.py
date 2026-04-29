from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


def _build_prompt(db_path: str, query: str, options: argparse.Namespace) -> str:
    repo_root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(repo_root / "src")}
    command = [
        sys.executable,
        "-m",
        "agent_memory.api.cli",
        "codex-prompt",
        db_path,
        query,
        "--preferred-scope",
        options.preferred_scope,
        "--top-k",
        str(options.top_k),
        "--max-prompt-lines",
        str(options.max_prompt_lines),
        "--max-prompt-chars",
        str(options.max_prompt_chars),
        "--max-prompt-tokens",
        str(options.max_prompt_tokens),
        "--max-alternatives",
        str(options.max_alternatives),
    ]
    if options.no_reason_codes:
        command.append("--no-reason-codes")
    result = subprocess.run(command, cwd=repo_root, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout or "agent-memory codex-prompt failed")
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("db_path")
    parser.add_argument("query")
    parser.add_argument("--preferred-scope", default="global")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--max-prompt-lines", type=int, default=8)
    parser.add_argument("--max-prompt-chars", type=int, default=1200)
    parser.add_argument("--max-prompt-tokens", type=int, default=300)
    parser.add_argument("--max-alternatives", type=int, default=2)
    parser.add_argument("--no-reason-codes", action="store_true")
    parser.add_argument("--codex-bin", default=os.environ.get("AGENT_MEMORY_CODEX_BIN", "codex"))
    parser.add_argument("--codex-model")
    parser.add_argument("--sandbox", default="workspace-write")
    parser.add_argument("--skip-git-repo-check", action="store_true", default=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--extra-codex-arg", action="append", default=[])
    args = parser.parse_args()

    prompt = _build_prompt(args.db_path, args.query, args)
    full_prompt = f"{prompt}\n\nUser request:\n{args.query}" if prompt else args.query
    command = shlex.split(args.codex_bin)
    command.append("exec")
    if args.skip_git_repo_check:
        command.append("--skip-git-repo-check")
    command.extend(["--sandbox", args.sandbox])
    if args.codex_model:
        command.extend(["--model", args.codex_model])
    command.extend(args.extra_codex_arg)
    command.append(full_prompt)

    if args.dry_run:
        print(json.dumps({"command": command, "prompt": full_prompt}, indent=2))
        return

    result = subprocess.run(command, capture_output=True, text=True)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
