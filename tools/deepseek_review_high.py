#!/usr/bin/env python3
"""DeepSeek Direct-API Helper mit erhoehtem max_tokens=32000 fuer komplexe R1-Reviews.

Identisch zu deepseek_review.py aber max_tokens=32000 statt 8000.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

KEY_FILE = Path.home() / ".deepseek_key"
API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-v4-pro"
CHAT_MODEL = "deepseek-v4-pro"


def load_key() -> str:
    if not KEY_FILE.exists():
        sys.exit(f"FEHLER: {KEY_FILE} nicht gefunden.")
    return KEY_FILE.read_text().strip()


def build_prompt(stdin_prompt: str, files: list) -> str:
    parts = [stdin_prompt.strip()]
    if files:
        parts.append("\n---\n\n## Angehaengte Files\n")
        for f in files:
            if not f.exists():
                sys.exit(f"FEHLER: Datei nicht gefunden: {f}")
            content = f.read_text()
            parts.append(f"\n### `{f}`\n\n```\n{content}\n```\n")
    return "\n".join(parts)


def call_deepseek(prompt: str, key: str, model: str) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 32000,  # R1: reasoning + answer combined
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        sys.exit(f"HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        sys.exit(f"Netzwerk-Fehler: {e}")


def estimate_tokens(text: str) -> int:
    return len(text) // 4


def main() -> None:
    if sys.stdin.isatty():
        sys.exit("FEHLER: Prompt via stdin pipen.")

    stdin_prompt = sys.stdin.read()
    args = sys.argv[1:]
    model = DEFAULT_MODEL
    if "--chat" in args:
        model = CHAT_MODEL
        args.remove("--chat")
    elif "--reasoner" in args:
        args.remove("--reasoner")
    files = [Path(arg) for arg in args]
    prompt = build_prompt(stdin_prompt, files)

    tokens = estimate_tokens(prompt)
    sys.stderr.write(f"[deepseek-high] ~{tokens} Tokens, {len(files)} File(s) → {model} (max_tokens=32000)\n")
    if tokens > 110000:
        sys.stderr.write(f"[deepseek-high] WARNUNG: nahe Context-Limit (128K).\n")
    sys.stderr.write(f"[deepseek-high] R1 denkt — bis zu 5 Min ...\n")

    key = load_key()
    result = call_deepseek(prompt, key, model)

    msg = result["choices"][0]["message"]["content"]
    usage = result.get("usage", {})
    sys.stderr.write(
        f"[deepseek-high] in={usage.get('prompt_tokens', '?')} "
        f"out={usage.get('completion_tokens', '?')} "
        f"total={usage.get('total_tokens', '?')}\n"
    )
    print(msg)


if __name__ == "__main__":
    main()
