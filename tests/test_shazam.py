import unittest
from unittest.mock import patch

from parser.shazam import get_shazam_chart, parse_chart_html


def chart_page(size=200):
    rows = []
    for position in range(1, size + 1):
        rows.append(f'''<li>
            <span class="x SongItem_rankingNumber_abc">{position}</span>
            <a data-test-id="charts_userevent_list_songTitle" aria-label="Трек {position}"></a>
            <a data-test-id="charts_userevent_list_songTitle" aria-label="Трек {position}"></a>
            <a data-test-id="charts_userevent_list_artistName" aria-label="Исполнитель {position}"></a>
        </li>''')
    return "<html><body><ul>" + "".join(rows) + "</ul></body></html>"


class ShazamTests(unittest.TestCase):
    def test_parses_all_tracks_and_ignores_duplicate_title_link(self):
        result = parse_chart_html(chart_page())
        self.assertEqual(len(result), 200)
        self.assertEqual(result[0], {
            "position": 1,
            "title": "Трек 1",
            "artists": ["Исполнитель 1"],
        })
        self.assertEqual(result[-1]["position"], 200)
        self.assertTrue(all(set(track) == {"position", "title", "artists"} for track in result))

    def test_preserves_displayed_artist_name(self):
        html = chart_page().replace(
            'aria-label="Исполнитель 1"',
            'aria-label="HUGEL, Imael Angel &amp; Ultra Naté"',
            1,
        )
        self.assertEqual(parse_chart_html(html)[0]["artists"], ["HUGEL, Imael Angel & Ultra Naté"])

    def test_rejects_missing_or_incomplete_chart(self):
        for html in ("<html></html>", chart_page(199)):
            with self.subTest(size=len(html)), self.assertRaises(RuntimeError):
                parse_chart_html(html)

    def test_rejects_invalid_track(self):
        for old, new in (
            ('aria-label="Трек 20"', 'aria-label=""'),
            ('aria-label="Исполнитель 20"', 'aria-label=""'),
            ('>20</span>', '>x</span>'),
        ):
            with self.subTest(old=old), self.assertRaises(RuntimeError):
                parse_chart_html(chart_page().replace(old, new))

    @patch("parser.shazam.shazam_parser._fetch_chart")
    def test_fetch_and_limit(self, fetch):
        fetch.return_value = parse_chart_html(chart_page())
        self.assertEqual(len(get_shazam_chart(5, timeout=12)), 5)
        fetch.assert_called_once_with(12)

    @patch("parser.shazam.shazam_parser._fetch_chart")
    def test_invalid_arguments(self, fetch):
        for limit in (0, -1, True, "5"):
            with self.assertRaises(ValueError):
                get_shazam_chart(limit)
        for timeout in (0, -1, float("nan"), float("inf"), "30"):
            with self.assertRaises(ValueError):
                get_shazam_chart(timeout=timeout)
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
