"""Controlled local FLUX.2 Klein style probes. Checkpoints are read-only."""
import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/style-lab-v7'
COMFY = ROOT / 'local-comfy'
sys.path.insert(0, str(ROOT / 'work/local-production-v6'))
from assets import graph
from download_models import digest
sys.path.insert(0, str(COMFY))
from comfy_client import call, run_graph, save

STYLES = {
    'ink': {
        'label': 'Dark ink / graphic novel',
        'prompt': ('Redraw the entire scene as an original hand-inked adult horror graphic '
            'novel illustration. Bold irregular black contour lines, angular expressive '
            'faces, dry-brush hatching and sparse printed halftones, broad flat matte '
            'shadow shapes on subtly textured paper. Every face, garment, tree and prop '
            'is deliberately drawn, not photographed. Use a restrained charcoal-black, '
            'desaturated ink-blue and warm umber palette, small muted amber fire accents '
            'and readable near-black negative space. Facial features are simplified '
            'but anatomically coherent, with small natural eyes and recognizable '
            'individual silhouettes. Serious unsettling storytelling, not a superhero '
            'poster or a cute comic. Skin is flat ink and pigment, with no glossy '
            'highlights, rendered pores, bevels, plastic surfaces or smooth 3D shading. '),
    },
    'cel': {
        'label': 'Hand-drawn 2D / matte cel',
        'prompt': ('Redraw the entire scene as a frame from an original mature hand-drawn '
            '2D horror animated film. Clean economical uneven pencil-and-ink contours, '
            'matte opaque cel paint, expressive simplified faces, two or three discrete '
            'flat shadow shapes per form, and hand-painted background layouts. Treat '
            'every person and object as a 2D drawing, never a 3D cartoon or a filtered '
            'photograph. Restrained adult proportions, small natural eyes, distinctly '
            'shaped faces and understated acting. Quiet charcoal, desaturated midnight '
            'blue and warm brown palette with restrained amber firelight. Deep night '
            'remains readable. Opaque flat pigments, matte skin, no shiny toy surfaces, '
            'airbrushed gradients, doll-like eyes or polished computer-rendered volume. '),
    },
    'gouache': {
        'label': 'Painterly / dark gouache',
        'prompt': ('Repaint the entire scene as an original dark gouache-and-charcoal '
            'horror illustration on coarse matte paper. Visible broken dry brushstrokes, '
            'opaque layered pigment, soft lost-and-found edges, rough scumbled shadows '
            'and deliberately simplified painted faces. Every form is constructed '
            'from brush marks and color shapes, not photo detail or 3D rendering. '
            'Restrained adult anatomy, small natural eyes, recognizable individual '
            'features and serious understated emotion. A limited palette of near-black '
            'charcoal, desaturated midnight blue, moss-grey and muted umber with small '
            'amber accents. Readable night silhouettes rather than crushed black. '
            'Skin, bark and cloth have the same tactile matte painted treatment: no '
            'glossy plastic, smoothed photographic skin or computer-rendered shine. '),
    },
}

