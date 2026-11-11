from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import tempfile
import unittest
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from scripts import render_cards as cards
from scripts import validate_cards


UTC = dt.timezone.utc
TEST_FONT = '@font-face{font-family:EmbeddedInter;src:url(data:font/woff;base64,AA==);}'


def synthetic_snapshot(end: dt.date = dt.date(2025, 1, 10),
                       contributions: dict[dt.date, int] | None = None) -> dict:
    """Build test-only fixtures in the same schema as the production GraphQL snapshot."""
    start = end-dt.timedelta(days=364)
    contributions = contributions or {}
    days = [
        {'date': (start+dt.timedelta(days=i)).isoformat(),
         'count': contributions.get(start+dt.timedelta(days=i), 0)}
        for i in range(365)
    ]
    return {
        'schema_version': 1,
        'source': 'github-graphql',
        'username': cards.USERNAME,
        'updated_at': '2025-01-11T00:00:00Z',
        'from': start.isoformat(),
        'to': end.isoformat(),
        'total': sum(item['count'] for item in days),
        'days': days,
    }


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.body


def graphql_response(snapshot: dict, *, total: int | None = None) -> dict:
    weeks = []
    days = snapshot['days']
    for index in range(0, len(days), 7):
        weeks.append({'contributionDays': [
            {'date': day['date'], 'contributionCount': day['count']}
            for day in days[index:index+7]
        ]})
    return {
        'data': {
            'rateLimit': {'remaining': 4999, 'resetAt': '2025-01-11T01:00:00Z', 'cost': 1},
            'user': {'contributionsCollection': {'contributionCalendar': {
                'totalContributions': snapshot['total'] if total is None else total,
                'weeks': weeks,
            }}},
        },
    }


