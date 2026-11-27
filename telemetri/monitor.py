#!/usr/bin/env python3
"""Real-time MAVLink telemetry link monitor for the ground station.

Runs next to QGroundControl (on a second UDP output of MAVProxy/mavlink-router
or directly on the telemetry radio) and measures what the pilot screen does
not show directly:

  * packet loss per component from MAVLink sequence numbers
  * local / remote RSSI, noise and SNR from SiK RADIO_STATUS
  * round-trip latency with TIMESYNC (ArduPilot answers TIMESYNC requests)
  * per-message receive rates (are the SRx_ stream rates really achieved?)

Every second one CSV row is written; this is the input of analyze.py.

examples
  python -m telemetri.monitor --device /dev/ttyUSB0 --baud 57600 --band 433 --csv logs/433_run1.csv
  python -m telemetri.monitor --device udpin:0.0.0.0:14551 --band 915 --csv logs/915_run1.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from collections import Counter

from pymavlink import mavutil

from telemetri.linkstats import Rolling, SeqLossTracker, link_grade, sik_raw_to_dbm, sik_snr_db

CSV_FIELDS = [
    "t_s", "band_mhz", "rx_pkts", "lost_pkts", "loss_pct_total", "loss_pct_1s",
    "rssi_dbm", "remrssi_dbm", "noise_dbm", "snr_db", "remsnr_db", "rxerrors", "fixed",
    "txbuf", "rtt_ms", "lat", "lon", "alt_m", "dist_m", "hb_hz", "att_hz", "gps_hz",
]


def haversine_m(lat1, lon1, lat2, lon2):
    import math
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class LinkMonitor:
    def __init__(self, args):
        self.args = args
        self.mav = mavutil.mavlink_connection(args.device, baud=args.baud,
                                              source_system=args.gcs_sysid, source_component=191)
        self.loss = SeqLossTracker()
        self.rtt = Rolling(50)
        self.rates = Counter()
        self.radio = None
        self.pos = None
        self.home = None
        self.t0 = time.time()
        self._win_rx = 0
        self._win_lost = 0
        self._pending_ts = {}
        self.writer = None
        if args.csv:
            os.makedirs(os.path.dirname(args.csv) or ".", exist_ok=True)
            self._csv_file = open(args.csv, "w", newline="")
            self.writer = csv.DictWriter(self._csv_file, fieldnames=CSV_FIELDS)
            self.writer.writeheader()

    # -- TIMESYNC based round-trip time ------------------------------------
    def send_timesync(self):
        ts1 = time.monotonic_ns()
        self._pending_ts[ts1] = ts1
        self.mav.mav.timesync_send(0, ts1)

    def on_timesync(self, msg):
        # Reply from vehicle: tc1 != 0 and ts1 echoes our request.
        if msg.tc1 != 0 and msg.ts1 in self._pending_ts:
            sent = self._pending_ts.pop(msg.ts1)
            self.rtt.add((time.monotonic_ns() - sent) / 1e6)
        # drop requests older than 5 s
        now = time.monotonic_ns()
        for k in [k for k in self._pending_ts if now - k > 5e9]:
            del self._pending_ts[k]

    # -- main loop ----------------------------------------------------------
    def handle(self, msg):
        if msg.get_type() == "BAD_DATA":
            return
        hdr = msg.get_header()
        if hdr.srcSystem == self.args.gcs_sysid:
            return  # our own echo
        lost = self.loss.update(hdr.srcSystem, hdr.srcComponent, hdr.seq)
        self._win_rx += 1
        self._win_lost += lost
        mtype = msg.get_type()
        self.rates[mtype] += 1

        if mtype == "RADIO_STATUS":
            self.radio = msg
        elif mtype == "TIMESYNC":
            self.on_timesync(msg)
        elif mtype == "GLOBAL_POSITION_INT":
            self.pos = (msg.lat / 1e7, msg.lon / 1e7, msg.relative_alt / 1000.0)
            if self.home is None and msg.lat != 0:
                self.home = self.pos

    def report(self):
        t = time.time() - self.t0
        win_total = self._win_rx + self._win_lost
        row = {
            "t_s": round(t, 1),
            "band_mhz": self.args.band,
            "rx_pkts": self.loss.received,
            "lost_pkts": self.loss.lost,
            "loss_pct_total": round(self.loss.loss_pct, 3),
            "loss_pct_1s": round(100 * self._win_lost / win_total, 2) if win_total else "",
            "rtt_ms": round(self.rtt.mean, 1) if len(self.rtt) else "",
            "hb_hz": self.rates["HEARTBEAT"],
            "att_hz": self.rates["ATTITUDE"],
            "gps_hz": self.rates["GLOBAL_POSITION_INT"],
        }
        if self.radio is not None:
            r = self.radio
            row.update(rssi_dbm=round(sik_raw_to_dbm(r.rssi), 1),
                       remrssi_dbm=round(sik_raw_to_dbm(r.remrssi), 1),
                       noise_dbm=round(sik_raw_to_dbm(r.noise), 1),
                       snr_db=round(sik_snr_db(r.rssi, r.noise), 1),
                       remsnr_db=round(sik_snr_db(r.remrssi, r.remnoise), 1),
                       rxerrors=r.rxerrors, fixed=r.fixed, txbuf=r.txbuf)
        if self.pos is not None:
            row.update(lat=self.pos[0], lon=self.pos[1], alt_m=round(self.pos[2], 1))
            if self.home:
                row["dist_m"] = round(haversine_m(self.home[0], self.home[1], *self.pos[:2]), 1)

        if self.writer:
            self.writer.writerow(row)
            self._csv_file.flush()

        snr = row.get("snr_db")
        grade = link_grade(snr) if isinstance(snr, float) else "NO RADIO_STATUS"
        print(f"t={t:6.1f}s loss(1s)={row['loss_pct_1s']!s:>5}% total={row['loss_pct_total']:.2f}% "
              f"RSSI={row.get('rssi_dbm', '-')}dBm SNR={snr if snr is not None else '-'}dB [{grade}] "
              f"RTT={row['rtt_ms'] or '-'}ms ATT={row['att_hz']}Hz dist={row.get('dist_m', '-')}m")
        sys.stdout.flush()
        self.rates.clear()
        self._win_rx = self._win_lost = 0

    def run(self):
        print(f"waiting for heartbeat on {self.args.device} ...")
        self.mav.wait_heartbeat(timeout=30)
        print(f"vehicle sysid={self.mav.target_system} found")
        next_report = time.time() + 1.0
        next_sync = time.time()
        while True:
            msg = self.mav.recv_match(blocking=True, timeout=0.05)
            if msg is not None:
                self.handle(msg)
            now = time.time()
            if now >= next_sync:
                self.send_timesync()
                next_sync = now + 1.0 / self.args.sync_hz
            if now >= next_report:
                self.report()
                next_report += 1.0
            if self.args.duration and now - self.t0 > self.args.duration:
                break


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device", required=True, help="serial port or pymavlink URL (udpin:..., tcp:...)")
    ap.add_argument("--baud", type=int, default=57600)
    ap.add_argument("--band", type=int, choices=(433, 868, 915), default=433, help="radio band [MHz] for the log")
    ap.add_argument("--csv", help="write 1 Hz link statistics to this CSV file")
    ap.add_argument("--duration", type=float, default=0, help="stop after N seconds (0 = forever)")
    ap.add_argument("--sync-hz", type=float, default=2.0, help="TIMESYNC request rate")
    ap.add_argument("--gcs-sysid", type=int, default=254)
    args = ap.parse_args(argv)
    try:
        LinkMonitor(args).run()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
