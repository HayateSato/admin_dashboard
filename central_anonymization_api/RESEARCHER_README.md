# Researcher Guide — Tumbling Window K-Anonymization for ECG

This document explains how the algorithm works step by step, including the data model, hierarchy structure, and each processing stage. It is intended for researchers and developers who want to understand, reproduce, or extend the method.

---

## Disclaimer

Although this algorithm was designed to run in real time **inside a mobile app** on a resource-constrained device (receiving live ECG from a proprietary wearable sensor), that mobile application and the wearable hardware are proprietary and cannot be shared. This repository contains only the algorithm, which is fully self-contained and can be tested with any ECG CSV dataset.

---

## Problem Statement

Conventional k-anonymization is designed for tabular demographic data (age, ZIP code, gender). Applying it directly to a **continuous streaming biometric signal** like ECG is not straightforward:

- ECG is a time series — values must preserve temporal order
- Devices are resource-constrained — computation must be bounded and predictable
- Privacy guarantees must apply to each transmitted data point, not just a static table
- The system must work without access to a central dataset

The **Tumbling Window K-Anonymization** method addresses all four constraints.

---

## System Context

The algorithm was designed to run entirely **on the mobile device**. No server is involved in the anonymization step:

```
┌─────────────────────────────────────────────────────────────────┐
│                     On-Device (Mobile App)                      │
│            ← this is where core/ runs in production →           │
│                                                                 │
│  Wearable ECG sensor                                            │
│       │ raw ECG stream (~121 Hz)                                │
│       ▼                                                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │            Tumbling Window Buffer                        │   │
│  │  Accumulates T seconds of ECG samples                   │   │
│  │  (T ∈ {5, 10, 15, 20, 30} seconds)                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│       │ full window (≈600 samples at T=5s, 121 Hz)              │
│       ▼                                                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │        Level-by-Level K-Anonymization (Algorithm)        │   │
│  │  Uses: ECG Generalization Hierarchy CSV                  │   │
│  │  Output: each raw value → anonymized range string        │   │
│  └──────────────────────────────────────────────────────────┘   │
│       │ anonymized window                                        │
│       ▼                                                         │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │               Mean Imputation                            │   │
│  │  "147;151" → 149.0   |   "*" → batch mean                │   │
│  └──────────────────────────────────────────────────────────┘   │
│       │ final float values (same timestamp order as input)      │
│       ▼                                                         │
│  Transmitted to server (InfluxDB) — raw data never leaves       │
└─────────────────────────────────────────────────────────────────┘
```

**In this demo repository**, Flask plays the role of the mobile app runtime — you send it a CSV file and it executes the same processing pipeline. This is purely for demonstration; the algorithm itself (`core/`) has no dependency on Flask or any web framework.

---

## Step 1 — Input Validation (`core/ecg_validator.py`)

Before anonymization, each record is validated:

| Rule | Condition | Action |
|------|-----------|--------|
| Zero ECG | `ecg == 0` or `ecg == None` | Mark `should_anonymize = False`; pass through unchanged |
| Out-of-range | `ecg < −2500` or `ecg > 2500` | Clamp to boundary; mark `should_anonymize = False` |
| Workout compact | `is_workout_compact == 1` | Force `should_anonymize = True` regardless of ECG value |

Records are **never deleted** — they are passed through with a flag. This matches the mobile app behavior where all records must be included in the transmission.

---

## Step 2 — Tumbling Window Batching (`server/main.py → _split_into_time_batches`)

Records are sorted by timestamp and grouped into non-overlapping fixed-duration windows:

```
Time ──────────────────────────────────────────────────────►

 │   Window 1 (T=10s)  │   Window 2 (T=10s)  │  Window 3...
 │                     │                     │
t=0                  t=10s                  t=20s

Each window is anonymized independently.
```

A **tumbling window** (as opposed to a sliding window) means there is no overlap between windows. Once a window closes, it is processed and the next window starts fresh. This keeps memory usage bounded and processing latency predictable.

---

## Step 3 — The ECG Generalization Hierarchy (`core/ECG_Generalization_hierarchy.csv`)

The hierarchy is a lookup table: for every integer ECG value in [−2500, 2500], it provides 8 levels of generalization from fine to coarse.

