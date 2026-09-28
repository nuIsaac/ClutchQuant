"""Live VLR validation using TEST_DATABASE_URL and a NEW disposable schema only.

Run from apps/api with PYTHONPATH=. Never uses the application DATABASE_URL.
--keep-schema retains the generated schema for local API/browser inspection.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import time
from unittest.mock import patch
from uuid import uuid4
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema
from app import artifacts
from app.data_sources.vlr import VlrSource
from app.dependencies import get_db
from app.main import app
from app.models import Match, Team, Forecast, PipelineRun
from app.ingestion.multi_source import sync_sources
from app.research import generate_models
from app.research.elo import expected_score, update_ratings
from app.research.preview import load_history
from app.scoring import calculate_brier_score, calculate_log_loss


def fingerprint(connection, table, where=''):
    digest=hashlib.sha256();count=0
    for row in connection.execute(text(f'SELECT row_to_json(t)::text FROM (SELECT * FROM {table} {where} ORDER BY id) t')).scalars():
        count+=1;digest.update(row.encode()+b'\n')
    return {'count':count,'sha256':digest.hexdigest()}


def integrity(connection):
    tables=['matches','match_maps','player_map_stats','forecasts','model_runs','match_observations']
    result={'tables':{t:fingerprint(connection,t) for t in tables},'orphans':{}}
    result['distinct_match_ids']=connection.scalar(text('SELECT count(DISTINCT id) FROM matches'))
    result['duplicate_forecast_groups']=connection.scalar(text('SELECT count(*) FROM (SELECT match_id,source_key FROM forecasts GROUP BY 1,2 HAVING count(*)>1) d'))
    result['potential_duplicate_match_groups']=connection.scalar(text('SELECT count(*) FROM (SELECT least(team1_id,team2_id),greatest(team1_id,team2_id),event_name,stage,scheduled_at FROM matches GROUP BY 1,2,3,4,5 HAVING count(*)>1) d'))
    for table,column,target in [('matches','team1_id','teams'),('matches','team2_id','teams'),('match_maps','match_id','matches'),('player_map_stats','match_map_id','match_maps'),('player_map_stats','player_id','players'),('player_map_stats','team_id','teams'),('forecasts','match_id','matches'),('forecasts','team1_id','teams'),('forecasts','team2_id','teams'),('forecasts','model_run_id','model_runs')]:
        result['orphans'][table+'.'+column]=connection.scalar(text(f'SELECT count(*) FROM {table} a LEFT JOIN {target} b ON a.{column}=b.id WHERE a.{column} IS NOT NULL AND b.id IS NULL'))
    return result


def baseline(rows):
    ratings={};correct=0;brier=0.;loss=0.
    for _,a,b,sa,sb,_ in sorted(rows,key=lambda r:(r[5],r[0])):
        p=expected_score(ratings.get(a,1500),ratings.get(b,1500));y=int(sa>sb)
        correct+=int((p>=.5)==bool(y));brier+=calculate_brier_score(p,y);loss+=calculate_log_loss(p,y)
        ratings[a],ratings[b]=update_ratings(ratings.get(a,1500),ratings.get(b,1500),y)
    return dict(model='frozen Elo v1',availability='UNKNOWN; chronological diagnostic only, not prospective validation',
                matches=len(rows),accuracy=correct/len(rows),brier=brier/len(rows),log_loss=loss/len(rows),
                period_start=min(r[5] for r in rows),period_end=max(r[5] for r in rows))


def config_for(connection):
    config=Config('alembic.ini');config.attributes['connection']=connection;return config


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',required=True);parser.add_argument('--keep-schema',action='store_true');args=parser.parse_args()
    url=os.environ['TEST_DATABASE_URL'];schema='clutchquant_live_validation_'+uuid4().hex
    admin=create_engine(url);engine=None
    with admin.begin() as c:c.execute(CreateSchema(schema))
    try:
        engine=create_engine(url,connect_args={'options':f'-csearch_path={schema}'})
        sessions=sessionmaker(bind=engine,autoflush=False)
        def migrate(revision):
            with engine.begin() as c:command.upgrade(config_for(c),revision)
        migrate('b72c904e1a36')
        history=load_history();rows=history['rows']
        team_ids=sorted({team for row in rows for team in row[1:3]})
        with engine.begin() as c:
            c.execute(insert(Team),[{'vlr_id':tid,'name':f'Historical VLR team {tid}'} for tid in team_ids])
            mapping=dict(c.execute(select(Team.vlr_id,Team.id)).all())
            values=[dict(vlr_id=mid,team1_id=mapping[a],team2_id=mapping[b],team1_score=sa,team2_score=sb,
                         scheduled_at=datetime.fromisoformat(at),status='completed') for mid,a,b,sa,sb,at in rows]
            for start in range(0,len(values),1000):c.execute(insert(Match),values[start:start+1000])
        with engine.connect() as c:before=integrity(c)
        migrate('head');migrate('head')
        with engine.connect() as c:
            after=integrity(c);assert before==after
            legacy_ids=dict(c.execute(select(Match.vlr_id,Match.id)).all())
            mapping_count=c.scalar(text('SELECT count(*) FROM match_sources'))
            command.check(config_for(c))
        report={'scope':'disposable schema; bundled history, not a production database copy','schema':schema,
                'history_sha256':history['sha256'],'migration_before':before,'migration_after':after,
                'backfilled_match_sources':mapping_count,'model_baseline':baseline(rows),'runs':[]}
        root=Path('/tmp')/schema;root.mkdir()
        with patch.object(artifacts,'ARTIFACT_ROOT',root),patch.object(generate_models,'SessionLocal',sessions),patch.object(generate_models,'engine',engine):
            for cycle in (1,2):
                at=datetime.now(timezone.utc);started=time.monotonic()
                ingestion=sync_sources([VlrSource()],pages=1,session_factory=sessions)
                assert ingestion['failed']==0 and ingestion['unresolved']==0
                forecasts=generate_models.generate(prospective=True)
                with sessions() as db:
                    db.add(PipelineRun(id=uuid4().hex,started_at=at,finished_at=datetime.now(timezone.utc),status='SUCCEEDED',details={
                        'collection_enabled':True,'steps':{'upcoming':ingestion,'forecasts':forecasts}}));db.commit()
                    current=dict(db.execute(select(Match.vlr_id,Match.id)).all())
                    assert all(current[k]==v for k,v in legacy_ids.items())
                    forecast_count=db.query(Forecast).count()
                report['runs'].append({'ingestion':ingestion,'forecasts':forecasts,'forecast_count':forecast_count,'seconds':round(time.monotonic()-started,3)})
                if cycle==2:
                    assert ingestion['created']==0 and ingestion['sources']['vlr']['match_mappings_created']==0
                    assert forecasts['created']==0 and forecast_count==report['runs'][0]['forecast_count']
            def dependency():
                with sessions() as db:yield db
            app.dependency_overrides[get_db]=dependency
            try:
                with TestClient(app) as client:
                    response=client.get('/api/v1/matches/upcoming/forecasts');assert response.status_code==200
                    matches=response.json();assert matches and all(m['sources'] and m['forecasts'] for m in matches)
                    report['api']={'matches':len(matches),'forecasts':sum(len(m['forecasts']) for m in matches),
                        'match_ids':[m['id'] for m in matches],'coverage':client.get('/api/v1/data/coverage').json(),
                        'health':client.get('/api/v1/data/health').json()}
            finally:app.dependency_overrides.clear()
        with engine.connect() as c:
            final=integrity(c);report['final_integrity']=final
            assert fingerprint(c,'matches',f'WHERE id<={max(legacy_ids.values())}')==before['tables']['matches']
            assert final['duplicate_forecast_groups']==0 and not any(final['orphans'].values())
        report['historical_match_rows_unchanged']=True;report['recorded_at']=datetime.now(timezone.utc).isoformat()
        Path(args.report).write_text(json.dumps(report,indent=2,default=str)+'\n')
        print(json.dumps({'report':args.report,'schema':schema,'history_matches':len(rows),
            'runs':[{'saved':r['ingestion']['saved'],'created':r['ingestion']['created'],'forecasts':r['forecasts']['created']} for r in report['runs']]}))
    finally:
        if engine:engine.dispose()
        if not args.keep_schema:
            with admin.begin() as c:c.execute(DropSchema(schema,cascade=True))
        admin.dispose()

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO);logging.getLogger('httpx').setLevel(logging.WARNING)
    main()
