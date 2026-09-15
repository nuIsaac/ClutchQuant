"""Current live probabilities. No database writes and no forecast-table output."""
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.ingestion.vlr_live import source
from app.research.elo import expected_score
from app.research.live import live_probability, VERSION
from app.research.preview import load_history, current_rows, build_state, encode
import hashlib

router=APIRouter(prefix='/api/v1/matches',tags=['live'])


class LiveMatch(BaseModel):
    vlr_id:int
    status:Literal['live','completed']
    team1_name:str
    team2_name:str
    best_of:int
    series_score:tuple[int,int]
    map_number:int|None
    map_name:str|None
    round_score:tuple[int,int]|None
    side:None=None
    event_name:str|None
    observed_at:datetime
    scheduled_at:datetime|None=None
    source_url:str
    raw_sha256:str
    team1_win_probability:float|None=Field(default=None,ge=0,le=1)
    current_map_probability:float|None=Field(default=None,ge=0,le=1)
    pre_match_probability:float|None=Field(default=None,ge=0,le=1)
    team1_rating:float|None=None
    team2_rating:float|None=None
    team1_unseen:bool|None=None
    team2_unseen:bool|None=None
    history_count:int=0
    model_version:str=VERSION
    dataset_sha256:str|None=None
    reason:str|None=None


class LiveResponse(BaseModel):
    source_status:Literal['ok','partial','unavailable']
    observed_at:datetime
    poll_seconds:int
    active_listed:int|None
    coverage_limit:int
    items:list[LiveMatch]


@router.get('/live',response_model=LiveResponse)
def live_matches(db:Annotated[Session,Depends(get_db)]):
    result=source.get()
    if not result['items']:return result
    try:
        history=load_history()
        merged={r[0]:r for r in history['rows']};merged.update(current_rows(db))
        # Never allow a currently-live series to train its own prior.
        active={m['vlr_id'] for m in result['items']}
        for mid in active:merged.pop(mid,None)
    except (OSError,ValueError,KeyError):merged={}
    items=[]
    for item in result['items']:
        row=dict(item)
        cutoff=datetime.fromisoformat(row['scheduled_at']) if row.get('scheduled_at') else None
        ratings,used=build_state(merged.values(),cutoff) if cutoff else ({},[])
        key=hashlib.sha256(encode(used)).hexdigest() if used else None
        if not used:
            row['reason']='Model history unavailable'
            if row['status']=='completed':
                row['team1_win_probability']=float(row['series_score'][0]>row['series_score'][1])
        else:
            a,b=(ratings.get(row[k],1500) for k in ['team1_vlr_id','team2_vlr_id'])
            prior=expected_score(a,b)
            row.update(live_probability(prior,row['best_of'],*row['series_score'],row['round_score']))
            row.update(pre_match_probability=prior,team1_rating=a,team2_rating=b,
                       team1_unseen=row['team1_vlr_id'] not in ratings,
                       team2_unseen=row['team2_vlr_id'] not in ratings,
                       history_count=len(used),dataset_sha256=key)
            if row['round_score'] is None and row['status']=='live':row['reason']='Series score only; round state unavailable'
        items.append(row)
    return {**result,'items':items}
