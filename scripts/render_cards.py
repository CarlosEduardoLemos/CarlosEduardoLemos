#!/usr/bin/env python3
"""Render self-contained, GitHub <img>-safe SVG profile cards.

Requires Python 3.11+ and fonttools[woff] (pyftsubset executable or module).
Optional `--refresh` queries GitHub GraphQL with GITHUB_TOKEN before rendering.

Usage:
  python scripts/render_cards.py --refresh
  python scripts/update_contributions.py
  python scripts/validate_contributions.py
  STATIC=1 python scripts/render_cards.py
  python scripts/render_cards.py --portrait assets/portrait.png
"""
from __future__ import annotations

import argparse
import base64
import calendar
import datetime as dt
import html
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'cards'
DATA = ROOT / 'data' / 'contributions.json'
USERNAME = 'CarlosEduardoLemos'
NAME = 'Carlos Eduardo de Souza Lemos'
BG = '#101018'
SURFACE = '#191922'
SURFACE2 = '#222231'
BORDER = '#4C495D'
WHITE = '#F5F3FF'
MUTED = '#B3AFCA'
ACCENT = '#B8A1FF'
ACCENT2 = '#8F81DD'

PROJECTS = [
    dict(slug='cybercontrol', title='CyberControl', subtitle='Security-focused IT operations',
         desc='Assets, vulnerabilities, risk and auditable workflows.',
         tags='Python  /  Flask  /  SQLite  /  RBAC',
         label='PERSONAL PROJECT', url='https://github.com/CarlosEduardoLemos/CyberControl'),
    dict(slug='timetracker', title='TimeTracker', subtitle='Collaborative frontend contribution',
         desc='React UI, reusable hooks, accessibility and testing.',
         tags='React  /  Vite  /  Tailwind  /  Vitest',
         label='BAYAREA COLLABORATION', url='https://github.com/fabrica-bayarea/TimeTracker-2026-2'),
    dict(slug='csharp', title='PrimeirosPassos-C-Sharp', subtitle='Learning in public',
         desc='C# fundamentals, LINQ, exceptions and async practice.',
         tags='C#  /  .NET  /  Learning',
         label='STUDY REPOSITORY', url='https://github.com/CarlosEduardoLemos/PrimeirosPassos-C-Sharp'),
]


def x(s: object) -> str:
    return html.escape(str(s), quote=True)


def font_css() -> str:
    """Subset the installed Inter font via pyftsubset, then inline WOFF."""
    explicit = os.environ.get('INTER_FONT')
    if explicit:
        src = Path(explicit)
    else:
        fc = shutil.which('fc-match')
        if not fc:
            raise RuntimeError('Install Inter and fontconfig, or set INTER_FONT to a local Inter OTF/TTF')
        src = Path(subprocess.check_output([fc, '-f', '%{file}', 'Inter'], text=True).strip())
    subsetter = shutil.which('pyftsubset')
    if not src.exists():
        raise RuntimeError('Inter font and fonttools (pyftsubset) are required')
    if not subsetter and not importlib.util.find_spec('fontTools.subset'):
        raise RuntimeError('Inter font and pyftsubset (fonttools) are required')
    glyphs = (NAME + 'IT Support Analyst → Software Development'
              + 'Building practical web applications with security in mind.'
              + 'VISIT PROFILE CONTACT LINKEDIN GITHUB EMAIL FEATURED WORK'
              + 'Security-focused IT operations Collaborative frontend contribution'
              + ''.join(p['title'] + p['subtitle'] + p['desc'] + p['tags'] + p['label'] for p in PROJECTS)
              + '0123456789,./:%+−–—•×|ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
              + 'JanFebMarAprMayJunJulAugSepOctNovDecMON TUE WED THU FRI SAT SUN'
              + 'ACTIVITY STREAK ACTIVE DAYS BUSIEST DAY CONTRIBUTIONS LAST 12 MONTHS'
              + 'TOTAL CONTRIBUTIONS MONTHLY CONTRIBUTIONS NO CONTRIBUTION OUTSIDE RANGE DATA UNAVAILABLE'
              + 'Awaiting validated contribution data Contribution data unavailable'
              + 'Total commits and contributions • click to explore')
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / 'inter.woff'
        subset = Path(td) / 'glyphs.txt'
        subset.write_text(glyphs, encoding='utf-8')
        command = [subsetter] if subsetter else [sys.executable, '-m', 'fontTools.subset']
        subprocess.run(command + [str(src), f'--output-file={target}',
                        '--flavor=woff', f'--text-file={subset}',
                        '--layout-features=*', '--name-IDs=0,1,2,4,6'], check=True,
                       stdout=subprocess.DEVNULL)
        font = base64.b64encode(target.read_bytes()).decode('ascii')
    return f"@font-face{{font-family:EmbeddedInter;src:url(data:font/woff;base64,{font}) format('woff');font-weight:100 900;font-style:normal}}"


