import unittest

from parser.whatstat_batch import match_categories
from parser.whatstat_categories.whatstat_categories_parser import parse_categories, parse_viewers


HTML = """
<html><body><table class="list"><tbody>
<tr><td>1</td><td><a href="/twitch/categories/cs-id">Counter-Strike</a></td><td>48 тыс.</td><td></td></tr>
<tr><td>2</td><td><a href="/twitch/categories/dota-id">Dota 2</a></td><td>43,8 тыс.</td><td></td></tr>
<tr><td>28</td><td><a href="/twitch/categories/fortnite-id">Fortnite</a></td><td>1 700</td><td></td></tr>
</tbody></table></body></html>
"""


class WhatstatParserTests(unittest.TestCase):
    def test_parses_rows_and_localized_viewer_counts(self):
        rows = parse_categories(HTML)
        self.assertEqual([row["position"] for row in rows], [1, 2, 28])
        self.assertEqual([row["average_viewers"] for row in rows], [48_000, 43_800, 1_700])
        self.assertEqual(rows[0]["category_id"], "cs-id")

    def test_viewer_suffixes(self):
        self.assertEqual(parse_viewers("951"), 951)
        self.assertEqual(parse_viewers("2,4 тыс."), 2_400)
        self.assertEqual(parse_viewers("1.2 млн"), 1_200_000)

    def test_empty_table_is_rejected(self):
        with self.assertRaises(RuntimeError):
            parse_categories("<html></html>")


class WhatstatMatchingTests(unittest.TestCase):
    def test_exact_names_and_counter_strike_alias_are_matched(self):
        categories = parse_categories(HTML)
        games = {
            "counter strike 2": "Counter-Strike 2",
            "dota 2": "Dota 2",
            "fortnite": "Fortnite",
            "other": "Other",
        }
        matched, unmatched = match_categories(categories, games)
        self.assertEqual(
            [entry["match_key"] for entry in matched],
            ["counter strike 2", "dota 2", "fortnite"],
        )
        self.assertEqual(unmatched, [])
        self.assertEqual(matched[0]["average_viewers"], 48_000)

    def test_new_and_mobile_games_are_kept_but_non_game_categories_are_skipped(self):
        categories = [
            {"title": "Grand Theft Auto VI", "category_id": "gta6", "url": "u1",
             "position": 1, "average_viewers": 500_000},
            {"title": "PUBG MOBILE", "category_id": "pubgm", "url": "u2",
             "position": 2, "average_viewers": 20_000},
            {"title": "Общение", "category_id": "chat", "url": "u3",
             "position": 3, "average_viewers": 10_000},
        ]

        matched, unmatched = match_categories(categories, {})

        self.assertEqual([entry["match_key"] for entry in matched],
                         ["grand theft auto vi", "pubg mobile"])
        self.assertEqual([entry["source_title"] for entry in matched],
                         ["Grand Theft Auto VI", "PUBG MOBILE"])
        self.assertEqual([entry["title"] for entry in unmatched],
                         ["Grand Theft Auto VI", "PUBG MOBILE", "Общение"])


if __name__ == "__main__":
    unittest.main()
