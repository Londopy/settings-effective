"""Render docs/demo.png: real effective.py output on a fixture, styled as a terminal.

Run from the repo root:  python docs/make_demo.py
Needs Pillow (dev-only; the tool itself has no dependencies).
"""
from __future__ import annotations

import io
import json
import re
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "settings-effective" / "scripts"))
import effective  # noqa: E402

FONT = next(p for p in [Path("C:/Windows/Fonts/CascadiaMono.ttf"),
                        Path("C:/Windows/Fonts/consola.ttf"),
                        Path("/System/Library/Fonts/Menlo.ttc"),
                        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")] if p.exists())

BG, FG, DIM = (24, 26, 32), (220, 223, 228), (120, 126, 138)
GREEN, YELLOW, RED, BLUE, PURPLE = (126, 204, 140), (230, 190, 90), (240, 110, 110), (110, 170, 240), (190, 140, 240)


def write(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2) if not isinstance(data, str) else data, encoding="utf-8")


def fixture(tmp: Path) -> dict:
    home, managed, proj, cj = tmp / "home", tmp / "managed", tmp / "Code" / "tidewatch", tmp / "claude.json"
    write(home / "settings.json", {
        "model": "opus", "attribution": {"commit": "", "pr": ""},
        "permissions": {"allow": ["Bash(git status)", "Bash(npm test)"], "defaultMode": "acceptEdits"},
        "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "~/bin/guard.sh"}]}]},
        "env": {"CLAUDE_CODE_MAX_OUTPUT_TOKENS": "16000"}, "maxEffortLevel": "high"})
    write(proj / ".claude" / "settings.json", {
        "model": "sonnet", "autoMode": {"allow": ["Bash(cargo *)"]},
        "permisions": {"deny": ["Read(.env)"]},
        "permissions": {"ask": ["Bash(npm test)"], "deny": ["Read(.env)"], "additionalDirectories": ["../shared"]},
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "cargo test --quiet"}]}]},
        "env": {"RUST_BACKTRACE": "1"}, "disableClaudeAiConnectors": True})
    write(proj / ".claude" / "settings.local.json", '{"model": "haiku",}')
    write(managed / "managed-settings.json", {"permissions": {"deny": ["Bash(curl *)"]}, "disableClaudeAiConnectors": False})
    write(cj, {"projects": {str(proj): {"hasTrustDialogAccepted": False}}, "copyOnSelect": False})
    return {"project": proj, "home": home, "managed": managed, "cj": cj, "tmp": tmp}


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        f = fixture(Path(tmp))
        buf = io.StringIO()
        with redirect_stdout(buf):
            effective.main(["--project", str(f["project"]), "--claude-home", str(f["home"]),
                            "--managed-dir", str(f["managed"]), "--claude-json", str(f["cj"])])
        out = (buf.getvalue()
               .replace(str(f["managed"]), "C:/Program Files/ClaudeCode")
               .replace(str(f["home"]), "~/.claude").replace(str(f["cj"]), "~/.claude.json")
               .replace(str(f["tmp"]), "~").replace("\\", "/"))

    lines = ["$ python effective.py", ""] + out.rstrip().splitlines()
    lines = [l if len(l) <= 118 else l[:117] + "…" for l in lines]
    font = ImageFont.truetype(str(FONT), 15)
    lh, pad, width = 22, 28, 1120
    height = pad * 2 + lh * len(lines) + 30
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([pad + i * 22, 14, pad + i * 22 + 12, 26], fill=c)
    d.text((width // 2 - 70, 12), "settings-effective", fill=DIM, font=font)
    y = pad + 20
    for line in lines:
        color = FG
        if line.startswith("$ "):
            color = GREEN
        elif line.startswith(("settings-effective", "hooks ", "findings")):
            color = BLUE
        elif re.match(r"\s{2}\S.*\s(SKIPPED|NO)\s", line) or line.strip().startswith("IGNORED"):
            color = RED
        elif line.strip().startswith("warn"):
            color = YELLOW
        elif line.strip().startswith("note"):
            color = DIM
        elif re.match(r"\s{2}\S.*\s(loaded|absent|unknown)\s", line) or line.startswith("  index"):
            color = DIM if " absent " in line or line.startswith("  index") else FG
        elif re.search(r"\s(user|project|local|managed|--settings|~/\.claude\.json|user, project)$", line):
            color = PURPLE
        d.text((pad, y), line, fill=color, font=font)
        y += lh
    outp = ROOT / "docs" / "demo.png"
    img.save(outp, optimize=True)
    print(f"wrote {outp} ({width}x{height})")


if __name__ == "__main__":
    main()
