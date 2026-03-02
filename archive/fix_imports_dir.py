"""Replace old package names with new ones in a specific directory subtree."""
import re, pathlib, sys

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

if len(sys.argv) < 2:
    print("Usage: python scripts/fix_imports_dir.py <directory> [py|md]")
    sys.exit(1)

target_dir = pathlib.Path(sys.argv[1])
ext = sys.argv[2] if len(sys.argv) > 2 else 'py'
print(f"Processing .{ext} files in {target_dir} …")
for path in target_dir.rglob(f"*.{ext}"):
    if '.git' in path.parts:
        continue
    rules = PY_RULES if ext == 'py' else MD_RULES
    process(path, rules)
print("Done.")
