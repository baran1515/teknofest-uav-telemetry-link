#!/usr/bin/env python3
"""Bench-test MAVLink source: imitates an ArduPilot vehicle behind a SiK radio.

Used to test the monitor / analyser on a desk without aircraft or radios.
The vehicle flies an outbound spiral, so distance grows and the modelled
signal level falls with free-space path loss; packets are dropped with a
probability that rises as SNR approaches zero. **All numbers produced by this
script are synthetic** and only exercise the tooling.

  python -m telemetri.fake_vehicle --out tcpin:127.0.0.1:5770 --band 915
  python -m telemetri.monitor --device tcp:127.0.0.1:5770 --band 915
"""
from __future__ import annotations

import argparse
import math
import random
import time

from pymavlink import mavutil
from pymavlink.dialects.v20 import ardupilotmega as mavlink2

from telemetri.linkstats import SIK_OFFSET_DBM, SIK_SCALE, fspl_db

HOME = (39.9208, 32.8541)  # arbitrary reference point (Ankara)


def dbm_to_sik_raw(dbm: float) -> int:
    return max(0, min(255, int(round((dbm - SIK_OFFSET_DBM) * SIK_SCALE))))


class FakeVehicle:
    def __init__(self, args):
        self.args = args
        self.mav = mavutil.mavlink_connection(args.out, source_system=1, source_component=1,
                                              dialect="ardupilotmega")
        self.t0 = time.time()
        self.rng = random.Random(args.seed)
        self.sent = 0
        self.dropped = 0
        self.snr_db = 40.0

    # -- channel model --------------------------------------------------------
    def distance_m(self, t):
        return min(self.args.max_dist, 20 + self.args.speed * t)

    def channel(self, t):
        d_km = self.distance_m(t) / 1000.0
        rx = self.args.tx_dbm + 2 * self.args.ant_dbi - fspl_db(d_km, self.args.band)
        rx += self.rng.gauss(0, 2.0)  # fading
        noise = self.args.noise_dbm + self.rng.gauss(0, 1.0)
        return rx, noise

    def should_drop(self):
        # base loss + steep increase below ~10 dB SNR
        p = self.args.loss / 100.0 + 1.0 / (1.0 + math.exp((self.snr_db - 6.0) / 1.5))
        return self.rng.random() < p

    def send(self, msg):
        self.sent += 1
        if self.should_drop():
            # still consume a sequence number like a real lost packet
            self.mav.mav.seq = (self.mav.mav.seq + 1) % 256
            self.dropped += 1
            return
        self.mav.mav.send(msg)

    # -- loop -------------------------------------------------------------
    def run(self):
        m = self.mav.mav
        tick = 0
        period = 0.02  # 50 Hz scheduler
        while True:
            t = time.time() - self.t0
            if self.args.duration and t > self.args.duration:
                break
            rx, noise = self.channel(t)
            self.snr_db = rx - noise

            if tick % 50 == 0:
                self.send(m.heartbeat_encode(mavutil.mavlink.MAV_TYPE_QUADROTOR,
                                             mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
                                             mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, 3, 4))
                raw_rssi, raw_noise = dbm_to_sik_raw(rx), dbm_to_sik_raw(noise)
                # real SiK radios inject RADIO_STATUS themselves; here it shares the stream
                self.send(mavlink2.MAVLink_radio_status_message(
                    raw_rssi, raw_rssi - 2, 80, raw_noise, raw_noise + 1, self.dropped & 0xFFFF, 0))
            if tick % 5 == 0:  # 10 Hz
                self.send(m.attitude_encode(int(t * 1000), 0.05 * math.sin(t), 0.03 * math.cos(t),
                                            t % 6.28, 0, 0, 0))
            if tick % 10 == 0:  # 5 Hz
                d = self.distance_m(t)
                ang = t * 0.1
                lat = HOME[0] + (d * math.cos(ang)) / 111319.5
                lon = HOME[1] + (d * math.sin(ang)) / (111319.5 * math.cos(math.radians(HOME[0])))
                self.send(m.global_position_int_encode(int(t * 1000), int(lat * 1e7), int(lon * 1e7),
                                                       int(950e3), int(80e3), 0, 0, 0, 0))

            # answer TIMESYNC requests (like ArduPilot does)
            req = self.mav.recv_match(type="TIMESYNC", blocking=False)
            while req is not None:
                if req.tc1 == 0:
                    time.sleep(self.args.latency_ms / 2000.0)
                    self.send(m.timesync_encode(time.monotonic_ns(), req.ts1))
                req = self.mav.recv_match(type="TIMESYNC", blocking=False)

            tick += 1
            time.sleep(period)
        print(f"fake vehicle: sent={self.sent} dropped={self.dropped} "
              f"({100 * self.dropped / max(1, self.sent):.2f}%)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="tcpin:127.0.0.1:5770")
    ap.add_argument("--band", type=int, default=433)
    ap.add_argument("--tx-dbm", type=float, default=20.0)
    ap.add_argument("--ant-dbi", type=float, default=2.15)
    ap.add_argument("--noise-dbm", type=float, default=-117.0)
    ap.add_argument("--speed", type=float, default=15.0, help="outbound speed m/s")
    ap.add_argument("--max-dist", type=float, default=3000.0)
    ap.add_argument("--loss", type=float, default=0.5, help="base packet loss %%")
    ap.add_argument("--latency-ms", type=float, default=40.0, help="modelled air RTT")
    ap.add_argument("--duration", type=float, default=0)
    ap.add_argument("--seed", type=int, default=1)
    FakeVehicle(ap.parse_args(argv)).run()


if __name__ == "__main__":
    main()