SCENES = {
    'shot-029': {
        'people': ['mark'],
        'intent': ('Exactly ONE young adult man, Mark, sits at the right of a nighttime '
            'lakeside campsite, leaning forward in his chair and looking into the dark '
            'forest, worried but restrained. Short dark hair, his established face, '
            'cobalt-blue overshirt over a dark T-shirt. The fire is low in the foreground, '
            'empty chair and bottle to the left, tent to the right, dark lake and pines '
            'behind. Keep the same framing, pose and object positions as image 1. '
            'Image 2 is a portrait of that SAME Mark for face shape, hair and wardrobe '
            'only; do not add a second person. Preserve the blue shirt as muted cobalt, '
            'not black. His mouth is closed, eyes natural and brows slightly tense. '),
    },
    'shot-039': {
        'people': ['chloe', 'jess'],
        'intent': ('Exactly TWO young adult women sit by the nighttime lakeside fire. '
            'Chloe stays on the LEFT with straight shoulder-length brown hair and a '
            'charcoal jacket; Jess stays on the RIGHT with short dark curls and an '
            'olive jacket. They look upward at an unseen storyteller with quiet '
            'unease, closed mouths and subtle brow tension, not broad smiles. Preserve '
            'their seated poses, framing, fire foreground, tent, lake and pine forest '
            'from image 1. Image 2 identifies the SAME Chloe and image 3 identifies '
            'the SAME Jess; these portraits are identity guides, not additional people. '
            'Keep the two faces distinct and the two jacket colors distinguishable. '),
    },
    'shot-060': {
        'people': [],
        'intent': ('A wide view of the same pine forest at deep night, with the existing '
            'very tall thin inhuman dead-wood effigies in their established positions '
            'between the trunks. Preserve the framing, tree positions, rough twig '
            'limbs, elongated narrow bodies and small featureless matte-black heads '
            'from image 1. Bark and roots are jagged and irregular, some figures are '
            'partly hidden by trees. No human faces, clothes, glowing eyes, new figures '
            'or visible campers. A low cold light barely separates the figures from '
            'the dark forest; no daylight or bright glowing blue sky. '),
    },
    'shot-062': {
        'people': [],
        'intent': ('The same single crude tan burlap doll in a close-up against a dark '
            'forest: rectangular sack head, two mismatched black button eyes, straight '
            'clumsy black cross-stitch mouth, plain tan cloth body and small closed '
            'mittens. Preserve the framing and main silhouette from image 1. The '
            'mittens hold ONE small clearly readable torn cobalt-blue shirt scrap '
            'at its lap. ONE narrow bark-covered branch hand curls its irregular '
            'twig fingers visibly around the doll\'s upper cloth arm, holding it '
            'suspended; not a decorative wreath behind it. The doll is an unsettling '
            'lifeless handmade prop, without a smile, eyebrows or a cute living face. '
            'Muted cold sidelight reveals its seams. No human hand or extra doll. '),
    },
}

INVARIANTS = ('Reference images define scene geometry and fictional character identities '
    'only. Replace their photographic material and rendering completely with the '
    'requested illustration medium. This is a single full-bleed 16:9 frame, not a '
    'panel layout, poster or storyboard. Keep the established people count, identities, '
    'ages, hair, clothing colors, spatial positions and story clues. No captions, '
    'speech bubbles, logos, lettering or borders. ')

# Human face instructions must not leak into creature/prop jobs.
OBJECT_STYLES = {
    'ink': ('Original hand-inked adult horror graphic novel illustration. Bold irregular '
        'black contour lines, angular broken shapes, dry-brush hatching and sparse '
        'printed halftones, broad flat matte shadow shapes on textured paper. Every '
        'tree and object is deliberately drawn with opaque flat ink and pigment. '
        'Near-black charcoal, muted ink blue and dirty umber; tactile rough edges '
        'rather than smooth 3D volume. Single full-bleed frame with no lettering. '),
    'cel': ('Original hand-drawn 2D adult horror animation frame. Economical uneven '
        'pencil-and-ink contours, opaque matte cel paint, flat discrete shadow shapes '
        'and hand-painted background layouts. Every tree and object is deliberately '
        'drawn in 2D, with jagged irregular silhouettes. Near-black charcoal, muted '
        'midnight blue and dirty umber, no glossy 3D volume. Single full-bleed frame '
        'with no lettering. '),
    'gouache': ('Original dark gouache-and-charcoal horror illustration on coarse '
        'matte paper. Broken dry brushstrokes, opaque layered pigment, rough scumbled '
        'shadows and lost-and-found edges. Every tree and object is constructed from '
        'painted shapes, never smooth photographic or 3D volume. Near-black charcoal, '
        'muted midnight blue and dirty umber. Single full-bleed frame, no lettering. '),
}

