"""Synthetic parser fixtures shaped like inspected VLR HTML, not live observations."""
from types import SimpleNamespace
import httpx
import pytest
from app.ingestion.vlr_live import parse_live_page, LiveSource


def fixture(status='live',score='0:0',rounds=(8,6)):
    return f'''<div class="match-header-vs-note">{status}</div><div class="match-header-vs-note">Bo3</div>
    <span class="moment-tz-convert" data-utc-ts="2026-09-15 12:00:00"></span>
    <a class="match-header-link mod-1" href="/team/10/a"><div class="wf-title-med">A</div></a>
    <a class="match-header-link mod-2" href="/team/20/b"><div class="wf-title-med">B</div></a>
    <div class="match-header-vs-score"><div class="sp-hide">{score}</div></div>
    <a class="vm-stats-gamesnav-item" data-game-id="99"><div><span>1</span>Ascent</div></a>
    <div class="vm-stats-game" data-game-id="99"><div class="vm-stats-game-header">
      <div class="team"><div class="team-name">A</div><div class="score">{rounds[0]}</div></div>
      <div class="map"><span>Ascent</span></div>
      <div class="team"><div class="team-name">B</div><div class="score">{rounds[1]}</div></div>
    </div></div>'''.encode()


def test_real_shaped_state_requires_explicit_status_and_scores():
    state=parse_live_page(fixture(),42)
    assert state['round_score']==(8,6) and state['series_score']==[0,0]
    assert state['side'] is None and state['map_name']=='Ascent'
    assert len(state['raw_sha256'])==64
    with pytest.raises(ValueError):parse_live_page(fixture('upcoming'),42)
    with pytest.raises(ValueError):parse_live_page(fixture(score='?'),42)
    with pytest.raises(ValueError):parse_live_page(fixture(rounds=(16,9)),42)
    with pytest.raises(ValueError):parse_live_page(fixture(status='final'),42)


def test_unknown_rounds_are_not_assumed_zero():
    assert parse_live_page(fixture(rounds=('-', '-')),42)['round_score'] is None
    assert parse_live_page(fixture(status='final',score='2:0'),42)['status']=='completed'


def test_cache_limits_source_requests_and_fails_closed(monkeypatch):
    calls=[]
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,url):
            calls.append(url)
            body=b'<a class="wf-module-item match-item" href="/42/a"><div class="ml-status">Upcoming</div></a>'
            return httpx.Response(200,content=body,request=httpx.Request('GET',url))
    monkeypatch.setattr('app.ingestion.vlr_live.httpx.Client',Client)
    cache=LiveSource()
    assert cache.get()['items']==[]
    assert cache.get()['poll_seconds']==300
    assert len(calls)==1
    monkeypatch.setattr(Client,'get',lambda *_:httpx.Response(403,request=httpx.Request('GET','https://www.vlr.gg/')))
    cache.deadline=0
    assert cache.get()['source_status']=='unavailable'
    assert cache.get()['items']==[]


def test_api_returns_only_source_states_without_writing(monkeypatch):
    from app.routers.live import live_matches, LiveResponse
    payload=dict(source_status='ok',items=[],observed_at='2026-09-15T12:00:00Z',poll_seconds=300,active_listed=0,coverage_limit=4)
    monkeypatch.setattr('app.routers.live.source.get',lambda:payload)
    assert LiveResponse.model_validate(live_matches(SimpleNamespace())).items==[]


def test_live_prior_excludes_current_and_later_series(monkeypatch):
    from app.routers.live import live_matches, LiveResponse
    state = parse_live_page(fixture(), 42)
    payload = dict(source_status='ok', items=[state], observed_at=state['observed_at'],
                   poll_seconds=30, active_listed=1, coverage_limit=4)
    monkeypatch.setattr('app.routers.live.source.get', lambda: payload)
    monkeypatch.setattr('app.routers.live.load_history', lambda: {'rows': [
        [1, 10, 20, 2, 0, '2026-09-14T12:00:00+00:00'],
        [42, 10, 20, 2, 0, '2026-09-14T13:00:00+00:00'],
        [99, 10, 20, 2, 0, '2026-09-16T12:00:00+00:00']]})
    monkeypatch.setattr('app.routers.live.current_rows', lambda db: {})
    row = LiveResponse.model_validate(live_matches(SimpleNamespace())).items[0]
    assert row.history_count == 1
    assert row.team1_rating == 1516 and row.team2_rating == 1484
    assert row.team1_win_probability > row.pre_match_probability > .5
    state['scheduled_at'] = None
    row = LiveResponse.model_validate(live_matches(SimpleNamespace())).items[0]
    assert row.team1_win_probability is None and row.history_count == 0
