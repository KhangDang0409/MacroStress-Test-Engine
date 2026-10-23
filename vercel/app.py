"""Vercel Flask entrypoint. Run locally with: python app.py"""
import json
import logging
import os
import re
from pathlib import Path
from flask import Flask, Response, request, send_from_directory
from bridge import DEFAULTS, LOCK, ModelError, SOURCE_HASH, execute, validate

ROOT = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=None)
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024

@app.get('/')
def home():
    return send_from_directory(ROOT / 'public', 'index.html')

@app.get('/<path:name>')
def assets(name):
    return send_from_directory(ROOT / 'public', name)

@app.get('/api/health')
def health():
    return dict(status='ok', source_sha256=SOURCE_HASH, defaults=DEFAULTS)

@app.get('/api/project')
def project():
    # Only expose public repository coordinates, never other environment values.
    owner = os.environ.get('VERCEL_GIT_REPO_OWNER', '')
    repo = os.environ.get('VERCEL_GIT_REPO_SLUG', '')
    provider = os.environ.get('VERCEL_GIT_PROVIDER', '')
    valid = lambda text: bool(re.fullmatch(r'[A-Za-z0-9_.-]+', text)) and text not in ('.', '..')
    url = None
    if provider == 'github' and valid(owner) and valid(repo):
        url = f'https://github.com/{owner}/{repo}'
    return {'github_url': url}, 200, {'Cache-Control': 'no-store'}

@app.post('/api/simulate')
def simulate():
    try:
        params = validate(request.get_json(silent=True))
    except (ValueError, TypeError) as exc:
        return {'error': str(exc)}, 400
    # Do not interleave process-global RNG draws from two portfolios.
    if not LOCK.acquire(blocking=False):
        return {'error': 'Another simulation is running on this instance. Please retry shortly.'}, 429
    try:
        output = execute(params)
        encoded = json.dumps(output, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        return Response(encoded, mimetype='application/json', headers={'Cache-Control': 'no-store'})
    except ModelError as exc:
        return {'error': str(exc)}, 502
    except MemoryError:
        return {'error': 'This run exceeded available memory. No approximate result was substituted.'}, 503
    except Exception:
        logging.exception('Simulation failed')
        return {'error': 'Simulation failed. See Vercel runtime logs for details; no fallback data or result was substituted.'}, 500
    finally:
        LOCK.release()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
