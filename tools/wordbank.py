"""Shared helpers for the word bank: loading, saving, normalizing and the rules every entry follows."""

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORDS_FILE = ROOT / "words.json"
RETIRED_FILE = ROOT / "archive" / "retired_words.json"
INDEX_FILE = ROOT / "index.html"

HINTS_PER_WORD = 4
# Categories that only make sense when current. When one grows past its cap, the words that have
# been in the bank longest are retired to archive/retired_words.json.
CATEGORY_CAPS = {"trends": 60}
DEFAULT_CAP = 120


def now_stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_bank(path=WORDS_FILE):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_bank(bank, path=WORDS_FILE):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False, indent=1)
        f.write("\n")


def load_retired(path=RETIRED_FILE):
    if not Path(path).exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_retired(entries, path=RETIRED_FILE):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=1)
        f.write("\n")


def norm(text):
    """Comparison key: case, accents, punctuation and a leading 'the' don't matter."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"^the ", "", text)


def all_words(bank):
    """(category id, entry) for every word in the bank."""
    for cat in bank["categories"]:
        for entry in cat["words"]:
            yield cat["id"], entry


def entry_problems(entry):
    """Rule breaks in one {word, hints} entry, as short messages. Empty when it's fine."""
    problems = []
    word = entry.get("word", "")
    hints = entry.get("hints", [])
    if not isinstance(word, str) or not word.strip():
        return ["missing word"]
    if len(word) > 40:
        problems.append("word longer than 40 characters")
    if not isinstance(hints, list) or len(hints) != HINTS_PER_WORD:
        problems.append(f"needs exactly {HINTS_PER_WORD} hints")
        return problems
    seen = set()
    word_tokens = {t for t in norm(word).split() if len(t) >= 4}
    for h in hints:
        if not isinstance(h, str) or not h.strip():
            problems.append("empty hint")
            continue
        if len(h.split()) > 3 or len(h) > 24:
            problems.append(f"hint too long: {h!r}")
        key = norm(h)
        if key in seen:
            problems.append(f"repeated hint: {h!r}")
        seen.add(key)
        if key == norm(word) or word_tokens & {t for t in key.split() if len(t) >= 4}:
            problems.append(f"hint gives the word away: {h!r}")
    return problems


def bank_problems(bank, retired=()):
    """Everything wrong with the bank as a whole: bad entries, repeats, retired words back in."""
    problems = []
    if not bank.get("updated"):
        problems.append("bank has no 'updated' stamp")
    retired_keys = {norm(r["word"]) for r in retired}
    seen = {}
    ids = set()
    for cat in bank.get("categories", []):
        for field in ("id", "emo", "name", "desc"):
            if not cat.get(field):
                problems.append(f"category {cat.get('id', '?')} has no {field}")
        if cat.get("id") in ids:
            problems.append(f"category id {cat['id']} used twice")
        ids.add(cat.get("id"))
        if not cat.get("words"):
            problems.append(f"category {cat.get('id')} has no words")
    for cat_id, entry in all_words(bank):
        label = f"{cat_id}: {entry.get('word', '?')}"
        problems += [f"{label}: {p}" for p in entry_problems(entry)]
        key = norm(entry.get("word", ""))
        if key in seen:
            problems.append(f"{label}: also in {seen[key]}")
        seen[key] = cat_id
        if key in retired_keys:
            problems.append(f"{label}: was retired, shouldn't come back")
    return problems


def retire_overflow(bank, retired, when=None):
    """Trim each category to its cap by retiring the words that have been in the bank longest
    (words with no 'added' date are the original set and go first). Returns the retired entries."""
    when = when or now_stamp()
    out = []
    for cat in bank["categories"]:
        cap = CATEGORY_CAPS.get(cat["id"], DEFAULT_CAP)
        extra = len(cat["words"]) - cap
        if extra <= 0:
            continue
        order = sorted(range(len(cat["words"])), key=lambda i: (cat["words"][i].get("added", ""), i))
        drop = set(order[:extra])
        for i in sorted(drop):
            e = cat["words"][i]
            out.append({"word": e["word"], "category": cat["id"], "added": e.get("added", ""),
                        "retired": when, "reason": f"category over its cap of {cap}"})
        cat["words"] = [e for i, e in enumerate(cat["words"]) if i not in drop]
    retired.extend(out)
    return out


def embed_in_page(bank, index_path=INDEX_FILE):
    """Copy the bank into index.html's built-in slot so the page works without downloading."""
    page = Path(index_path).read_text(encoding="utf-8")
    start_tag = '<script id="builtin-words" type="application/json">'
    a = page.index(start_tag) + len(start_tag)
    b = page.index("</script>", a)
    data = json.dumps(bank, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = page[:a] + data + page[b:]
    Path(index_path).write_text(page, encoding="utf-8")
