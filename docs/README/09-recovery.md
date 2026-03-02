# Resume & Recovery

[← Reports](08-reports.md) · [Architecture →](10-architecture.md)

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

**Validation checks on `--continue`:**
- Config ID must match the existing `meta.json` experiment ID.
- A `meta.json` must already exist (ensures you are continuing, not starting fresh).

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

## Frequently Asked Questions

**Q: How much data do I lose if a run crashes mid-phase?**
A: At most one record. CoEval writes each JSONL record atomically as it completes. The worst case is one in-flight batch item that was being processed when the crash occurred. All previously written records are intact and are read back on resume.

**Q: What is the difference between `--continue` and `--resume`?**
A: `--continue` restarts the same experiment in-place — it reads `meta.json`, skips completed phases, and fills gaps in in-progress phases using the same experiment ID and config. `--resume PATH` forks a new experiment from an existing one by copying Phases 1 and 2 artifacts (attributes and rubric) from the source run, then running Phases 3–5 fresh with the new config's models. Use `--continue` to restart after a crash; use `--resume` to build on top of an existing benchmark with different student or judge models.

**Q: How do I add a new model to an experiment that has already finished?**
A: Use `--continue --only-models new-model-name`. This re-runs only Phases 4 and 5 for the specified model while leaving all other models' data untouched. Alternatively, set the affected phases to `Model` mode in the config, which skips (task, model) pairs whose JSONL file already exists.

**Q: What should I do if I see malformed or corrupted JSONL records?**
A: Run `coeval repair --run ./eval_runs/my-experiment --dry-run --stats` first to preview what would be repaired. If the output looks right, run `coeval repair --run ./eval_runs/my-experiment` to apply the fixes — malformed records are marked as failed and the phase checkpoint is cleared from `meta.json`. Then run `coeval run --config my-experiment.yaml --continue` to regenerate only the failed items.

**Q: Can I re-use the attribute mapping and rubric from one experiment in another?**
A: Yes. Set `resume_from: path/to/source-experiment` in the new experiment's `experiment` block. Phases 1 and 2 artifacts are copied from the source run, and you can set those phases to `Keep` in the new config to skip them entirely. This is useful when running evaluation ablations that share the same task definitions.

**Q: How do I check what is left to complete in a partially finished run?**
A: Run `coeval status --run ./eval_runs/my-experiment` to see a progress dashboard showing phase artifact counts, pending batch jobs, and recent log errors. For a cost estimate of remaining work only, run `coeval plan --config my-experiment.yaml --continue`.

---

[← Reports](08-reports.md) · [Architecture →](10-architecture.md)
