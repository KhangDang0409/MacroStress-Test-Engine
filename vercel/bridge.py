"""UI transport for the untouched original. No financial formulas live here."""
import builtins
import hashlib
import json
import pickle
import tempfile
import threading
import time
from pathlib import Path
from functools import wraps

import numpy as np
import yfinance as yf

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'original_streamlit.py'
CODE = compile(SOURCE.read_bytes(), str(SOURCE), 'exec')
SOURCE_HASH = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
LOCK = threading.Lock()  # The original uses numpy's process-global random state.
CACHE_DIR = Path(tempfile.gettempdir()) / ('macrostress-' + SOURCE_HASH[:12])
CACHE_DIR.mkdir(exist_ok=True)
yf.set_tz_cache_location(str(CACHE_DIR / 'yfinance'))

SCENARIOS = [
    'Normal Market Conditions',
    'Hawkish Policy (Interest Rate Shock)',
    'Stagflation (High Inflation & Low Growth)',
    'Black Swan Crash (Liquidity Crisis)',
]
DEFAULTS = dict(tickers='JNJ, WMT, PG', weights='0.33, 0.33, 0.34',
                initial_investment=100000000, scenario=SCENARIOS[0], days=90, paths=3000)

class ModelError(Exception):
    pass

class Context:
    def __enter__(self): return self
    def __exit__(self, *args): return False


def validate(payload):
    if not isinstance(payload, dict): raise ValueError('Expected a JSON object.')
    p = {**DEFAULTS, **payload}
    if not isinstance(p['tickers'], str) or not isinstance(p['weights'], str):
        raise ValueError('Tickers and weights must be comma-separated text.')
    tickers = [x.strip().upper() for x in p['tickers'].split(',') if x.strip()]
    try:
        weights = np.array([float(x.strip()) for x in p['weights'].split(',') if x.strip()])
    except ValueError:
        raise ValueError('Weights must be numbers, e.g. 0.33, 0.33, 0.34.')
    if not tickers or len(tickers) != len(weights):
        raise ValueError('Provide one weight for each ticker.')
    if not np.isfinite(weights).all() or not np.isfinite(weights.sum()) or weights.sum() == 0:
        raise ValueError('Weights must be finite and have a nonzero sum.')
    # Negative weights are deliberately allowed: the original allows them.
    for name in ('days', 'paths'):
        if type(p[name]) is not int: raise ValueError(f'{name} must be an integer.')
    if not 30 <= p['days'] <= 252: raise ValueError('Days must be 30–252.')
    if not 1000 <= p['paths'] <= 10000 or p['paths'] % 1000:
        raise ValueError('Paths must be 1,000–10,000 in increments of 1,000.')
    if p['scenario'] not in SCENARIOS: raise ValueError('Unknown scenario.')
    if isinstance(p['initial_investment'], bool) or not isinstance(p['initial_investment'], (int, float)):
        raise ValueError('Initial investment must be numeric.')
    if not np.isfinite(p['initial_investment']) or p['initial_investment'] < 1000000:
        raise ValueError('Initial investment must be at least 1,000,000.')
    return {k: p[k] for k in DEFAULTS}


class WebUI:
    """Implement only the exact UI calls used by this uploaded source."""
    def __init__(self, params, use_cache=True):
        self.params = params
        self.use_cache = use_cache
        self.sidebar = Context()
        self.output = dict(metrics=[], charts=[], tables=[], description='', source_sha256=SOURCE_HASH)
        self.last_error = 'The original application stopped.'

    def set_page_config(self, **kwargs): pass
    def title(self, text): self.output['title'] = text
    def header(self, text): pass
    def divider(self): pass
    def markdown(self, text):
        if not self.output['description']: self.output['description'] = text
    def text_input(self, label, value):
        return self.params['tickers' if label.startswith('Enter Tickers') else 'weights']
    def number_input(self, *args, **kwargs): return self.params['initial_investment']
    def selectbox(self, *args, **kwargs): return self.params['scenario']
    def slider(self, label, *args, **kwargs):
        return self.params['days' if label.startswith('Time Horizon') else 'paths']
    def spinner(self, *args, **kwargs): return Context()
    def expander(self, *args, **kwargs): return Context()
    def columns(self, count): return [self for _ in range(count)]
    def tabs(self, names): return [Context() for _ in names]
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def error(self, text): self.last_error = text
    def stop(self): raise ModelError(self.last_error)
    def dataframe(self, df, **kwargs):
        self.output['tables'].append(json.loads(df.to_json(orient='split')))
    def metric(self, label, value, delta=None, **kwargs):
        self.output['metrics'].append(dict(label=label, value=value, delta=delta, **kwargs))
    def plotly_chart(self, fig, **kwargs):
        # Plotly's own serializer preserves its original traces, bins and annotations.
        self.output['charts'].append(dict(key=kwargs.get('key'), figure=json.loads(fig.to_json())))

    def cache_data(self, func=None, *, ttl=None):
        def decorate(fn):
            @wraps(fn)
            def cached(*args, **kwargs):
                if not self.use_cache: return fn(*args, **kwargs)
                key = hashlib.sha256(pickle.dumps((fn.__name__, args, kwargs), protocol=5)).hexdigest()
                path = CACHE_DIR / (key + '.pickle')
                if path.exists() and (ttl is None or time.time() - path.stat().st_mtime < ttl):
                    try: return pickle.loads(path.read_bytes())
                    except (OSError, pickle.UnpicklingError, EOFError): pass
                result = fn(*args, **kwargs)
                # Cache storage is local/ephemeral. Eviction never approximates results.
                try:
                    data = pickle.dumps(result, protocol=5)
                    files = sorted(CACHE_DIR.glob('*.pickle'), key=lambda p: p.stat().st_mtime)
                    total = sum(p.stat().st_size for p in files)
                    while files and total + len(data) > 128 * 1024**2:
                        old = files.pop(0)
                        total -= old.stat().st_size
                        old.unlink(missing_ok=True)
                    if len(data) <= 128 * 1024**2: path.write_bytes(data)
                except OSError: pass
                return result
            return cached
        return decorate(func) if func is not None else decorate


def execute(params, *, use_cache=True, download_override=None, capture=False):
    """Execute byte-identical original source; substitute UI only.

    download_override/capture are offline verification hooks, never HTTP inputs.
    Caller must hold LOCK when used concurrently.
    """
    ui = WebUI(params, use_cache)
    original_import = builtins.__import__
    def imported(name, globals=None, locals=None, fromlist=(), level=0):
        if name == 'streamlit': return ui
        if name == 'yfinance' and download_override is not None:
            from types import SimpleNamespace
            return SimpleNamespace(download=download_override)
        return original_import(name, globals, locals, fromlist, level)
    scope = {'__name__': '__original_model__', '__file__': str(SOURCE),
             '__builtins__': {**vars(builtins), '__import__': imported}}
    try:
        exec(CODE, scope)
        if capture: return ui.output, scope
        result = ui.output
    finally:
        if not capture:
            # Functions have references to their execution globals; break the cycle
            # so the original large simulation arrays can be freed immediately.
            scope.clear()
    return result
