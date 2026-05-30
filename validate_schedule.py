"""
Run after entering any new schedule data:
    python validate_schedule.py

Flags entries that are likely parsing errors so you can verify
against the source image before publishing.
"""
import json, re
from pathlib import Path
from collections import defaultdict

DATA = Path(__file__).parent / "docs" / "schedule.json"

# Store's standard shift boundary — doubles split here
SPLIT_POINTS = {240, 270}  # 4:00 PM = 240 min past noon, 4:30 PM = 270

def to_min(t):
    m = re.match(r'(\d+):(\d+)\s*(AM|PM)', t, re.I)
    if not m:
        return None
    h, mn, ampm = int(m[1]), int(m[2]), m[3].upper()
    if ampm == 'PM' and h != 12: h += 12
    if ampm == 'AM' and h == 12: h = 0
    return h * 60 + mn

def run():
    with open(DATA) as f:
        data = json.load(f)

    shifts = data.get("shifts", [])
    warnings = []

    by_dp = defaultdict(list)
    for s in shifts:
        by_dp[(s["date"], s["name"])].append(s)

    for (date, name), day_shifts in sorted(by_dp.items()):
        for s in day_shifts:
            start = to_min(s["start"])
            end   = to_min(s["end"])
            if start is None or end is None:
                warnings.append(f"  ⚠  {date} {name}: unparseable time '{s['start']} – {s['end']}'")
                continue

            hours = (end - start) / 60

            # ── Long single shift — possible merged double ──
            # A real double would be two ~5h blocks split at 4pm.
            # If a single entry is >9h AND its midpoint is within 30 min of 4pm,
            # it's very likely two shifts read as one.
            if len(day_shifts) == 1 and hours >= 9:
                midpoint_min = (start + end) // 2
                noon = 12 * 60
                mid_rel = midpoint_min - noon   # minutes past noon
                near_split = any(abs(mid_rel - sp) <= 45 for sp in SPLIT_POINTS)
                if near_split:
                    mid_h = midpoint_min // 60
                    mid_m = midpoint_min % 60
                    mid_ampm = "PM" if mid_h >= 12 else "AM"
                    if mid_h > 12: mid_h -= 12
                    warnings.append(
                        f"  ⚠  POSSIBLE MERGED DOUBLE — {date} {name}: "
                        f"{s['start']} – {s['end']} ({hours:.1f}h). "
                        f"Midpoint ~{mid_h}:{mid_m:02d} {mid_ampm}. "
                        f"Verify image: may be two shifts."
                    )
                else:
                    warnings.append(
                        f"  ℹ  LONG SHIFT — {date} {name}: "
                        f"{s['start']} – {s['end']} ({hours:.1f}h). "
                        f"Probably legitimate but worth a glance."
                    )

    # ── Gaps between consecutive shifts for same person on same day ──
    # If person A has 9:30am-4pm and 4:30pm-9:30pm there may be a missing
    # half-hour shift, or the end time was mis-read.
    for (date, name), day_shifts in sorted(by_dp.items()):
        if len(day_shifts) < 2:
            continue
        sorted_s = sorted(day_shifts, key=lambda x: to_min(x["start"]) or 0)
        for i in range(len(sorted_s) - 1):
            end_a   = to_min(sorted_s[i]["end"])
            start_b = to_min(sorted_s[i + 1]["start"])
            if end_a is None or start_b is None:
                continue
            gap = start_b - end_a
            if gap > 30:
                warnings.append(
                    f"  ⚠  GAP IN DOUBLE — {date} {name}: "
                    f"shift 1 ends {sorted_s[i]['end']}, "
                    f"shift 2 starts {sorted_s[i+1]['start']} "
                    f"({gap} min gap). Check for typo."
                )

    # ── Report ──
    if not warnings:
        print(f"✅  Schedule looks clean — {len(shifts)} shifts, no issues detected.")
    else:
        print(f"🔍  {len(warnings)} item(s) to verify against source image:\n")
        for w in warnings:
            print(w)
        print(f"\nTotal shifts: {len(shifts)}")

if __name__ == "__main__":
    run()
