#!/usr/bin/env python3
"""Read / write SiK telemetry radio parameters with AT commands.

Applies one of the profiles in config/ (e.g. sik_433.txt) to the LOCAL radio
and, with --remote, to the paired radio over the air (RT commands).
Both radios of a pair must end up with identical NETID / AIR_SPEED /
MIN_FREQ / MAX_FREQ / NUM_CHANNELS / ECC / MAVLINK settings.

  python -m telemetri.sik_config --port /dev/ttyUSB0 --show
  python -m telemetri.sik_config --port /dev/ttyUSB0 --profile config/sik_433.txt --remote

requires: pip install pyserial
"""
from __future__ import annotations

import argparse
import time

import serial


def at(ser: serial.Serial, cmd: str, wait: float = 0.3) -> str:
    ser.reset_input_buffer()
    ser.write((cmd + "\r\n").encode())
    time.sleep(wait)
    return ser.read(ser.in_waiting or 1).decode(errors="ignore").strip()


def enter_command_mode(ser: serial.Serial) -> None:
    time.sleep(1.1)              # guard time: no data for 1 s before "+++"
    ser.write(b"+++")
    time.sleep(1.1)
    resp = ser.read(ser.in_waiting or 1).decode(errors="ignore")
    if "OK" not in resp:
        raise RuntimeError(f"radio did not enter AT mode (got {resp!r})")


def load_profile(path: str) -> list[tuple[str, int]]:
    """Profile lines: 'S<n>=<value>  # comment'."""
    items = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            reg, val = line.split("=")
            items.append((reg.strip().upper(), int(val)))
    return items


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=57600)
    ap.add_argument("--profile")
    ap.add_argument("--remote", action="store_true", help="also configure the paired radio (RT)")
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args(argv)

    with serial.Serial(args.port, args.baud, timeout=1) as ser:
        enter_command_mode(ser)
        print(at(ser, "ATI", 0.5))
        if args.show or not args.profile:
            print(at(ser, "ATI5", 1.0))          # all local parameters
            if args.remote:
                print(at(ser, "RTI5", 1.5))
        if args.profile:
            prefixes = ["AT"] + (["RT"] if args.remote else [])
            # remote first: once the local radio changes, the pair loses sync
            for pre in reversed(prefixes):
                for reg, val in load_profile(args.profile):
                    r = at(ser, f"{pre}{reg}={val}")
                    print(f"{pre}{reg}={val:<8} -> {r}")
                print(f"{pre}&W ->", at(ser, f"{pre}&W", 0.5))
            for pre in reversed(prefixes):
                at(ser, f"{pre}Z", 0.5)          # reboot to apply
            print("parameters written, radios rebooting")
        else:
            at(ser, "ATO")                       # back to data mode


if __name__ == "__main__":
    main()
