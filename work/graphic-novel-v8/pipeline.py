"""Local ink art direction, character references and a bounded continuity pilot."""
import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/graphic-novel-v8'
COMFY = ROOT / 'local-comfy'
sys.path.insert(0, str(ROOT / 'work/local-production-v6'))
from assets import graph
from download_models import digest
sys.path.insert(0, str(COMFY))
from comfy_client import call, run_graph, save

STYLE_SOURCE = ROOT / 'outputs/style-lab-v7/assets/ink-shot-029-r2.png'
PEOPLE = {
    'mark': {'description': 'a young adult man with short side-parted dark hair and the face shape of image 1',
        'wardrobe': 'a muted cobalt-blue buttoned overshirt over a plain dark charcoal T-shirt',
        'skin': 'muted warm tan', 'seed': 2026100600},
    'chloe': {'description': 'a young adult woman with straight shoulder-length brown hair and the face shape of image 1',
        'wardrobe': 'a matte CHARCOAL GREY camping jacket with a high collar, never blue',
        'skin': 'muted warm beige', 'seed': 2026100601},
    'jess': {'description': 'a young adult woman with short dark curly hair and the face shape of image 1',
        'wardrobe': 'a faded matte OLIVE GREEN camping jacket over a plain dark T-shirt',
        'skin': 'muted warm olive-tan', 'seed': 2026100602},
}
INK = ('Original adult horror graphic novel illustration in hand-drawn black ink. '
    'Bold slightly irregular contours, angular coherent forms, sparse dry-brush '
    'hatching, restrained paper grain and broad opaque matte color shapes. '
    'Charcoal-black and muted ink-blue shadows, earthy skin colors, small ochre-amber '
    'light accents where motivated. The entire image is drawn, never photographed '
    'or rendered in 3D. Small natural adult eyes, understated acting and distinct '
    'individual faces. No glossy plastic volume, smooth airbrush skin, superhero '
    'muscles, childlike eyes, lettering, logos, speech balloons or borders. ')
OBJECT_INK = ('Original adult horror graphic novel illustration in hand-drawn black '
    'ink. Bold irregular contours, angular broken shapes, dry-brush hatching, '
    'restrained paper grain and broad opaque matte color shapes. Charcoal-black, '
    'muted ink-blue and dirty umber. Everything is drawn, never photographed or '
    'rendered in 3D. Single full-bleed image without lettering, logos or borders. ')
PILOT_SHOTS = [f'shot-{number:03}' for number in range(37, 45)]
MARK_PROBES = ['shot-019', 'shot-029']
SHOT_ACTIONS = {
    'shot-019': 'Exactly ONE Mark in a serious campfire reaction close-up, short dark hair, muted cobalt BLUE overshirt over a charcoal T-shirt. Quiet alarm, closed mouth, gaze away from camera. No other person.',
    'shot-029': 'Exactly ONE Mark leaning forward in a camping chair on the right, muted cobalt BLUE overshirt and dark T-shirt. Restrained concern toward the forest. Fire low in foreground, empty chair left, tent right. No other person.',
    'shot-037': 'Exactly ONE Jess sits by the fire hugging her knees, dark curls and olive jacket; anxious restrained gaze toward the unseen narrator. No other person.',
    'shot-038': 'Exactly ONE Jess in a tight chest-up close-up, short dark curls and olive jacket. Her mouth is slightly parted as she tries to reassure the unseen narrator, with uncertain eyes and subdued tension. No added cup or second person.',
    'shot-039': 'Exactly TWO women: straight-haired Chloe on the LEFT in CHARCOAL GREY, curly-haired Jess on the RIGHT in OLIVE GREEN. They look upward at an unseen standing narrator; closed mouths, subtle concern. No third person.',
    'shot-040': 'An empty campsite cutaway: one muted green tent, one small parked camping car at the clearing edge, the lake and a narrow exit path. Preserve the original arrangement. Nobody is visible.',
    'shot-041': 'Exactly ONE Chloe in a quiet close-up at the campsite, straight shoulder-length brown hair and CHARCOAL GREY jacket. A serious settled expression, slight chin inclination. No other person. This still frame does not depict an animated nod.',
    'shot-042': 'Empty first-person view of the pine trail. A small soft pale cold patch on damp leaves and roots low in frame. All equipment and the observer are behind the camera. No hand, torch, person, creature or visible cone of light in the air.',
    'shot-043': 'Empty upward view into a dense closed canopy of interlocking pine and oak branches. Cold reflected light grazes the lowest branches, with higher branches merging into near-black silhouettes. No person, creature, equipment or daylight sky.',
    'shot-044': 'Empty long corridor of pine trunks along a dark footpath. A small diffuse cold patch on the closest ground, then the trail disappears into darkness. No foreground hand, torch, equipment, creature or airborne beam.',
}


