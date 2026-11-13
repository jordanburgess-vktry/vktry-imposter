import re
import unittest
from pathlib import Path

PAGE = (Path(__file__).resolve().parent.parent / "index.html").read_text(encoding="utf-8")
SCRIPT = "\n".join(re.findall(r"<script>(.*?)</script>", PAGE, re.S))


class PageScript(unittest.TestCase):
    def test_no_native_dialogs(self):
        # confirm()/alert()/prompt() return at once without showing anything in some phone web
        # views, which broke the close button on the card screen. Use ask() instead.
        calls = re.findall(r"(?<![\w.$])(?:window\.)?(confirm|alert|prompt)\s*\(", SCRIPT)
        self.assertEqual(calls, [])

    def test_close_and_reset_use_the_in_page_sheet(self):
        self.assertIn('id="ask"', PAGE)
        self.assertRegex(SCRIPT, r'async function quit\(\)\{if\(await ask\(')
        self.assertRegex(SCRIPT, r'\$\("#sc-reset"\)\.onclick=async\(\)=>\{if\(await ask\(')

    def test_role_is_not_on_the_page_while_the_card_deals_in(self):
        # The next player's role used to be written under the card before it slid in, so it
        # showed for a moment. dealCard must leave the layer empty and hidden; the drag fills it.
        deal = SCRIPT[SCRIPT.index("function dealCard"):SCRIPT.index("/* Drag-to-reveal */")]
        self.assertIn('u.className="under concealed";u.innerHTML="";', deal)
        self.assertNotRegex(deal, r"u\.innerHTML=isImp")
        drag = SCRIPT[SCRIPT.index("/* Drag-to-reveal */"):]
        self.assertIn("u.innerHTML=G.roleHtml", drag[:drag.index('"pointermove"')])

    def test_category_toggle_is_saved_and_used_on_the_imposter_card(self):
        self.assertIn('id="t-cathint"', PAGE)
        self.assertIn('"catHint"', SCRIPT[SCRIPT.index("function save"):])
        self.assertIn("S.catHint?", SCRIPT[SCRIPT.index("function dealCard"):])

    def test_result_screen_does_not_show_hints(self):
        reveal = SCRIPT[SCRIPT.index('$("#reveal").onclick'):SCRIPT.index("/* ---------- Scoring")]
        self.assertNotIn("impHints", reveal)

    def test_screens_scroll_instead_of_squashing_sections(self):
        # On short phones the setup groups shrank and hid rows; children must not shrink.
        self.assertIn(".screen>*{flex-shrink:0}", PAGE)


if __name__ == "__main__":
    unittest.main()
