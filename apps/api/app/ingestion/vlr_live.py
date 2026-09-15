"""Read-only, bounded live-source snapshots. Never writes evaluation observations."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import re
import threading
import time

import httpx
from bs4 import BeautifulSoup

from app.ingestion.vlr import extract_id, VLR_BASE_URL
from app.research.live import map_winner, series_probability

ACTIVE_SECONDS = 30
IDLE_SECONDS = 300
MAX_ACTIVE = 4


def parse_live_page(content, vlr_id):
    soup=BeautifulSoup(content,'html.parser')
    notes=[n.get_text(' ',strip=True).lower() for n in soup.select('.match-header-vs-note')]
    if not any(n in {'live','final'} for n in notes):
        raise ValueError('Explicit live/final source status required')
    status='completed' if 'final' in notes else 'live'
    bo=re.search(r'\bbo([135])\b',' '.join(notes))
    if bo is None: raise ValueError('Unknown series format')
    teams=[]
    for side in (1,2):
        link=soup.select_one(f'.match-header-link.mod-{side}')
        name=link.select_one('.wf-title-med') if link else None
        tid=extract_id(link.get('href')) if link else None
        if not tid or name is None: raise ValueError('Unknown team identity')
        teams.append((tid,name.get_text(' ',strip=True)))
    if teams[0][0]==teams[1][0]: raise ValueError('Duplicate teams')
    score=soup.select_one('.match-header-vs-score .sp-hide')
    parts=re.findall(r'\d+',score.get_text(' ',strip=True)) if score else []
    if len(parts)!=2: raise ValueError('Unknown series score')
    a,b=map(int,parts);best_of=int(bo.group(1));target=best_of//2+1
    series_probability(a,b,best_of,[.5]*max(0,best_of-a-b))
    if (status=='completed') != (max(a,b)==target):
        raise ValueError('Status and score disagree')
    map_number=a+b+1 if status=='live' else None
    rounds=None;map_name=None
    nav={}
    for n in soup.select('.vm-stats-gamesnav-item[data-game-id]'):
        if n.get('data-game-id','').isdigit():
            label=n.select_one('div > span')
            if label and label.get_text(strip=True).isdigit():nav[int(label.get_text(strip=True))]=n['data-game-id']
    if map_number in nav:
        game=soup.select_one(f'.vm-stats-game[data-game-id="{nav[map_number]}"] .vm-stats-game-header')
        if game:
            sides=game.select('.team')
            scores=[s.select_one('.score') for s in sides]
            names=[s.select_one('.team-name') for s in sides]
            if (len(scores)==2 and all(s and s.get_text(strip=True).isdigit() for s in scores)
                    and all(n and n.get_text(' ',strip=True)==teams[i][1] for i,n in enumerate(names))):
                candidate=tuple(int(s.get_text(strip=True)) for s in scores)
                map_winner(*candidate)
                rounds=candidate
                name=game.select_one('.map span')
                map_name=' '.join(name.find_all(string=True,recursive=False)).strip() if name else None
    event=soup.select_one('.match-header-event')
    start=soup.select_one('.moment-tz-convert[data-utc-ts]')
    scheduled=None
    if start:
        try:scheduled=datetime.strptime(start['data-utc-ts'],'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).isoformat()
        except ValueError:pass
    return dict(vlr_id=vlr_id,status=status,team1_vlr_id=teams[0][0],team2_vlr_id=teams[1][0],
                team1_name=teams[0][1],team2_name=teams[1][1],best_of=best_of,
                series_score=[a,b],map_number=map_number,map_name=map_name,round_score=rounds,
                side=None,event_name=event.get_text(' ',strip=True) if event else None,
                scheduled_at=scheduled,
                source_url=f'{VLR_BASE_URL}/{vlr_id}/',raw_sha256=hashlib.sha256(content).hexdigest(),
                observed_at=datetime.now(timezone.utc).isoformat())


class LiveSource:
    def __init__(self):
        self.lock=threading.Lock();self.deadline=0.;self.cached=None

    def get(self):
        with self.lock:
            if self.cached is not None and time.monotonic()<self.deadline:
                return self.cached
            now=datetime.now(timezone.utc).isoformat()
            try:
                with httpx.Client(timeout=4,follow_redirects=True,max_redirects=2,headers={'User-Agent':'Mozilla/5.0'}) as client:
                    listing=client.get(f'{VLR_BASE_URL}/matches/');listing.raise_for_status()
                    soup=BeautifulSoup(listing.content,'html.parser')
                    cards=soup.select('a.wf-module-item.match-item')
                    if not cards: raise ValueError('Listing markup unavailable')
                    active=[]
                    for card in cards:
                        status=card.select_one('.ml-status')
                        if status and status.get_text(strip=True).lower()=='live':
                            mid=extract_id(card.get('href'))
                            if mid and mid not in active:active.append(mid)
                    def fetch(mid):
                        try:
                            response=client.get(f'{VLR_BASE_URL}/{mid}/');response.raise_for_status()
                            return parse_live_page(response.content,mid)
                        except (httpx.HTTPError,ValueError):return None
                    with ThreadPoolExecutor(max_workers=MAX_ACTIVE) as pool:
                        rows=list(pool.map(fetch,active[:MAX_ACTIVE]))
                    items=[r for r in rows if r is not None]
                    cadence=ACTIVE_SECONDS if active else IDLE_SECONDS
                    result=dict(source_status='partial' if len(active)>len(items) else 'ok',
                                items=items,observed_at=now,poll_seconds=cadence,
                                active_listed=len(active),coverage_limit=MAX_ACTIVE)
            except (httpx.HTTPError,ValueError):
                cadence=60
                result=dict(source_status='unavailable',items=[],observed_at=now,
                            poll_seconds=cadence,active_listed=None,coverage_limit=MAX_ACTIVE)
            self.cached=result;self.deadline=time.monotonic()+cadence
            return result


source=LiveSource()