```
CSV format (5001 rows, one per integer ECG value):
  leaf_value, level_1_range, level_2_range, ..., level_7_range, root

Example rows:
  0,    -1;1,     -2;2,     -4;4,     -8;8,     -16;16,   -32;32,   -125;125,   *
  150,  149;150,  148;151,  146;153,  142;157,  134;165,  117;182,  50;249,     *
 -230, -231;-230, -232;-229,-234;-227,-238;-223,-246;-215,-263;-198,-374;-87,   *

Level 1 = finest (range of ~2 values)
Level 8 = root ("*", full suppression)
```

The hierarchy was pre-computed to reflect the natural distribution of ECG values from wearable recordings — ranges are narrower near zero (frequent values) and wider at the extremes (rare values). This is the **custom part of the algorithm** that makes it suitable for ECG.

The same CSV is used in:
- This Python server (standalone demo)
- The Flutter mobile app (identical algorithm in Dart)
- A PHP partner registration system

All three must use identical hierarchy data to ensure consistent anonymization.

---

## Step 4 — Level-by-Level K-Anonymization (`core/level_hierarchy_anonymizer.py`)

This is the core algorithm. Given a batch of N records, it produces k-anonymous output:

```
Input batch (sorted by ECG value):
  [−230, −105, −104, −103, 0*, 88, 149, 150, 151, 152, 300]
  (* = zero ECG, already flagged as should_anonymize=False)

Target: k = 3

─────────────────────────────────────────
LEVEL 1 — finest ranges:

  -230 → "-231;-230"   (group size 1 → ✗ not satisfied)
  -105 → "-106;-105"   (group size 1 → ✗)
  -104 → "-104;-103"   (group size 2 → ✗)
  -103 → "-104;-103"
   88  → "87;88"       (group size 1 → ✗)
  149  → "149;150"     (group size 3 → ✓ satisfied!)
  150  → "149;150"
  151  → "151;152"     (group size 2 → ✗)
  152  → "151;152"
  300  → "300;301"     (group size 1 → ✗)

Move satisfied group {149, 150, 151*} to output.    (* wrong — actually 149,150 only in level 1)
Remaining: [−230, −105, −104, −103, 88, 151, 152, 300]

─────────────────────────────────────────
LEVEL 2 — coarser ranges:

  -230 → "-232;-229"   (size 1 → ✗)
  -105 → "-106;-103"   (size 3 → ✓)
  -104 → "-106;-103"
  -103 → "-106;-103"
   88  → "87;90"       (size 1 → ✗)
  151  → "151;154"     (size 2 → ✗)
  152  → "151;154"
  300  → "298;303"     (size 1 → ✗)

Move {-105,-104,-103} to output.
Remaining: [−230, 88, 151, 152, 300]

─────────────────────────────────────────
... continue up levels until all records satisfied or level 8 reached.
Records still unsatisfied at level 8 → suppressed as "*"

─────────────────────────────────────────
OUTPUT (sorted back to original timestamp order):
  timestamp  original   range       level
  T+0        -230       "-239;-220"   5
  T+1        -105       "-106;-103"   2
  T+2        -104       "-106;-103"   2
  T+3        -103       "-106;-103"   2
  T+4        0          "0"           0  (not anonymized — zero ECG)
  T+5        88         "81;96"       4
  T+6        149        "149;150"     1
  T+7        150        "149;150"     1
  T+8        151        "149;152"     2
  T+9        152        "149;152"     2
  T+10       300        "298;303"     3
```

**Key property:** records that are easy to generalize (near common values) get assigned to fine-grained ranges early; rare values get pushed to coarser ranges. This minimizes distortion across the whole signal.

**Suppression** (`"*"`) only happens when a value truly cannot reach k identical generalized values at any level. In practice with ECG data this is rare.

---

## Step 5 — Mean Imputation (`core/mean_imputation.py`)

Ranges are converted to usable numerical values:

| Range string | Rule | Result |
|-------------|------|--------|
| `"149;150"` | midpoint | `149.5` |
| `"-106;-103"` | midpoint | `−104.5` |
| `"88"` | already a single value | `88.0` |
| `"*"` (suppressed) | replace with **batch mean** of non-suppressed values | e.g. `−14.2` |

The batch mean replacement for suppressed values ensures the transmitted signal never contains obviously synthetic constant values.

