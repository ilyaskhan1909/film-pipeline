"""Package existing local keyframes, not narration/music/edit projects, for Kaggle."""
import json
import shutil
import zipfile
from pathlib import Path

from PIL import Image

from contract import digest, identity, save_json, validate_inputs

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT = ROOT / 'outputs/video-roundtrip'
DATASET = 'iliaskhan/the-last-firework-video-inputs-v5'


def prepare():
    plan = json.loads((ROOT / 'outputs/a14b-dual/experiment-plan.json').read_text(encoding='utf-8'))
    shot = plan['shots'][0]
    source = ROOT / 'outputs/first-film/curated/assets/images' / f'{shot["id"]}.png'
    if digest(source) != shot['sha256']:
        raise ValueError('Checkpoint image changed.')
    with Image.open(source) as image:
        native_size = list(image.size)
        image.verify()
    manifest = {'schema': 'video-inputs/v1', 'project_id': 'the-last-firework-v5',
        'assets': [{'id': shot['id'], 'file': f'frames/{shot["id"]}.png',
            'sha256': shot['sha256'], 'native_size': native_size,
            'origin': 'Existing local v4.1 checkpoint; no image generation performed in this handoff.',
            'provenance': shot['checkpoint_generation'],
            'editorial_status': 'selected_checkpoint_frame_requiring_new_motion_review'}],
        'requests': [{'id': 'lake-a14b-pilot-01', 'asset_id': shot['id'],
            'prompt': shot['prompt'], 'config': plan['config'],
            'intent': 'First controlled technical/motion probe, NOT production approval.'}],
        'negative_prompt': plan['negative_prompt'],
        'profile': {'engine': 'wan22-a14b-q8-fp32-two-t4', 'models': plan['models'],
                    'pins': plan['pins'], 'gpu_validated': False,
                    'text_encoder': 'T5 NF4/FP32; part of video conditioning, not speech synthesis'},
        'policy': {'kaggle_scope': 'silent_image_to_video_only', 'paid_apis': False,
            'automatic_edit_insertion': False, 'music_narration_titles_captions': 'local_only',
            'automatic_upscale_interpolation_looping': False,
            'original_checkpoint': 'read_only', 'maximum_batch_worker_seconds': 7200}}
    manifest['handoff_id'] = 'video-' + identity(manifest)[:16]
    validate_inputs(manifest)
    folder = OUTPUT / 'inputs' / manifest['handoff_id']
    (folder / 'frames').mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, folder / manifest['assets'][0]['file'])
    save_json(folder / 'video-inputs.json', manifest)
    save_json(folder / 'checksums.json', {
        'video-inputs.json': digest(folder / 'video-inputs.json'),
        manifest['assets'][0]['file']: digest(folder / manifest['assets'][0]['file'])})
    archive = OUTPUT / f'{manifest["handoff_id"]}-inputs.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=3) as bundle:
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                bundle.write(path, path.relative_to(folder).as_posix())
    dataset_folder = HERE / 'dataset'
    dataset_folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(archive, dataset_folder / 'video-inputs.zip')
    save_json(dataset_folder / 'dataset-metadata.json', {
        'id': DATASET, 'title': 'The Last Firework video inputs v5',
        'licenses': [{'name': 'other'}],
        'description': 'Private I2V inputs: existing generated keyframes, motion prompts and checksums. No audio, music or edit project. Experimental model backend not yet GPU verified.'})
    current_path = OUTPUT / 'handoff-current.json'
    previous = json.loads(current_path.read_text()) if current_path.exists() else {}
    already_uploaded = previous.get('handoff_id') == manifest['handoff_id'] and previous.get('remote_uploaded', False)
    save_json(current_path, {'handoff_id': manifest['handoff_id'],
        'input_manifest': str(folder / 'video-inputs.json'), 'input_archive': str(archive),
        'kaggle_dataset': DATASET, 'remote_uploaded': already_uploaded,
        'gpu_run_submitted': previous.get('gpu_run_submitted', False) if already_uploaded else False})
    print('LOCAL INPUTS', archive, archive.stat().st_size, 'bytes')
    return manifest


if __name__ == '__main__':
    prepare()
