#!/usr/bin/env python3
"""DeepSeek Direct-API Helper — fuer Code-Reviews ohne pal-MCP-Token-Limit.

Aufruf:
    cat prompt.md | ./venv/bin/python3 tools/deepseek_review.py file1.py file2.py
    cat prompt.md | ./venv/bin/python3 tools/deepseek_review.py --chat file.py

Modelle (Stand 2026-05-14 — DeepSeek V4 Generation):
    --pro        (Default) deepseek-v4-pro → Stärkstes Reasoning, 1M Context,
                 131K Output. ~6-30s. Mike-Anweisung 2026-05-14:
                 'Kosten irrelevant, bestes Modell mit optimalsten Parametern'.
                 Stark fuer: Code-Review, Architektur, Race-Conditions,
                 KISS-Trade-offs, niedrige Halluzinations-Rate weil V4-Pro
                 intern Code-Pfade verifiziert. 75% Rabatt bis 31.05.2026.
    --flash      deepseek-v4-flash → Schnell, 1M Context. ~3s.
                 Opt-in fuer Bulk/Trivial wo Pro overthinkt.

Aliase `--reasoner` / `--chat` bleiben als Compat-Pfade (mappen auf
v4-pro / v4-flash). Alt-Namen `deepseek-reasoner` / `deepseek-chat` sind
DEPRECATED ab 24.07.2026.

Key-Datei: ~/.deepseek_key (chmod 600). Niemals im Repo.

Vergleich pal-MCP vs Direkt:
- pal MCP `chat`:     Files-Limit 7077 Tokens (~28KB Code) ← haeufig zu klein
- Direkt-API:         1M Tokens Context, 131K Output — ganzes Repo passt rein
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

KEY_FILE = Path.home() / ".deepseek_key"
API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-v4-pro"    # Mike 2026-05-14: bestes Modell überall
CHAT_MODEL = "deepseek-v4-flash"     # Opt-in fuer Bulk/Trivial


def load_key() -> str:
    if not KEY_FILE.exists():
        sys.exit(f"FEHLER: {KEY_FILE} nicht gefunden. "
                 f"Key dort ablegen (chmod 600).")
    return KEY_FILE.read_text().strip()


def build_prompt(stdin_prompt: str, files: list[Path]) -> str:
    parts = [stdin_prompt.strip()]
    if files:
        parts.append("\n---\n\n## Angehaengte Files\n")
        for f in files:
            if not f.exists():
                sys.exit(f"FEHLER: Datei nicht gefunden: {f}")
            try:
                content = f.read_text()
            except Exception as e:
                sys.exit(f"FEHLER beim Lesen von {f}: {e}")
            parts.append(f"\n### `{f}`\n\n```\n{content}\n```\n")
    return "\n".join(parts)


def call_deepseek(prompt: str, key: str, model: str) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 16000,  # R1: reasoning + answer combined; 8K war zu knapp
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
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        sys.exit(f"HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        sys.exit(f"Netzwerk-Fehler: {e}")


def estimate_tokens(text: str) -> int:
    """Grobe Schaetzung: 4 Zeichen ≈ 1 Token (DeepSeek-typisch)."""
    return len(text) // 4


def main() -> None:
    if sys.stdin.isatty():
        sys.exit("FEHLER: Prompt via stdin pipen.\n"
                 "  Beispiel: cat prompt.md | tools/deepseek_review.py file.py")

    stdin_prompt = sys.stdin.read()
    args = sys.argv[1:]
    model = DEFAULT_MODEL  # v4-pro — Mike's Default (Kosten egal)
    # --flash / --chat → Flash (Bulk/Trivial)
    if "--flash" in args:
        model = CHAT_MODEL
        args.remove("--flash")
    elif "--chat" in args:
        model = CHAT_MODEL
        args.remove("--chat")
    # --pro / --reasoner → Pro (explizit, ist eh Default)
    elif "--pro" in args:
        args.remove("--pro")
    elif "--reasoner" in args:
        args.remove("--reasoner")
    files = [Path(arg) for arg in args]
    prompt = build_prompt(stdin_prompt, files)

    tokens = estimate_tokens(prompt)
    sys.stderr.write(f"[deepseek] ~{tokens} Tokens, {len(files)} File(s) → {model}\n")
    if tokens > 900000:
        sys.stderr.write(f"[deepseek] WARNUNG: nahe 1M Context-Limit.\n")
    if model == DEFAULT_MODEL:
        sys.stderr.write(f"[deepseek] V4-Pro denkt — kann 6-30s dauern ...\n")

    key = load_key()
    result = call_deepseek(prompt, key, model)

    msg = result["choices"][0]["message"]["content"]
    usage = result.get("usage", {})
    sys.stderr.write(
        f"[deepseek] in={usage.get('prompt_tokens', '?')} "
        f"out={usage.get('completion_tokens', '?')} "
        f"total={usage.get('total_tokens', '?')}\n"
    )
    print(msg)


if __name__ == "__main__":
    main()
