# ECG Anonymization Demo

An interactive demonstration of **Tumbling Window K-Anonymization** for real-time ECG signals, developed as part of the **PrivacyUmbrella** research project.

---

## Disclaimer

In the actual PrivacyUmbrella system, this algorithm runs **inside a mobile app** that receives live ECG data from a proprietary wearable device in real time. The algorithm anonymizes the signal locally on the device before transmitting anything to a server — **no server is required for anonymization**.

**The mobile application and the wearable device are in-house developed tools and cannot be shared in this repository.** The wearable hardware is a physical device that cannot be distributed externally, and the mobile application contains proprietary system components that belong to the project partners.

This repository contains only the anonymization algorithm itself (`core/`), wrapped in a Flask web server purely for interactive demonstration. We are happy to share the algorithm and welcome academic collaboration. For questions about the broader system, please contact the authors.

---

## How It Works

You run one command. That starts a local web server which serves both the interactive page and the anonymization API.

```
Your browser
    │
    │  visits http://localhost:8080
    ▼
┌──────────────────────────────────────────────────┐
│  server/main.py  (Flask, port 8080)              │
│  — demo wrapper only, not how production works — │
│                                                  │
│  GET  /              → serves the web page       │
│  POST /api/v1/visualize                          │
│    1. loads your CSV (or bundled demo data)      │
│    2. runs k-anonymity algorithm  ←──────────┐   │
│    3. generates comparison plot              │   │
│    4. returns plot + Pearson r as JSON       │   │
└──────────────────────────────────────────────│───┘
                                               │
                                          core/
                                  (the actual algorithm —
                                   this is what runs inside
                                   the mobile app on-device)
```

Nothing runs in the background. No database. No separate process. Just one command and your browser.

---

## Quick Start — Docker

```bash
docker compose up --build
```

Open **http://localhost:8080**. No Python installation needed.

---

## Quick Start — Python

**Requirements:** Python 3.9 or later

```bash
# 1. Install dependencies (only needed once)
pip install -r requirements.txt

# 2. Start the server
python server/main.py
```

Open **http://localhost:8080** in your browser.

Expected startup output:
```
✅ Loaded ECG hierarchy: 5001 values (-2500 to 2500)
 * Running on http://127.0.0.1:8080
```

---

## Using the Interface

Choose your settings and click **Run Anonymization**. The server processes the data and returns a comparison plot in seconds.

| Setting | Options | Effect |
|---------|---------|--------|
| **K-value** | 2, 3, 5, 10, 20, 30 | Higher = stronger privacy, more signal distortion |
| **Tumbling Window (T)** | 5s, 10s, 15s, 20s, 30s | Longer = better utility at the same K |
| **Dataset** | Upload CSV or leave blank | Uses the bundled demo recording if no file is uploaded |

### Reading the result

- **Grey dashed line** — original ECG signal
- **Blue line** — anonymized ECG signal
- **Pearson r** — signal fidelity (1.0 = identical shape, 0 = no correlation)

You can change settings and click **Run Anonymization** again to compare configurations.

---

## Using Your Own ECG Data

Upload any CSV with at least these two columns:

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | integer | Unix timestamp in milliseconds |
| `ecg` | integer | ECG amplitude in μV, range −2500 to 2500 |

Rows where `ecg = 0` are skipped (common in multi-sensor wearable exports). Extra columns are ignored.

---

## Project Structure

```
.
├── core/                        ← the anonymization algorithm (portable — this is
│   ├── level_hierarchy_anonymizer.py    what runs inside the mobile app on-device)
│   ├── mean_imputation.py
│   ├── ecg_validator.py
│   └── ECG_Generalization_hierarchy.csv
│
├── server/                      ← Flask demo wrapper (not how production works)
│   ├── main.py                  ← entry point — run this
│   ├── web/
│   │   └── index.html           ← interactive web page (served by Flask at /)
│   ├── data/
│   │   └── Demo_dataset.csv     ← default ECG recording used when no file is uploaded
│   └── visualization/
│       └── ecg_plotter.py       ← generates the comparison plot (matplotlib)
│
├── client/                      ← for developers who want to call the API
│   ├── README.md                ← explains mobile-first context + full API docs
│   ├── anon_client.py           ← Python client library
│   └── example_usage.py         ← Python usage example
│
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

The `client/` folder is **not needed to run the demo** — it is documentation and example code for developers who want to integrate with the API server. See `client/README.md`.

---

## Algorithm Documentation

For a full technical walkthrough of every step — validation, tumbling window batching, level-by-level k-anonymity, mean imputation — see `RESEARCHER_README.md`.

---

## Citation

If you use this algorithm in your research, please cite:

> [Citation will be added upon publication]
