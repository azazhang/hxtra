#!/usr/bin/env python3
"""Analyze real METRO-LEDSYNC-M4LEDTRACE-R01 HWKNOB01 M4 LED command data.

Only read-only, deduplicated, exact-sequence event data. Timestamp arithmetic
uses unsigned 32-bit modulo for the M4 1-us clock; stable windows are explicitly
defined AFTER inspecting the recorded series and are reproducible, not inferred
causally from unknown user knob-event times.

Usage:
  python tools/analyze_metro_ledtrace_r01.py INPUT.jsonl [--out REPORT.json]
"""
import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

VARIANT="METRO-LEDSYNC-M4LEDTRACE-R01"
# Identified stable runs in the physical trace (inclusive rising edge seq).
# Manually selected from clear successive ON-to-ON period plateaus.
WINDOWS=(
    ("110 BPM before edits",381,815),
    ("103 BPM",831,845),
    ("94 BPM",853,871),
    ("69 BPM",883,895),
    ("56 BPM",907,917),
    ("165 BPM after edits",939,999),
)

def delta_us(later,earlier):
    return (later-earlier)&0xffffffff

def clock_fit(timestamps):
    if len(timestamps)<3:
        raise ValueError("at least 3 rising edges required")
    # OLS time = intercept + beat_index*period; residuals are an explicit
    # descriptive timing metric, not an optical latency or audio phase test.
    n=len(timestamps)
    mx=(n-1)/2
    my=statistics.mean(timestamps)
    slope=sum((i-mx)*(v-my) for i,v in enumerate(timestamps))/sum((i-mx)**2 for i in range(n))
    alpha=my-slope*mx
    residuals=[(v-alpha-slope*i)*1000 for i,v in enumerate(timestamps)]
    intervals=[(b-a)*1000 for a,b in zip(timestamps,timestamps[1:])]
    return dict(beats=n,intervals=n-1,
        fitted_period_ms=round(slope*1000,6),
        fitted_bpm=round(60/slope,4),
        mean_consecutive_period_ms=round(statistics.mean(intervals),6),
        sd_consecutive_period_ms=round(statistics.stdev(intervals),6),
        rms_phase_residual_ms=round(math.sqrt(statistics.mean(v*v for v in residuals)),6),
        max_abs_phase_residual_ms=round(max(abs(v) for v in residuals),6),
        first_fit_residual_ms=round(residuals[0],6),
        last_fit_residual_ms=round(residuals[-1],6))

def analyze(path):
    path=Path(path)
    raw=path.read_bytes()
    rows=[json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    if not rows:
        raise ValueError("empty trace")
    assert all(r.get("revision")==VARIANT for r in rows if "revision" in r), "wrong image"
    invalid=[(i,r.get("invalid_sample")) for i,r in enumerate(rows) if "invalid_sample" in r]
    records={}; conflicting=[]
    for i,row in enumerate(rows):
        for e in row.get("events",[]):
            seq=e["sequence"]
            rec=(e["timestamp_us_u32"],e["led_lit"])
            if seq in records and records[seq]!=rec:
                conflicting.append((i,seq,records[seq],rec))
            records[seq]=rec
    if not records:raise ValueError("no LED events")
    if conflicting:raise ValueError(f"conflicting records: {conflicting[:5]}")
    seqs=sorted(records)
    missing=[i for i in range(seqs[0],seqs[-1]+1) if i not in records]
    states=[records[k][1] for k in seqs]
    state_collisions=[(a,b) for a,b in zip(seqs,seqs[1:]) if records[a][1]==records[b][1]]
    # Use first observed M4 tick as relative time reference.
    base=records[seqs[0]][0]
    rel={k:delta_us(records[k][0],base)/1e6 for k in seqs}
    def rising_times(start,end):
        return [rel[k] for k in seqs if start<=k<=end and records[k][1]]
    stable=[]
    for label,low,high in WINDOWS:
        v=rising_times(low,high)
        stable.append({"name":label,"seq_range":[low,high],
            "first_on_rel_s":round(v[0],3),
            "last_on_rel_s":round(v[-1],3),
            **clock_fit(v)})
    trans=[]
    for k in seqs[1:]:
        if records[k][1] and not records[k-1][1]:
            off_on=delta_us(records[k][0],records[k-1][0])/1000
            if off_on<=20:
                trans.append({"on_sequence":k,"on_rel_s":round(rel[k],6),
                    "preceding_dark_gap_ms":round(off_on,6)})
    ons=[k for k in seqs if records[k][1]]
    full=[delta_us(records[b][0],records[a][0])/1000 for a,b in zip(ons,ons[1:])]
    # The first visibly displaced ON after the 110-BPM plateau:
    # seq815 at old phase, seq817 at new schedule.
    first_jump_ms=delta_us(records[817][0],records[815][0])/1000
    expected_old_period_ms=stable[0]["fitted_period_ms"]
    return {
        "name":"METRO-LEDSYNC-M4LEDTRACE-R01-HWKNOB01",
        "source":path.name,
        "source_sha256":hashlib.sha256(raw).hexdigest(),
        "observational_limit":"M4 LED colour/command after visibility filter, before optical ring; no sound waveform",
        "usb_samples":len(rows),
        "host_sample_elapsed_s":round(rows[-1]["host_monotonic_s"]-rows[0]["host_monotonic_s"],6),
        "invalid_samples":invalid,
        "duplicated_record_conflicts":conflicting,
        "edge_count":len(seqs),
        "sequence_range":[seqs[0],seqs[-1]],
        "missing_sequences":missing,
        "nonalternating_adjacent_edges":state_collisions,
        "on_count":sum(states),
        "off_count":len(states)-sum(states),
        "complete_on_to_on_intervals":len(full),
        "min_on_to_on_ms":round(min(full),6),
        "max_on_to_on_ms":round(max(full),6),
        "stable_segments":stable,
        "off_to_on_under_20ms":trans,
        "first_transition": {
            "old_phase_last_on_sequence":815,
            "new_phase_first_on_sequence":817,
            "observed_on_to_on_ms":round(first_jump_ms,6),
            "old_fitted_period_ms":expected_old_period_ms,
            "phase_discontinuity_vs_old_period_ms":round(first_jump_ms-expected_old_period_ms,6),
            "cannot_infer_user_knob_exact_time":True,
        },
    }

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source",type=Path)
    ap.add_argument("--out",type=Path)
    args=ap.parse_args()
    report=analyze(args.source)
    out=json.dumps(report,indent=2)+"\n"
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(out)
    print(out,end="")

if __name__=="__main__":
    main()
