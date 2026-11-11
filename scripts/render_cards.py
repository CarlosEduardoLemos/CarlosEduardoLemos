#!/usr/bin/env python3
"""Render self-contained, GitHub <img>-safe SVG profile cards.

Requires Python 3.11+ and fonttools' pyftsubset executable. No third-party
Python imports. Optional `--refresh` uses GitHub GraphQL and GITHUB_TOKEN to
replace data/contributions.json with real public-profile activity.

Usage:
  python scripts/render_cards.py --refresh
  STATIC=1 python scripts/render_cards.py
  python scripts/render_cards.py --portrait assets/portrait.png
"""
from __future__ import annotations

import argparse
import base64
import calendar
import datetime as dt
import html
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
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
    if not src.exists() or not shutil.which('pyftsubset'):
        raise RuntimeError('Inter font and pyftsubset (fonttools) are required')
    glyphs = (NAME + 'IT Support Analyst → Software Development'
              + 'Building practical web applications with security in mind.'
              + 'VISIT PROFILE CONTACT LINKEDIN GITHUB EMAIL FEATURED WORK'
              + 'Security-focused IT operations Collaborative frontend contribution'
              + ''.join(p['title'] + p['subtitle'] + p['desc'] + p['tags'] + p['label'] for p in PROJECTS)
              + '0123456789,./:%+−–—•×|ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
              + 'JanFebMarAprMayJunJulAugSepOctNovDecMON TUE WED THU FRI SAT SUN'
              + 'ACTIVITY STREAK ACTIVE DAYS BUSIEST DAY CONTRIBUTIONS LAST 12 MONTHS'
              + 'No contribution data yet Daily update pending GitHub activity'
              + 'Total commits and contributions • click to explore')
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / 'inter.woff'
        subset = Path(td) / 'glyphs.txt'
        subset.write_text(glyphs, encoding='utf-8')
        subprocess.run(['pyftsubset', str(src), f'--output-file={target}',
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
      .animated-glint{display:none!important}
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
        <path d="M711 144l22 22 47-54" fill="none" stroke="{ACCENT}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
        <circle class="animated-glint" cx="803" cy="83" r="4" fill="{ACCENT}" opacity="0">
          <animate attributeName="opacity" values="0;1;0" dur="3s" begin="0.9s" repeatCount="indefinite"/>
        </circle>'''
    if static:
        pic = pic.replace('<circle class="animated-glint" cx="803" cy="83" r="4" fill="'+ACCENT+'" opacity="0">\n          <animate attributeName="opacity" values="0;1;0" dur="3s" begin="0.9s" repeatCount="indefinite"/>\n        </circle>', '')
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


def fetch_contributions() -> dict:
    token = os.getenv('GITHUB_TOKEN') or os.getenv('GH_TOKEN')
    if not token:
        raise RuntimeError('GITHUB_TOKEN required for --refresh (set in GitHub Actions)')
    today = dt.datetime.now(dt.timezone.utc).date()
    first = today - dt.timedelta(days=364)
    query = '''query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){contributionsCollection(from:$from,to:$to){contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}'''
    payload = json.dumps({'query': query, 'variables': {
        'login': USERNAME, 'from': first.isoformat()+'T00:00:00Z',
        'to': today.isoformat()+'T23:59:59Z'}}).encode('utf-8')
    request = urllib.request.Request('https://api.github.com/graphql', data=payload,
        headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
                 'Content-Type':'application/json','User-Agent':'profile-card-renderer'}, method='POST')
    with urllib.request.urlopen(request, timeout=35) as response:
        result = json.load(response)
    if result.get('errors') or not result.get('data',{}).get('user'):
        raise RuntimeError('GitHub GraphQL error: '+str(result.get('errors')))
    cal = result['data']['user']['contributionsCollection']['contributionCalendar']
    days = sorted(({'date': d['date'], 'count': int(d['contributionCount'])}
                   for week in cal['weeks'] for d in week['contributionDays']
                   if first.isoformat() <= d['date'] <= today.isoformat()),
                  key=lambda d:d['date'])
    result = {'username':USERNAME,'updated_at':dt.datetime.now(dt.timezone.utc).isoformat(),
              'from':first.isoformat(),'to':today.isoformat(),'days':days}
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result


def get_data() -> dict:
    if not DATA.exists():
        return {'username': USERNAME, 'days': []}
    d = json.loads(DATA.read_text(encoding='utf-8'))
    if d.get('username') != USERNAME or not isinstance(d.get('days'),list):
        raise ValueError('Invalid contributions.json; expected username and days array')
    # Merge duplicates, reject negative values / malformed dates.
    normalized = {}
    for day in d['days']:
        date = dt.date.fromisoformat(day['date'])
        count = int(day['count'])
        if count < 0:
            raise ValueError('Contribution count cannot be negative')
        normalized[date.isoformat()] = count
    d['days'] = [{'date': k,'count': v} for k,v in sorted(normalized.items())]
    return d


def stats(data: dict) -> dict:
    counts = {dt.date.fromisoformat(d['date']):d['count'] for d in data['days']}
    if not counts:
        return {'active':0,'streak':0,'busiest':None,'monthly':[], 'total':0}
    today = dt.datetime.now(dt.timezone.utc).date()
    end = min(today, max(counts))
    # Typical contribution streak: count back from today, or yesterday when today is empty.
    cursor = end if counts.get(end,0)>0 else end-dt.timedelta(days=1)
    streak = 0
    while counts.get(cursor,0)>0:
        streak += 1
        cursor -= dt.timedelta(days=1)
    months=[]
    year,month = end.year,end.month
    for offset in range(11,-1,-1):
        y = year+(month-1-offset)//12
        m = (month-1-offset)%12+1
        total=sum(v for d,v in counts.items() if d.year==y and d.month==m)
        months.append((dt.date(y,m,1),total))
    busiest = max(((d,v) for d,v in counts.items() if v>0),
                  key=lambda item:(item[1],-item[0].toordinal()), default=None)
    return {'active':sum(v>0 for v in counts.values()),'streak':streak,
            'busiest':busiest,'monthly':months,'total':sum(counts.values())}


def activity(font: str, static: bool, data: dict) -> None:
    s=stats(data)
    have=bool(data['days'])
    b=s['busiest']
    busy=f'{b[0]:%d %b} · {b[1]}' if b else '—'
    content = f'''<text x="35" y="44" class="eyebrow accent">GITHUB ACTIVITY</text>
    <text x="35" y="82" font-size="26" class="title">Contributions by month</text>
    <text x="35" y="108" font-size="13" class="muted">Last 12 calendar months · UTC</text>
    <path d="M34 130H826" stroke="{BORDER}" opacity=".6"/>
    <text x="47" y="171" font-size="26" font-weight="700">{s['streak'] if have else '—'}</text>
    <text x="47" y="193" class="muted small">DAY STREAK</text>
    <text x="324" y="171" font-size="26" font-weight="700">{s['active'] if have else '—'}</text>
    <text x="324" y="193" class="muted small">ACTIVE DAYS</text>
    <text x="595" y="171" font-size="23" font-weight="700">{x(busy)}</text>
    <text x="595" y="193" class="muted small">BUSIEST DAY</text>
    <path d="M35 213H825" stroke="{BORDER}" opacity=".6"/>'''
    if have:
        maxv=max(1,max(v for _,v in s['monthly']))
        for i,(date,v) in enumerate(s['monthly']):
            height= max(3, round(102*v/maxv)) if v else 3
            bx=46+i*65
            content+=f'''<rect x="{bx}" y="{346-height}" width="35" height="{height}" rx="5" fill="{ACCENT if v else SURFACE2}" class="bar" style="--delay:{0 if static else 1.0+i*.045:.3f}s"/>
            <text x="{bx+18}" y="{364-height}" font-size="10" text-anchor="middle" class="muted">{v}</text>
            <text x="{bx+18}" y="373" font-size="12" text-anchor="middle" class="muted">{date:%b}</text>'''
    else:
        content+='''<text x="430" y="298" font-size="19" text-anchor="middle" class="muted">Daily contribution data pending first workflow run</text>'''
    save('activity.svg',shell(860,405,content,font,static,.72,'Monthly GitHub contributions, streak, active days and busiest day'))


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
    s=stats(data)
    counts={dt.date.fromisoformat(d['date']):d['count'] for d in data['days']}
    body=f'''<text x="35" y="43" class="eyebrow accent">CONTRIBUTION GRAPH</text>
    <text x="35" y="78" font-size="25" class="title">The work, one day at a time.</text>
    <text x="35" y="102" font-size="13" class="muted">{x(str(s['total'])+' contributions · last 365 days' if counts else 'Daily data pending first workflow run')}</text>'''
    today=dt.datetime.now(dt.timezone.utc).date()
    start=today-dt.timedelta(days=364)
    grid_start=start-dt.timedelta(days=(start.weekday()+1)%7)  # Sunday-first
    max_count=max(counts.values(),default=0)
    # Fixed geometry for 53 weeks, rows Sunday through Saturday.
    for i in range(371):
        date=grid_start+dt.timedelta(days=i)
        if date>today or date<start:
            continue
        week=i//7
        row=i%7
        v=counts.get(date,0)
        opacity=0 if v==0 else (.23+.77*(v/max(1,max_count))**.55)
        color=SURFACE2 if v==0 else ACCENT
        cx=42+week*14.6
        cy=137+row*18
        delay=0 if static else 2.28+week*.014+row*.012
        body+=f'<rect x="{cx:.1f}" y="{cy}" width="11.4" height="11.4" rx="2.5" fill="{color}" fill-opacity="{opacity if v else 1:.3f}" class="cell" style="--cell-delay:{delay:.3f}s"><title>{date.isoformat()}: {v} contributions</title></rect>'
    body+=f'''<text x="42" y="288" font-size="11" class="muted">LESS</text>
    <rect x="83" y="277" width="11" height="11" rx="2" fill="{SURFACE2}"/>
    <rect x="99" y="277" width="11" height="11" rx="2" fill="{ACCENT}" opacity=".30"/>
    <rect x="115" y="277" width="11" height="11" rx="2" fill="{ACCENT}" opacity=".55"/>
    <rect x="131" y="277" width="11" height="11" rx="2" fill="{ACCENT}" opacity=".8"/>
    <rect x="147" y="277" width="11" height="11" rx="2" fill="{ACCENT}"/>
    <text x="166" y="288" font-size="11" class="muted">MORE</text>'''
    save('contributions.svg',shell(860,314,body,font,static,2.20,'GitHub contribution heatmap in brand violet'))


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--refresh',action='store_true',help='Fetch real GitHub contribution data first')
    p.add_argument('--portrait',type=Path,help='Optional local portrait; embedded as a data URI')
    args=p.parse_args()
    static=os.getenv('STATIC','0')=='1'
    if args.refresh:
        fetch_contributions()
    d=get_data()
    font=font_css()
    hero(font,static,args.portrait)
    tiles(font,static)
    activity(font,static,d)
    repos(font,static)
    contribution_grid(font,static,d)
    print(f'Rendered {len(list(OUT.glob("*.svg")))} self-contained SVG cards into {OUT}; STATIC={int(static)}; days={len(d["days"])}')


if __name__=='__main__':
    main()