def sha(path):
    return digest(Path(path))


def reference(source, role):
    source = Path(source)
    checksum = sha(source)
    name = f'v8-{role}-{checksum[:12]}.png'
    destination = COMFY / 'data/input' / name
    if destination.exists() and sha(destination) != checksum:
        raise RuntimeError('Reference collision; existing input preserved.')
    if not destination.exists():
        shutil.copy2(source, destination)
    with Image.open(source) as image:
        size = list(image.size)
    return {'image': name, 'source': str(source), 'sha256': checksum, 'size': size, 'role': role}


def make_graph(job):
    if not re.fullmatch(r'[a-z0-9-]+', job['id']) or not 0 <= len(job['references']) <= 4:
        raise ValueError('Unsafe ID or more than four reference images.')
    nodes = graph(job, 'fast')
    nodes['13']['inputs']['filename_prefix'] = f'v8/{job["id"]}-r{job["prompt_revision"]}'
    return nodes


def write_jobs(name, jobs):
    destination = OUT / name
    if destination.exists():
        raise RuntimeError('Manifest already exists. Resume, do not overwrite.')
    prepared = [(OUT / 'workflows' / f'{job["id"]}-r{job["prompt_revision"]}-api.json', make_graph(job)) for job in jobs]
    for path, nodes in prepared:
        if path.exists() and json.loads(path.read_text()) != nodes:
            raise RuntimeError('Existing workflow preserved; choose a new revision.')
    save(destination, jobs)
    for path, nodes in prepared:
        if not path.exists():
            save(path, nodes)
    print('PREPARED', name, len(jobs), flush=True)


def baseline():
    if (OUT / 'preservation-baseline.json').exists():
        return
    paths = set((ROOT / 'outputs/style-lab-v7').rglob('*'))
    paths = {path for path in paths if path.is_file()}
    paths.update((ROOT / 'outputs/local-production-v6/assets').glob('*'))
    paths.update(path for path in (ROOT / 'outputs/local-production-v6').iterdir() if path.is_file())
    paths.update((ROOT / 'outputs/first-film/curated/assets/references').glob('*.png'))
    paths.add(ROOT / 'outputs/first-film/The_Last_Firework_1080p.mp4')
    paths.add(ROOT / 'outputs/first-film/curated/assets/shot_plan.json')
    for shot in PILOT_SHOTS + MARK_PROBES:
        paths.add(ROOT / 'outputs/first-film/curated/assets/images' / f'{shot}.png')
    save(OUT / 'preservation-baseline.json', [{'file': str(path), 'size': path.stat().st_size,
        'sha256': sha(path)} for path in sorted(paths) if path.is_file()])


