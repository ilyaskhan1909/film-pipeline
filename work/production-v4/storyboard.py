"""Authored shot plan. The story is data; no notebook code is executed."""
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def original_story():
    notebook = json.loads((ROOT/'work/reference-v21/videogenerator-v2-1.ipynb').read_text(encoding='utf-8'))
    for cell in notebook['cells']:
        if cell['cell_type'] != 'code':
            continue
        try:
            tree = ast.parse(''.join(cell['source']))
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'story_text' for t in node.targets):
                return ast.literal_eval(node.value).strip()
    raise ValueError('Reference story not found')

CHARACTERS = {
    'mark': 'Mark, a young adult man with short dark hair, clean-shaven face, wearing an unbuttoned cobalt-blue camping shirt over a plain dark undershirt. Keep the blue shirt clearly recognizable.',
    'chloe': 'Chloe, a young adult woman with shoulder-length straight brown hair, wearing a charcoal camping jacket.',
    'jess': 'Jess, a young adult woman with dark curly hair, wearing a faded olive camping jacket.',
    'doll': 'A crude palm-sized effigy of stained coarse tan burlap, an asymmetric sack-shaped head, lumpy stuffing and clumsy black stitches. The left black button eye is twice the diameter of the right button. The mouth is a short straight crooked stitch. Thin cloth arms pinch a tiny thumbnail-sized frayed scrap of cobalt-blue fabric. Deliberately primitive hand-sewn construction, expressionless, unsettling, never a cute smiling toy.',
    'figure': 'An inhuman woodland effigy over three metres tall, with an impossibly narrow vertical body and extremely elongated branch-like arms and legs of rough dark bark. A small featureless black oval head has only two tiny dark button glints. Limbs taper into thin twig fingers. Bare wooden structure, without human skin, hair, clothing, muscles or a recognizable human face. Most of its silhouette disappears against the tree trunks.',
}
STYLE = ('A naturalistic live-action cinematic frame, credible physical materials, controlled highlights, '
         'readable shadow detail, restrained color grading, realistic skin when visible. '
         'One deliberate composition, no lettering, watermark, collage, frame borders or artificial lens flare.')
# World context must not introduce props outside the authored camera crop.
# Previously the global tent/fire-ring list defeated every empty lake or macro shot.
SETTING = ('A remote American state-park lake and pine forest in summer, July 2018. '
           'Only the objects named in the shot description are visible in this camera crop.')
LIGHTS = {
    'day': 'Warm late-afternoon sunlight, natural green foliage, calm clear water and a genuinely relaxed summer atmosphere. No ominous fog or supernatural elements.',
    'dusk': 'The sun has set behind the tree line. Orange and purple remain in the sky; a small campfire is the warm practical light. Twilight, not pitch-black night.',
    'night': 'Night with warm practical campfire illumination. The lake and opposite forest fall into restrained cool shadows, still readable. No bright red lights or dense blue fog.',
    'forest': 'A dense pine and oak forest at night. A small soft patch of cold camera-side light falls on damp leaves and matte bark. Empty foreground and readable deep shadows; the rest of the forest is dark. All depicted objects are passive materials.',
}