OBJECT_INTENTS = {
    'shot-060': ('Reinterpret image 1 as a pine forest at deep midnight. Keep its camera '
        'framing, main tree positions and arrangement of upright wooden effigies. '
        'Each effigy is entirely dead wood: a very narrow twisted bark-covered '
        'vertical root for a torso, long irregular leafless twigs as appendages, '
        'jagged tapering root ends. Each has a small solid charcoal-black featureless '
        'wooden head, a blank opaque shape without openings or face features. Bodies '
        'are visibly split, knotted, splintered wood in dirty grey-brown, with no '
        'skin, clothing or smooth mannequin surface. Some partly disappear behind '
        'the trunks. Deep near-black forest masses #0B1018 surround faint cold '
        'blue-grey edges #303947 on bark. The figures are barely revealed in the '
        'darkness rather than presented in a bright display. No visible campers, '
        'eyes, mouths, heads with a human haircut, glowing parts, daylight or sky glow. '),
    'shot-062': ('A close-up of ONE small lifeless crudely sewn tan burlap doll held '
        'suspended by ONE dead-wood hand. Image 1 defines the story prop and the '
        'close framing, but redesign the grip: a bark-covered wrist enters diagonally '
        'from the upper left foreground and ends in four thin irregular solid twig '
        'fingers. The fingers visibly curl around and pinch the doll\'s upper cloth '
        'arm, in front of and behind that same arm, supporting its weight. This is '
        'a connected hand grasping the arm, not a loop of branch behind the head. '
        'The doll has an angular rectangular sagging sack head, two small uneven '
        'dull black four-hole buttons sewn off-centre, and one straight clumsy '
        'cross-stitch seam across the head. A narrow limp tan cloth body, ragged '
        'opaque seams and closed misshapen cloth mittens. The mittens at its lap '
        'hold ONE tiny frayed cobalt-blue woven shirt scrap, still clearly visible. '
        'It is a crude inert ominous object, with no living expression or rounded '
        'plush mascot proportions. Deep navy-black forest #0B1018; a narrow muted '
        'cold rim barely reveals rough cloth and wood. No human hand, extra dolls, '
        'sparkles, shiny button catchlights or bright daylight. '),
}


def sha(path):
    return digest(Path(path))


def input_copy(source, role):
    checksum = sha(source)
    name = f'v7-{role}-{checksum[:12]}.png'
    destination = COMFY / 'data/input' / name
    if destination.exists() and sha(destination) != checksum:
        raise RuntimeError('Reference collision: no existing file overwritten.')
    if not destination.exists():
        shutil.copy2(source, destination)
    with Image.open(source) as image:
        size = list(image.size)
    return {'image': name, 'source': str(source), 'sha256': checksum, 'size': size}


def make_graph(job):
    nodes = graph(job, 'fast')
    nodes['13']['inputs']['filename_prefix'] = f'v7/{job["id"]}-r{job["prompt_revision"]}'
    return nodes