def base_style(font: str, static: bool) -> str:
    animation = '' if static else '''
    @keyframes enter{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:translateY(0)}}
    @keyframes bar-grow{from{transform:scaleY(.04)}to{transform:scaleY(1)}}
    @keyframes cell-grow{from{opacity:.1;transform:scale(.65)}to{opacity:1;transform:scale(1)}}
    @keyframes line-draw{from{stroke-dashoffset:560}to{stroke-dashoffset:0}}
    .enter{opacity:0;animation:enter .8s cubic-bezier(.2,.75,.25,1) var(--delay,0s) both}
    .bar{transform-box:fill-box;transform-origin:center bottom;animation:bar-grow .7s ease-out calc(var(--delay,0s) + .45s) both}
    .cell{transform-box:fill-box;transform-origin:center;animation:cell-grow .42s ease-out var(--cell-delay,0s) both}
    .trace{stroke-dasharray:560;stroke-dashoffset:560;animation:line-draw 1.5s ease-out calc(var(--delay,0s) + .4s) both}
    @media (prefers-reduced-motion:reduce){
      *,*::before,*::after{animation:none!important;transition:none!important}
      .enter,.cell{opacity:1!important;transform:none!important}
      .bar{transform:none!important}
      .trace{stroke-dashoffset:0!important}
    }
    '''
    return f'''<style><![CDATA[{font}
      text{{font-family:EmbeddedInter,Inter,Arial,sans-serif;fill:{WHITE}}}
      .muted{{fill:{MUTED}}}.accent{{fill:{ACCENT}}}
      .eyebrow{{font-size:12px;letter-spacing:2.2px;font-weight:600}}
      .title{{font-weight:700}}.small{{font-size:14px}}
      {animation}
    ]]></style>'''


def shell(w: int, h: int, content: str, font: str, static: bool, delay: float = 0,
          label: str = '') -> str:
    # The SVG needs no network fetches: all styles and fonts are embedded.
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{x(label)}">
    <title>{x(label)}</title>{base_style(font,static)}
    <rect width="{w}" height="{h}" rx="22" fill="{BG}"/>
    <rect x="1" y="1" width="{w-2}" height="{h-2}" rx="21" fill="{SURFACE}" stroke="{BORDER}" stroke-opacity=".65"/>
    <path d="M22 1 H{w-44}" stroke="{ACCENT}" stroke-opacity=".46"/>
    <g class="enter" style="--delay:{0 if static else delay:.2f}s">{content}</g>
    </svg>'''


def save(name: str, svg: str) -> None:
    OUT.mkdir(exist_ok=True, parents=True)
    (OUT / name).write_text(svg, encoding='utf-8')


def data_uri_portrait(path: Path | None) -> str:
    if not path:
        return ''
    ext = path.suffix.lower()
    if ext not in ('.png', '.jpg', '.jpeg', '.webp'):
        raise ValueError('Portrait must be a local PNG, JPEG or WebP')
    mime = {'.png':'image/png', '.jpg':'image/jpeg', '.jpeg':'image/jpeg', '.webp':'image/webp'}[ext]
    return f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode('ascii')


def hero(font: str, static: bool, portrait: Path | None) -> None:
    pic = ''
    if portrait:
        uri = data_uri_portrait(portrait)
        pic = f'''<defs><clipPath id="portrait-cut"><circle cx="748" cy="136" r="67"/></clipPath></defs>
        <circle cx="748" cy="136" r="72" fill="none" stroke="{ACCENT}" stroke-width="2"/>
        <image href="{uri}" x="681" y="69" width="134" height="134" preserveAspectRatio="xMidYMid slice" clip-path="url(#portrait-cut)"/>'''
    else:
        pic = f'''<circle cx="745" cy="139" r="70" fill="{SURFACE2}" stroke="{BORDER}"/>
        <path d="M711 144l22 22 47-54" fill="none" stroke="{ACCENT}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>'''
    body = f'''<circle cx="55" cy="51" r="5" fill="{ACCENT}"/>
    <text x="72" y="56" class="eyebrow accent">HELLO, I'M</text>
    <text x="48" y="118" font-size="38" font-weight="750">Carlos Eduardo</text>
    <text x="48" y="159" font-size="33" font-weight="650">de Souza Lemos</text>
    <text x="48" y="201" class="muted" font-size="17">IT Support Analyst  /  Software Development</text>
    <text x="48" y="237" class="muted" font-size="14">Building practical web applications with security in mind.</text>
    <path d="M48 264h720" stroke="{BORDER}" opacity=".7"/>
    <text x="48" y="289" class="eyebrow accent">PYTHON  •  FLASK  •  REACT  •  APPLICATION SECURITY</text>{pic}'''
    save('hero.svg', shell(860, 316, body, font, static, .0, 'Carlos Eduardo de Souza Lemos — profile introduction'))