def prepare_characters():
    baseline()
    save(OUT / 'style-lock.json', {'direction': 'dark hand-inked adult horror graphic novel',
        'style_choice_user_authorized': True, 'authorization_text': 'Хорошо сделаем первый стиль',
        'approved_style_source': str(STYLE_SOURCE), 'style_source_sha256': sha(STYLE_SOURCE),
        'specific_new_images_user_approved': False, 'whole_film_restyled': False,
        'local_generator': 'ComfyUI / FLUX.2 Klein 4B distilled FP8', 'paid_api': False,
        'ink_prompt': INK, 'object_ink_prompt': OBJECT_INK,
        'wardrobe': {name: person['wardrobe'] for name, person in PEOPLE.items()}})
    jobs = []
    for name, person in PEOPLE.items():
        refs = [reference(ROOT / 'outputs/first-film/curated/assets/references' / f'{name}.png', f'identity-{name}'),
            reference(STYLE_SOURCE, 'ink-style')]
        prompt = (INK + f'Character reference portrait of exactly ONE {name.title()}, {person["description"]}. '
            f'The established outfit is {person["wardrobe"]}. '
            'Image 1 defines that one fictional person\'s face, age, hair and clothing. '
            'Image 2 provides ONLY the black-ink linework, matte shapes and paper texture; '
            'do not copy its man, campsite, pose, objects or background. '
            'Front-facing chest-up reference portrait, head upright and entirely in frame, '
            'both shoulders visible, looking directly forward, neutral closed mouth, '
            'relaxed brows. Keep individual nose, jaw, eyebrow and hair silhouettes '
            f'recognizable. Matte {person["skin"]} skin painted as two or three flat '
            'pigment shapes, with a quiet simple charcoal backdrop and neutral low '
            'diffuse illumination for identification. This is a reference drawing, '
            'not a glamorous poster. No hands, extra heads or people, collars from '
            'other characters, dialogue text, labels or panel divisions.')
        jobs.append({'id': f'{name}-front', 'kind': 'character', 'person': name,
            'size': [1024, 1024], 'seed': person['seed'], 'prompt_revision': 1,
            'prompt': prompt, 'references': refs, 'user_approved': False})
    write_jobs('character-jobs.json', jobs)


def selected_front(name):
    selections = json.loads((OUT / 'character-selection.json').read_text())
    item = selections[name]
    source = OUT / item['file']
    if sha(source) != item['sha256'] or item['decision'] != 'use_as_reference':
        raise RuntimeError('Character must pass visual selection before conditioning later jobs.')
    return source


def prepare_cleanups():
    originals = json.loads((OUT / 'character-jobs.json').read_text())
    jobs = []
    for previous in originals:
        if previous['person'] == 'mark':
            continue
        source = OUT / 'candidates' / f'{previous["id"]}-r1.png'
        prompt = ('Edit image 1, the same single illustrated character portrait. '
            'Remove ONLY every small rectangular branding patch and label from the '
            'jacket sleeves and chest. Replace those patch areas with plain continuous '
            'matte jacket cloth in the same local color and ink hatching. Keep all '
            'normal seams, pockets, zipper, face shape, eyes, nose, mouth, hair, '
            'skin pigment, pose, framing, background and drawing medium unchanged. '
            'The jacket is completely unbranded, with no badges, insignia or letters. '
            'Do not change the character or add objects.')
        job = {**previous, 'prompt_revision': 2, 'prompt': prompt,
            'references': [reference(source, f'cleanup-{previous["person"]}')],
            'kind': 'localized-branding-cleanup', 'parent_candidate': str(source)}
        jobs.append(job)
    write_jobs('cleanup-jobs.json', jobs)