def prepare():
    if (OUT / 'jobs.json').exists():
        raise RuntimeError('Prepared experiment exists. Resume run; do not overwrite it.')
    jobs = []
    for index, (shot, scene) in enumerate(SCENES.items()):
        refs = [input_copy(ROOT / 'outputs/first-film/curated/assets/images' / f'{shot}.png', shot)]
        refs += [input_copy(ROOT / 'outputs/first-film/curated/assets/references' / f'{name}.png', name)
                 for name in scene['people']]
        for style, spec in STYLES.items():
            job = {'id': f'{style}-{shot}', 'shot': shot, 'style': style,
                'seed': 2026100700 + index, 'size': [1536, 864], 'prompt_revision': 1,
                'prompt': spec['prompt'] + INVARIANTS + scene['intent'],
                'references': refs, 'editorial_approved': False}
            jobs.append(job)
            save(OUT / 'workflows' / f'{job["id"]}-r1-api.json', make_graph(job))
    save(OUT / 'jobs.json', jobs)
    save(OUT / 'experiment.json', {'generator': 'local ComfyUI / FLUX.2 Klein 4B distilled FP8',
        'settings': {'steps': 4, 'cfg': 1.0, 'sampler': 'euler', 'size': [1536, 864]},
        'comparison': '3 prompt-defined media x 4 fixed scenes; same per-scene seed and references',
        'seed_note': 'Matched noise controls one variable; it does not guarantee identical geometry.',
        'style_reference': None, 'cloud_image_generation': False, 'paid_api': False,
        'style_labels': {key: value['label'] for key, value in STYLES.items()},
        'limitations': ['Only this installed quantized 4B configuration is tested.',
            'Small curated sample, not a universal model ranking.',
            'Still image tests, not animation or motion consistency tests.',
            'No automatic quality approval or Kaggle upload.'],
        'official_prompting_source': 'https://help.bfl.ai/articles/7592221790-how-do-i-generate-quickly-with-flux-2-klein'})
    paths = {Path(ref['source']) for job in jobs for ref in job['references']}
    paths.update((ROOT / 'outputs/local-production-v6/assets').glob('*.png'))
    for relative in ['outputs/first-film/The_Last_Firework_1080p.mp4',
            'outputs/local-production-v6/The_Last_Firework_v6_1080p.mp4',
            'outputs/local-production-v6/DELIVERY.json',
            'outputs/local-production-v6/editorial-selection.json']:
        paths.add(ROOT / relative)
    baseline = [{'file': str(path), 'size': path.stat().st_size, 'sha256': sha(path)}
                for path in sorted(paths)]
    save(OUT / 'preservation-baseline.json', baseline)
    print('PREPARED', len(jobs), 'separate local style probes.', flush=True)


def refinements():
    """Second, separate experiment: adjust illustrated lighting only."""
    if (OUT / 'refinements.json').exists():
        raise RuntimeError('Refinement manifest exists; resume without overwriting.')
    original = json.loads((OUT / 'jobs.json').read_text(encoding='utf-8'))
    jobs = []
    for previous in original:
        if previous['style'] not in ('ink', 'gouache') or previous['shot'] not in ('shot-029', 'shot-039'):
            continue
        style, shot = previous['style'], previous['shot']
        source = OUT / 'assets' / f'{previous["id"]}-r1.png'
        prompt = ('Edit image 1, an already drawn horror illustration. Preserve its exact '
            'drawing medium, contour lines or brush marks, the same character faces, '
            'ages, expressions, people count, poses, clothing, props and camera framing. '
            'Change ONLY the illustrated nighttime light and painted color-value hierarchy. '
            'The sky is a flat very dark charcoal navy #0B1018, almost black. The lake '
            'and distant trees merge into deep navy-black silhouette masses #121923, '
            'with only faint muted blue-grey edge separation. It is deep midnight, '
            'not twilight and not daylight. The campfire is the only warm light: '
            'small muted ochre-amber #B5783B painted shapes on the near-facing cheek, '
            'nose, chin and hands; the far side of each face has a broad matte charcoal '
            'shadow. Faces stay clearly readable through two or three deliberate '
            'flat color shapes, without 3D shading or shiny highlights. The rest of '
            'the frame is quiet and dark, while the flame is the brightest small '
            'shape. Preserve Mark\'s muted cobalt blue shirt or the women\'s charcoal '
            'and olive jackets as appropriate. Maintain tactile matte paper, no '
            'photographic skin, plastic volume, bloom, extra people, new objects '
            'or lettering. This is an illustration lighting adjustment, not a '
            'photorealistic relight or a new composition. ')
        job = {**previous, 'prompt_revision': 2, 'prompt': prompt,
            'references': [input_copy(source, f'{style}-{shot}-lighting')],
            'experiment': 'lighting refinement; reference type differs from controlled r1 matrix',
            'parent_candidate': str(source), 'user_approved': False}
        jobs.append(job)
        save(OUT / 'workflows' / f'{job["id"]}-r2-api.json', make_graph(job))
    save(OUT / 'refinements.json', jobs)
    print('PREPARED', len(jobs), 'separate lighting refinements.', flush=True)


