"""Replace old package names with new ones across every .py (and optionally .md) file."""
import os, re, pathlib, sys

ROOT = pathlib.Path(".")

PY_RULES = [
    # import statements
    (re.compile(r'\bfrom experiments\.'),   'from runner.'),
    (re.compile(r'\bimport experiments\.'), 'import runner.'),
    (re.compile(r'\bfrom analysis\.'),      'from analyzer.'),
    (re.compile(r'\bimport analysis\.'),    'import analyzer.'),
    # string references (sys.modules keys, patch.dict, monkeypatch paths)
    (re.compile(r"(?<=['\"])experiments\."), 'runner.'),
    (re.compile(r"(?<=['\"])analysis\."),    'analyzer.'),
]

MD_RULES = [
    # code-block examples in markdown
    (re.compile(r'\bfrom experiments\.'), 'from runner.'),
    (re.compile(r'\bfrom analysis\.'),    'from analyzer.'),
]

def process(path, rules):
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return
    new_text = text
    for pattern, replacement in rules:
        new_text = pattern.sub(replacement, new_text)
    if new_text != text:
        path.write_text(new_text, encoding='utf-8')
        print(f"  updated: {path}")

ext = sys.argv[1] if len(sys.argv) > 1 else 'py'
print(f"Processing .{ext} files …")
for path in ROOT.rglob(f"*.{ext}"):
    if '.git' in path.parts:
        continue
    rules = PY_RULES if ext == 'py' else MD_RULES
    process(path, rules)
print("Done.")