def prepare_views():
    jobs = []
    for name, person in PEOPLE.items():
        canonical = selected_front(name)
        refs = [reference(canonical, f'drawn-identity-{name}')]
        prompt = (INK + f'Exactly ONE {name.title()}, the SAME drawn fictional character '
            'from image 1. Turn the camera to a clean LEFT-facing full side profile '
            'of the head and upper chest. Preserve the same face construction, nose '
            'shape, age, hair length and silhouette, neck proportions, ink line '
            f'weight and {person["wardrobe"]}. Neutral closed mouth, relaxed brows, '
            'one visible eye in full side profile. Simple charcoal backdrop, the '
            'same neutral diffuse reference illumination and matte pigment. No '
            'second view, extra person, hand, new clothing, lettering or panel border.')
        jobs.append({'id': f'{name}-profile', 'kind': 'profile', 'person': name,
            'size': [1024, 1024], 'seed': person['seed'] + 10, 'prompt_revision': 1,
            'prompt': prompt, 'references': refs, 'user_approved': False})
        prompt = (INK + f'Three side-by-side head-and-shoulder expression studies of the '
            f'SAME {name.title()} from image 1, all in the same frontal camera view. '
            'This is deliberately a character model sheet with three separated '
            'views, NOT a scene containing three people. Left: neutral closed mouth '
            'and relaxed eyes. Centre: restrained worry, subtle inner brow tension '
            'and a gently pressed closed mouth. Right: controlled fear, tense brows '
            'and slightly parted lips, still natural small eyes and no screaming '
            'or tears. Preserve identical face shape, hair, age, proportions, ink '
            f'line weight and {person["wardrobe"]} in all three views. '
            'The same quiet charcoal backdrop and neutral reference illumination. '
            'No captions, labels, borders, extra views or other characters.')
        jobs.append({'id': f'{name}-expressions', 'kind': 'expression-sheet', 'person': name,
            'size': [1536, 864], 'seed': person['seed'] + 20, 'prompt_revision': 1,
            'prompt': prompt, 'references': refs, 'user_approved': False})
    write_jobs('view-jobs.json', jobs)


def prepare_pilot():
    plan = json.loads((ROOT / 'outputs/first-film/curated/assets/shot_plan.json').read_text(encoding='utf-8'))
    by_id = {shot['id']: shot for shot in plan['shots']}
    jobs = []
    for index, shot_id in enumerate(PILOT_SHOTS + MARK_PROBES):
        shot = by_id[shot_id]
        names = [name for name in shot['refs'] if name in PEOPLE]
        refs = [reference(ROOT / 'outputs/first-film/curated/assets/images' / f'{shot_id}.png', shot_id)]
        refs += [reference(selected_front(name), f'drawn-identity-{name}') for name in names]
        refs.append(reference(STYLE_SOURCE, 'ink-style'))
        roles = ['Image 1 defines only the original camera framing, poses, object positions and geography; replace its photographic rendering with ink.']
        roles += [f'Image {number} defines the drawn face, hair and wardrobe of the SAME {name.title()}, not an extra person.'
                  for number, name in enumerate(names, 2)]
        roles.append(f'Image {len(refs)} is ONLY the ink medium, linework and low-key night value guide. Do not import its man, shirt, camp layout or objects.')
        night = ('Deep midnight: distant trees and sky are near-black charcoal navy, '
            'with sparse dim blue-grey silhouette separation, never bright twilight. ')
        if shot['lighting'] == 'night':
            night += ('The campfire provides the only warm key: small flat muted amber '
                'pigment shapes on the near-facing cheek, chin and hands, while the '
                'far side of a face is a broad matte charcoal shadow. Preserve readable '
                'faces and costume midtones, a small bright flame and a darker forest. ')
        else:
            night += ('Only the nearest bark and ground have small flat cold grey-blue '
                'illuminated shapes. The deeper forest remains dark with readable '
                'edges, without artificial fog or a visible light cone. ')
        prompt = ((INK if names else OBJECT_INK) + ' '.join(roles) + ' ' +
            SHOT_ACTIONS[shot_id] + ' ' + night +
            'Keep the same serious adult horror drawing treatment across this sequence. '
            'Single full-bleed 16:9 frame, no poster layout, new story event or border. '
            'Never add a character or colored garment from a style-only reference.')
        jobs.append({'id': shot_id, 'kind': 'sequence-keyframe' if shot_id in PILOT_SHOTS else 'standalone-continuity-probe', 'shot': shot_id,
            'people': names, 'beat': shot['beat'], 'motion': shot['motion'], 'lighting': shot['lighting'],
            'size': [1536, 864], 'seed': 2026100800 + index, 'prompt_revision': 1,
            'prompt': prompt, 'references': refs, 'user_approved': False})
    write_jobs('pilot-jobs.json', jobs)


