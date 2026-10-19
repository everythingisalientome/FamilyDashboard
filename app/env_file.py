"""A comment-preserving model of a ``.env`` file (pure: text in, text out).

``parse`` keeps every line — comments, blanks, order and line endings — so
``render(parse(text)) == text`` byte for byte, and ``apply`` only touches the
lines it changes. ``schema`` reads ``.env.example`` for the admin page's help
text and sections. Value syntax follows python-dotenv: optional quotes, and an
unquoted value's inline comment starts at whitespace + ``#``.
"""

import re
from dataclasses import dataclass, replace
from datetime import date

_PAIR_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
_RULE_RE = re.compile(r"^#\s*-{4,}\s*$")
KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class Entry:
    """One line. ``raw`` includes its line ending; key/value only for pairs."""

    kind: str  # "comment" | "blank" | "pair"
    key: str
    value: str
    raw: str


def _unquote(rest: str) -> str:
    text = rest.strip()
    if len(text) >= 2 and text[0] in "'\"":
        end = text.find(text[0], 1)
        while end > 0 and text[end - 1] == "\\":
            end = text.find(text[0], end + 1)
        if end > 0:
            inner = text[1:end]
            return inner.replace("\\" + text[0], text[0]).replace("\\\\", "\\")
    return re.split(r"\s+#", text, maxsplit=1)[0].strip()


def parse(text: str) -> list[Entry]:
    """Every line of ``text`` as an Entry, in order."""
    entries: list[Entry] = []
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        match = _PAIR_RE.match(line)
        if match:
            entries.append(Entry("pair", match.group(1), _unquote(match.group(2)), raw))
        elif line.strip():
            entries.append(Entry("comment", "", "", raw))
        else:
            entries.append(Entry("blank", "", "", raw))
    return entries


def render(entries: list[Entry]) -> str:
    return "".join(e.raw for e in entries)


def values(entries: list[Entry]) -> dict[str, str]:
    """Key → value; the last occurrence wins (as in python-dotenv)."""
    return {e.key: e.value for e in entries if e.kind == "pair"}


def quote(value: str) -> str:
    """As-is, unless leading/trailing spaces or '#' need single quotes."""
    if value != value.strip() or "#" in value:
        return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"
    return value


def _eol(entries: list[Entry]) -> str:
    for e in entries:
        if e.raw.endswith("\r\n"):
            return "\r\n"
        if e.raw.endswith("\n"):
            return "\n"
    return "\n"


def apply(
    entries: list[Entry], changes: dict[str, str | None], today: date | None = None
) -> list[Entry]:
    """Update keys in place, drop ``None`` keys, append new keys at the end."""
    eol = _eol(entries)
    seen: set[str] = set()
    out: list[Entry] = []
    for e in entries:
        if e.kind != "pair" or e.key not in changes:
            out.append(e)
            continue
        new = changes[e.key]
        if new is None:
            continue
        seen.add(e.key)
        if new == e.value:
            out.append(e)
            continue
        ending = e.raw[len(e.raw.rstrip("\r\n")):]
        out.append(replace(e, value=new, raw=f"{e.key}={quote(new)}{ending}"))

    added = [k for k, v in changes.items() if v is not None and k not in seen]
    if added:
        if out and not out[-1].raw.endswith(("\n", "\r")):
            out[-1] = replace(out[-1], raw=out[-1].raw + eol)
        stamp = (today or date.today()).isoformat()
        out.append(Entry("blank", "", "", eol))
        out.append(Entry("comment", "", "", f"# Added via /admin {stamp}{eol}"))
        for key in added:
            value = changes[key] or ""
            out.append(Entry("pair", key, value, f"{key}={quote(value)}{eol}"))
    return out


def schema(example: list[Entry]) -> list[dict]:
    """Sections of ``.env.example``: [{title, intro, keys: [{key, default, comment}]}].

    A heading is a single comment line between two ``# ----`` rules. A key's
    comment is the comment block above its run of keys, from after the block's
    last bare ``#``; what comes before that bare ``#`` (or a block that ends at
    a blank line) is the section's intro, if it has none yet.
    """
    sections: list[dict] = [{"title": "General", "intro": "", "keys": []}]
    block: list[str] = []
    run_comment = ""
    opened = False  # just passed an opening rule; a 1-line block is a heading
    for e in example:
        text = e.raw.strip()
        if e.kind == "comment" and _RULE_RE.match(text):
            if opened and len(block) == 1:
                sections.append({"title": block[0].strip(), "intro": "", "keys": []})
                opened = False
            else:
                opened = True
            block, run_comment = [], ""
            continue
        if e.kind == "comment":
            body = text[1:]
            block.append(body[1:] if body.startswith(" ") else body)
            continue
        opened = False
        section = sections[-1]
        fresh = not section["intro"] and not section["keys"]
        if e.kind == "blank":
            if block and fresh:
                section["intro"] = "\n".join(block).strip()
            block, run_comment = [], ""
            continue
        if block:
            cut = max((i for i, b in enumerate(block) if not b.strip()), default=-1)
            if cut >= 0 and fresh:
                section["intro"] = "\n".join(block[:cut]).strip()
            run_comment, block = "\n".join(block[cut + 1:]).strip(), []
        section["keys"].append({"key": e.key, "default": e.value, "comment": run_comment})
    return [s for s in sections if s["keys"]]


def diff(current: list[Entry], example: list[Entry]) -> dict[str, list[str]]:
    """How ``.env`` has drifted from ``.env.example``."""
    cur, ex = values(current), values(example)
    return {
        "missing_in_env": [k for k in ex if k not in cur],
        "unknown_in_env": [k for k in cur if k not in ex],
        "changed_from_default": [k for k in ex if k in cur and cur[k] != ex[k]],
    }
