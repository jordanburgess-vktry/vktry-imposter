"""Check words.json: every entry follows the rules, nothing repeats, retired words stay out,
and the copy built into index.html matches. Exits 1 if anything is wrong.

    python3 tools/check_words.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wordbank import INDEX_FILE, bank_problems, load_bank, load_retired  # noqa: E402


def embedded_bank(index_path=INDEX_FILE):
    page = Path(index_path).read_text(encoding="utf-8")
    start_tag = '<script id="builtin-words" type="application/json">'
    a = page.index(start_tag) + len(start_tag)
    b = page.index("</script>", a)
    return json.loads(page[a:b].replace("<\\/", "</"))


def main():
    bank = load_bank()
    problems = bank_problems(bank, load_retired())
    if embedded_bank() != bank:
        problems.append("index.html's built-in copy is out of date: run python3 tools/embed_words.py")
    n_words = sum(len(c["words"]) for c in bank["categories"])
    print(f"{len(bank['categories'])} categories, {n_words} words, updated {bank.get('updated')}")
    for c in bank["categories"]:
        print(f"  {c['id']:<11} {len(c['words'])}")
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("No problems.")


if __name__ == "__main__":
    main()
