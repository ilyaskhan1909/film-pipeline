"""Verify only this Comfy service; never modify Docker settings or other projects."""
import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from comfy_client import call, run_graph, save

HERE = Path(__file__).resolve().parent
COMPOSE = ['docker','compose','-f',str(HERE / 'compose.yaml')]
EXPECTED_OTHER_CONTAINERS = [
    'lt-tds-api-gateway','lt-tds-analytics-service','lt-tds-dashboard','lt-tds-tds',
    'lt-tds-billing-service','lt-tds-ai-service','lt-tds-domain-manager',
    'lt-tds-push-service','lt-tds-postgres','lt-tds-redis','lt-tds-clickhouse',
]


def execute(args, source=None):
    return subprocess.check_output(args, input=source, text=True, encoding='utf-8')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--observe-other-containers',action='store_true',
                        help='Record unrelated containers as observed, without asserting they must be running.')
    args=parser.parse_args()
    stats = call('/system_stats')
    save(HERE / 'reports/system-stats.json', stats)
    gpu = json.loads(execute(COMPOSE + ['exec','-T','comfy','python','-'],
                            (HERE / 'gpu_probe.py').read_text(encoding='utf-8')))
    save(HERE / 'reports/gpu-test.json', gpu)
    graph_report = run_graph(HERE / 'workflows/transport-smoke-api.json', 120)
    if not graph_report['completed'] or len(graph_report['outputs']) != 1:
        raise RuntimeError('Transport graph did not complete with exactly one image.')
    source = np.asarray(Image.open(HERE / 'data/input/checkpoint-smoke.png').convert('RGB'))
    returned = np.asarray(Image.open(graph_report['outputs'][0]['file']).convert('RGB'))
    if not np.array_equal(source, returned):
        raise RuntimeError('Transport graph unexpectedly changed checkpoint pixels.')
    container = json.loads(execute(['docker','inspect','videogenerator-comfy']))[0]
    if not container['State']['Running']:
        raise RuntimeError('Our ComfyUI container is not running.')
    if container['State'].get('Health',{}).get('Status') != 'healthy':
        raise RuntimeError('Wait for the container healthcheck before verification.')
    if not container['HostConfig']['ReadonlyRootfs'] or container['Config']['User'] != '1000:1000':
        raise RuntimeError('Unexpected container isolation configuration.')
    ports = container['HostConfig']['PortBindings']['8188/tcp']
    if any(p['HostIp'] != '127.0.0.1' for p in ports):
        raise RuntimeError('ComfyUI is exposed beyond localhost.')
    others = json.loads(execute(['docker','inspect',*EXPECTED_OTHER_CONTAINERS]))
    other_states = {item['Name'].lstrip('/'):item['State']['Running'] for item in others}
    save(HERE/'reports/other-containers-observed.json',[
        {'name':item['Name'].lstrip('/'),'state':item['State']} for item in others])
    if not all(other_states.values()) and not args.observe_other_containers:
        raise RuntimeError('An existing container is no longer running; inspect without restarting it.')
    build = json.loads(execute(COMPOSE + ['exec','-T','comfy','python','-'],
        "from pathlib import Path; print(Path('/opt/image-build.json').read_text())"))
    save(HERE / 'reports/image-build.json', build)
    pip_check = execute(COMPOSE + ['exec','-T','comfy','python','-m','pip','check']).strip()
    inference_path=HERE.parent/'outputs/local-production-v6/local-generation-validation.json'
    inference=json.loads(inference_path.read_text(encoding='utf-8')) if inference_path.exists() else {}
    report = {
        'verified_at_utc':datetime.now(timezone.utc).isoformat(),
        'service_url':'http://127.0.0.1:8188',
        'comfy_release':build['comfy_release'], 'comfy_commit':build['comfy_commit'],
        'dependency_check':pip_check, 'image_id':container['Image'],
        'gpu':gpu, 'comfy_http_api':'passed', 'api_graph_execution':'passed',
        'transport_pixels_identical':True, 'transport_report':graph_report['prompt_id'],
        'non_root':True, 'read_only_container_root':True, 'localhost_only':True,
        'health':container['State'].get('Health',{}).get('Status'),
        'previous_containers_still_running':other_states,
        'other_containers_all_running':all(other_states.values()),
        'other_container_observation_only':args.observe_other_containers,
        'other_container_mutations_issued':False,
        'models_downloaded_by_setup':False,
        'model_weights_present':any(p.is_file() and p.suffix.lower() in
            {'.safetensors','.gguf','.pt','.pth','.ckpt'} for p in (HERE / 'data/models').rglob('*')),
        'image_generation_tested':inference.get('completed_candidates',0)>0,
        'image_generation_evidence':str(inference_path) if inference else None,
        'setup_verifier_runs_diffusion':False,
        'voice_or_music_fixed':False, 'paid_api_nodes_enabled':False,
        'custom_nodes_installed':False, 'automatic_kaggle_upload':False,
    }
    save(HERE / 'VALIDATION.json', report)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
