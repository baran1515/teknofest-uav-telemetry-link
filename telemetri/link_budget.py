#!/usr/bin/env python3
"""Free-space link budget: 433 MHz vs 915 MHz telemetry.

Prints received power, link margin and first-Fresnel-zone radius for a set
of distances. Default values are typical for 100 mW SiK-class radios with
2.15 dBi dipoles; replace them with the datasheet values of your modules.

  python -m telemetri.link_budget --dist 0.5 1 2 5 10
"""
from __future__ import annotations

import argparse

from telemetri.linkstats import fresnel_radius_m, fspl_db, link_margin_db


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bands", type=float, nargs="+", default=[433.0, 915.0])
    ap.add_argument("--dist", type=float, nargs="+", default=[0.5, 1, 2, 3, 5, 8])
    ap.add_argument("--tx-dbm", type=float, default=20.0, help="transmit power (20 dBm = 100 mW)")
    ap.add_argument("--gtx", type=float, default=2.15, help="air antenna gain dBi")
    ap.add_argument("--grx", type=float, default=2.15, help="ground antenna gain dBi")
    ap.add_argument("--cable", type=float, default=1.0, help="total cable/connector loss dB")
    ap.add_argument("--sens", type=float, default=-108.0,
                    help="receiver sensitivity at the chosen air rate [dBm]")
    args = ap.parse_args(argv)

    print(f"Tx {args.tx_dbm} dBm, Gtx {args.gtx} dBi, Grx {args.grx} dBi, "
          f"cable {args.cable} dB, sensitivity {args.sens} dBm\n")
    print(f"{'MHz':>6} {'km':>6} {'FSPL dB':>8} {'Rx dBm':>8} {'margin dB':>10} {'Fresnel r m':>12}")
    for f in args.bands:
        for d in args.dist:
            loss = fspl_db(d, f)
            margin = link_margin_db(args.tx_dbm, args.gtx, args.grx, args.cable, d, f, args.sens)
            rx = args.sens + margin
            flag = "" if margin >= 10 else "  <-- < 10 dB fade margin"
            print(f"{f:>6.0f} {d:>6.1f} {loss:>8.1f} {rx:>8.1f} {margin:>10.1f} "
                  f"{fresnel_radius_m(d, f):>12.1f}{flag}")
        print()
    print("Not: 433 MHz aynı mesafede ~6.5 dB daha az serbest uzay kaybına sahiptir,\n"
          "ancak Fresnel bölgesi daha geniştir (yerden yükseklik daha kritik) ve anten boyu büyüktür.")


if __name__ == "__main__":
    main()
