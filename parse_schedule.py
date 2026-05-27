"""
Parse a schedule image with Claude Vision → update docs/schedule.json → rebuild HTML.

Usage:
    python parse_schedule.py <image_path>

The image can be a screenshot, photo of a printed schedule, or any common format.
Claude will extract all shifts and merge them into docs/schedule.json.
"""

import base64
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from anthropic import Anthropic

CST          = timezone(timedelta(hours=-6))
SCHEDULE_FILE = Path(__file__).parent / "docs" / "schedule.json"

client = Anthropic()


def parse_image(image_path: str) -> list[dict]:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    suffix = path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png",  ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = media_types.get(suffix, "image/jpeg")

    with open(path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    today = datetime.now(CST).strftime("%Y-%m-%d")
    year  = datetime.now(CST).year

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data,
                    },
                },
                {
                    "type": "text",
                    "text": f"""Parse this staff work schedule image. Today is {today}.

Extract every shift you can see. Return a JSON array only — no explanation, no markdown fences.

Format each shift exactly like this:
[
  {{
    "date": "YYYY-MM-DD",
    "name": "Full Name",
    "start": "9:00 AM",
    "end": "5:00 PM",
    "role": "Budtender"
  }}
]

Rules:
- Use {year} as the year unless the schedule clearly shows a different year
- If no role/position is shown, use "Staff"
- Use 12-hour time format with AM/PM
- If you cannot determine a date, skip that shift
- Return ONLY the JSON array, nothing else""",
                },
            ],
        }],
    )

    content = response.content[0].text.strip()
    # Strip markdown fences if present
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1]).strip()

    return json.loads(content)


def merge_shifts(existing: list[dict], new_shifts: list[dict]) -> list[dict]:
    """Merge new shifts in, replacing any existing shifts for the same date+name combo."""
    # Remove existing shifts that overlap with new ones (same date + name)
    new_keys = {(s["date"], s["name"]) for s in new_shifts}
    kept = [s for s in existing if (s["date"], s["name"]) not in new_keys]
    merged = kept + new_shifts
    merged.sort(key=lambda s: (s["date"], s.get("start", ""), s.get("name", "")))
    return merged


def main():
    if len(sys.argv) < 2:
        print("Usage: python parse_schedule.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]
    print(f"Parsing schedule from: {image_path}")

    print("Sending to Claude Vision...")
    new_shifts = parse_image(image_path)
    print(f"Extracted {len(new_shifts)} shifts")

    # Load existing schedule
    schedule = {"shifts": [], "last_updated": None}
    if SCHEDULE_FILE.exists():
        with open(SCHEDULE_FILE) as f:
            schedule = json.load(f)

    # Merge
    schedule["shifts"] = merge_shifts(schedule.get("shifts", []), new_shifts)
    schedule["last_updated"] = datetime.now(CST).isoformat()

    # Save
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(schedule, f, indent=2)
    print(f"Saved → {SCHEDULE_FILE}  ({len(schedule['shifts'])} total shifts)")

    # Rebuild HTML
    print("Rebuilding HTML...")
    import build_preview
    build_preview.build()
    print("Done. Commit docs/schedule.json and docs/index.html to publish.")


if __name__ == "__main__":
    main()