# Each tuple is an independently authored frame: description, identity refs, lens / framing.
PLANS = [
    ('day', [
        ('The tiny secluded campsite beside the still lake, seen from above the near shore. A single green tent, four empty camping chairs and one stone fire ring occupy a small clearing. The rest of the shore is undisturbed forest. Water and forest occupy most of the composition; no people.', [], '24mm wide establishing shot'),
        ('A low view along the lake surface, showing almost perfect reflections of tall pine trees and an open summer sky. No people or tent in frame.', [], '35mm landscape at water level'),
        ('The campsite viewed between two foreground pine trunks: green tent, stone fire ring, camping chairs and still lake. Empty chairs; no people.', [], '35mm environmental frame'),
        ('Two distant friends wading in the cool lake, seen from behind as small anonymous silhouettes. Their faces are not visible. Sunny quiet shore.', [], '85mm long shot from shore'),
        ('Burgers and hot dogs cooking on a simple camping grill. A little natural cooking smoke, warm sunlight, no hands, faces or brands.', [], '70mm close detail'),
        ('A small campfire sends sparks upward beside the lake as daylight gently fades. Camping chairs at the edges, no identifiable people.', [], '50mm campfire detail'),
    ]),
    ('dusk', [
        ('The same secluded lake after sunset. The empty opposite tree line is now darker; the water is still, with a narrow orange-purple reflection.', [], '35mm wide horizon'),
        ('A single empty camping chair at the edge of the firelight, with the dark tree line behind it. Ordinary camping equipment; nothing supernatural visible.', [], '65mm uneasy medium detail'),
    ]),
    ('dusk', [
        ('Orange and bruising purple sky above the near-black silhouettes of pines, reflected in the lake. No firework bursts.', [], '50mm layered landscape'),
        ('The lake stretches toward the distant forest; no town is visible. A quiet wide frame emphasizes the miles of separation.', [], '24mm wide shore view'),
        ('Warm campfire embers in the lower foreground with deep twilight across the water. A calm surface, not a storm.', [], '85mm compressed foreground/background'),
    ]),
    ('dusk', [('The impenetrable forest across the lake. Nothing visible moves; a dark gap between two trunks becomes the focal point.', [], '85mm distant tree line')]),
    ('dusk', [
        ('Birds burst up from a pine canopy on the opposite shore, their wings caught as small dark shapes against twilight. No explosion or visible attacker.', [], '70mm canopy view'),
        ('The lake shore and trees seen from the campers position; a few birds still scatter above the pines. Keep the water unnaturally quiet.', [], '35mm reaction environment'),
        ('A charred stick rests beside bright campfire embers. The sudden disturbance is implied, not illustrated with a gun or fireworks.', [], '85mm ember close-up'),
    ]),
    ('night', [
        ('Mark seated beside the campfire in a candid side-profile view. He nudges the embers with a charred stick and gives a brief, unconvincing smile. The established blue shirt is prominent. Not a portrait pose; he looks at the fire, not the viewer.', ['mark'], '50mm medium side view'),
        ('Close view of the charred stick touching the embers, with only a small part of Marks blue sleeve at the edge. No visible face and no extra arms.', ['mark'], '85mm insert at fire level'),
    ]),
    ('night', [
        ('Chloe listens beside the fire, her easy expression turning uncertain. She looks past the camera toward the water, not directly into the lens.', ['chloe'], '85mm candid close-up'),
        ('A still lake viewed between empty camping chairs in the foreground. The distant tree line feels too close, without showing a monster.', [], '35mm lakeside point of view'),
        ('Mark has stopped smiling and stares into the dark across the water. Blue shirt, one side of his face softly lit by the campfire.', ['mark'], '65mm restrained reaction close-up'),
    ]),
    ('night', [
        ('Chloe seated close to the narrator, seen in three-quarter profile. Her worried eyes are fixed on the opposite forest. Warm firelight outlines the charcoal jacket.', ['chloe'], '85mm intimate side close-up'),
        ('Close detail of Chloes hand gripping one clothed forearm at the edge of a camping chair. Only one natural hand is clearly visible, no faces, no injury.', ['chloe'], '85mm isolated hand insert'),
    ]),
    ('night', [
        ('The lake and far forest seen from a seated first-person viewpoint. A small edge of the campfire is out of focus at the side; no human face.', [], '50mm seated point of view'),
        ('Chloe looks toward the unseen narrator, trying to believe a reassuring answer. A quiet uncertain face, not crying or screaming.', ['chloe'], '85mm reaction close-up'),
    ]),
    ('night', [
        ('Dark pines at the northern curve of the lake, seen across still black water. Narrow patches of reflected firelight, no visible source of the disturbing noise.', [], '70mm distant shore'),
        ('The eastern lake edge, low dark branches over a calm surface. Empty frame with no monster or glowing eyes.', [], '50mm shoreline angle'),
        ('Jess and Chloe sit silently beside the small fire, looking in different directions across the water. Jess has dark curly hair and an olive jacket; Chloe has straight brown hair and a charcoal jacket. No extra people.', ['jess','chloe'], '50mm medium two-shot from the side'),
        ('Only the campfires final ring of light and the dark trees beyond it. The surrounding night occupies most of the frame.', [], '35mm low wide campsite'),
    ]),
    ('night', [
        ('A plain dented beer can lies on damp dirt beside a camping chair. No readable label, no hand or face.', [], '85mm ground-level insert'),
        ('Mark leans forward at the edge of his camping chair, resolute and frustrated, his blue shirt catching warm firelight. He looks toward the forest.', ['mark'], '50mm medium side view'),
    ]),
    ('night', [
        ('Mark retrieves a heavy black flashlight from an open camping backpack. His blue shirt is visible; show a simple natural hand grip, no complicated finger gesture.', ['mark'], '65mm medium detail'),
        ('Mark walks away from the campsite toward the pine tree line, viewed from behind. The flashlight beam points ahead; his blue shirt fades into darkness. No other person.', ['mark'], '35mm rear long shot'),
        ('Marks receding silhouette between two distant pine trunks, seen from camp. His flashlight makes a small isolated white patch in the forest.', ['mark'], '85mm distant rear view'),
        ('The same dark entry into the forest after the flashlight has disappeared. Absolutely no person or lamp visible.', [], '50mm empty forest entrance'),
    ]),
    ('night', [
        ('Marks empty camping chair beside a diminishing fire, with the lake beyond. His absence is the focal point. No people.', [], '50mm empty chair'),
        ('The motionless lake at night, entirely empty of boats or people. Pines form a dark wall across the water.', [], '35mm prolonged wide stillness'),
        ('An unlit narrow trail disappearing into dark pines just beyond the campfires reach. No creature, eyes or human silhouette.', [], '70mm forest gap'),
    ]),
    ('night', [
        ('Jess seated beside the fire, hugging her knees close to her chest. Dark curly hair, faded olive jacket, subdued anxiety. She looks toward the unseen narrator.', ['jess'], '65mm medium side close-up'),
        ('Closer view of Jess trying to offer reassurance, but her eyes remain uncertain. Natural skin, no exaggerated tears.', ['jess'], '85mm close-up'),
    ]),
    ('night', [
        ('Chloe and Jess look up toward the unseen narrator who has stood. Camera is now a little above their eye level. Both remain near the campfire; no extra person.', ['chloe','jess'], '50mm first-person medium two-shot'),
        ('The green tent, small parked camping car at the edge of the clearing, and a narrow path out of camp. A practical escape route, no action or new event shown.', [], '35mm environmental cutaway'),
    ]),
    ('forest', [
        ('Chloes pale face in warm firelight as she gives a small serious nod, charcoal jacket and familiar brown hair. The background is the campsite, not the deeper forest.', ['chloe'], '85mm quiet close-up'),
        ('A first-person view toward the dark pine trail. A narrow flashlight beam reveals only a patch of damp leaves and tree roots; no person in frame.', [], '35mm flashlight point of view'),
        ('The dense interlocking canopy of pine branches at night, blocking the sky. A faint flashlight spill catches a few rough branches from below.', [], '24mm upward forest view'),
        ('A narrow corridor of trees lit by the narrators flashlight. Empty path, cold air implied by stillness, no artificial smoke or fog wall.', [], '50mm forest point of view'),
    ]),
    ('forest', [
        ('One hiking boot at the bottom edge of a first-person view, stepping onto dry leaves on a dark forest path. Most of the frame is forest floor within flashlight light.', [], '50mm downward point of view'),
        ('A beam of white light cuts across empty rough tree trunks. No reply, face or visible attacker.', [], '65mm empty search frame'),
    ]),
    ('forest', [
        ('Marks heavy black flashlight lies on damp soil, still switched on. Its beam creates a clear round patch of light on the gnarled roots of a huge oak. No person.', [], '50mm discovery shot at ground level'),
        ('Wide view of the huge oak and its roots, surrounded by dark pines. A fallen flashlight is the only practical light near the base; nobody stands beside it.', [], '35mm low oak establishing shot'),
        ('The fallen heavy black flashlight and the empty ground around it. A second narrow search beam grazes the leaves. The absence of Mark is unmistakable.', [], '85mm flashlight insert'),
    ]),
    ('forest', [('A small indistinct burlap object lies at the edge of the fallen flashlight beam among oak roots and leaves. It is only partially revealed; no person.', ['doll'], '65mm partial discovery detail')]),
    ('forest', [
        ('The established crude burlap doll lies at the base of the oak in damp dirt and leaves. A narrow flashlight beam reveals its stained cloth body and two mismatched black button eyes. The small blue fabric scrap is present but not yet emphasized.', ['doll'], '65mm full doll close-up'),
        ('Extreme close-up of the dolls coarse burlap face, irregular stitches and two mismatched black buttons. An ordinary handmade cloth doll, not a human face.', ['doll'], '100mm macro texture'),
        ('Extreme close-up of just two knotted stained burlap cloth hands pinching ONE loose tiny frayed scrap of cobalt-blue cloth between them. Only cloth fingers, stitches and the rag fill the frame. The dolls head and torso are entirely outside the crop. The blue rag is loose, not wrapped around wrists.', [], '100mm hands and cloth insert'),
    ]),
    ('forest', [
        ('Extreme close-up: a SINGLE thumbnail-sized torn scrap of cobalt-blue shirt fabric is pinched between two primitive knotted burlap cloth fingertips. Loose frayed blue threads are sharply readable. The fabric and cloth fingertips fill the frame; the doll body and face are entirely outside the crop. The blue fabric is a loose rag, not a cuff or sleeve.', [], '100mm blue cloth macro'),
        ('The familiar burlap doll beside the fallen black flashlight, both on the damp ground among oak roots. No human figure visible.', ['doll'], '50mm low two-object composition'),
    ]),
    ('forest', [
        ('The narrators flashlight illuminates a narrow open route between rough tree trunks, seen from first person while turning away from the oak. No attacker in frame yet.', [], '35mm tense point of view'),
        ('A diagonal sweep of flashlight illumination across trunks at the edge of the path. Keep the image sharp enough to read; restrained asymmetry, not a blurred abstract frame.', [], '50mm off-axis forest view'),
        ('The dark forest beyond the circle of light. Small details of branches emerge at the frame edge; no clear creatures or glowing eyes yet.', [], '70mm suspense detail'),
    ]),
    ('forest', [('Two tiny dark button-eye reflections barely visible between pine trunks just beyond the beam. Keep the face hidden and the glint small, not bright neon eyes.', [], '85mm first glimpse')]),
    ('forest', [
        ('A dozen towering impossibly thin wooden effigies stand motionless among the pines at the edge of a flashlight beam. Their bare branch bodies blend into trunks; small featureless heads remain black voids. The scene feels like an empty forest until the unnatural long limbs become visible.', [], '35mm wide restrained reveal'),
        ('Three towering wooden branch-limbed effigies stand mostly concealed behind thick pine trunks. Only long thin twig arms emerge. Each twig hand holds a palm-sized crude burlap doll far below its small hidden black head. The objects are much smaller than the hands. A first-person flashlight illuminates bark and dolls, leaving the heads outside the beam.', [], '65mm partial reveal through trees'),
        ('Extreme close-up of one long rough dead-wood twig hand, with four tapered twig fingers curling around the cloth arm of a tiny crude burlap effigy. Only wooden fingers and the small cloth object are in frame; the tall body and head are entirely outside the crop. The fingers are irregular branching dead wood, not a human hand inside bark.', [], '85mm doll and skeletal hand detail'),
        ('The tiny featureless black oval head of a woodland effigy is barely visible between tree trunks. Two tiny lifeless dark button glints catch the beam. Rough bark at the edges dissolves into darkness.', ['figure'], '100mm barely visible face close detail'),
        ('Several rows of towering bare wooden effigies are half hidden behind pines. Their narrow elongated branch limbs blend into tree trunks. A small circle of ground light emphasizes how little the narrator can see.', [], '24mm surrounded point of view'),
    ]),
    ('forest', [
        ('The closest towering wooden effigy raises an extremely elongated thin branch arm. A single twig finger points sideways and away toward a distant warm camp glow between trees. Its tiny featureless head remains a black void, most of its bare wooden body concealed by a thick pine trunk.', ['figure'], '65mm medium silhouette with readable pointing direction'),
        ('First-person view back toward the direction of camp through the dark trees. A tiny warm glow is visible far away between trunks, contrasting with the cold flashlight light.', [], '85mm distant camp glow'),
        ('The fallen flashlight beside the oak roots, the burlap doll still motionless. A final detail of the blue fabric scrap in the narrow beam.', ['doll'], '65mm final object insert'),
    ]),
    ('night', [
        ('The distant campsite fire seen through dense dark pine trunks from inside the forest. The campsite is partly hidden. No explosion or injured people; the sudden sound and screams are carried by audio.', [], '85mm remote camp view'),
        ('Two empty camping chairs beside the small campfire on the silent lake shore. An unsettling final composition with the forest occupying most of the image. No visible bodies or monster.', [], '35mm final wide campsite'),
        ('Still lake water reflects only the last few embers and the black wall of pine trees. No people, text or supernatural red lights.', [], '50mm closing water detail'),
    ]),
]

