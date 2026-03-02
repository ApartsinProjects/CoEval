# Resume, Recovery & Repair

[← Cost Planning](09-cost-control.md) · [Analytics & Reports →](11-analytics-reports.md)

---

CoEval is designed to be interrupted. Every JSONL record is written atomically; a crash mid-phase loses at most one record. The full pipeline is resumable from any point without duplicate API calls.

## How Checkpointing Works

Each experiment folder contains a `meta.json` file that tracks:
- Which phases are fully completed
- Phase start and end timestamps
- Batch job IDs for in-flight async jobs

Within each phase, JSONL records are written one at a time as they complete. On resume, CoEval reads the existing records and skips any (task, teacher/student/judge, item) triples already present.

```
eval_runs/my-experiment/
├── meta.json                         ← phase completion state
├── text_summarization__gpt-4o.datapoints.jsonl      ← Phase 3 output
├── text_summarization__gpt-4o__claude.responses.jsonl  ← Phase 4 (partial)
└── ...
```

---

## Resuming After Interruption

```bash
# Continue exactly where the run stopped
coeval run --config my-experiment.yaml --continue
```

`--continue`:
1. Reads `phases_completed` from `meta.json`; skips fully completed phases
2. For in-progress phases: reads existing JSONL records and skips already-written items
3. Submits only the missing calls; existing data is never touched

No data is duplicated. No extra API calls are made for completed items.

---

## Forking from an Earlier Run

When you want to add new student models or change judges without regenerating Phase 3 data:

```bash
coeval run \
    --config new-experiment-v2.yaml \
    --resume eval_runs/my-experiment-v1
```

`--resume PATH`:
- Copies Phase 1 (attributes) and Phase 2 (rubric) results from the source run
- Phases 3–5 run fresh with the new config's models

This lets you build a library of benchmark items once and run many evaluation variants without paying for repeated teacher calls.

---

## Targeted Model Re-Run

After fixing a bug in one model's prompt configuration or adding a new model mid-project:

```bash
# Re-run only specific models in phases 3–5
coeval run \
    --config my-experiment.yaml \
    --continue \
    --only-models gpt-4o,claude-3-5-haiku
```

All other models' data is left untouched. This is particularly useful for:
- Adding a newly released model to an existing benchmark
- Re-running a model that had API errors without paying for intact models
- Comparing a fine-tuned variant against an existing baseline

---

## Repairing Corrupted Data

When a run produces malformed JSONL records (truncated responses, invalid JSON, duplicate entries), the repair tool fixes them without data loss:

### Step 1 — Preview

```bash
coeval repair --run ./eval_runs/my-experiment --dry-run --stats
```

Output example:
```
Phase 4 — response_collection
  text_summ__gpt-4o__claude.responses.jsonl
    Total records:   2,400
    Valid:           2,387
    Malformed:          13   ← would be marked as failed
    Duplicates:          0
```

### Step 2 — Apply

```bash
coeval repair --run ./eval_runs/my-experiment
```

The repair tool:
1. Marks malformed records as `{"status": "failed", "reason": "..."}`
2. Removes the phase checkpoint from `meta.json` for any phase with repairs
3. Leaves all valid records intact

### Step 3 — Fill Gaps

```bash
coeval run --config my-experiment.yaml --continue
```

`--continue` sees the failed records as gaps and regenerates only those items. The repaired run is indistinguishable from one that completed cleanly.

---

## Phase Mode Reference for Recovery

When recovering a partially complete run, use per-phase modes to control exactly what gets re-run:

```yaml
experiment:
  phases:
    attribute_mapping:   Keep     # attributes already mapped; skip entirely
    rubric_mapping:      Keep     # rubric already built; skip entirely
    data_generation:     Extend   # append missing teacher items only
    response_collection: Extend   # append missing student responses only
    evaluation:          Extend   # append missing judge scores only
```

`Extend` mode reads the existing JSONL file and skips any item already present. It is safe to use even when the file is partially complete.

---

## Recovery Decision Tree

```
Run failed or was interrupted?
│
├─► All phases completed?
│     └─► No → coeval run --continue
│
├─► JSONL files look corrupted?
│     └─► Yes → coeval repair --dry-run → coeval repair → coeval run --continue
│
├─► Want to add a new model to existing benchmark?
│     └─► coeval run --continue --only-models new-model-name
│
├─► Want to re-use Phase 1/2 for a new experiment?
│     └─► coeval run --config new.yaml --resume old-experiment-path
│
└─► Want to check what's left before continuing?
      └─► coeval status --run ./eval_runs/my-experiment
          coeval plan --config my-experiment.yaml --continue
```

---

[← Cost Planning](09-cost-control.md) · [Analytics & Reports →](11-analytics-reports.md)
