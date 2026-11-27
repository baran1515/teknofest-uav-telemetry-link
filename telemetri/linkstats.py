"""Link-quality primitives used by the monitor and the offline analyser.

Everything in this module is pure Python (no pymavlink, no I/O) so it can be
unit-tested and reused on the ground station or in post-processing.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# MAVLink sequence-number based packet loss
# --------------------------------------------------------------------------


class SeqLossTracker:
    """Counts lost MAVLink packets per (sysid, compid) from the 8-bit `seq`.

    MAVLink increments `seq` by one for every packet a component sends, so a
    jump of k > 1 means k-1 packets were lost on the way. A jump larger than
    `reset_gap` (default 128, i.e. half the ring) is treated as a sender
    reboot/stream reset instead of 200+ lost packets.
    """

    def __init__(self, reset_gap: int = 128):
        self.reset_gap = reset_gap
        self._last: dict[tuple[int, int], int] = {}
        self.received = 0
        self.lost = 0
        self.resets = 0

    def update(self, sysid: int, compid: int, seq: int) -> int:
        """Register one packet. Returns the number of packets lost before it."""
        key = (sysid, compid)
        self.received += 1
        last = self._last.get(key)
        self._last[key] = seq
        if last is None:
            return 0
        gap = (seq - last - 1) & 0xFF
        if gap >= self.reset_gap:
            self.resets += 1
            return 0
        self.lost += gap
        return gap

    @property
    def loss_pct(self) -> float:
        total = self.received + self.lost
        return 100.0 * self.lost / total if total else 0.0


# --------------------------------------------------------------------------
# SiK radio (RFD900 / 3DR / Holybro) RADIO_STATUS conversion
# --------------------------------------------------------------------------
# SiK firmware reports RSSI and noise as raw register values (0..255).
# For the Si1000 based radios the documented approximation is
#     signal_dBm ~= raw / 1.9 - 127
# and the "fade margin" / SNR is therefore (rssi - noise) / 1.9 dB.

SIK_SCALE = 1.9
SIK_OFFSET_DBM = -127.0


def sik_raw_to_dbm(raw: int) -> float:
    return raw / SIK_SCALE + SIK_OFFSET_DBM


def sik_snr_db(rssi_raw: int, noise_raw: int) -> float:
    return (rssi_raw - noise_raw) / SIK_SCALE


def link_grade(snr_db: float) -> str:
    """Rough operator-facing grade used on the ground-station dashboard."""
    if snr_db >= 30:
        return "EXCELLENT"
    if snr_db >= 20:
        return "GOOD"
    if snr_db >= 10:
        return "MARGINAL"
    return "CRITICAL"


# --------------------------------------------------------------------------
# Rolling statistics
# --------------------------------------------------------------------------


@dataclass
class Rolling:
    """Fixed-size window with mean / min / max / percentile."""

    size: int = 200
    _buf: deque = field(default_factory=deque)

    def add(self, value: float) -> None:
        self._buf.append(value)
        if len(self._buf) > self.size:
            self._buf.popleft()

    def __len__(self) -> int:
        return len(self._buf)

    @property
    def mean(self) -> float:
        return sum(self._buf) / len(self._buf) if self._buf else math.nan

    @property
    def min(self) -> float:
        return min(self._buf) if self._buf else math.nan

    @property
    def max(self) -> float:
        return max(self._buf) if self._buf else math.nan

    def percentile(self, p: float) -> float:
        return percentile(list(self._buf), p)


def percentile(values: list[float], p: float) -> float:
    """Linear-interpolated percentile (same as numpy's default)."""
    if not values:
        return math.nan
    s = sorted(values)
    k = (len(s) - 1) * p / 100.0
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return float(s[int(k)])
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


# --------------------------------------------------------------------------
# Link budget (free-space)
# --------------------------------------------------------------------------


def fspl_db(distance_km: float, freq_mhz: float) -> float:
    """Free-space path loss in dB."""
    return 20 * math.log10(distance_km) + 20 * math.log10(freq_mhz) + 32.44


def fresnel_radius_m(distance_km: float, freq_mhz: float) -> float:
    """Radius of the first Fresnel zone at mid-path, metres."""
    wavelength = 299.792458 / freq_mhz
    d = distance_km * 1000.0
    return math.sqrt(wavelength * (d / 2) * (d / 2) / d)


def link_margin_db(tx_dbm: float, gtx_dbi: float, grx_dbi: float, cable_loss_db: float,
                   distance_km: float, freq_mhz: float, sensitivity_dbm: float) -> float:
    rx = tx_dbm + gtx_dbi + grx_dbi - cable_loss_db - fspl_db(distance_km, freq_mhz)
    return rx - sensitivity_dbm
