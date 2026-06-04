"""Build the TACL LaTeX (Overleaf) bundle from index.html, one command.

Pipeline (html2tex skill, tacl template):
  1. convert_to_tex.py : HTML (KaTeX) -> LaTeX body + thebibliography + figures
  2. strip the HTML <header> (annotate link + author block) from body.tex so the
     anonymous author block comes only from the TACL template
  3. pack_tmlr_bundle.py --template tacl : graft into the official tacl2021v1
     submission template (two-column A4, native lineno line numbers, header)

Output: docs/paper/tacl_tex/ (main.tex + body/bib/figures + tacl2021v1.sty +
acl_natbib.bst) -- upload that folder to Overleaf, or push via the skill's
overleaf_push.py. For camera-ready, edit main.tex: '[]' -> '[acceptedWithA]' on
the tacl2021v1 package and fill the real author block.

Run from repo root:  python docs/paper/build_tacl_tex.py
"""
import io
import subprocess
import sys
from pathlib import Path

PAPER = Path(__file__).resolve().parent
SKILL = Path(r"E:/Projects/claude-skills/html2tex/scripts")
OUT = PAPER / "tacl_tex"
TITLE = ("CoEval: Ranking Language Models for Custom Tasks Without Labeled Data "
         "or Trustworthy Benchmarks")
env = {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
import os
env = {**os.environ, **env}

subprocess.run([sys.executable, str(SKILL / "convert_to_tex.py"),
                "--input", str(PAPER / "index.html"), "--out-dir", str(OUT)],
               check=True, env=env)

# strip everything before the first \section{...} (the HTML header leaked into body)
body = OUT / "body.tex"
b = body.read_text(encoding="utf-8")
i = b.index("\\section{")
body.write_text(b[i:], encoding="utf-8")

subprocess.run([sys.executable, str(SKILL / "pack_tmlr_bundle.py"),
                "--in-dir", str(OUT), "--template", "tacl", "--title", TITLE],
               check=True, env=env)

m = (OUT / "main.tex").read_text(encoding="utf-8")
ok = ("\\label{r1}" in m and "Anonymous Authors" in m
      and "Apartsin" not in m and "127.0.0.1" not in m)
print(f"built {OUT}/main.tex | anonymized+citations-linked: {ok}")
