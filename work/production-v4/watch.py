"""Authenticated, read-only live logs, with compact progress and no credentials."""
import argparse
import json
import time
import requests
from pathlib import Path
from kaggle.api.kaggle_api_extended import KaggleApi

parser = argparse.ArgumentParser()
parser.add_argument('notebook')
parser.add_argument('--output',type=Path,required=True)
args = parser.parse_args()
api = KaggleApi()
api.authenticate()
args.output.parent.mkdir(parents=True,exist_ok=True)
with args.output.open('a',encoding='utf-8') as stream:
    seen = set()
    for attempt in range(40):
        try:
            for event in api.kernels_logs_stream(args.notebook):
                key=(str(event.get('time')),event.get('data',''))
                if key in seen: continue
                seen.add(key)
                data = event.get('data','')
                try:
                    data = data.encode('latin1').decode('utf-8')
                except UnicodeError:
                    pass
                event['data'] = data
                stream.write(json.dumps(event,ensure_ascii=False)+'\n')
                stream.flush()
                if any(key in data for key in ['GPU:', 'Words:', 'IMAGE ', 'TTS ', 'Alignment ', 'CACHED ', 'Traceback', 'Error:', 'RuntimeError', 'archive', 'Run All', 'Resumed']):
                    print(data.rstrip(),flush=True)
            break
        except requests.RequestException:
            print('Log connection interrupted; reconnecting (GPU job continues).',flush=True)
            time.sleep(min(30,3+attempt))
print('STREAM COMPLETE',flush=True)
