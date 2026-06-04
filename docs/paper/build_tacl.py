"""Build the anonymized TACL submission DOCX from index.html (one command).

Keeps the canonical HTML authored; double-blind anonymization is applied only to a
TEMPORARY copy used for this build. Pipeline: anonymize -> html2doc (--profile tacl,
two-column A4) -> finalize_tacl (A4 + line numbers + confidential header).

Run from repo root:  python docs/paper/build_tacl.py
"""
import os
import re
import subprocess
import sys
from pathlib import Path

PAPER = Path(__file__).resolve().parent
SKILL = Path(os.environ.get("HTML2DOC_DIR", r"C:\Users\apart\.claude\skills\html2doc")) / "scripts"
OUT = PAPER / "CoEval_TACL.docx"

src = (PAPER / "index.html").read_text(encoding="utf-8")

# --- build-time anonymization (double-blind) ---
anon, n = re.subn(
    r'<div class="authors">.*?</div>\s*<div class="affil">.*?</div>',
    '<div class="authors"><span class="name">Anonymous Author(s)</span></div>\n'
    '  <div class="affil">Affiliation withheld for double-blind review</div>',
    src, count=1, flags=re.DOTALL,
)
assert n == 1, "author block not found"
# Withhold any self-identifying URLs (none at present; guard for future edits).
anon = re.sub(r'https?://(?:[a-z0-9-]+\.)*(?:github\.io|github\.com)/[^\s"<]*',
              "[URL withheld for review]", anon)
assert "Apartsin" not in anon and "Aperstein" not in anon and "Holon" not in anon and "Afeka" not in anon, \
    "residual author identity"

tmp = PAPER / "_tacl_anon.html"
mathml = PAPER / "_tacl_mathml.html"
tmp.write_text(anon, encoding="utf-8")

env = {**os.environ, "NODE_PATH": str(SKILL.parent / "node_modules"),
       "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
try:
    subprocess.run(["node", str(SKILL / "katex_to_mathml.js"),
                    "--input", str(tmp), "--output", str(mathml)], check=True, env=env)
    subprocess.run([sys.executable, str(SKILL / "convert_to_docx.py"),
                    "--input", str(mathml), "--output", str(OUT),
                    "--profile", "tacl", "--resource-path", str(PAPER)], check=True, env=env)
    subprocess.run([sys.executable, str(SKILL / "apply_academic_style.py"),
                    "--input", str(OUT), "--output", str(OUT), "--profile", "tacl"], check=True, env=env)
    subprocess.run([sys.executable, str(PAPER / "finalize_tacl.py"), str(OUT)], check=True, env=env)
finally:
    tmp.unlink(missing_ok=True)
    mathml.unlink(missing_ok=True)

# verify anonymization landed in the docx
import zipfile
x = zipfile.ZipFile(OUT).read("word/document.xml").decode("utf-8")
ok = all(s not in x for s in ("Apartsin", "Aperstein", "Holon", "Afeka")) and "Anonymous Author" in x
print(f"built {OUT.name}: anonymized={ok}")
