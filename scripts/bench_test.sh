#!/usr/bin/env bash
# Desk test of the whole tool chain without aircraft or radios:
# fake vehicle (synthetic channel model) -> monitor -> analyze, for 433 and 915 MHz.
# NOTE: the numbers produced here are SYNTHETIC and only validate the tooling.
set -euo pipefail
cd "$(dirname "$0")/.."
DUR=${DUR:-20}
mkdir -p logs/bench reports/bench
port=5770
for band in 433 915; do
  python3 -m telemetri.fake_vehicle --out tcpin:127.0.0.1:$port --band $band \
      --speed 150 --duration $((DUR + 3)) &
  sleep 1
  python3 -m telemetri.monitor --device tcp:127.0.0.1:$port --band $band \
      --csv logs/bench/bench_${band}.csv --duration "$DUR"
  wait
  port=$((port + 1))
done
python3 -m telemetri.analyze logs/bench/*.csv --out reports/bench