def make_plan():
    story = original_story()
    paragraphs = [line.strip() for line in story.splitlines() if line.strip()]
    assert len(paragraphs) == len(PLANS) == 26
    segments = []
    shots = []
    for beat, (text, (light, rows)) in enumerate(zip(paragraphs, PLANS)):
        emotion = ('calm' if beat == 0 else 'uneasy' if beat < 10 else
                   'worried' if beat < 18 else 'afraid' if beat < 23 else 'terror')
        direction = {
            'calm': 'A warm, credible first-person recollection of a happy summer camping trip. Relaxed and conversational, not ominous.',
            'uneasy': 'A credible first-person recollection. Growing unease, a little guarded, still trying to sound rational. Do not overact.',
            'worried': 'An intimate first-person account. Restrained fear and concern for a missing friend. Build tension through meaningful pauses, not a constant whisper.',
            'afraid': 'An intimate first-person horror account. Fear rises as the narrator understands what he has found. Clear words, natural breathing, controlled intensity.',
            'terror': 'A first-person recollection of profound fear. Urgent but intelligible, emotionally shaken without screaming or a theatrical monster voice.',
        }[emotion]
        segments.append({'index': beat, 'text': text, 'emotion': emotion,
                         'voice_instruction': direction + ' Same adult English narrator throughout. Natural clear American English, around 135 words per minute. Read exactly the text, with no added words, music or sound effects.'})
        for description, refs, lens in rows:
            effective_light = 'night' if beat == 15 and refs == ['chloe'] else light
            identity = ' '.join(CHARACTERS[name] for name in refs)
            if beat==23 and not refs:
                identity=CHARACTERS['figure']+' '+(CHARACTERS['doll'] if 'doll' in description or 'cloth object' in description else '')
            prompt = f'{lens}. {description} {identity} {LIGHTS[effective_light]} {SETTING if effective_light != "forest" else "A remote state-park forest in summer, July 2018."} {STYLE}'
            if refs:
                prompt += ' Reference images define appearance and clothing only; create this newly specified camera angle and action. Do not reproduce a reference portrait pose or background.'
            shots.append({'id': f'shot-{len(shots):03d}', 'index': len(shots), 'beat': beat,
                          'refs': refs, 'lighting': effective_light, 'lens': lens,
                          'description': description, 'prompt': prompt,
                          'motion': ['push-in', 'pan-right', 'hold', 'pan-left'][len(shots)%4],
                          'weight': 1.0})
    assert ' '.join(s['text'] for s in segments) == ' '.join(story.split())
    return {'schema': 4, 'title': 'The Last Firework', 'story': story,
            'segments': segments, 'shots': shots, 'characters': CHARACTERS,
            'reference_characters':dict(CHARACTERS,doll='A palm-sized primitive hand-sewn burlap effigy. Asymmetric rectangular sack-shaped head, lumpy body, coarse stained tan weave, clumsy irregular black stitches. One large black button eye and one distinctly smaller black button eye. A single short straight black mouth stitch. Two bare empty knotted cloth hands; plain burlap arms with loose tan threads. Plain expressionless unfinished handmade construction, all cloth is tan. Clear object reference with empty hands; no accessories or colored fabric.'),
            'pilot_shots': [0, 1, 4, 15, 20, 51, 54, 61], 'pilot_audio': [0, 1, 19]}

if __name__ == '__main__':
    plan = make_plan()
    print(json.dumps({'words': len(plan['story'].split()), 'segments': len(plan['segments']),
                      'shots': len(plan['shots']), 'pilot': [(plan['shots'][i]['id'], plan['shots'][i]['description']) for i in plan['pilot_shots']]}, ensure_ascii=False))
