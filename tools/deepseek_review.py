#!/usr/bin/env python3
"""DeepSeek Direct-API Helper — fuer Code-Reviews ohne pal-MCP-Token-Limit.

Aufruf:
    cat prompt.md | ./venv/bin/python3 tools/deepseek_review.py file1.py file2.py
    cat prompt.md | ./venv/bin/python3 tools/deepseek_review.py --chat file.py

Modelle:
    --reasoner   (Default) deepseek-reasoner → R1, ~6-30s, ~$0.005/Request
                 Mike-Entscheidung 28.04.2026: lieber langsamer + teurer +
                 besser statt schnell + billig + durchschnitt. Quality > Speed.
                 Stark fuer: Code-Review, Architektur, Race-Conditions,
                 mathematische Korrektheit, KISS-Trade-offs, niedrige
                 Halluzinations-Rate weil R1 intern Code-Pfade verifiziert.
    --chat       deepseek-chat → V4-flash, ~3s, ~$0.001/Request
                 Opt-in fuer Trivial-Fragen wo R1 overthinkt:
                 "Ist Funktion X im Code?", Tippfehler-Suche, Pure
                 Verifikations-Fragen ohne Trade-off.

Key-Datei: ~/.deepseek_key (chmod 600). Niemals im Repo.

Vergleich pal-MCP vs Direkt:
- pal MCP `chat`:     Files-Limit 7077 Tokens (~28KB Code) ← haeufig zu klein
- Direkt-API:         65K Tokens (~260KB Code) — kompletter mw_radio.py passt rein
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

KEY_FILE = Path.home() / ".deepseek_key"
API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-reasoner"   # R1 — Quality > Speed (Mike 2026-04-28)
CHAT_MODEL = "deepseek-chat"          # V4-flash — Opt-in fuer triviale Fragen


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
    model = DEFAULT_MODEL  # R1 — Quality > Speed
    if "--chat" in args:
        model = CHAT_MODEL
        args.remove("--chat")
    elif "--reasoner" in args:
        args.remove("--reasoner")  # explizit, ist eh Default
    files = [Path(arg) for arg in args]
    prompt = build_prompt(stdin_prompt, files)

    tokens = estimate_tokens(prompt)
    sys.stderr.write(f"[deepseek] ~{tokens} Tokens, {len(files)} File(s) → {model}\n")
    if tokens > 110000:
        sys.stderr.write(f"[deepseek] WARNUNG: nahe Context-Limit (128K).\n")
    if model == DEFAULT_MODEL:
        sys.stderr.write(f"[deepseek] R1 denkt — kann 6-30s dauern ...\n")

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
