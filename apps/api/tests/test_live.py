import pytest
from app.research.live import map_probability, series_probability, live_probability


@pytest.mark.parametrize("a,b", [(0,0),(5,0),(6,0),(5,3),(6,3),(11,11),(12,11),(12,12),(15,15),(16,15)])
@pytest.mark.parametrize("p", [.35,.5,.65])
def test_map_bounds_complement_and_determinism(a,b,p):
    x=map_probability(a,b,p)
    assert 0 <= x <= 1
    assert x == map_probability(a,b,p)
    assert x + map_probability(b,a,1-p) == pytest.approx(1)


def test_terminal_and_overtime():
    assert map_probability(13,11,.3) == 1
    assert map_probability(11,13,.7) == 0
    assert map_probability(15,13,.3) == 1
    assert map_probability(12,12,.6) == pytest.approx(.36/(.36+.16))
    assert map_probability(12,11,.5) == .75
    assert map_probability(11,12,.5) == .25
    with pytest.raises(ValueError): map_probability(16,10,.5)


def test_nonlinear_round_effects():
    early=map_probability(6,0,.5)-map_probability(5,0,.5)
    close=map_probability(6,3,.5)-map_probability(5,3,.5)
    late=map_probability(12,11,.5)-map_probability(11,11,.5)
    assert 0 < early < close < late
    assert map_probability(8,6,.6) > map_probability(8,6,.5)
    assert map_probability(8,6,.5) > map_probability(7,6,.5)


@pytest.mark.parametrize("bo", [1,3,5])
def test_series_and_prior_consistency(bo):
    target=bo//2+1
    assert series_probability(target,0,bo,[]) == 1
    assert series_probability(0,target,bo,[]) == 0
    assert live_probability(.7,bo,0,0,(0,0))["team1_win_probability"] == pytest.approx(.7)
    if bo>1:
        assert live_probability(.7,bo,1,0)["team1_win_probability"] > .7
        assert live_probability(.7,bo,0,1)["team1_win_probability"] < .7


def test_side_switch_and_ot_symmetry():
    args=dict(defending_probability=.4,first_side="attack",overtime_first_side="attack")
    assert map_probability(0,0,.6,**args) == pytest.approx(.5)
    assert map_probability(12,12,.6,**args) == pytest.approx(.5)
    with pytest.raises(ValueError): map_probability(5,5,.6,defending_probability=.4)