def tiles(font: str, static: bool) -> None:
    values = [('github', 'GITHUB', 'Browse my repositories', '01'),
              ('linkedin', 'LINKEDIN', 'Connect professionally', '02'),
              ('email', 'EMAIL', 'Start a conversation', '03')]
    for i,(slug,title,caption,num) in enumerate(values):
        content = f'''<text x="24" y="39" class="eyebrow accent">{num}  /  CONNECT</text>
        <text x="24" y="92" font-size="26" class="title">{title}</text>
        <text x="24" y="123" class="muted" font-size="13">{x(caption)}</text>
        <path d="M218 44h15m-7-7 7 7-7 7" stroke="{ACCENT}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'''
        save(f'tile-{slug}.svg', shell(270, 150, content,font, static,.18 + i*.16,title+' link tile'))


class ContributionError(RuntimeError):
    """A GitHub response or saved contribution snapshot failed validation."""


def contribution_window(end: dt.date) -> tuple[dt.date, list[dt.date]]:
    start = end - dt.timedelta(days=364)
    return start, [start + dt.timedelta(days=i) for i in range(365)]


def validate_contributions(value: object, *, expected_from: dt.date | None = None,
                           expected_to: dt.date | None = None) -> dict:
    if not isinstance(value, dict) or value.get('schema_version') != 1:
        raise ContributionError('Contribution JSON must use schema_version 1.')
    if value.get('username') != USERNAME:
        raise ContributionError(f'Contribution JSON must belong to {USERNAME}.')
    if value.get('source') != 'github-graphql':
        raise ContributionError('Contribution JSON must come from the GitHub GraphQL contribution calendar.')

    try:
        first = dt.date.fromisoformat(value['from'])
        last = dt.date.fromisoformat(value['to'])
    except (KeyError, TypeError, ValueError) as exc:
        raise ContributionError('Contribution JSON has invalid from/to dates.') from exc
    if value['from'] != first.isoformat() or value['to'] != last.isoformat():
        raise ContributionError('Contribution JSON dates must use YYYY-MM-DD.')
    if last - first != dt.timedelta(days=364):
        raise ContributionError('Contribution JSON must cover exactly 365 days.')
    if expected_from is not None and first != expected_from:
        raise ContributionError('GitHub returned an unexpected start date.')
    if expected_to is not None and last != expected_to:
        raise ContributionError('GitHub returned an unexpected end date.')

    updated = value.get('updated_at')
    if not isinstance(updated, str):
        raise ContributionError('Contribution JSON is missing updated_at.')
    try:
        updated_dt = dt.datetime.fromisoformat(updated.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ContributionError('Contribution JSON has an invalid updated_at timestamp.') from exc
    if updated_dt.tzinfo is None or updated_dt.utcoffset() != dt.timedelta(0):
        raise ContributionError('updated_at must be a UTC timestamp.')

    days = value.get('days')
    if not isinstance(days, list):
        raise ContributionError('Contribution JSON days must be an array.')
    normalized: dict[dt.date, int] = {}
    for item in days:
        if not isinstance(item, dict):
            raise ContributionError('Each contribution day must be an object.')
        try:
            day = dt.date.fromisoformat(item['date'])
            count = item['count']
        except (KeyError, TypeError, ValueError) as exc:
            raise ContributionError('Contribution JSON contains an invalid day or count.') from exc
        if item['date'] != day.isoformat():
            raise ContributionError('Contribution dates must use YYYY-MM-DD.')
        if isinstance(count, bool) or not isinstance(count, int):
            raise ContributionError(f'Contribution count for {day.isoformat()} must be an integer.')
        if count < 0:
            raise ContributionError(f'Contribution count for {day.isoformat()} cannot be negative.')
        if day in normalized:
            raise ContributionError(f'Duplicate contribution date: {day.isoformat()}.')
        normalized[day] = count

    _, expected_days = contribution_window(last)
    if first != expected_days[0] or set(normalized) != set(expected_days):
        raise ContributionError('Contribution JSON must contain one entry for each of its 365 dates.')
    total = value.get('total')
    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
        raise ContributionError('Contribution JSON total must be a non-negative integer.')
    if total != sum(normalized.values()):
        raise ContributionError('Contribution JSON total does not match its daily counts.')

    return {
        'schema_version': 1,
        'source': 'github-graphql',
        'username': USERNAME,
        'updated_at': updated_dt.astimezone(dt.timezone.utc).isoformat().replace('+00:00', 'Z'),
        'from': first.isoformat(),
        'to': last.isoformat(),
        'total': total,
        'days': [{'date': day.isoformat(), 'count': normalized[day]} for day in expected_days],
    }


def save_contributions(value: dict, path: Path | None = None) -> dict:
    normalized = validate_contributions(value)
    path = path or DATA
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                         prefix=f'.{path.name}.', suffix='.tmp',
                                         delete=False) as output:
            temporary = Path(output.name)
            json.dump(normalized, output, indent=2, ensure_ascii=False)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return normalized


