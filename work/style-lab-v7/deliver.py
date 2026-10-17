"""Verify and package style probes, not a movie or a production approval."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import style_lab as lab

OUT = lab.OUT


def comparison(name, columns, rows, candidates, title):
    thumb_w, thumb_h, gap, top, label_h = 640, 360, 18, 95, 32
    canvas = Image.new('RGB', (len(columns) * (thumb_w + gap) + gap,
        top + len(rows) * (thumb_h + label_h + gap) + gap), '#151719')
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 22)
    small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)
    draw.text((gap, 15), title, font=font, fill='#e4e3df')
    for col, label in enumerate(columns):
        draw.text((gap + col * (thumb_w + gap), 56), label, font=font, fill='#bfc8d2')
    for row, label in enumerate(rows):
        for col in range(len(columns)):
            stem = candidates[row][col]
            x, y = gap + col * (thumb_w + gap), top + row * (thumb_h + label_h + gap)
            with Image.open(OUT / 'assets' / f'{stem}.png') as image:
                canvas.paste(image.convert('RGB').resize((thumb_w, thumb_h), Image.Resampling.LANCZOS), (x, y))
            draw.text((x, y + thumb_h + 6), label + ' / ' + stem, font=small, fill='#bcbfc4')
    canvas.save(OUT / name, quality=95, subsampling=0)


def main():
    reports = sorted((OUT / 'assets').glob('*.json'))
    if len(reports) != 24:
        raise RuntimeError(f'Expected 24 completed GPU probes, found {len(reports)}.')
    observations = []
    baseline = json.loads((OUT / 'preservation-validation.json').read_text())
    if not baseline['unchanged']:
        raise RuntimeError('Preservation check must pass before delivery.')
    manifest_jobs = []
    for name in ['jobs.json', 'refinements.json', 'object-refinements.json', 'wardrobe-repairs.json']:
        manifest_jobs.extend(json.loads((OUT / name).read_text(encoding='utf-8')))
    expected = {f'{job["id"]}-r{job["prompt_revision"]}': job for job in manifest_jobs}
    if len(expected) != 24:
        raise RuntimeError('Duplicate or missing job in experiment manifests.')
    for report in reports:
        item = json.loads(report.read_text(encoding='utf-8'))
        if item['job'] != expected[report.stem] or lab.sha(item['image']) != item['sha256']:
            raise RuntimeError('Candidate/manifest checksum mismatch.')
        workflow = Path(item['workflow'])
        if json.loads(workflow.read_text()) != lab.make_graph(item['job']):
            raise RuntimeError('Workflow provenance mismatch.')
        history_path = lab.COMFY / 'reports' / f'{item["prompt_id"]}.json'
        history = json.loads(history_path.read_text())
        if not history['completed'] or history['outputs'][0]['sha256'] != item['sha256']:
            raise RuntimeError('Completed local generation history mismatch.')
        with Image.open(item['image']) as image:
            image.verify()
        observations.append({'file': str(Path(item['image']).relative_to(OUT)),
            'sha256': item['sha256'], 'prompt_id': item['prompt_id'], 'seconds': item['seconds'],
            'size': item['job']['size'], 'gpu_generation_confirmed': True,
            'visual_inspection': 'Codex reviewed all 24 candidates using image viewing tools; see REVIEW.txt',
            'user_approved': False, 'movie_inserted': False})
    lab.save(OUT / 'generation-validation.json', {'completed_local_gpu_images': len(observations),
        'all_candidates_hashes_workflows_histories_verified': True, 'images': observations,
        'automatic_quality_approval': False, 'full_sequence_style_consistency_tested': False,
        'animation_tested': False, 'uploaded_to_kaggle': False})
    lab.save(OUT / 'style-presets.json', {'version': 7, 'recommended_style': 'ink',
        'user_approved': False, 'human_medium_prompts': {k: v['prompt'] for k, v in lab.STYLES.items()},
        'object_medium_prompts': lab.OBJECT_STYLES, 'scene_invariants': lab.INVARIANTS,
        'generator_settings': {'steps': 4, 'cfg': 1.0, 'sampler': 'euler', 'size': [1536, 864]},
        'wardrobe': {'mark': 'cobalt-blue overshirt over a dark T-shirt',
            'chloe': 'charcoal-grey jacket', 'jess': 'muted olive jacket'},
        'guardrails': ['Use only characters actually present in the shot.',
            'Do not put human-face instructions into objects or creatures.',
            'Avoid OR clauses for scene-specific wardrobe.',
            'An existing failed composition may resist a style-transfer edit.',
            'Explicitly review face/wardrobe/clue continuity after every edit.'],
        'suggested_style_reference': 'assets/ink-shot-029-r2.png',
        'style_reference_conditioning_tested': False})
    comparison('night-refinements.jpg', ['Ink / night', 'Gouache / night'], ['Mark', 'Chloe + Jess'],
        [['ink-shot-029-r2', 'gouache-shot-029-r2'], ['ink-shot-039-r3', 'gouache-shot-039-r3']],
        'Lighting refinements + wardrobe repairs (not the original controlled matrix)')
    comparison('object-refinements.jpg', [v['label'] for v in lab.STYLES.values()],
        ['Forest: design still provisional', 'Doll: all rejected for missing grip'],
        [[f'{style}-shot-060-r2' for style in lab.STYLES],
         [f'{style}-shot-062-r2' for style in lab.STYLES]],
        'Object-only prompts: three media, same references and seeds')
    archive = OUT / 'style-lab-v7.zip'
    if archive.exists():
        raise RuntimeError('Archive exists; do not overwrite a delivered checkpoint.')
    sources = sorted([p for p in OUT.rglob('*') if p.is_file() and p.suffix in ('.json', '.txt', '.jpg', '.png')])
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        for source in sources:
            bundle.write(source, source.relative_to(OUT).as_posix())
        refs = {r['image']: r for job in manifest_jobs for r in job['references']}
        for name, reference in sorted(refs.items()):
            path = lab.COMFY / 'data/input' / name
            if lab.sha(path) != reference['sha256']:
                raise RuntimeError('Cached Comfy reference mismatch.')
            bundle.write(path, 'comfy-inputs/' + name)
        for source in sorted(Path(__file__).parent.glob('*.py')):
            bundle.write(source, 'reproduction/' + source.name)
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip():
            raise RuntimeError('ZIP CRC failed.')
        entries = len(bundle.namelist())
    lab.save(OUT / 'DELIVERY.json', {'images': len(observations), 'archive': str(archive),
        'archive_bytes': archive.stat().st_size, 'archive_sha256': lab.sha(archive),
        'archive_files': entries, 'zip_crc_passed': True,
        'recommended_style': 'dark ink graphic novel, subject to user selection',
        'all_candidates_visually_inspected': True, 'user_approved': False,
        'original_checkpoint_unchanged_files': 505, 'v6_and_source_baseline_unchanged_files': baseline['checked_files'],
        'paid_api': False, 'kaggle_uploaded': False, 'video_edited': False})
    print(json.dumps({'images': len(observations), 'archive_bytes': archive.stat().st_size,
        'zip_entries': entries, 'checks': 'hashes, histories, workflows, preservation, ZIP CRC passed'}, indent=2))


if __name__ == '__main__':
    main()
