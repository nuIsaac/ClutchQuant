from datetime import datetime,timedelta,timezone
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import get_db
from app.models import Base, PipelineRun


def test_public_health_is_sanitized_and_disabled_thespike_is_normal():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    now=datetime.now(timezone.utc)
    with Session(engine) as db:
        db.add(PipelineRun(id='a'*32,started_at=now-timedelta(minutes=2),finished_at=now,status='SUCCEEDED',details={
            'collection_enabled':True,'secret':'do-not-expose',
            'steps':{'upcoming':{'sources':{'vlr':{'saved':8,'failed':0,'fetched':10,'token':'do-not-expose'}}},
                     'forecasts':{'status':'GENERATED','created':8,'skipped':0,'duplicates_prevented':0,'dataset_sha256':'private-key'}}}))
        db.commit()
    def session():
        with Session(engine) as db: yield db
    app.dependency_overrides[get_db]=session
    try:
        with TestClient(app) as client:
            payload=client.get('/api/v1/data/health').json()
            assert payload['sources']['vlr']['status']=='ok'
            assert payload['sources']['thespike']['status']=='disabled'
            assert payload['sources']['vlr']['counts']['saved']==8
            assert payload['forecasts']['created']==8
            assert 'do-not-expose' not in json.dumps(payload)
            assert 'private-key' not in json.dumps(payload)
            assert client.get('/api/v1/data/coverage').json()['upcoming']['canonical_total']==0
            with Session(engine) as db:
                db.add(PipelineRun(id='b'*32,started_at=now+timedelta(seconds=1),finished_at=now+timedelta(seconds=2),status='PARTIAL',details={
                    'collection_enabled':True,'steps':{'upcoming':{'sources':{'vlr':{'saved':0,'failed':1}}}}}))
                db.commit()
            payload=client.get('/api/v1/data/health').json()
            assert payload['sources']['vlr']['status']=='unavailable'
            assert payload['sources']['vlr']['last_success_at'] is not None
            assert payload['sources']['thespike']['status']=='disabled'
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