def prepare_view_repairs():
    previous = {job['id']: job for job in json.loads((OUT / 'view-jobs.json').read_text())}
    mark_source = OUT / 'candidates/mark-expressions-r1.png'
    mark = {**previous['mark-expressions'], 'prompt_revision': 2,
        'kind': 'targeted-expression-repair',
        'references': [reference(mark_source, 'mark-expression-repair')],
        'prompt': ('Edit ONLY the LEFT face in image 1, the three-view illustrated Mark expression sheet. '
            'Make that left expression genuinely neutral and relaxed: remove vertical glabellar '
            'furrows and forehead tension marks, relax the inner eyebrows to a level resting '
            'position, open resting eyelids naturally, and keep a relaxed closed mouth. '
            'No angry downward eyebrow pinch. Retain the exact left face shape, adult age, '
            'hair silhouette, nose, jacket color, pose, matte pigment and ink drawing medium. '
            'The centre worried view and right fearful view remain unchanged. '
            'Keep precisely three views, with no labels, lettering or added objects.')}
    jess = {**previous['jess-profile'], 'prompt_revision': 2,
        'kind': 'profile-identity-repair',
        'references': [reference(selected_front('jess'), 'drawn-identity-jess')],
        'prompt': ('Draw the SAME young adult WOMAN Jess from image 1 in a strict 90-degree '
            'left-facing head-and-upper-chest side profile. The far eye, far eyebrow and '
            'far nostril are completely hidden, not a three-quarter view. Preserve her '
            'specific soft jaw, feminine face construction, smooth unshaven upper lip and '
            'chin, dark collar-length curls, muted olive-tan skin and faded OLIVE GREEN '
            'jacket over dark T-shirt. Do not introduce beard, moustache, stubble, masculine '
            'jaw proportions or another person. Black-ink contours, flat matte pigment '
            'and paper grain exactly as in image 1. Sparse hatching only in the neck '
            'shadow, not hairlike marks around her lips. Relaxed closed mouth, neutral '
            'eyebrow and plain charcoal backdrop. Entire head in frame, one visible eye, '
            'no text, patch or logo.')}
    write_jobs('view-repair-jobs.json', [mark, jess])


def prepare_scene_cleanups(ground_only=False):
    previous = {job['id']: job for job in json.loads((OUT / 'pilot-jobs.json').read_text())}
    jobs = []
    for shot_id, target in (('shot-037', 'small rectangular patch on the visible jacket sleeve'),
                            ('shot-040', 'small rectangular label near the tent base')):
        source = OUT / 'candidates' / f'{shot_id}-r1.png'
        job = {**previous[shot_id], 'prompt_revision': 2, 'kind': 'localized-scene-label-cleanup',
            'references': [reference(source, f'cleanup-{shot_id}')],
            'parent_candidate': str(source),
            'prompt': (f'Edit image 1. Remove ONLY the {target}; replace it with plain '
                'continuous unbranded cloth, preserving the exact local cloth color, '
                'folds and black-ink texture. No badge, letters or rectangular outline. '
                'Keep all faces, hair, pose, fingers, wardrobe colors, campsite geometry, '
                'camera framing, fire, trees, lake, vehicle, sky, night lighting, matte '
                'pigment and graphic-novel medium unchanged. Do not add or move anything.')}
        jobs.append(job)
    source = OUT / 'candidates/shot-044-r1.png'
    jobs.append({**previous['shot-044'], 'prompt_revision': 2, 'kind': 'localized-ground-light-repair',
        'references': [reference(source, 'cleanup-ground-shot-044')], 'parent_candidate': str(source),
        'prompt': ('Edit ONLY the small bright cyan oval on the ground low in image 1. '
            'It must NOT be a puddle, pool, disc or painted object. Replace the hard-edged '
            'cyan oval with continuous matte dirty grey-brown forest ground, the same '
            'scattered leaves, roots and ink hatching as the adjacent path. A very faint '
            'soft diffuse cold illumination on that textured ground is allowed, without '
            'a visible outline, saturated blue fill, water, reflection or flat ellipse. '
            'Keep the trees, path geometry, dark sky, framing, ink medium and all other '
            'parts of the image unchanged. No people, hands, torch, equipment or visible '
            'light cone. Single full-bleed nighttime graphic-novel frame.')})
    write_jobs('scene-ground-repair-jobs.json' if ground_only else 'scene-cleanup-jobs.json', jobs[-1:] if ground_only else jobs)


