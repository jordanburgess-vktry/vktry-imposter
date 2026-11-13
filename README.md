# VKTRY Imposter

A pass-the-phone party game. Everyone sees a secret word except the imposters, who each get a
different hint and see who the other imposters are. Rounds are scored and a scoreboard keeps
the running totals.

The game is one page (`index.html`) published with GitHub Pages. On a phone, open the site and
use "Add to Home Screen" (Safari: Share → Add to Home Screen; Chrome: menu → Install app). It
then opens full screen with the VKTRY icon and works offline.

## Files

| Path | What it is |
| --- | --- |
| `index.html` | The game. Contains a built-in copy of the word list. |
| `words.json` | The word list: 16 categories, four imposter hints per word. |
| `manifest.webmanifest`, `icons/` | Home-screen install: name, colors, icons (from the official VKTRY logo). |
| `sw.js` | Offline support. Always tries the network first, so updates show up right away. |
| `tools/check_words.py` | Checks the word rules, repeats, and that `index.html` matches `words.json`. |
| `tools/embed_words.py` | Copies `words.json` into `index.html`. |
| `tools/generate_words.py` | Optional: adds new words with Claude (needs an Anthropic API key). |
| `tests/` | Word-list, page and scoring tests (the scoring tests need Node.js). |
| `.github/workflows/pages.yml` | Checks, tests, then publishes to GitHub Pages on every push to `main`. |

## Editing words

Edit `words.json`, then:

```bash
python3 tools/embed_words.py
python3 tools/check_words.py
python3 -m unittest discover -s tests
```

Each word needs exactly four hints. A hint is one to three words, must not contain the word,
and should let an imposter bluff without naming the word. Push to `main` to publish; phones
pick up the change the next time the game opens.

## Adding words with Claude (optional)

`tools/generate_words.py` asks Claude for new words (searching the web for trending
categories), reviews them, and saves them. Run it locally with your own key in the
environment; there is no scheduled job.

```bash
pip install anthropic
python3 tools/generate_words.py --dry-run
```
