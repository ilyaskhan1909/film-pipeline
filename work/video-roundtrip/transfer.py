"""Official API only. Upload private inputs, guard GPU submissions, fetch results."""
import argparse
import json
import re
from pathlib import Path

from contract import save_json
from prepare import DATASET, OUTPUT

HERE = Path(__file__).resolve().parent
KERNEL = 'iliaskhan/videogenerator-v5-video-only'


def duration_seconds(value):
    # Current SDK serializes some fractional durations with an extra '.0'.
    match = re.fullmatch(r'(\d+(?:\.\d+)?)(?:\.0)?s', value)
    if match is None:
        raise ValueError('Unrecognized quota duration; refuse an unchecked GPU submission.')
    return float(match.group(1))


def quota_remaining(response):
    gpu = response['gpuQuota']
    if gpu.get('isPayToScaleEnabled'):
        raise RuntimeError('Pay-to-scale is enabled; this free-only workflow will not submit a GPU run.')
    return max(0, duration_seconds(gpu['totalTimeAllowed']) -
               duration_seconds(gpu['timeUsed']) - duration_seconds(gpu['timeReserved']))


def main():
    from kaggle.api.kaggle_api_extended import KaggleApi
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['upload-inputs','quota','run','fetch'])
    args = parser.parse_args()
    api = KaggleApi()
    api.authenticate()
    if args.action == 'upload-inputs':
        response = api.dataset_create_new(str(HERE / 'dataset'), public=False,
            quiet=True, convert_to_csv=False, dir_mode='skip')
        data = json.loads(str(response))
        save_json(OUTPUT / 'kaggle-input-upload.json', data)
        if data.get('error') or data.get('status') == 'error':
            raise RuntimeError('Private input dataset creation failed; existing datasets are never overwritten.')
        current = json.loads((OUTPUT / 'handoff-current.json').read_text())
        current.update(remote_uploaded=True, kaggle_dataset=DATASET,
                       dataset_response_status=data.get('status'))
        save_json(OUTPUT / 'handoff-current.json', current)
        print(json.dumps({'private_dataset': DATASET, 'status':data.get('status'),
                          'gpu_run_submitted':False, 'browser_used':False}))
    elif args.action in ('quota','run'):
        response = json.loads(str(api.quota_view()))
        available = quota_remaining(response)
        save_json(OUTPUT / 'kaggle-quota.json', {'response':response,'remaining_seconds':available})
        if args.action == 'quota':
            print(json.dumps({'remaining_seconds':available,'refresh':response['quotaRefreshTime']}))
            return
        # Conservative allowance includes bootstrap time and both cards, without
        # claiming an exact platform GPU-accounting rate.
        needed = 2 * (7200 + 1800)
        if available < needed:
            raise RuntimeError(f'GPU run not submitted: remaining {available:.0f}s < safety budget {needed}s.')
        metadata = json.loads((HERE / 'remote/kernel-metadata.json').read_text())
        if not metadata['is_private'] or metadata['dataset_sources'] != [DATASET]:
            raise RuntimeError('Unexpected remote kernel privacy or data sources.')
        result = json.loads(str(api.kernels_push(str(HERE / 'remote'), timeout='9000', acc='NvidiaTeslaT4')))
        save_json(OUTPUT / 'kaggle-run-submission.json', result)
        if result.get('error'):
            raise RuntimeError('Kaggle rejected the GPU submission.')
        print(json.dumps({'kernel':KERNEL,'submitted':True}))
    else:
        folder = OUTPUT / 'kaggle-output'
        folder.mkdir(parents=True, exist_ok=True)
        files, cursor = api.kernels_output(KERNEL, path=str(folder),
            file_pattern='*results.zip', force=False, quiet=True)
        print(json.dumps({'downloaded_files':files,'next_page':cursor}))


if __name__ == '__main__':
    main()