def prepare_two_person_cleanup():
    previous = next(job for job in json.loads((OUT / 'pilot-jobs.json').read_text()) if job['id'] == 'shot-039')
    source = OUT / 'candidates/shot-039-r1.png'
    write_jobs('two-person-cleanup-jobs.json', [{**previous, 'prompt_revision': 2,
        'kind': 'localized-scene-label-cleanup', 'parent_candidate': str(source),
        'references': [reference(source, 'cleanup-shot-039')],
        'prompt': ('Edit image 1, the exact same two illustrated women by the campfire. '
            'Remove ONLY the tiny square badge with a circular mark on the outer upper '
            'sleeve of the curly-haired woman on the RIGHT. Replace that small badge '
            'with continuous plain matte olive jacket fabric in the same local color '
            'and ink texture. Preserve both women\'s faces, hair, age, gaze, poses, '
            'hands, clothing silhouettes, grey LEFT jacket, olive RIGHT jacket, '
            'fire, tent, trees, framing, pigment, darkness and ink medium. No patch, '
            'circle, insignia, letter or logo remains on that sleeve. Add nothing.') }])


def run(manifest, ids):
    if Path(manifest).name != manifest or not manifest.endswith('.json'):
        raise ValueError('Local JSON manifest filename required.')
    jobs = json.loads((OUT / manifest).read_text(encoding='utf-8'))
    models = json.loads((ROOT / 'outputs/style-lab-v7/model-lock.json').read_text())
    for item in models:
        path = COMFY / 'data/models' / item['file']
        if not path.is_file() or path.stat().st_size != item['size'] or sha(path) != item['sha256']:
            raise RuntimeError('Model checksum verification failed: ' + item['file'])
    save(OUT / 'model-lock.json', models)
    for job in jobs:
        if ids and job['id'] not in ids:
            continue
        nodes = make_graph(job)
        fingerprint = hashlib.sha256(json.dumps({'graph': nodes, 'models': models,
            'reference_hashes': [r['sha256'] for r in job['references']]}, sort_keys=True).encode()).hexdigest()
        stem = f'{job["id"]}-r{job["prompt_revision"]}'
        report_path = OUT / 'candidates' / f'{stem}.json'
        if report_path.exists():
            previous = json.loads(report_path.read_text())
            if previous['fingerprint'] == fingerprint and sha(previous['image']) == previous['sha256']:
                print('CACHED', stem, flush=True)
                continue
            raise RuntimeError('Existing output differs; prepare a separate revision.')
        queue = call('/queue')
        if queue.get('queue_running') or queue.get('queue_pending'):
            raise RuntimeError('Another task is queued. No queue was modified.')
        for ref in job['references']:
            if sha(ref['source']) != ref['sha256'] or sha(COMFY / 'data/input' / ref['image']) != ref['sha256']:
                raise RuntimeError('Reference hash mismatch.')
        workflow = OUT / 'workflows' / f'{stem}-api.json'
        if json.loads(workflow.read_text()) != nodes:
            raise RuntimeError('Prepared workflow mismatch.')
        print('GENERATING', stem, flush=True)
        started = time.monotonic()
        result = run_graph(workflow, 1800)
        if not result['completed'] or len(result['outputs']) != 1:
            raise RuntimeError('Expected one completed image.')
        source = Path(result['outputs'][0]['file'])
        with Image.open(source) as image:
            pixels = np.asarray(image.convert('RGB'))
            if list(image.size) != job['size'] or pixels.std() < 2:
                raise RuntimeError('Invalid output size or blank image.')
        destination = OUT / 'candidates' / f'{stem}.png'
        if destination.exists():
            raise RuntimeError('Untracked candidate exists; no overwrite.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        save(report_path, {'job': job, 'image': str(destination), 'sha256': sha(destination),
            'fingerprint': fingerprint, 'prompt_id': result['prompt_id'],
            'seconds': round(time.monotonic() - started, 2), 'workflow': str(workflow),
            'models': models, 'source_output': str(source), 'user_approved': False,
            'automatic_quality_approval': False, 'kaggle_uploaded': False})
        print('CANDIDATE', stem, flush=True)


