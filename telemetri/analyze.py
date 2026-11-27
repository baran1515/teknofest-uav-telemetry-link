#!/usr/bin/env python3
"""Offline analysis of link-monitor CSV logs (one or more test runs).

Produces a Markdown summary table per band and, if matplotlib is available,
plots of loss / RSSI / SNR against distance.

  python -m telemetri.analyze logs/*.csv --out reports/
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from collections import defaultdict

from telemetri.linkstats import percentile


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return math.nan


def load_runs(paths):
    runs = []
    for p in paths:
        with open(p, newline="") as fh:
            rows = list(csv.DictReader(fh))
        if rows:
            runs.append((os.path.basename(p), rows))
    return runs


def summarize(name, rows):
    last = rows[-1]
    rx, lost = _f(last["rx_pkts"]), _f(last["lost_pkts"])
    clean = lambda key: [x for x in (_f(r.get(key)) for r in rows) if not math.isnan(x)]
    rssi, snr, rtt, dist = clean("rssi_dbm"), clean("snr_db"), clean("rtt_ms"), clean("dist_m")
    att = clean("att_hz")
    return {
        "run": name,
        "band": int(_f(last["band_mhz"])),
        "duration_s": _f(last["t_s"]),
        "packets": int(rx + lost),
        "loss_pct": 100 * lost / (rx + lost) if rx + lost else math.nan,
        "rssi_mean": sum(rssi) / len(rssi) if rssi else math.nan,
        "rssi_min": min(rssi) if rssi else math.nan,
        "snr_mean": sum(snr) / len(snr) if snr else math.nan,
        "snr_p5": percentile(snr, 5),
        "rtt_p50": percentile(rtt, 50),
        "rtt_p95": percentile(rtt, 95),
        "max_dist_m": max(dist) if dist else math.nan,
        "att_hz_mean": sum(att) / len(att) if att else math.nan,
    }


def markdown_table(summaries):
    cols = [("run", "Koşu", "{}"), ("band", "Bant [MHz]", "{}"), ("duration_s", "Süre [s]", "{:.0f}"),
            ("packets", "Paket", "{}"), ("loss_pct", "Kayıp [%]", "{:.2f}"),
            ("rssi_mean", "RSSI ort [dBm]", "{:.1f}"), ("rssi_min", "RSSI min [dBm]", "{:.1f}"),
            ("snr_mean", "SNR ort [dB]", "{:.1f}"), ("snr_p5", "SNR p5 [dB]", "{:.1f}"),
            ("rtt_p50", "RTT p50 [ms]", "{:.0f}"), ("rtt_p95", "RTT p95 [ms]", "{:.0f}"),
            ("max_dist_m", "Maks. mesafe [m]", "{:.0f}"), ("att_hz_mean", "ATTITUDE [Hz]", "{:.1f}")]
    out = ["| " + " | ".join(c[1] for c in cols) + " |", "|" + "---|" * len(cols)]
    for s in summaries:
        cells = []
        for key, _, fmt in cols:
            v = s[key]
            cells.append("-" if isinstance(v, float) and math.isnan(v) else fmt.format(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def plot(runs, out_dir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed - skipping plots")
        return []
    fig, axes = plt.subplots(3, 1, figsize=(9, 10), sharex=True)
    for name, rows in runs:
        d = [_f(r.get("dist_m")) for r in rows]
        label = f"{name} ({rows[-1]['band_mhz']} MHz)"
        axes[0].plot(d, [_f(r.get("loss_pct_1s")) for r in rows], ".", label=label, alpha=0.6)
        axes[1].plot(d, [_f(r.get("rssi_dbm")) for r in rows], ".", label=label, alpha=0.6)
        axes[2].plot(d, [_f(r.get("snr_db")) for r in rows], ".", label=label, alpha=0.6)
    axes[0].set_ylabel("paket kaybı (1 s) [%]")
    axes[0].axhline(2.0, color="red", linestyle="--", linewidth=1, label="%2 hedef")
    axes[1].set_ylabel("RSSI [dBm]")
    axes[2].set_ylabel("SNR [dB]")
    axes[2].axhline(10.0, color="orange", linestyle="--", linewidth=1, label="10 dB sınır")
    axes[2].set_xlabel("YKİ'ye mesafe [m]")
    for ax in axes:
        ax.grid(True)
        ax.legend(fontsize=8)
    fig.tight_layout()
    path = os.path.join(out_dir, "link_vs_distance.png")
    fig.savefig(path, dpi=110)
    return [path]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="+")
    ap.add_argument("--out", default="reports")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    runs = load_runs(args.csv)
    if not runs:
        raise SystemExit("no data")
    os.makedirs(args.out, exist_ok=True)
    summaries = [summarize(n, r) for n, r in runs]

    by_band = defaultdict(list)
    for s in summaries:
        by_band[s["band"]].append(s)

    lines = ["# Telemetri Link Test Raporu", "", markdown_table(summaries), ""]
    for band, items in sorted(by_band.items()):
        worst = max(s["loss_pct"] for s in items)
        verdict = "GEÇTİ" if worst < 2.0 else "KALDI"
        lines.append(f"- **{band} MHz**: en kötü koşu kaybı %{worst:.2f} → hedef (<%2): **{verdict}**")
    for p in plot(runs, args.out):
        lines += ["", f"![link]({os.path.basename(p)})"]

    report = os.path.join(args.out, "report.md")
    with open(report, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nsaved {report}")


if __name__ == "__main__":
    main()
