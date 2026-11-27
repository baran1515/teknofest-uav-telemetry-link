#!/usr/bin/env python3
"""Upload a waypoint mission over a lossy telemetry link and verify it.

Implements the MAVLink mission micro-service from the ground-station side:

    GCS                        Vehicle
     |---- MISSION_COUNT(n) ---->|
     |<--- MISSION_REQUEST_INT(0)|
     |---- MISSION_ITEM_INT(0) ->|
     |            ...            |
     |<--- MISSION_ACK ----------|

Every step has a timeout and is retried (the vehicle re-requests items it
did not get, the GCS re-sends MISSION_COUNT if nothing comes back). After the
upload the mission is downloaded again and compared item by item.

Waypoint file (CSV):  lat,lon,alt_m   one line per waypoint, '#' comments.

  python -m telemetri.mission_upload --device udpin:0.0.0.0:14551 --wp config/example_mission.csv
"""
from __future__ import annotations

import argparse
import time

from pymavlink import mavutil

MAV = mavutil.mavlink


def load_waypoints(path):
    wps = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if line:
                lat, lon, alt = (float(x) for x in line.split(","))
                wps.append((lat, lon, alt))
    return wps


def build_items(conn, wps):
    """Item 0 = home placeholder (ArduPilot convention), then TAKEOFF + WAYPOINTs."""
    ts, tc = conn.target_system, conn.target_component
    items = [MAV.MAVLink_mission_item_int_message(ts, tc, 0, MAV.MAV_FRAME_GLOBAL, MAV.MAV_CMD_NAV_WAYPOINT,
                                                  0, 1, 0, 0, 0, 0, int(wps[0][0] * 1e7),
                                                  int(wps[0][1] * 1e7), 0)]
    items.append(MAV.MAVLink_mission_item_int_message(ts, tc, 1, MAV.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                                                      MAV.MAV_CMD_NAV_TAKEOFF, 0, 1, 0, 0, 0, 0,
                                                      0, 0, wps[0][2]))
    for i, (lat, lon, alt) in enumerate(wps, start=2):
        items.append(MAV.MAVLink_mission_item_int_message(ts, tc, i, MAV.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                                                          MAV.MAV_CMD_NAV_WAYPOINT, 0, 1, 0, 2, 0, 0,
                                                          int(lat * 1e7), int(lon * 1e7), alt))
    return items


def upload(conn, items, timeout=2.0, max_retries=10):
    ts, tc = conn.target_system, conn.target_component
    retries = 0
    conn.mav.mission_count_send(ts, tc, len(items), MAV.MAV_MISSION_TYPE_MISSION)
    sent = set()
    while True:
        msg = conn.recv_match(type=["MISSION_REQUEST_INT", "MISSION_REQUEST", "MISSION_ACK"],
                              blocking=True, timeout=timeout)
        if msg is None:
            retries += 1
            if retries > max_retries:
                raise TimeoutError("mission upload: no response from vehicle")
            print(f"  timeout, re-sending MISSION_COUNT (retry {retries})")
            conn.mav.mission_count_send(ts, tc, len(items), MAV.MAV_MISSION_TYPE_MISSION)
            continue
        if msg.get_type() == "MISSION_ACK":
            if msg.type != MAV.MAV_MISSION_ACCEPTED:
                raise RuntimeError(f"vehicle rejected mission: ack type {msg.type}")
            return retries
        seq = msg.seq
        if seq in sent:
            retries += 1  # vehicle asked again: our item was lost on the link
        conn.mav.send(items[seq])
        sent.add(seq)
        print(f"  sent item {seq}/{len(items) - 1}")


def download(conn, timeout=2.0, max_retries=10):
    ts, tc = conn.target_system, conn.target_component
    conn.mav.mission_request_list_send(ts, tc, MAV.MAV_MISSION_TYPE_MISSION)
    msg = conn.recv_match(type="MISSION_COUNT", blocking=True, timeout=timeout)
    if msg is None:
        raise TimeoutError("no MISSION_COUNT")
    items = []
    for seq in range(msg.count):
        for _ in range(max_retries):
            conn.mav.mission_request_int_send(ts, tc, seq, MAV.MAV_MISSION_TYPE_MISSION)
            item = conn.recv_match(type="MISSION_ITEM_INT", blocking=True, timeout=timeout)
            if item is not None and item.seq == seq:
                items.append(item)
                break
        else:
            raise TimeoutError(f"item {seq} not received")
    conn.mav.mission_ack_send(ts, tc, MAV.MAV_MISSION_ACCEPTED, MAV.MAV_MISSION_TYPE_MISSION)
    return items


def verify(sent, got):
    if len(sent) != len(got):
        return [f"count mismatch {len(sent)} != {len(got)}"]
    errors = []
    for a, b in zip(sent[1:], got[1:]):  # item 0 (home) is overwritten by the vehicle
        if (a.command, a.x, a.y) != (b.command, b.x, b.y) or abs(a.z - b.z) > 0.01:
            errors.append(f"item {a.seq} differs")
    return errors


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device", required=True)
    ap.add_argument("--baud", type=int, default=57600)
    ap.add_argument("--wp", required=True, help="CSV waypoint file")
    args = ap.parse_args(argv)

    conn = mavutil.mavlink_connection(args.device, baud=args.baud, source_system=254)
    conn.wait_heartbeat(timeout=30)
    items = build_items(conn, load_waypoints(args.wp))
    t0 = time.time()
    retries = upload(conn, items)
    print(f"upload OK: {len(items)} items, {retries} retries, {time.time() - t0:.1f} s")
    errors = verify(items, download(conn))
    print("verify:", "OK" if not errors else errors)


if __name__ == "__main__":
    main()
