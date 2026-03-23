"""
Central Anonymization API — Example Usage

Run this script to see a full demonstration of the client talking to the server.

Prerequisites:
  1. Install dependencies:        pip install -r ../requirements.txt
  2. Start the server:            cd ../server && python app.py
  3. Run this script:             python example_usage.py

The server must be running before executing this script.
"""

import time
import sys
import os

# Allow running this file directly without installing the package
sys.path.insert(0, os.path.dirname(__file__))
from anon_client import CentralAnonClient, AnonClientError

# ---------------------------------------------------------------------------
# Configuration — adjust to match your server setup
# ---------------------------------------------------------------------------
SERVER_URL  = 'https://localhost:6000'
API_KEY     = ''        # leave empty if server has no API_KEY set
VERIFY_SSL  = False     # False for self-signed cert (browser warning is expected)

# ---------------------------------------------------------------------------
# Helper: generate fake ECG records for testing
# ---------------------------------------------------------------------------
def make_sample_records(n: int = 20, start_offset_ms: int = 0) -> list:
    """
    Generate n fake ECG records spaced 10 ms apart.
    ECG values cover a range including zeros, out-of-range, and normal values
    so you can see all three validation outcomes.
    """
    sample_ecg_values = [
        150, -230, 88, 0,      # 0 will be skipped (zero-ECG rule)
        1500, -800, 50, 300,
        -100, 200, 3000,       # 3000 will be clamped (out-of-range rule)
        -2400, 2400, 75,
        -50, 500, -1200, 900, 42,
    ]
    now_ms = int(time.time() * 1000) + start_offset_ms
    return [
        {
            'timestamp':  now_ms + i * 10,
            'ecg':        sample_ecg_values[i % len(sample_ecg_values)],
            'unique_key': 'patient_test_001',
            'field':      'ecg',
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Main demo
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("  Central Anonymization API — Client Demo")
    print("=" * 60)

    client = CentralAnonClient(
        base_url=SERVER_URL,
        api_key=API_KEY or None,
        verify_ssl=VERIFY_SSL,
        timeout=60,
    )

    # ── 1. Health check ──────────────────────────────────────────────────
    print("\n[1] Health check")
    if not client.is_healthy():
        print(f"  Server at {SERVER_URL} is not reachable or hierarchy not loaded.")
        print("  Make sure the server is running:  cd ../server && python app.py")
        sys.exit(1)

    health = client.health_check()
    print(f"  Status:           {health['status']}")
    print(f"  Hierarchy loaded: {health['hierarchy_loaded']} ({health['hierarchy_size']} ECG values)")
    print(f"  Default k-value:  {health['default_k_value']}")

    # ── 2. Server info ───────────────────────────────────────────────────
    print("\n[2] Server info")
    try:
        info = client.get_info()
        print(f"  Algorithm:        {info['algorithm']}")
        print(f"  Supported k:      {info['supported_k']}")
        print(f"  ECG range:        {info['ecg_range']}")
    except Exception as e:
        print(f"  (skipped — {e})")

    # ── 3. Anonymize with k=10 ───────────────────────────────────────────
    print("\n[3] Anonymize 20 records with k=10, batch_size=5s")
    records = make_sample_records(n=20)

    try:
        result = client.anonymize(records, k_value=10, batch_size_seconds=5)
    except AnonClientError as e:
        print(f"  Server error: {e}")
        sys.exit(1)

    stats = result['stats']
    print(f"  Input records:    {stats['total_input']}")
    print(f"  Output records:   {stats['total_output']}")
    print(f"  Batches:          {stats['batches_processed']}")
    print(f"  Validation:")
    v = stats['validation']
    print(f"    - valid for anonymization: {v['valid_for_anonymization']}")
    print(f"    - zero ECG skipped:        {v['zero_ecg_skipped']}")
    print(f"    - out-of-range clamped:    {v['clamped_ecg_skipped']}")

    print("\n  First 5 output records:")
    print(f"  {'ECG_orig':>10}  {'Range':>20}  {'Imputed':>10}  {'Level':>6}  {'Anon?':>6}")
    print("  " + "-" * 58)
    for r in result['anonymized_records'][:5]:
        print(
            f"  {r['ecg_original']:>10}  "
            f"{str(r.get('ecg_anonymized_range', '-')):>20}  "
            f"{r['ecg']:>10.2f}  "
            f"{r.get('assigned_level', '-'):>6}  "
            f"{'yes' if r['was_anonymized'] else 'no':>6}"
        )

    # ── 4. Same data with different k-values ─────────────────────────────
    print("\n[4] Compare k-values on the same 50 records")
    big_records = make_sample_records(n=50)
    for k in [5, 10, 20, 50]:
        res = client.anonymize(big_records, k_value=k, batch_size_seconds=5)
        anon_count = sum(1 for r in res['anonymized_records'] if r['was_anonymized'])
        avg_level  = (
            sum(r['assigned_level'] for r in res['anonymized_records'] if r['was_anonymized'])
            / max(anon_count, 1)
        )
        print(f"  k={k:>2}: anonymized={anon_count:>3}/{stats['total_input']}  avg_hierarchy_level={avg_level:.2f}")

    # ── 5. Convenience method ────────────────────────────────────────────
    print("\n[5] Using anonymize_records_only() — returns just the list")
    anon_list = client.anonymize_records_only(
        make_sample_records(n=5), k_value=10
    )
    print(f"  Returned {len(anon_list)} records directly as a list")

    print("\nDone.")


if __name__ == '__main__':
    main()
