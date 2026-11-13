"""Copy words.json into index.html's built-in word list (used when the page can't download it).

    python3 tools/embed_words.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wordbank import embed_in_page, load_bank  # noqa: E402

if __name__ == "__main__":
    bank = load_bank()
    embed_in_page(bank)
    print(f"Embedded {sum(len(c['words']) for c in bank['categories'])} words (updated {bank['updated']}) in index.html")