def _graphql_error(errors: object, token: str) -> str:
    entries = errors if isinstance(errors, list) else []
    descriptions = []
    for error in entries[:3]:
        if not isinstance(error, dict):
            continue
        extensions = error.get('extensions') or {}
        if not isinstance(extensions, dict):
            extensions = {}
        code = str(extensions.get('type') or extensions.get('code') or '').upper()
        message = str(error.get('message') or 'unspecified GraphQL error').replace(token, '[redacted]')
        if code in ('RATE_LIMITED', 'RATE_LIMIT_EXCEEDED') or 'rate limit' in message.lower():
            descriptions.append('rate limit exceeded')
        elif code in ('FORBIDDEN', 'UNAUTHORIZED') or 'resource not accessible' in message.lower():
            descriptions.append('token lacks permission to read this contribution calendar')
        else:
            descriptions.append(message[:240])
    return '; '.join(descriptions) or 'unspecified GraphQL error'


def _http_error(error: urllib.error.HTTPError) -> ContributionError:
    status = error.code
    remaining = error.headers.get('X-RateLimit-Remaining', '') if error.headers else ''
    try:
        response_hint = error.read(2048).decode('utf-8', 'replace').lower()
    except OSError:
        response_hint = ''
    finally:
        error.close()
    if 'rate limit' in response_hint or 'secondary rate' in response_hint or 'abuse detection' in response_hint:
        return ContributionError('GitHub GraphQL rate limit exceeded; the previous valid data was preserved.')
    if status == 429 or (status == 403 and remaining == '0'):
        return ContributionError('GitHub GraphQL rate limit exceeded; the previous valid data was preserved.')
    if status == 401:
        return ContributionError('GitHub GraphQL rejected GITHUB_TOKEN (HTTP 401); check that Actions provides a valid token.')
    if status == 403:
        return ContributionError('GitHub GraphQL denied access (HTTP 403); check token permissions and organization policy.')
    return ContributionError(f'GitHub GraphQL returned HTTP {status}; the previous valid data was preserved.')


