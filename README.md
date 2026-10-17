# TMS course registrations

A daily snapshot of the public KnowledgeTree course schedule
(<https://tms.ktree.com.sg/CourseSchedule/Index>), used to track how many
places are taken in each course session over time.

## How it works

1. **GitHub Actions** runs `scrape.py` every day at about 7:30 AM Singapore time
   (`.github/workflows/snapshot.yml`). It reads the public schedule page (no
   login, read-only) and commits the result.
2. **Claude** then reads the newest snapshot each morning, compares it with the
   day before, updates the *KTree Course Slot Tracker* dashboard and the Notion
   snapshot page, and sends a summary notification.

## Files

| Path | What it holds |
| --- | --- |
| `data/snapshots/YYYY-MM-DD.json` | One snapshot per day (Singapore date): every listed session and its places remaining. |
| `data/latest.json` | A copy of the most recent snapshot. |

Each row has: `session` (course code · timing · start · end, the key used to
compare days), `code`, `course`, `level`, `timing`, `start`, `end`, `remarks`
and `places` (places remaining).

## Running it by hand

From the **Actions** tab, open *Daily schedule snapshot* and choose
**Run workflow**. Locally: `pip install -r requirements.txt && python scrape.py`.

If a run fails (for example the page layout changed), GitHub emails the repo
owner and no snapshot is committed for that day.
