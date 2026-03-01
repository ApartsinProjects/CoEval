import json
import glob
import os
import sys

base = r"E:\Projects\CoEval\main\benchmark\runs\medium-benchmark-v1"

def analyze_phase3():
    print("=" * 60)
    print("PHASE 3: datapoints")
    print("=" * 60)
    files = glob.glob(os.path.join(base, "phase3_datapoints", "*.jsonl"))
    total = 0
    invalid = 0
    empty_resp = 0
    bad_keys = 0
    for f in sorted(files):
        fname = os.path.basename(f)
        with open(f, encoding='utf-8') as fh:
            lines = [l.strip() for l in fh if l.strip()]
        file_invalid = []
        for i, line in enumerate(lines):
            total += 1
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                invalid += 1
                file_invalid.append(f"  line {i+1}: JSON parse error: {e}")
                continue
            # Check expected fields for phase3: seq_num, question, answer
            for key in ('seq_num', 'question', 'answer'):
                if key not in rec:
                    bad_keys += 1
                    file_invalid.append(f"  line {i+1}: missing key '{key}', keys={list(rec.keys())[:6]}")
                    break
            else:
                if rec.get('answer', '') == '' or rec.get('answer') is None:
                    empty_resp += 1
                    file_invalid.append(f"  line {i+1}: empty answer, seq_num={rec.get('seq_num')}")
                if rec.get('question', '') == '' or rec.get('question') is None:
                    empty_resp += 1
                    file_invalid.append(f"  line {i+1}: empty question, seq_num={rec.get('seq_num')}")
        if file_invalid:
            print(f"\nFile: {fname} ({len(lines)} records, {len(file_invalid)} issues)")
            for issue in file_invalid[:10]:
                print(issue)
    print(f"\nPhase 3 totals: {total} records, {invalid} JSON errors, {empty_resp} empty fields, {bad_keys} missing keys")


def analyze_phase4():
    print("\n" + "=" * 60)
    print("PHASE 4: responses")
    print("=" * 60)
    files = glob.glob(os.path.join(base, "phase4_responses", "*.jsonl"))
    total = 0
    invalid = 0
    empty_resp = 0
    bad_keys = 0
    for f in sorted(files):
        fname = os.path.basename(f)
        with open(f, encoding='utf-8') as fh:
            lines = [l.strip() for l in fh if l.strip()]
        file_invalid = []
        for i, line in enumerate(lines):
            total += 1
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                invalid += 1
                file_invalid.append(f"  line {i+1}: JSON parse error: {e}")
                continue
            # Check for response field
            for key in ('datapoint_id', 'response'):
                if key not in rec:
                    bad_keys += 1
                    file_invalid.append(f"  line {i+1}: missing key '{key}', keys={list(rec.keys())[:6]}")
                    break
            else:
                resp = rec.get('response', '')
                if resp == '' or resp is None:
                    empty_resp += 1
                    file_invalid.append(f"  line {i+1}: empty response, id={rec.get('datapoint_id')}")
        if file_invalid:
            print(f"\nFile: {fname} ({len(lines)} records, {len(file_invalid)} issues)")
            for issue in file_invalid[:10]:
                print(issue)
    print(f"\nPhase 4 totals: {total} records, {invalid} JSON errors, {empty_resp} empty responses, {bad_keys} missing keys")


def analyze_phase5():
    print("\n" + "=" * 60)
    print("PHASE 5: evaluations")
    print("=" * 60)
    files = glob.glob(os.path.join(base, "phase5_evaluations", "*.jsonl"))
    total = 0
    invalid = 0
    empty_score = 0
    bad_keys = 0
    for f in sorted(files):
        fname = os.path.basename(f)
        with open(f, encoding='utf-8') as fh:
            lines = [l.strip() for l in fh if l.strip()]
        file_invalid = []
        for i, line in enumerate(lines):
            total += 1
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                invalid += 1
                file_invalid.append(f"  line {i+1}: JSON parse error: {e}")
                continue
            # Check for score field
            score_key = next((k for k in ('score', 'evaluation', 'result') if k in rec), None)
            if score_key is None and 'response_id' in rec:
                # Check all keys
                pass
            for key in ('response_id',):
                if key not in rec:
                    bad_keys += 1
                    file_invalid.append(f"  line {i+1}: missing key '{key}', keys={list(rec.keys())[:8]}")
                    break
            else:
                # Check score validity
                scores = {k: v for k, v in rec.items() if 'score' in k.lower() or 'eval' in k.lower()}
                if not scores:
                    # Print first 3 keys to understand structure
                    pass
                null_scores = [k for k,v in scores.items() if v is None or v == '']
                if null_scores:
                    empty_score += 1
                    file_invalid.append(f"  line {i+1}: null/empty score fields {null_scores}, id={rec.get('response_id')}")
        if file_invalid:
            print(f"\nFile: {fname} ({len(lines)} records, {len(file_invalid)} issues)")
            for issue in file_invalid[:10]:
                print(issue)
    print(f"\nPhase 5 totals: {total} records, {invalid} JSON errors, {empty_score} null scores, {bad_keys} missing keys")
    
    # Also show structure of first record
    if files:
        with open(files[0], encoding='utf-8') as fh:
            first = fh.readline().strip()
        if first:
            rec = json.loads(first)
            print(f"\nPhase 5 sample record keys: {list(rec.keys())}")


analyze_phase3()
analyze_phase4()
analyze_phase5()