---

## Privacy Properties

**What k-anonymity guarantees:**
Each transmitted ECG value is identical to at least k−1 other values in the same time window. An adversary observing only the transmitted values cannot distinguish one individual's ECG pattern from at least k−1 others within that window.

**What k-anonymity does NOT guarantee:**
- Protection against adversaries with auxiliary data (background knowledge attacks)
- Long-term re-identification across many windows
- Protection of non-ECG fields (handled separately by the system)

**Parameter guidance (from the paper's evaluation):**

| k | T | Pearson r (typical) | Recommended use |
|---|---|---------------------|-----------------|
| 2 | 5s | 0.97–0.99 | Testing only |
| 5 | 5s | 0.90–0.95 | Low-privacy scenarios |
| 10 | 10s | 0.88–0.93 | Balanced |
| 20 | 30s | 0.85–0.92 | **Recommended (paper)** |
| 30 | 30s | 0.80–0.88 | High-privacy research |

The paper found that increasing T from 5s to 30s can recover most of the utility loss caused by increasing k from 2 to 20.

---

## Code Map

```
core/                            ← portable algorithm — no Flask, no external deps
├── ecg_validator.py
│     EcgValidator.validate_and_filter()
│       → marks each record with should_anonymize flag
│
├── level_hierarchy_anonymizer.py
│     EcgHierarchy.load_from_csv()
│       → loads the 5001-row hierarchy into a dict {int: [str×8]}
│     LevelHierarchyEcgAnonymizer.anonymize_batch()
│       → level-by-level assignment algorithm (returns EcgAnonymizationRecord list)
│
└── mean_imputation.py
      EcgMeanImputation.apply_mean_imputation()
        → converts range strings → float values
        → replaces "*" with batch mean

server/                          ← Flask demo wrapper (not how production works)
├── main.py
│     _split_into_time_batches()  → groups records into T-second tumbling windows
│     /api/v1/anonymize           → batch anonymization endpoint (scripting use)
│     /api/v1/visualize           → anonymize + generate comparison plot (demo UI)
│     GET /                       → serves server/web/index.html
│
├── web/index.html               ← interactive browser demo page
├── data/Demo_dataset.csv        ← default ECG recording for the demo
└── visualization/
      ecg_plotter.py
        build_comparison_plot()   → matplotlib figure → base64 PNG
        _pearson()                → Pearson r on merged timestamps

client/                          ← for developers integrating with the API
├── README.md                    ← mobile-first context + full API reference
├── anon_client.py               ← Python client library
└── example_usage.py             ← Python usage walkthrough
```

---

## Reproducing the Paper Figure

The paper figure (Figure X) shows four configurations on the same ECG recording:
K=2/T=5s, K=2/T=30s, K=20/T=5s, K=20/T=30s in a 2×2 grid.

To reproduce this with the demo dataset:

```python
# Run each combination and note the Pearson r values:
configs = [(2, 5), (2, 30), (20, 5), (20, 30)]
# Use POST /api/v1/visualize with k_value and time_window_seconds for each
```

The reference script that generated the paper figure is `client/example_usage.py`.

---

## Extending the Algorithm

**To use a different ECG range** (e.g. ±5000 μV for a different sensor):
- Regenerate `ECG_Generalization_hierarchy.csv` to cover the new range
- Update `EcgHierarchy.MIN_ECG` / `MAX_ECG` constants
- Update `EcgValidator.ECG_MIN` / `ECG_MAX`

**To add more hierarchy levels:**
- Add columns to the CSV
- Update `EcgHierarchy.MAX_LEVEL`

**To use a sliding window instead of tumbling:**
- Replace `_split_into_time_batches()` in `server/main.py` with a sliding window generator

**To apply to a signal other than ECG:**
- Replace the hierarchy CSV with one built for your signal's distribution
- The algorithm itself (`level_hierarchy_anonymizer.py`) is signal-agnostic

---

## Dependencies

The core algorithm (`core/`) uses only Python standard library — no external packages.

The server and visualization layer require:

| Package | Purpose |
|---------|---------|
| `flask`, `flask-cors` | HTTP API server |
| `pandas`, `numpy` | CSV loading and array operations |
| `scipy` | Pearson correlation coefficient |
| `matplotlib` | Comparison plot generation |
