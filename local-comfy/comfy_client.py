"""Local ComfyUI API client. No browser, no cloud calls, no auto-approval."""
import argparse
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
URL = 'http://127.0.0.1:8188'


def call(endpoint, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(URL + endpoint, data=data,
        headers={'Content-Type':'application/json'}, method='GET' if data is None else 'POST')
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            # /free acknowledges success with an empty body; /prompt and status return JSON.
            body=response.read()
            return json.loads(body) if body.strip() else None
    except urllib.error.HTTPError as exc:
        detail = exc.read(4096).decode('utf-8', errors='replace')
        raise RuntimeError(f'ComfyUI HTTP {exc.code}: {detail}') from exc


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.partial')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


def run_graph(path, budget):
    graph = json.loads(Path(path).read_text(encoding='utf-8'))
    response = call('/prompt', {'prompt':graph,'client_id':str(uuid.uuid4())})
    if response.get('node_errors') or not response.get('prompt_id'):
        raise RuntimeError('Graph validation failed: ' + json.dumps(response))
    prompt_id = response['prompt_id']
    deadline = time.monotonic() + budget
    while time.monotonic() < deadline:
        history = call('/history/' + prompt_id)
        if prompt_id in history:
            record = history[prompt_id]
            if record.get('status', {}).get('status_str') == 'error':
                save(HERE / 'reports' / (prompt_id + '-error.json'), record)
                raise RuntimeError('ComfyUI workflow failed; see the saved local error report.')
            outputs = []
            for node, result in record.get('outputs', {}).items():
                for image in result.get('images', []):
                    filename, subfolder = image['filename'], image.get('subfolder', '')
                    if (Path(filename).name != filename or '\\' in subfolder or ':' in subfolder
                            or subfolder.startswith('/') or '..' in subfolder.split('/')):
                        raise ValueError('Unsafe output path returned by ComfyUI.')
                    source = HERE / 'data/output' / subfolder / filename
                    if not source.is_file():
                        raise FileNotFoundError('Expected bind-mounted local output: ' + str(source))
                    outputs.append({'node':node,'file':str(source),
                        'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                        'editorial_approved':False,'automatic_kaggle_upload':False})
            report = {'prompt_id':prompt_id,'workflow':str(Path(path).resolve()),
                'completed':record.get('status', {}).get('completed',False),
                'outputs':outputs,'paid_api':False,'history':record}
            save(HERE / 'reports' / (prompt_id + '.json'), report)
            print(json.dumps({k:v for k,v in report.items() if k != 'history'},indent=2))
            return report
        time.sleep(2)
    # Do not interrupt somebody else's workflow or clear the global queue.
    raise TimeoutError('Client wait budget exceeded; inspect /queue before retrying. Nothing was cancelled.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['status','run'])
    parser.add_argument('--workflow', type=Path)
    parser.add_argument('--wait-seconds', type=int, default=600)
    args = parser.parse_args()
    if args.action == 'status':
        report = call('/system_stats')
        save(HERE / 'reports/system-stats.json', report)
        print(json.dumps(report,indent=2))
    else:
        if args.workflow is None:
            parser.error('--workflow is required')
        run_graph(args.workflow,args.wait_seconds)
