"""Diagnostic map calibration only. Never promotes a live model or writes DB rows."""
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from scipy.optimize import minimize_scalar
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine
from app.models import Match, MatchMap
from app.research.preview import load_history, encode
from app.research.elo import expected_score, update_ratings
from app.research.live import map_probability
import hashlib


def main():
    history=load_history()
    with engine.connect() as c:
        c.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        with Session(bind=c) as db:
            maps=[dict(match_vlr_id=m.vlr_id,game_id=g.vlr_game_id,map_name=g.map_name,
                       score_a=g.team1_score,score_b=g.team2_score)
                  for g,m in db.execute(select(MatchMap,Match).join(Match,Match.id==MatchMap.match_id))]
    by_match=defaultdict(list)
    for row in maps:
        a,b=row['score_a'],row['score_b']
        if a is not None and b is not None and max(a,b)>=13 and abs(a-b)>=2:
            by_match[row['match_vlr_id']].append(row)
    ratings={};samples=[]
    # All map features for a series are captured before its result updates Elo.
    # Equal scheduled times are grouped, so one result cannot affect its peers.
    groups=defaultdict(list)
    for row in history['rows']: groups[row[5]].append(row)
    for at,rows in sorted(groups.items()):
        for mid,a,b,sa,sb,_ in rows:
            delta=(ratings.get(a,1500)-ratings.get(b,1500))*math.log(10)/400
            for item in by_match.get(mid,[]):
                samples.append({**item,'scheduled_at':at,'elo_log_odds':delta,
                                'outcome':int(item['score_a']>item['score_b'])})
        for mid,a,b,sa,sb,_ in rows:
            ratings[a],ratings[b]=update_ratings(ratings.get(a,1500),ratings.get(b,1500),int(sa>sb))
    dates=sorted({r['scheduled_at'] for r in samples})
    if len(dates)<10: raise ValueError('Insufficient chronological groups for diagnostic calibration')
    cutoff=dates[int(len(dates)*.8)]
    train=[r for r in samples if r['scheduled_at']<cutoff]
    test=[r for r in samples if r['scheduled_at']>=cutoff]
    def predict(row,beta):
        q=1/(1+math.exp(-beta*row['elo_log_odds']))
        return map_probability(0,0,q)
    def metrics(rows,predictor):
        ps=[min(1-1e-12,max(1e-12,predictor(r))) for r in rows]
        return {'count':len(rows),'brier':sum((p-r['outcome'])**2 for p,r in zip(ps,rows))/len(rows),
                'log_loss':-sum(r['outcome']*math.log(p)+(1-r['outcome'])*math.log(1-p) for p,r in zip(ps,rows))/len(rows)}
    fit=minimize_scalar(lambda b:metrics(train,lambda r:predict(r,b))['log_loss'],bounds=(0,2),method='bounded')
    report={'protocol':'map-calibration-diagnostic-v1','created_at':datetime.now(timezone.utc).isoformat(),
            'historical_availability':'UNKNOWN','round_state_training_samples':0,
            'database_maps':len(maps),'usable_maps':len(samples),'series':len({r['match_vlr_id'] for r in samples}),
            'map_names':sorted({r['map_name'] for r in samples}),'range':[dates[0],dates[-1]],
            'train_maps':len(train),'holdout_from':cutoff,'fitted_round_log_odds_scale':float(fit.x),
            'holdout':{'fitted':metrics(test,lambda r:predict(r,fit.x)),
                       'elo_as_map_prior':metrics(test,lambda r:1/(1+math.exp(-r['elo_log_odds']))),
                       'neutral':metrics(test,lambda r:.5)},
            'deployed_mapping':'invert_series_then_map_probability',
            'decision':'Map-only diagnostic lacks round-state validation. Retain the coherent pre-match series prior; no fitted live model promoted.',
            'research_snapshot_sha256':history['sha256'],
            'map_input_sha256':hashlib.sha256(encode(samples)).hexdigest(),'map_inputs':samples}
    Path(__file__).with_name('live_calibration.json').write_bytes(encode(report)+b'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='map_inputs'},indent=2))


if __name__=='__main__':main()