def object_refinements():
    if (OUT / 'object-refinements.json').exists():
        raise RuntimeError('Object refinement manifest exists; resume without overwriting.')
    original = json.loads((OUT / 'jobs.json').read_text(encoding='utf-8'))
    jobs = []
    for previous in original:
        if previous['shot'] not in OBJECT_INTENTS:
            continue
        job = {**previous, 'prompt_revision': 2,
            'prompt': OBJECT_STYLES[previous['style']] + OBJECT_INTENTS[previous['shot']],
            'experiment': 'object-only style prompt + revised design/night; original geometry reference and seed retained',
            'user_approved': False}
        jobs.append(job)
        save(OUT / 'workflows' / f'{job["id"]}-r2-api.json', make_graph(job))
    save(OUT / 'object-refinements.json', jobs)
    print('PREPARED', len(jobs), 'object-only prompt revisions.', flush=True)


def wardrobe_repairs():
    """One-variable repair after an ambiguous shared wardrobe clause colored Chloe blue."""
    if (OUT / 'wardrobe-repairs.json').exists():
        raise RuntimeError('Wardrobe repair manifest exists; resume without overwriting.')
    original = json.loads((OUT / 'refinements.json').read_text(encoding='utf-8'))
    jobs = []
    for previous in original:
        if previous['shot'] != 'shot-039':
            continue
        source = OUT / 'assets' / f'{previous["id"]}-r2.png'
        job = {**previous, 'prompt_revision': 3,
            'prompt': ('Edit image 1. Make exactly ONE localized color correction: '
                'Chloe, the straight-haired woman on the LEFT, wears a matte CHARCOAL '
                'GREY jacket #3E4147. Repaint only that jacket with desaturated grey '
                'midtones and near-black grey shadows, with the same drawn folds '
                'and contour lines. It is grey, not cobalt blue. Keep Jess on the '
                'RIGHT and her muted OLIVE jacket completely unchanged. Keep both '
                'faces, hair, expressions, anatomy, poses, the existing drawn/painted '
                'medium, campfire, trees, lake, tent, all props and dark nighttime '
                'lighting exactly as in image 1. No new objects, borders or lettering.'),
            'references': [input_copy(source, f'{previous["style"]}-women-wardrobe')],
            'experiment': 'localized wardrobe color repair only; not a new style comparison',
            'parent_candidate': str(source), 'user_approved': False}
        jobs.append(job)
        save(OUT / 'workflows' / f'{job["id"]}-r3-api.json', make_graph(job))
    save(OUT / 'wardrobe-repairs.json', jobs)
    print('PREPARED', len(jobs), 'localized wardrobe repairs.', flush=True)


