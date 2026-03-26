"""
ECG Visualization — Comparison Plot Generator

Generates a matplotlib comparison plot of the original ECG signal overlaid with
the anonymized version.  Returns a base64-encoded PNG suitable for embedding
directly in a JSON API response.

Layout mirrors the style of the reference ecg_comparison_2x2_grid.py:
  - Original signal: dashed grey  (#c0c0c0)
  - Anonymized signal: blue (#0D2FEE) for K ≤ 5, orange (#ff7f0e) for K ≥ 10
  - Pearson r displayed in the title
  - Only a 5-second middle slice is shown (same as the paper figure)
"""

import io
import base64
import logging
from datetime import timedelta
from typing import List, Dict, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use('Agg')   # headless — no GUI window needed
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)

# ── Visual constants ─────────────────────────────────────────────────────────
_COLOR_ORIGINAL = '#c0c0c0'   # dashed grey — original signal
_COLOR_LOW_K    = '#0D2FEE'   # blue — anonymized signal (all k values)

_DISPLAY_SECONDS  = 5         # seconds of signal to show in the plot
_DISPLAY_POSITION = 'middle'  # 'start' | 'middle' | 'end'


def build_comparison_plot(
    original_records:    List[Dict],
    anonymized_records:  List[Dict],
    k_value:             int,
    time_window_seconds: int,
) -> Tuple[str, Optional[float]]:
    """
    Build an original-vs-anonymized ECG comparison plot.

    Parameters
    ----------
    original_records    : list of dicts, each with 'timestamp' (ms int) and 'ecg' (numeric)
    anonymized_records  : list of dicts, each with 'timestamp' (ms int) and 'ecg' (numeric)
    k_value             : k-anonymity parameter that was used
    time_window_seconds : tumbling window size that was used

    Returns
    -------
    Tuple[base64_png_str, pearson_r]
        pearson_r is None when fewer than 10 timestamps match between the two signals.
    """
    orig_df = _to_df(original_records)
    anon_df = _to_df(anonymized_records)

    # Pearson computed on the full signal (not the display slice)
    pearson_r = _pearson(orig_df, anon_df)

    # Trim to the display window for the plot
    orig_plot = _time_window(orig_df, _DISPLAY_SECONDS, _DISPLAY_POSITION)
    anon_plot = _time_window(anon_df, _DISPLAY_SECONDS, _DISPLAY_POSITION)

    r_str = f"{pearson_r:.4f}" if pearson_r is not None else "N/A"

    fig, ax = plt.subplots(figsize=(10, 4), constrained_layout=True)

    ax.plot(
        orig_plot['relative_time'], orig_plot['ecg'],
        color=_COLOR_ORIGINAL, linewidth=0.9, linestyle='--',
        label='Original', zorder=1,
    )
    ax.plot(
        anon_plot['relative_time'], anon_plot['ecg'],
        color=_COLOR_LOW_K, linewidth=0.9,
        label=f'Anonymized  (K={k_value}, T={time_window_seconds}s)',
        zorder=2,
    )

    ax.set_title(
        f'Privacy Guarantee  K = {k_value}   |   Tumbling Window  T = {time_window_seconds}s'
        f'   |   Pearson  r = {r_str}',
        fontsize=11, pad=10,
    )
    ax.set_xlabel('Time (seconds)', fontsize=10)
    ax.set_ylabel('ECG Value (μV)', fontsize=10)
    ax.legend(fontsize=9, loc='upper right')
    ax.tick_params(labelsize=8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)

    return base64.b64encode(buf.read()).decode('utf-8'), pearson_r


# ── Internal helpers ──────────────────────────────────────────────────────────

def _to_df(records: List[Dict]) -> pd.DataFrame:
    """Convert a list of {'timestamp', 'ecg'} dicts to a clean DataFrame."""
    df = pd.DataFrame(records)[['timestamp', 'ecg']].copy()
    df['ecg'] = pd.to_numeric(df['ecg'], errors='coerce')
    df = df[
        df['ecg'].notna() &
        (df['ecg'] != 0) &
        (df['ecg'] >= -2500) &
        (df['ecg'] <= 2500)
    ].copy()
    df['timestamp_dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.sort_values('timestamp_dt').reset_index(drop=True)
    start = df['timestamp_dt'].min()
    df['relative_time'] = (df['timestamp_dt'] - start).dt.total_seconds()
    return df


def _time_window(df: pd.DataFrame, duration: float, position: str) -> pd.DataFrame:
    """Return a slice of `df` limited to `duration` seconds from `position`."""
    total = (df['timestamp_dt'].max() - df['timestamp_dt'].min()).total_seconds()
    if total <= duration:
        return df.copy()

    min_t = df['timestamp_dt'].min()
    max_t = df['timestamp_dt'].max()

    if position == 'start':
        window_start = min_t
    elif position == 'end':
        window_start = max_t - timedelta(seconds=duration)
    else:  # middle
        mid = min_t + timedelta(seconds=total / 2)
        window_start = mid - timedelta(seconds=duration / 2)

    window_end = window_start + timedelta(seconds=duration)
    filtered = df[
        (df['timestamp_dt'] >= window_start) &
        (df['timestamp_dt'] <= window_end)
    ].copy()

    new_start = filtered['timestamp_dt'].min()
    filtered['relative_time'] = (filtered['timestamp_dt'] - new_start).dt.total_seconds()
    return filtered


def _pearson(orig_df: pd.DataFrame, anon_df: pd.DataFrame) -> Optional[float]:
    """Pearson r between original and anonymized, aligned by exact timestamp."""
    merged = pd.merge(
        orig_df[['timestamp', 'ecg']],
        anon_df[['timestamp', 'ecg']],
        on='timestamp', suffixes=('_orig', '_anon'),
    )
    if len(merged) < 10:
        return None
    r, _ = stats.pearsonr(merged['ecg_orig'], merged['ecg_anon'])
    return float(r)
