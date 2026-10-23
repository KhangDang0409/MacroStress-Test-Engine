"""Offline regression tests: fixtures are test-only, never a runtime fallback."""
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bridge
from bridge import DEFAULTS, SCENARIOS, WebUI, execute, validate
from app import app


def market(ticker, **kwargs):
    """Fixed two-year fixture with defensive and volatile assets."""
    rng = np.random.RandomState(sum(map(ord,ticker)))
    sigma = {'JNJ':.008,'WMT':.019,'PG':.035,'SPY':.011}.get(ticker,.028)
    close=100*np.exp(np.cumsum(rng.normal(.0002,sigma,504)))
    return pd.DataFrame({'Close':close,'Volume':rng.randint(10000,1000000,504)},
                        index=pd.bdate_range('2023-01-02',periods=504))


def reference(params, seed, downloader=market):
    """Run the uploaded program with standard imports and a recording UI.
    Production uses a scoped importer; reference uses ordinary imports.
    The numerical code is the original in both, verified by SHA-256 below.
    """
    ui=WebUI(params,use_cache=False)
    namespace={'__name__':'reference'}
    np.random.seed(seed)
    with patch.dict(sys.modules,{'streamlit':ui,'yfinance':SimpleNamespace(download=downloader)}):
        exec(compile(bridge.SOURCE.read_bytes(),'original_uploaded_app.py','exec'),namespace)
    return ui.output,namespace

NUMERIC_NAMES = ['weights','prices','volumes','daily_returns','historical_vols','historical_corr','mu','adtv',
 'jump_intensity_arr','jump_mean_arr','jump_vol_arr','liquidity_penalty_arr','mu_shocked','cov_shocked',
 'stressed_corr','simulated_paths','final_values','percentage_returns','var_95_val','var_95_pct',
 'cvar_95_val','cvar_95_pct','prob_of_loss','sample_indices','classifier_df']

@pytest.mark.parametrize('scenario',SCENARIOS)
@pytest.mark.parametrize('seed',[7,103])
def test_full_pipeline_and_serialized_charts_exact(scenario,seed):
    params={**DEFAULTS,'scenario':scenario,'days':30,'paths':1000}
    expected,ref=reference(params,seed)
    np.random.seed(seed)
    actual,got=execute(params,use_cache=False,download_override=market,capture=True)
    for name in NUMERIC_NAMES:
        if isinstance(ref[name],pd.DataFrame): pd.testing.assert_frame_equal(ref[name],got[name],check_exact=True)
        else: np.testing.assert_array_equal(ref[name],got[name],err_msg=name)
    assert actual==expected  # all four metric strings and all four Plotly figures
    assert len(actual['charts'][0]['figure']['data'])==101
    assert len(json.dumps(actual).encode()) < 4500000
    assert json.loads(json.dumps(actual))==actual


def test_original_source_integrity():
    expected=(bridge.ROOT/'SOURCE_SHA256.txt').read_text().split()[0]
    assert hashlib.sha256(bridge.SOURCE.read_bytes()).hexdigest()==expected

@pytest.mark.parametrize('payload',[
 {'weights':'1'}, {'weights':'0,0,0'}, {'weights':'nan,1,2'}, {'days':29},
 {'paths':1500}, {'scenario':'invalid'}, {'initial_investment':float('inf')}, {'tickers':''}
])
def test_invalid_inputs_rejected(payload):
    with pytest.raises(ValueError): validate({**DEFAULTS,**payload})


def test_vn_branch_spy_fallback_and_negative_weights():
    params={**DEFAULTS,'tickers':'HPG.VN, FPT.VN','weights':'1.2,-0.2', 'scenario':SCENARIOS[-1],'days':30,'paths':1000}
    def downloader(ticker,**kw):
        if ticker=='SPY':raise RuntimeError('fixture unavailable')
        return market(ticker,**kw)
    ref,ns=reference(params,18,downloader)
    np.random.seed(18)
    got,out=execute(validate(params),use_cache=False,download_override=downloader,capture=True)
    assert got==ref
    assert out['global_adtv_benchmark']==1200000000000
    assert out['spy_vol']==.15
    np.testing.assert_array_equal(ns['simulated_paths'],out['simulated_paths'])


def test_cholesky_repair_branch():
    params={**DEFAULTS,'days':30,'paths':1000}
    _,ns=reference(params,1)
    cov=np.array([[.04,.08],[.08,.04]])  # not positive definite
    args=(np.array([.03,.04]),cov,np.array([.5,.5]),1e8,30,1000,np.array([1.,2.]),
          np.array([-.05,-.1]),np.array([.02,.03]),np.array([.005,.01]))
    np.random.seed(90); ref=ns['run_ultimate_quant_engine'](*args)
    _,out=execute(params,use_cache=False,download_override=market,capture=True)
    np.random.seed(90);got=out['run_ultimate_quant_engine'](*args)
    np.testing.assert_array_equal(ref,got)
    assert np.isfinite(got).all()


def test_cache_reuses_draws_and_expires_market_data(tmp_path,monkeypatch):
    monkeypatch.setattr(bridge,'CACHE_DIR',tmp_path)
    clock=[1000.]
    # actual file mtimes are used; TTL test below changes mtime explicitly.
    ui=WebUI(DEFAULTS)
    calls=[]
    @ui.cache_data(ttl=300)
    def fetch(x): calls.append(x);return np.array([len(calls)])
    np.testing.assert_array_equal(fetch(1),fetch(1));assert len(calls)==1
    import os,time
    for p in tmp_path.glob('*.pickle'):os.utime(p,(time.time()-301,time.time()-301))
    assert fetch(1)[0]==2
    @ui.cache_data
    def draws(n):return np.random.normal(size=n)
    np.testing.assert_array_equal(draws(20),draws(20))


def test_http_transport(monkeypatch):
    production_execute=execute
    monkeypatch.setattr('app.execute',lambda p:production_execute(p,use_cache=False,download_override=market))
    client=app.test_client()
    assert client.get('/').status_code==200
    assert client.get('/client.js').status_code==200
    assert client.get('/api/health').json['source_sha256']==bridge.SOURCE_HASH
    assert client.post('/api/simulate',json={'weights':'bad'}).status_code==400
    params={**DEFAULTS,'days':30,'paths':1000}
    np.random.seed(42);expected,_=reference(params,42)
    np.random.seed(42);response=client.post('/api/simulate',json=params)
    assert response.status_code==200
    assert response.json==expected
    with bridge.LOCK:
        assert client.post('/api/simulate',json=params).status_code==429


def test_maximum_days_and_paths_exact():
    params={**DEFAULTS,'tickers':'PG','weights':'1','days':252,'paths':10000,'scenario':SCENARIOS[-1]}
    expected,ns=reference(params,53)
    expected_paths=ns['simulated_paths'].copy()
    ns.clear()
    np.random.seed(53)
    actual,out=execute(params,use_cache=False,download_override=market,capture=True)
    np.testing.assert_array_equal(out['simulated_paths'],expected_paths)
    assert actual==expected
    assert len(json.dumps(actual).encode())<4500000