def run(ids, manifest='jobs.json'):
    if Path(manifest).name != manifest or not manifest.endswith('.json'):
        raise ValueError('Experiment manifest must be a local JSON filename.')
    jobs = json.loads((OUT / manifest).read_text(encoding='utf-8'))
    lock = json.loads((ROOT / 'outputs/local-production-v6/research/model-lock.json').read_text())
    models = [item for item in lock if item['profile'] in ('fast', 'shared')]
    for item in models:
        path = COMFY / 'data/models' / item['file']
        if not path.is_file() or path.stat().st_size != item['size'] or sha(path) != item['sha256']:
            raise RuntimeError('Required model failed pinned size/hash verification: ' + item['file'])
    save(OUT / 'model-lock.json', models)
    for job in jobs:
        if ids and job['id'] not in ids:
            continue
        nodes = make_graph(job)
        fingerprint = hashlib.sha256(json.dumps({'graph': nodes, 'models': models},
            sort_keys=True).encode()).hexdigest()
        stem = f'{job["id"]}-r{job["prompt_revision"]}'
        report_path = OUT / 'assets' / f'{stem}.json'
        if report_path.exists():
            previous = json.loads(report_path.read_text())
            if previous['fingerprint'] == fingerprint and sha(previous['image']) == previous['sha256']:
                print('CACHED', stem, flush=True)
                continue
            raise RuntimeError('Existing candidate differs. Use a separate revision.')
        queue = call('/queue')
        if queue.get('queue_running') or queue.get('queue_pending'):
            raise RuntimeError('Another task is queued; no queue changed or cancelled.')
        for ref in job['references']:
            if sha(ref['source']) != ref['sha256'] or sha(COMFY / 'data/input' / ref['image']) != ref['sha256']:
                raise RuntimeError('Reference changed; refusing stale provenance.')
        workflow_path = OUT / 'workflows' / f'{stem}-api.json'
        if json.loads(workflow_path.read_text()) != nodes:
            raise RuntimeError('Saved workflow mismatch.')
        started = time.monotonic()
        print('GENERATING', stem, flush=True)
        result = run_graph(workflow_path, 1800)
        if not result['completed'] or len(result['outputs']) != 1:
            raise RuntimeError('One completed image was not returned.')
        source = Path(result['outputs'][0]['file'])
        with Image.open(source) as image:
            pixels = np.asarray(image.convert('RGB'))
            if list(image.size) != job['size'] or pixels.std() < 2:
                raise RuntimeError('Invalid image dimensions or blank image.')
        destination = OUT / 'assets' / f'{stem}.png'
        if destination.exists():
            raise RuntimeError('Untracked output exists; no overwrite.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        save(report_path, {'job': job, 'image': str(destination), 'sha256': sha(destination),
            'fingerprint': fingerprint, 'prompt_id': result['prompt_id'],
            'seconds': round(time.monotonic() - started, 2), 'models': models,
            'workflow': str(workflow_path), 'source_output': str(source),
            'automatic_quality_approval': False, 'user_approved': False, 'kaggle_uploaded': False})
        print('CANDIDATE', destination.name, flush=True)


def board():
    width, height = 640, 360
    gap, top, label_height = 18, 62, 34
    canvas = Image.new('RGB', (3 * width + 4 * gap, top + 4 * (height + label_height + gap) + gap), '#151719')
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 23)
    small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 18)
    for col, (style, spec) in enumerate(STYLES.items()):
        x = gap + col * (width + gap)
        draw.text((x, 18), spec['label'], font=font, fill='#e4e3df')
        for row, shot in enumerate(SCENES):
            y = top + row * (height + label_height + gap)
            path = OUT / 'assets' / f'{style}-{shot}-r1.png'
            if path.exists():
                with Image.open(path) as image:
                    canvas.paste(image.convert('RGB').resize((width, height), Image.Resampling.LANCZOS), (x, y))
            draw.text((x, y + height + 6), shot + ' / ' + style, font=small, fill='#bcbfc4')
    canvas.save(OUT / 'style-comparison.jpg', quality=95, subsampling=0)
    print('BOARD', OUT / 'style-comparison.jpg', flush=True)


def verify():
    baseline = json.loads((OUT / 'preservation-baseline.json').read_text())
    failed = [item['file'] for item in baseline
        if not Path(item['file']).is_file() or Path(item['file']).stat().st_size != item['size']
        or sha(item['file']) != item['sha256']]
    save(OUT / 'preservation-validation.json', {'checked_files': len(baseline),
        'unchanged': not failed, 'changed': failed})
    if failed:
        raise RuntimeError('Checkpoint preservation check failed: ' + ', '.join(failed))
    print('PRESERVED', len(baseline), 'source and v6 deliverable files.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'refinements', 'object-refinements',
        'wardrobe-repairs', 'run', 'board', 'verify'])
    parser.add_argument('--ids', nargs='*')
    parser.add_argument('--manifest', default='jobs.json')
    args = parser.parse_args()
    {'prepare': prepare, 'refinements': refinements, 'run': lambda: run(args.ids, args.manifest),
     'object-refinements': object_refinements,
     'wardrobe-repairs': wardrobe_repairs,
     'board': board, 'verify': verify}[args.action]()
