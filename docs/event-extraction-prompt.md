# Event extraction prompt

Paste this prompt together with a photo (a daycare year calendar, an
appointment email, a flyer) into any chat model. Paste the JSON it returns into
the **Add events** tab on `/admin`. The server validates the same schema, so the
prompt and the importer are one contract — change one, change the other.

Fill the two bracketed lines; leave the rest exactly as is.

---

```
You are extracting calendar events from an image for a family wall dashboard.
Today is [YYYY-MM-DD]. The person this image is about is [Prisha | Prapti | Family | unknown].

Return ONLY a JSON array, no prose, no markdown fences. One object per event:

{
  "person":      "prisha" | "prapti" | "family" | null,
  "kind":        "closed" | "early_close" | "appointment" | "event",
  "title":       string,            // short, as printed, without CLOSED / time suffixes
  "date":        "YYYY-MM-DD",
  "end_date":    "YYYY-MM-DD" | null,   // only for multi-day ranges
  "all_day":     true | false,
  "start_time":  "HH:MM" | null,    // 24h
  "end_time":    "HH:MM" | null,
  "location":    string | null,     // place name + address on one line
  "notes":       string | null,     // provider, phone, anything else useful
  "supersedes":  {"date":"YYYY-MM-DD","start_time":"HH:MM"|null} | null,
  "confidence":  "high" | "medium" | "low"
}

Rules:
- person: use the person given above. If the image itself names a person
  ("A visit for Prapti"), use that instead. If neither, null.
- kind "closed" ONLY when the word CLOSED (or "no school", "no daycare") appears
  for that day. "early_close" when it says closes early / closes at a time / early
  dismissal; put the time in start_time. "appointment" for medical, dental, or
  any scheduled visit with a provider. Everything else is "event".
- Take the year from the nearest month heading, not the page title. If a line
  prints its own year (e.g. "January 1, 2027"), use that.
- A range like "10th–14th" is ONE event with date and end_date.
- A month marked "No Events" produces nothing.
- Combined lines ("CLOSED / Teacher Workday", "CLOSED – Teacher Workday &
  Parent/Teacher Conferences") are ONE "closed" event; keep the reason in title.
- all_day is true unless a clock time is printed.
- If the image says rescheduled/moved and shows previous details, fill
  "supersedes" with the OLD date/time, and date/start_time with the NEW one.
- Keep titles short enough for a calendar chip (under ~40 characters).
  Do not include the person's name in the title.
- Include past dates; the importer decides whether to keep them.
- confidence "low" if any digit or month was hard to read. Never guess a
  missing year or day — omit the event and mention it in a final object
  {"skipped": "reason"} instead.
- Output nothing but the JSON array.
```

---

## Worked examples

### Daycare year calendar (Kiddie Academy, "2026 Academic Calendar")

Selected rows the prompt should produce — note the year rollover on the last
one, the range, and that "Center Closes at 12:00" is `early_close`, not `closed`:

```json
[
  {"person":"prapti","kind":"closed","title":"Thanksgiving Day","date":"2026-11-26","end_date":null,"all_day":true,"start_time":null,"end_time":null,"location":null,"notes":null,"supersedes":null,"confidence":"high"},
  {"person":"prapti","kind":"closed","title":"Indigenous Peoples' Day – Teacher Workday","date":"2026-10-12","end_date":null,"all_day":true,"start_time":null,"end_time":null,"location":null,"notes":"Parent/Teacher Conferences","supersedes":null,"confidence":"high"},
  {"person":"prapti","kind":"early_close","title":"Family Luncheon","date":"2026-11-25","end_date":null,"all_day":false,"start_time":"12:00","end_time":null,"location":null,"notes":"Center closes at 12:00","supersedes":null,"confidence":"high"},
  {"person":"prapti","kind":"event","title":"Back to School Blast","date":"2026-08-10","end_date":"2026-08-14","all_day":true,"start_time":null,"end_time":null,"location":null,"notes":null,"supersedes":null,"confidence":"high"},
  {"person":"prapti","kind":"event","title":"Parent/Teacher Conferences","date":"2026-04-22","end_date":null,"all_day":true,"start_time":null,"end_time":null,"location":null,"notes":null,"supersedes":null,"confidence":"high"},
  {"person":"prapti","kind":"closed","title":"New Year's Day","date":"2027-01-01","end_date":null,"all_day":true,"start_time":null,"end_time":null,"location":null,"notes":null,"supersedes":null,"confidence":"high"}
]
```

### Rescheduled appointment email (phone screenshot)

```json
[
  {"person":"prapti","kind":"appointment","title":"Well Child","date":"2026-11-10","end_date":null,"all_day":false,"start_time":"08:40","end_time":null,"location":"Atrium Health Levine Children's Rocky River Peds, 5427 NC Highway 49 S, Suite 103, Harrisburg NC 28075","notes":"Geetika Gupta, MD · 704-455-5565 · rescheduled","supersedes":{"date":null,"start_time":null},"confidence":"high"}
]
```

The screenshot cut off the "Previous Details" section, so `supersedes` has
nulls; a full screenshot fills them and the importer offers to delete the old
appointment.

## How the importer uses this

- `person` → `extendedProperties.private.person` on the Google event (the
  dashboard's person tag; name-in-title is only the fallback for hand-entered
  events).
- `kind` → `extendedProperties.private.kind`, and folded into the title wording
  so the ICS-side keyword categories still fire: `closed` → "Daycare closed –
  Thanksgiving Day" (holiday category), `early_close` → "Closes 12:00 – Family
  Luncheon" (early-dismissal category).
- Event id is derived from `person|date|title`, so pasting the same JSON twice
  adds nothing.
- Rows dated before today are shown unchecked by default.
