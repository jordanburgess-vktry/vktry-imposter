"""Add new words to words.json with Claude, then retire the oldest trends.

For each category Claude writes new words (four imposter hints each). Categories that depend on
what's current search the web first, so new trends, releases and names make it in. A second pass
reviews every new word before it's added. New words are stamped with the date they were added;
the app shows them more often until they've been played.

    pip install anthropic
    ANTHROPIC_API_KEY=... python3 tools/generate_words.py                # default amounts
    python3 tools/generate_words.py --per-category 3 --trends 6
    python3 tools/generate_words.py --categories music,screen --dry-run   # print, don't save
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wordbank import (  # noqa: E402
    HINTS_PER_WORD, all_words, bank_problems, embed_in_page, entry_problems, load_bank,
    load_retired, norm, now_stamp, retire_overflow, save_bank, save_retired,
)

try:
    import anthropic
except ImportError:
    anthropic = None

MODEL = "claude-opus-5-5"
# Categories where "current" matters: these search the web before writing words.
SEARCH_CATEGORIES = {"trends", "music", "screen", "famous", "athletes", "moments", "gaming", "brands", "food"}

STYLE = """VKTRY Imposter is a pass-the-phone party game. Every player sees a secret word except the
imposter(s), who each see one hint instead: a loose clue that helps them bluff. Players take turns
saying one word related to the secret word, then vote on who's faking it. VKTRY makes
carbon-fiber performance insoles; the crowd is athletes, coaches and sports fans, mostly in the
US, aged 18-40.

A good WORD:
- Is instantly recognizable to that crowd. Proper nouns and current things are preferred: real
  people, teams, shows, brands, places, events, memes.
- Is specific enough that players can give one-word clues about it.
- Is not hateful, sexual, about a tragedy or death, a politician, or a divisive figure.
- Is not an athletic footwear or insole brand (no Nike, Adidas, etc.).

A good HINT (each word has exactly {n} hints, because each imposter gets a different one):
- 1-2 words (3 at most for a fixed phrase), Title Case.
- Loosely connected: enough for the imposter to bluff a plausible clue, NOT enough to name the
  word on sight. Mildly witty associations are best.
- Never contains the word or a distinctive part of it, and is never a synonym or the obvious
  category (Taylor Swift -> "Singer" is too vague, "Swiftie" gives it away).
- The {n} hints for one word point at different associations.
Examples: Valley -> Deep; Drake -> Owl; Coldplay -> Kiss Cam; Snoop Dogg -> Olympics;
Wimbledon -> Strawberries; Ryan Reynolds -> Wrexham; Martha Stewart -> Prison."""

GENERATE_PROMPT = """{style}

Today is {today}. Write {count} NEW words for the category "{name}" ({desc}).
{search_note}
These words are already in the game in this category, so don't repeat them or near-duplicates:
{existing}

Words in other categories (also avoid these):
{others}

Words that were retired from the game (don't bring these back):
{retired}

Reply with your final answer between <words> and </words> tags, as a JSON array:
<words>[{{"word": "...", "hints": ["...", "...", "...", "..."]}}]</words>"""

SEARCH_NOTE = """Before writing, search the web for what is popular or newly notable right now for this category
(this month and the last few months), so most new words are current: new releases, viral moments,
breakout names, recent records. Only use things that are widely known, not niche."""

REVIEW_PROMPT = """{style}

Today is {today}. Review these new words before they go into the game. Some were found by web
search and may be newer than your training data: do not drop a word only because you don't
recognize it. Judge it on the rules above.

For each entry decide:
- "ok": fine as is.
- "fix": the word is fine but one or more hints break the rules (too revealing, contains the word,
  too vague, repeated idea). Give all {n} hints, fixed.
- "drop": the word breaks the rules (not widely known, offensive, a duplicate of another entry,
  a politician, a footwear brand) or can't be fixed simply.

Reply only with a JSON array between <review> and </review> tags, one object per entry in order:
<review>[{{"i": 0, "verdict": "ok" | "fix" | "drop", "hints": ["...", "...", "...", "..."], "reason": "..."}}]</review>

Entries:
{entries}"""


def tagged_json(text, tag):
    """The JSON value between <tag> and </tag> in Claude's reply."""
    m = re.search(rf"<{tag}>\s*(.*?)\s*</{tag}>", text, re.S)
    if not m:
        raise ValueError(f"no <{tag}> block in the reply")
    return json.loads(m.group(1))


def ask_claude(client, prompt, web_search=False):
    """Send one prompt and return the reply text. Handles server-tool pauses and refusals."""
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 8}] if web_search else []
    messages = [{"role": "user", "content": prompt}]
    for _ in range(5):  # a long web search can pause the turn; continue it a few times at most
        with client.beta.messages.stream(
            model=MODEL,
            max_tokens=32000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "high"},
            tools=tools,
            messages=messages,
        ) as stream:
            message = stream.get_final_message()
        if message.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": message.content})
            continue
        if message.stop_reason == "refusal":
            raise RuntimeError(f"Claude declined: {getattr(message.stop_details, 'category', None)}")
        if message.stop_reason == "max_tokens":
            print("  WARNING: reply hit max_tokens and may be cut off")
        return "".join(b.text for b in message.content if b.type == "text")
    raise RuntimeError("the reply was still paused after 5 continuations")


def clean_entry(raw):
    """A {word, hints} dict from Claude's output, trimmed, or None if it isn't one."""
    if not isinstance(raw, dict):
        return None
    word = str(raw.get("word", "")).strip()
    hints = [str(h).strip() for h in raw.get("hints", []) if str(h).strip()]
    if not word or not hints:
        return None
    return {"word": word, "hints": hints[:HINTS_PER_WORD]}