def fetch_contributions(*, today: dt.date | None = None,
                        now: dt.datetime | None = None) -> dict:
    token = os.getenv('GITHUB_TOKEN', '').strip()
    if not token:
        raise ContributionError('GITHUB_TOKEN is required to query GitHub GraphQL.')
    now = now or dt.datetime.now(dt.timezone.utc)
    today = today or now.astimezone(dt.timezone.utc).date()
    first, expected_days = contribution_window(today)
    # GitHub's official contribution calendar aggregates qualifying commits,
    # opened issues and PRs, and submitted PR reviews; this is not a commit count.
    query = '''query($login:String!,$from:DateTime!,$to:DateTime!){rateLimit{remaining resetAt cost} user(login:$login){contributionsCollection(from:$from,to:$to){contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}'''
    payload = json.dumps({'query': query, 'variables': {
        'login': USERNAME, 'from': first.isoformat()+'T00:00:00Z',
        'to': today.isoformat()+'T23:59:59Z'}}).encode('utf-8')
    request = urllib.request.Request('https://api.github.com/graphql', data=payload,
        headers={'Authorization':'Bearer '+token, 'Accept':'application/vnd.github+json',
                 'Content-Type':'application/json', 'User-Agent':'profile-card-renderer'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            status = getattr(response, 'status', 200)
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise _http_error(exc) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ContributionError('GitHub GraphQL request failed due to a network or timeout error.') from None
    if status != 200:
        raise ContributionError(f'GitHub GraphQL returned HTTP {status}.')
    try:
        result = json.loads(body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ContributionError('GitHub GraphQL returned an invalid JSON response.') from None
    if not isinstance(result, dict):
        raise ContributionError('GitHub GraphQL returned an invalid response object.')
    if result.get('errors'):
        raise ContributionError('GitHub GraphQL error: '+_graphql_error(result['errors'], token))

    root = result.get('data')
    rate_limit = root.get('rateLimit') if isinstance(root, dict) else None
    remaining = rate_limit.get('remaining') if isinstance(rate_limit, dict) else None
    if isinstance(remaining, bool) or not isinstance(remaining, int) or remaining < 0:
        raise ContributionError('GitHub GraphQL response omitted valid rate limit information.')
    cost = rate_limit.get('cost')
    reset_at = rate_limit.get('resetAt')
    try:
        reset_time = dt.datetime.fromisoformat(reset_at.replace('Z', '+00:00'))
    except (AttributeError, ValueError):
        raise ContributionError('GitHub GraphQL response contained an invalid rate limit reset time.') from None
    if (isinstance(cost, bool) or not isinstance(cost, int) or cost < 0
            or reset_time.tzinfo is None or reset_time.utcoffset() != dt.timedelta(0)):
        raise ContributionError('GitHub GraphQL response contained invalid rate limit details.')
    if remaining == 0:
        print('::warning::GitHub GraphQL returned data with no rate limit capacity remaining.', file=sys.stderr)
    user = root.get('user') if isinstance(root, dict) else None
    if not isinstance(user, dict):
        raise ContributionError(f'GitHub GraphQL did not return user {USERNAME}; no data was saved.')
    collection = user.get('contributionsCollection')
    calendar_data = collection.get('contributionCalendar') if isinstance(collection, dict) else None
    if not isinstance(calendar_data, dict):
        raise ContributionError('GitHub GraphQL did not return a contribution calendar.')
    calendar_total = calendar_data.get('totalContributions')
    if isinstance(calendar_total, bool) or not isinstance(calendar_total, int) or calendar_total < 0:
        raise ContributionError('GitHub returned an invalid or negative contribution total.')

    counts: dict[dt.date, int] = {}
    weeks = calendar_data.get('weeks')
    if not isinstance(weeks, list):
        raise ContributionError('GitHub returned an invalid contribution weeks list.')
    for week in weeks:
        if not isinstance(week, dict) or not isinstance(week.get('contributionDays'), list):
            raise ContributionError('GitHub returned a malformed contribution week.')
        for item in week['contributionDays']:
            if not isinstance(item, dict):
                raise ContributionError('GitHub returned a malformed contribution day.')
            try:
                day = dt.date.fromisoformat(item['date'])
                count = item['contributionCount']
            except (KeyError, TypeError, ValueError) as exc:
                raise ContributionError('GitHub returned an invalid contribution date or count.') from exc
            if item['date'] != day.isoformat():
                raise ContributionError('GitHub returned a contribution date outside YYYY-MM-DD format.')
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ContributionError(f'GitHub returned a negative or invalid count for {day.isoformat()}.')
            if first <= day <= today:
                if day in counts:
                    raise ContributionError(f'GitHub returned duplicate contribution date {day.isoformat()}.')
                counts[day] = count
    if set(counts) != set(expected_days):
        raise ContributionError('GitHub returned an incomplete 365-day calendar; no data was saved.')
    if calendar_total != sum(counts.values()):
        raise ContributionError('GitHub calendar total did not match the daily contribution counts; no data was saved.')

    snapshot = {
        'schema_version': 1, 'source': 'github-graphql', 'username': USERNAME,
        'updated_at': now.astimezone(dt.timezone.utc).isoformat().replace('+00:00', 'Z'),
        'from': first.isoformat(), 'to': today.isoformat(),
        'total': calendar_total,
        'days': [{'date': day.isoformat(), 'count': counts[day]} for day in expected_days],
    }
    return save_contributions(snapshot)


def load_data(*, strict: bool = False, path: Path | None = None) -> dict:
    path = path or DATA
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
        return validate_contributions(raw)
    except (OSError, json.JSONDecodeError, ContributionError) as exc:
        message = f'No valid cached contribution snapshot: {exc}'
        if strict:
            raise ContributionError(message) from exc
        print(f'Warning: {message}', file=sys.stderr)
        return {'username': USERNAME, 'available': False, 'days': []}


MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def stats(data: dict, *, today: dt.date | None = None) -> dict:
    if not data.get('available', True) or not data.get('days'):
        return {'available': False, 'active': None, 'streak': None,
                'busiest': None, 'monthly': [], 'total': None}
    counts = {dt.date.fromisoformat(d['date']): d['count'] for d in data['days']}
    end = today or dt.date.fromisoformat(data['to'])
    start = dt.date.fromisoformat(data['from'])
    if end < start or end > dt.date.fromisoformat(data['to']):
        raise ValueError('Statistics date must fall inside the validated contribution snapshot.')
    cursor = end if counts.get(end, 0) > 0 else end - dt.timedelta(days=1)
    streak = 0
    while cursor >= start and counts.get(cursor, 0) > 0:
        streak += 1
        cursor -= dt.timedelta(days=1)
    monthly_totals: dict[tuple[int, int], int] = {}
    for date, count in counts.items():
        key = (date.year, date.month)
        monthly_totals[key] = monthly_totals.get(key, 0) + count
    months = []
    month_cursor = dt.date(start.year, start.month, 1)
    end_month = dt.date(end.year, end.month, 1)
    while month_cursor <= end_month:
        months.append((month_cursor, monthly_totals.get((month_cursor.year, month_cursor.month), 0)))
        month_cursor = (dt.date(month_cursor.year + (month_cursor.month == 12),
                                1 if month_cursor.month == 12 else month_cursor.month + 1, 1))
    busiest = max(((date, count) for date, count in counts.items() if count > 0),
                  key=lambda item: (item[1], -item[0].toordinal()), default=None)
    return {'available': True, 'active': sum(count > 0 for count in counts.values()),
            'streak': streak, 'busiest': busiest, 'monthly': months,
            'total': sum(counts.values())}


def activity(font: str, static: bool, data: dict) -> None:
    s = stats(data)
    available = s['available']
    busy = '—'
    if s['busiest']:
        busy_date, busy_count = s['busiest']
        busy = f'{busy_date.day:02d} {MONTHS[busy_date.month-1]} +{busy_count}'
    if available:
        span = f"{data['from']} – {data['to']} UTC | 365 days"
        updated = data['updated_at'][:10]+' UTC'
    else:
        span = 'Contribution data unavailable | waiting for a validated GitHub response'
        updated = 'Not available'
    metrics = [
        (40, s['total'] if available else '—', 'TOTAL CONTRIBUTIONS'),
        (244, s['active'] if available else '—', 'ACTIVE DAYS'),
        (448, s['streak'] if available else '—', 'CURRENT STREAK'),
        (652, busy, 'BUSIEST DAY'),
    ]
    content = f'''<text x="35" y="41" class="eyebrow accent">GITHUB CONTRIBUTIONS</text>
    <text x="35" y="76" font-size="25" class="title">Activity over the last year</text>
    <text x="35" y="101" font-size="12" class="muted">{x(span)}</text>
    <path d="M35 116H825" stroke="{BORDER}" opacity=".6"/>'''
    for xpos, value, label in metrics:
        value_size = 24 if label == 'BUSIEST DAY' else 30
        content += f'''<text x="{xpos}" y="151" font-size="{value_size}" font-weight="700">{x(value)}</text>
        <text x="{xpos}" y="172" font-size="14" class="eyebrow muted">{label}</text>'''
    content += f'''<path d="M35 187H825" stroke="{BORDER}" opacity=".6"/>
    <text x="35" y="216" font-size="17" class="title">MONTHLY CONTRIBUTIONS</text>
    <text x="825" y="216" font-size="13" text-anchor="end" class="muted">Updated {x(updated)}</text>
    <path d="M35 375H825" stroke="{BORDER}" opacity=".7"/>'''
    if available:
        max_value = max((value for _, value in s['monthly']), default=0)
        for index, (date, value) in enumerate(s['monthly']):
            height = max(3, round(112 * value / max(1, max_value))) if value else 3
            bx = 40 + index * 60
            top = 375 - height
            opacity = .24 + .76 * (value / max_value) ** .55 if value and max_value else 1
            color = ACCENT if value else SURFACE2
            label = f"{MONTHS[date.month-1]} {str(date.year)[-2:]}"
            content += f'''<rect x="{bx}" y="{top}" width="32" height="{height}" rx="4" fill="{color}" fill-opacity="{opacity:.3f}" class="bar" style="--delay:{0 if static else .7+index*.04:.3f}s"/>
            <text x="{bx+16}" y="{max(241, top-7)}" font-size="14" text-anchor="middle" class="muted">{value}</text>
            <text x="{bx+16}" y="400" font-size="13" text-anchor="middle" class="muted">{label}</text>'''
    else:
        content += '''<text x="430" y="306" font-size="16" text-anchor="middle" class="muted">No validated contribution snapshot is available yet.</text>'''
    save('activity.svg', shell(860, 425, content, font, static, .55,
         'GitHub contributions over 365 days: total, active days, current streak, busiest day and monthly totals'))


def repos(font: str, static: bool) -> None:
    for i,p in enumerate(PROJECTS):
        body=f'''<text x="36" y="44" class="eyebrow accent">{x(p['label'])}</text>
        <text x="36" y="96" font-size="30" class="title">{x(p['title'])}</text>
        <text x="36" y="126" font-size="17" class="muted">{x(p['subtitle'])}</text>
        <text x="36" y="163" font-size="15">{x(p['desc'])}</text>
        <rect x="35" y="190" width="790" height="1" fill="{BORDER}"/>
        <text x="36" y="220" font-size="13" class="accent">{x(p['tags'])}</text>
        <text x="815" y="220" text-anchor="end" font-size="14" class="muted">VIEW REPOSITORY</text>'''
        save('repo-'+p['slug']+'.svg',shell(860,246,body,font,static,1.34+i*.24,p['title']+' featured repository'))


def contribution_grid(font: str, static: bool, data: dict) -> None:
    available = data.get('schema_version') == 1 and data.get('available', True)
    end = dt.date.fromisoformat(data['to']) if available else dt.datetime.now(dt.timezone.utc).date()
    start = dt.date.fromisoformat(data['from']) if available else end-dt.timedelta(days=364)
    counts = {dt.date.fromisoformat(day['date']): day['count'] for day in data['days']} if available else {}
    total = sum(counts.values()) if available else None
    subtitle = (f'{total:,} contributions | trailing 365 days' if available
                else 'Contribution total unavailable | waiting for a validated GitHub response')
    updated = data['updated_at'][:10]+' UTC' if available else 'Not available'
    body = f'''<text x="35" y="40" class="eyebrow accent">CONTRIBUTION GRAPH</text>
    <text x="35" y="73" font-size="24" class="title">The work, one day at a time.</text>
    <text x="35" y="98" font-size="14" class="muted">{x(subtitle)}</text>
    <text x="35" y="117" font-size="12" class="muted">{x(start.isoformat()+' – '+end.isoformat()+' UTC')} | Updated {x(updated)}</text>'''
    grid_start = start-dt.timedelta(days=(start.weekday()+1)%7)  # Sunday-first.
    week_count = ((end-grid_start).days+1+6)//7
    x0, col_step, y0, row_step = 74, 14.4, 151, 16.5

    month_cursor = dt.date(start.year, start.month, 1)
    end_month = dt.date(end.year, end.month, 1)
    while month_cursor <= end_month:
        marker = max(start, month_cursor)
        column = (marker-grid_start).days//7
        body += f'<text x="{x0+column*col_step:.1f}" y="139" font-size="12" class="muted">{MONTHS[month_cursor.month-1]} {str(month_cursor.year)[-2:]}</text>'
        month_cursor = dt.date(month_cursor.year+(month_cursor.month == 12),
                               1 if month_cursor.month == 12 else month_cursor.month+1, 1)

    weekdays = ('Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat')
    for row, weekday in enumerate(weekdays):
        body += f'<text x="33" y="{y0+row*row_step+9:.1f}" font-size="11" class="muted">{weekday}</text>'

    max_count = max(counts.values(), default=0)
    cell_w, cell_h = 10.2, 10.2
    for week in range(week_count):
        for row in range(7):
            date = grid_start+dt.timedelta(days=week*7+row)
            in_range = start <= date <= end
            value = counts.get(date, 0)
            cx, cy = x0+week*col_step, y0+row*row_step
            delay = 0 if static else 2.05+row*.08+week*.001
            style = f' class="cell" style="--cell-delay:{delay:.3f}s"' if in_range else ''
            if not in_range:
                color, opacity, stroke = BG, 1, BORDER
                description = f'{date.isoformat()}: outside the 365-day range'
            elif not available:
                color, opacity, stroke = MUTED, .48, MUTED
                description = f'{date.isoformat()}: contribution data unavailable'
            elif value == 0:
                color, opacity, stroke = SURFACE2, 1, 'none'
                description = f'{date.isoformat()}: 0 contributions'
            else:
                opacity, stroke = .24+.76*(value/max(1, max_count))**.55, 'none'
                color = ACCENT
                description = f'{date.isoformat()}: {value} contributions'
            body += (f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{cell_w}" height="{cell_h}" '
                     f'rx="2" fill="{color}" fill-opacity="{opacity:.3f}" stroke="{stroke}" '
                     f'stroke-opacity=".7"{style}><title>{x(description)}</title></rect>')

    legend_y = 283
    body += f'''<text x="35" y="{legend_y+10}" font-size="11" class="muted">LESS</text>
    <rect x="68" y="{legend_y}" width="10" height="10" rx="2" fill="{SURFACE2}"/>
    <rect x="83" y="{legend_y}" width="10" height="10" rx="2" fill="{ACCENT}" opacity=".30"/>
    <rect x="98" y="{legend_y}" width="10" height="10" rx="2" fill="{ACCENT}" opacity=".52"/>
    <rect x="113" y="{legend_y}" width="10" height="10" rx="2" fill="{ACCENT}" opacity=".76"/>
    <rect x="128" y="{legend_y}" width="10" height="10" rx="2" fill="{ACCENT}"/>
    <text x="145" y="{legend_y+10}" font-size="11" class="muted">MORE</text>
    <rect x="197" y="{legend_y}" width="10" height="10" rx="2" fill="{BG}" stroke="{BORDER}" stroke-opacity=".7"/>
    <text x="214" y="{legend_y+10}" font-size="11" class="muted">Outside range</text>
    <rect x="321" y="{legend_y}" width="10" height="10" rx="2" fill="{MUTED}" fill-opacity=".48" stroke="{MUTED}" stroke-opacity=".7"/>
    <text x="338" y="{legend_y+10}" font-size="11" class="muted">Data unavailable</text>
    <rect x="469" y="{legend_y}" width="10" height="10" rx="2" fill="{SURFACE2}"/>
    <text x="486" y="{legend_y+10}" font-size="11" class="muted">No contributions</text>
    <text x="35" y="320" font-size="12" class="muted">Each column is a week | weekdays run Sunday to Saturday | colors scale with daily contributions</text>'''
    save('contributions.svg', shell(860, 338, body, font, static, 1.95,
         'GitHub contribution calendar for 365 days with weekdays, months, intensity legend and data status'))


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--refresh',action='store_true',help='Fetch real GitHub contribution data first')
    p.add_argument('--portrait',type=Path,help='Optional local portrait; embedded as a data URI')
    args=p.parse_args()
    static=os.getenv('STATIC','0')=='1'
    try:
        if args.refresh:
            try:
                d = fetch_contributions()
            except ContributionError as exc:
                print(f'::warning::{exc}', file=sys.stderr)
                d = load_data(strict=True)
        else:
            d = load_data()
    except ContributionError as exc:
        print(f'Error: {exc}', file=sys.stderr)
        raise SystemExit(1) from exc
    font=font_css()
    hero(font,static,args.portrait)
    tiles(font,static)
    activity(font,static,d)
    repos(font,static)
    contribution_grid(font,static,d)
    print(f'Rendered {len(list(OUT.glob("*.svg")))} self-contained SVG cards into {OUT}; STATIC={int(static)}; data_available={d.get("schema_version") == 1}; days={len(d["days"])}')


if __name__=='__main__':
    main()