def verify():
    baseline = json.loads((OUT / 'preservation-baseline.json').read_text())
    failed = [item['file'] for item in baseline if not Path(item['file']).is_file()
        or Path(item['file']).stat().st_size != item['size'] or sha(item['file']) != item['sha256']]
    save(OUT / 'preservation-validation.json', {'checked_files': len(baseline), 'unchanged': not failed, 'changed': failed})
    if failed:
        raise RuntimeError('Checkpoint changed: ' + ', '.join(failed))
    print('PRESERVED', len(baseline), 'baseline files.', flush=True)


def board(manifest):
    jobs = json.loads((OUT / manifest).read_text())
    columns = 3 if len(jobs) % 3 == 0 else 2
    cell_w, cell_h, gap, label_h = 512, 320, 18, 34
    rows = (len(jobs) + columns - 1) // columns
    canvas = Image.new('RGB', (columns * (cell_w + gap) + gap,
        rows * (cell_h + label_h + gap) + gap), '#151719')
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 20)
    for index, job in enumerate(jobs):
        stem = f'{job["id"]}-r{job["prompt_revision"]}'
        x, y = gap + (index % columns) * (cell_w + gap), gap + (index // columns) * (cell_h + label_h + gap)
        source = OUT / 'candidates' / f'{stem}.png'
        if source.exists():
            with Image.open(source) as image:
                image = image.convert('RGB')
                image.thumbnail((cell_w, cell_h), Image.Resampling.LANCZOS)
                canvas.paste(image, (x + (cell_w - image.width) // 2, y))
        draw.text((x, y + cell_h + 5), stem, font=font, fill='#d1d4d8')
    destination = OUT / (Path(manifest).stem + '-board.jpg')
    canvas.save(destination, quality=95, subsampling=0)
    print('BOARD', destination, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['characters', 'cleanups', 'views', 'view-repairs', 'pilot', 'scene-cleanups', 'ground-repair', 'two-person-cleanup', 'run', 'verify', 'board'])
    parser.add_argument('--manifest', default='character-jobs.json')
    parser.add_argument('--ids', nargs='*')
    args = parser.parse_args()
    {'characters': prepare_characters, 'cleanups': prepare_cleanups, 'views': prepare_views, 'view-repairs': prepare_view_repairs, 'pilot': prepare_pilot, 'scene-cleanups': prepare_scene_cleanups, 'ground-repair': lambda: prepare_scene_cleanups(True), 'two-person-cleanup': prepare_two_person_cleanup,
        'run': lambda: run(args.manifest, args.ids), 'verify': verify,
        'board': lambda: board(args.manifest)}[args.action]()