class ContributionValidationTests(unittest.TestCase):
    def test_valid_positive_snapshot_is_saved_and_reloaded(self):
        end = dt.date(2025, 1, 10)
        start = end-dt.timedelta(days=364)
        fixture = synthetic_snapshot(end, {
            start+dt.timedelta(days=2): 3,
            start+dt.timedelta(days=25): 7,
        })
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'contributions.json'
            saved = cards.save_contributions(fixture, path)
            loaded = cards.load_data(strict=True, path=path)
            self.assertEqual(len(loaded['days']), 365)
            self.assertEqual(loaded['total'], 10)
            self.assertEqual(loaded, saved)

    def test_empty_days_are_invalid_but_a_full_zero_calendar_is_valid(self):
        zero_fixture = synthetic_snapshot(contributions={})
        self.assertEqual(cards.validate_contributions(zero_fixture)['total'], 0)
        empty = dict(zero_fixture, days=[])
        with self.assertRaisesRegex(cards.ContributionError, 'one entry for each'):
            cards.validate_contributions(empty)
        with self.assertRaises(cards.ContributionError):
            cards.validate_contributions({'username': cards.USERNAME, 'days': []})

    def test_invalid_dates_duplicates_negative_and_mismatched_totals_are_rejected(self):
        base = synthetic_snapshot()
        duplicate = dict(base, days=base['days']+[base['days'][0]])
        with self.assertRaisesRegex(cards.ContributionError, 'Duplicate'):
            cards.validate_contributions(duplicate)
        negative = dict(base, days=[dict(base['days'][0], count=-1)]+base['days'][1:])
        with self.assertRaisesRegex(cards.ContributionError, 'cannot be negative'):
            cards.validate_contributions(negative)
        bad_total = dict(base, total=1)
        with self.assertRaisesRegex(cards.ContributionError, 'does not match'):
            cards.validate_contributions(bad_total)

    def test_failed_graphql_response_preserves_last_valid_json(self):
        fixture = synthetic_snapshot(contributions={dt.date(2025, 1, 10): 2})
        error_response = {'errors': [{'message': 'Resource not accessible',
                                      'extensions': {'type': 'FORBIDDEN'}}]}
        token = 'unit-test-token-do-not-print'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'contributions.json'
            path.write_text(json.dumps(fixture), encoding='utf-8')
            before = path.read_bytes()
            request_seen = {}

            def fake_open(request, timeout):
                request_seen['authorization'] = request.get_header('Authorization')
                request_seen['timeout'] = timeout
                return FakeResponse(json.dumps(error_response).encode())

            with mock.patch.object(cards, 'DATA', path), mock.patch.dict('os.environ', {'GITHUB_TOKEN': token}), \
                    mock.patch.object(cards.urllib.request, 'urlopen', side_effect=fake_open):
                with self.assertRaisesRegex(cards.ContributionError, 'lacks permission') as caught:
                    cards.fetch_contributions(today=dt.date(2025, 1, 10),
                                              now=dt.datetime(2025, 1, 11, tzinfo=UTC))
            self.assertEqual(request_seen['authorization'], f'Bearer {token}')
            self.assertNotIn(token, str(caught.exception))
            self.assertEqual(path.read_bytes(), before)

    def test_http_and_rate_limit_errors_are_reported_without_body_or_token(self):
        token = 'do-not-print-this-token'
        for status, headers, expected in (
            (403, {'X-RateLimit-Remaining': '12'}, 'permissions'),
            (429, {}, 'rate limit'),
        ):
            error = urllib.error.HTTPError(
                'https://api.github.com/graphql', status, 'API error', headers,
                io.BytesIO(token.encode()),
            )
            with mock.patch.dict('os.environ', {'GITHUB_TOKEN': token}), \
                    mock.patch.object(cards.urllib.request, 'urlopen', side_effect=error):
                with self.assertRaises(cards.ContributionError) as caught:
                    cards.fetch_contributions(today=dt.date(2025, 1, 10))
            self.assertIn(expected, str(caught.exception).lower())
            self.assertNotIn(token, str(caught.exception))

    def test_invalid_graphql_calendar_is_not_written(self):
        snapshot = synthetic_snapshot(contributions={dt.date(2025, 1, 10): 2})
        bad = graphql_response(snapshot, total=0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'contributions.json'
            path.write_text(json.dumps(snapshot), encoding='utf-8')
            previous = path.read_bytes()
            with mock.patch.object(cards, 'DATA', path), mock.patch.dict('os.environ', {'GITHUB_TOKEN': 'test-token'}), \
                    mock.patch.object(cards.urllib.request, 'urlopen', return_value=FakeResponse(json.dumps(bad).encode())):
                with self.assertRaisesRegex(cards.ContributionError, 'did not match'):
                    cards.fetch_contributions(today=dt.date(2025, 1, 10),
                                              now=dt.datetime(2025, 1, 11, tzinfo=UTC))
            self.assertEqual(path.read_bytes(), previous)

    def test_non_json_graphql_response_is_rejected(self):
        with mock.patch.dict('os.environ', {'GITHUB_TOKEN': 'test-token'}), \
                mock.patch.object(cards.urllib.request, 'urlopen', return_value=FakeResponse(b'<not-json>')):
            with self.assertRaisesRegex(cards.ContributionError, 'invalid JSON'):
                cards.fetch_contributions(today=dt.date(2025, 1, 10))

    def test_valid_graphql_zero_calendar_is_saved_as_zero_not_failure(self):
        snapshot = synthetic_snapshot()
        response = graphql_response(snapshot)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'contributions.json'
            with mock.patch.object(cards, 'DATA', path), mock.patch.dict('os.environ', {'GITHUB_TOKEN': 'test-token'}), \
                    mock.patch.object(cards.urllib.request, 'urlopen', return_value=FakeResponse(json.dumps(response).encode())):
                saved = cards.fetch_contributions(today=dt.date(2025, 1, 10),
                                                  now=dt.datetime(2025, 1, 11, tzinfo=UTC))
            self.assertEqual(saved['total'], 0)
            self.assertEqual(len(saved['days']), 365)
            self.assertTrue(path.exists())


class ContributionStatisticsTests(unittest.TestCase):
    def test_streak_includes_today_when_active(self):
        end = dt.date(2025, 1, 10)
        fixture = synthetic_snapshot(end, {
            end-dt.timedelta(days=2): 1,
            end-dt.timedelta(days=1): 2,
            end: 4,
        })
        result = cards.stats(fixture, today=end)
        self.assertEqual(result['streak'], 3)
        self.assertEqual(result['active'], 3)
        self.assertEqual(result['busiest'], (end, 4))
        self.assertEqual(result['total'], 7)

    def test_streak_falls_back_to_yesterday_when_today_is_empty(self):
        end = dt.date(2025, 1, 10)
        fixture = synthetic_snapshot(end, {
            end-dt.timedelta(days=2): 2,
            end-dt.timedelta(days=1): 5,
        })
        self.assertEqual(cards.stats(fixture, today=end)['streak'], 2)

    def test_monthly_totals_cross_year_boundary(self):
        end = dt.date(2025, 1, 10)
        fixture = synthetic_snapshot(end, {
            dt.date(2024, 1, 20): 2,
            dt.date(2024, 12, 31): 3,
            dt.date(2025, 1, 1): 4,
        })
        totals = {(date.year, date.month): value for date, value in cards.stats(fixture)['monthly']}
        self.assertEqual(totals[(2024, 1)], 2)
        self.assertEqual(totals[(2024, 12)], 3)
        self.assertEqual(totals[(2025, 1)], 4)
        self.assertEqual(len(totals), 13)


class SvgRenderingTests(unittest.TestCase):
    def _render(self, directory: Path, data_path: Path, static: bool) -> dict[str, str]:
        with mock.patch.object(cards, 'OUT', directory), mock.patch.object(cards, 'DATA', data_path), \
                mock.patch.object(cards, 'font_css', return_value=TEST_FONT), \
                mock.patch.dict('os.environ', {'STATIC': '1' if static else '0'}), \
                mock.patch('sys.argv', ['render_cards.py']), contextlib.redirect_stdout(io.StringIO()):
            cards.main()
        return {path.name: path.read_text(encoding='utf-8') for path in directory.glob('*.svg')}

    def test_rendering_static_mode_has_same_data_and_valid_self_contained_svg(self):
        fixture = synthetic_snapshot(contributions={
            dt.date(2024, 12, 31): 3,
            dt.date(2025, 1, 9): 2,
            dt.date(2025, 1, 10): 4,
        })
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = root/'contributions.json'
            data_path.write_text(json.dumps(fixture), encoding='utf-8')
            card_dir = root/'cards'
            card_dir.mkdir()
            animated = self._render(card_dir, data_path, static=False)
            self.assertEqual(len(animated), 9)
            self.assertIn('@keyframes', animated['activity.svg'])
            self.assertIn('prefers-reduced-motion:reduce', animated['activity.svg'])
            self.assertNotIn('<animate', animated['hero.svg'])
            validate_cards.validate_directory(card_dir)

            for name in ('activity.svg', 'contributions.svg'):
                root_svg = ET.fromstring(animated[name])
                animated_text = [element.text for element in root_svg.iter(f'{{{validate_cards.SVG_NS}}}text')]
                animated_titles = [element.text for element in root_svg.iter(f'{{{validate_cards.SVG_NS}}}title')]
                self.assertTrue(animated_titles)
                (card_dir/name).write_text(animated[name], encoding='utf-8')
                self.assertIn('TOTAL CONTRIBUTIONS', animated['activity.svg'])

            static = self._render(card_dir, data_path, static=True)
            for name in ('activity.svg', 'contributions.svg'):
                static_svg = ET.fromstring(static[name])
                static_text = [element.text for element in static_svg.iter(f'{{{validate_cards.SVG_NS}}}text')]
                static_titles = [element.text for element in static_svg.iter(f'{{{validate_cards.SVG_NS}}}title')]
                animated_svg = ET.fromstring(animated[name])
                animated_values = [element.text for element in animated_svg.iter(f'{{{validate_cards.SVG_NS}}}text')]
                animated_tips = [element.text for element in animated_svg.iter(f'{{{validate_cards.SVG_NS}}}title')]
                self.assertEqual(static_text, animated_values)
                self.assertEqual(static_titles, animated_tips)
                self.assertNotIn('@keyframes', static[name])
                self.assertNotIn('animation:', static[name])
                self.assertNotIn('<animate', static[name])
            validate_cards.validate_directory(card_dir)

    def test_svg_validator_rejects_external_resources_and_malformed_xml(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'external.svg'
            path.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1" role="img" aria-label="x"><title>x</title><style>@font-face{src:url(data:font/woff;base64,AA==)}</style><image href="https://example.org/a.png"/></svg>', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'external resource'):
                validate_cards.validate_svg(path)
            path.write_text('<svg><', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'invalid XML'):
                validate_cards.validate_svg(path)


if __name__ == '__main__':
    unittest.main()
