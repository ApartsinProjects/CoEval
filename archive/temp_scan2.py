import json, glob, os, sys

base = r"E:\Projects\CoEval\main\benchmark\runs\medium-benchmark-v1"

def check(label, files, required_keys, empty_keys):
    print(f"\n{'='*60}")
    print(f"{label}")
    print('='*60)
    total = 0
    issues = []
    for f in sorted(files):
        fname = os.path.basename(f)
        with open(f, encoding='utf-8') as fh:
            lines = [l.strip() for l in fh if l.strip()]
        for i, line in enumerate(lines):
            total += 1
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                issues.append((fname, i+1, f"JSON error: {e}", None))
                continue
            for k in required_keys:
                if k not in rec:
                    issues.append((fname, i+1, f"missing key '{k}'", None))
                    break
            else:
                for k in empty_keys:
                    v = rec.get(k)
                    if v is None or v == '' or (isinstance(v, dict) and all(vv is None or vv == '' for vv in v.values())):
                        issues.append((fname, i+1, f"empty/null '{k}'", rec.get('id') or rec.get('response_id') or '?'))

    print(f"Total records: {total}")
    if issues:
        print(f"ISSUES FOUND: {len(issues)}")
        for fname, lineno, msg, rid in issues[:30]:
            print(f"  {fname}:{lineno}: {msg}" + (f" (id={rid})" if rid else ""))
        if len(issues) > 30:
            print(f"  ... and {len(issues)-30} more")
    else:
        print("No issues found. All records valid.")
    return issues

# Phase 3: check reference_response and prompt
p3 = glob.glob(os.path.join(base, "phase3_datapoints", "*.jsonl"))
issues3 = check("PHASE 3 (datapoints)", p3,
    required_keys=['id', 'task_id', 'teacher_model_id', 'prompt', 'reference_response'],
    empty_keys=['reference_response', 'prompt'])

# Phase 4: check response field
p4 = glob.glob(os.path.join(base, "phase4_responses", "*.jsonl"))
issues4 = check("PHASE 4 (responses)", p4,
    required_keys=['datapoint_id', 'response'],
    empty_keys=['response'])

# Phase 5: check scores
p5 = glob.glob(os.path.join(base, "phase5_evaluations", "*.jsonl"))
issues5 = check("PHASE 5 (evaluations)", p5,
    required_keys=['response_id', 'scores'],
    empty_keys=['scores'])

print(f"\n\nSUMMARY: Phase3={len(issues3)} Phase4={len(issues4)} Phase5={len(issues5)}")

# Show one sample record from each phase
for label, files in [("Phase3 sample", p3), ("Phase4 sample", p4), ("Phase5 sample", p5)]:
    if files:
        with open(files[0], encoding='utf-8') as fh:
            line = fh.readline().strip()
        if line:
            r = json.loads(line)
            print(f"\n{label} keys: {list(r.keys())}")
            # Show empty_keys values
            for k in list(r.keys())[:3]:
                v = r[k]
                if isinstance(v, str):
                    print(f"  {k}: {repr(v[:80])}")
                else:
                    print(f"  {k}: {v}")