def filter_new(candidates, taken_keys):
    """Keep candidates that follow the rules and aren't already taken. Prints why others go."""
    kept = []
    for c in candidates:
        entry = clean_entry(c)
        if entry is None:
            print(f"  skip (malformed): {c!r}"[:120])
            continue
        key = norm(entry["word"])
        if key in taken_keys:
            print(f"  skip (already in the game or retired): {entry['word']}")
            continue
        problems = entry_problems(entry)
        if problems:
            print(f"  skip ({'; '.join(problems)}): {entry['word']}")
            continue
        taken_keys.add(key)
        kept.append(entry)
    return kept


def apply_review(entries, verdicts):
    """Entries after the review: ok kept, fix gets the new hints (if they pass), drop removed.
    An entry the review didn't mention is kept as is."""
    by_i = {v.get("i"): v for v in verdicts if isinstance(v, dict)}
    out = []
    for i, e in enumerate(entries):
        v = by_i.get(i, {"verdict": "ok"})
        verdict = v.get("verdict", "ok")
        if verdict == "drop":
            print(f"  REVIEW drop: {e['word']} ({v.get('reason', '')})")
            continue
        if verdict == "fix":
            fixed = {"word": e["word"], "hints": [str(h).strip() for h in v.get("hints", [])][:HINTS_PER_WORD]}
            problems = entry_problems(fixed)
            if problems:
                print(f"  REVIEW drop (fix still breaks rules: {'; '.join(problems)}): {e['word']}")
                continue
            print(f"  REVIEW fix: {e['word']}: {e['hints']} -> {fixed['hints']}")
            e = fixed
        out.append(e)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--per-category", type=int, default=2, help="new words per category (default 2)")
    ap.add_argument("--trends", type=int, default=5, help="new words for Internet Trends (default 5)")
    ap.add_argument("--categories", default="", help="comma-separated category ids (default: all)")
    ap.add_argument("--dry-run", action="store_true", help="print the new words without saving")
    args = ap.parse_args()

    if anthropic is None:
        sys.exit("The 'anthropic' package isn't installed. Run: pip install anthropic")
    client = anthropic.Anthropic()

    bank = load_bank()
    retired = load_retired()
    wanted = {c.strip() for c in args.categories.split(",") if c.strip()}
    unknown = wanted - {c["id"] for c in bank["categories"]}
    if unknown:
        sys.exit(f"Unknown categories: {', '.join(sorted(unknown))}")

    taken = {norm(e["word"]) for _, e in all_words(bank)} | {norm(r["word"]) for r in retired}
    stamp = now_stamp()
    today = date.today().isoformat()
    style = STYLE.format(n=HINTS_PER_WORD)
    retired_list = ", ".join(r["word"] for r in retired[-300:]) or "(none)"

    proposed = []  # (category, entry)
    for cat in bank["categories"]:
        if wanted and cat["id"] not in wanted:
            continue
        count = args.trends if cat["id"] == "trends" else args.per_category
        if count <= 0:
            continue
        search = cat["id"] in SEARCH_CATEGORIES
        print(f"{cat['name']}: asking for {count}{' (with web search)' if search else ''}")
        others = ", ".join(e["word"] for cid, e in all_words(bank) if cid != cat["id"])
        prompt = GENERATE_PROMPT.format(
            style=style, today=today, count=count, name=cat["name"], desc=cat["desc"],
            search_note=SEARCH_NOTE if search else "",
            existing=", ".join(e["word"] for e in cat["words"]), others=others, retired=retired_list)
        try:
            raw = tagged_json(ask_claude(client, prompt, web_search=search), "words")
        except (ValueError, RuntimeError) as e:
            print(f"  WARNING: skipping {cat['id']} this run: {e}")
            continue
        for entry in filter_new(raw, taken)[:count]:
            proposed.append((cat, entry))

    added = 0
    if not proposed:
        print("No new words this run.")
    else:
        print(f"\nReviewing {len(proposed)} new words")
        listing = json.dumps([{"i": i, "category": c["name"], "word": e["word"], "hints": e["hints"]}
                              for i, (c, e) in enumerate(proposed)], ensure_ascii=False, indent=1)
        try:
            verdicts = tagged_json(ask_claude(client, REVIEW_PROMPT.format(
                style=style, today=today, n=HINTS_PER_WORD, entries=listing)), "review")
        except (ValueError, RuntimeError) as e:
            sys.exit(f"Review failed, nothing saved: {e}")
        reviewed = apply_review([e for _, e in proposed], verdicts)
        added = 0
        # a fix only changes hints, so each reviewed entry maps back to its category by word
        cat_of = {norm(e["word"]): c for c, e in proposed}
        for e in reviewed:
            e["added"] = stamp
            cat_of[norm(e["word"])]["words"].append(e)
            added += 1
            print(f"  + {cat_of[norm(e['word'])]['id']}: {e['word']} {e['hints']}")
        print(f"Added {added} words.")

    gone = retire_overflow(bank, retired, stamp)
    for r in gone:
        print(f"  - retired {r['category']}: {r['word']}")

    problems = bank_problems(bank, retired)
    if problems:
        print("\nThe updated bank has problems, nothing saved:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    if args.dry_run:
        print("\nDry run: nothing saved.")
        return
    if not added and not gone:
        print("Nothing changed.")
        return
    bank["updated"] = stamp
    save_bank(bank)
    save_retired(retired)
    embed_in_page(bank)
    print(f"Saved words.json and index.html ({sum(len(c['words']) for c in bank['categories'])} words).")


if __name__ == "__main__":
    main()
