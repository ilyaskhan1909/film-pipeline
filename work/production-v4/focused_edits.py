"""Use specific observed source frames, not a vague whole-story reference."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def apply_edits(plan):
    full=json.loads((ROOT/'outputs/first-film/full/assets/production_manifest.json').read_text(encoding='utf-8'))
    repair=json.loads((ROOT/'outputs/first-film/repair/assets/production_manifest.json').read_text(encoding='utf-8'))
    lookup={s['index']:s for s in repair['shots']}
    registry={}
    def source(key,index,origin,crop=None):
        manifest=full if origin=='full' else repair
        shot=full['shots'][index] if origin=='full' else lookup[index]
        g=shot['generation']
        assert g['model']=='black-forest-labs/FLUX.2-klein-4B'
        registry[key]={'source_run_id':manifest['run_id'],'source_image':shot['image'],
            'source_sha256':g['sha256'],'prompt':g['prompt'],'refs':shot['refs'],
            'seed':g['seed'],'size':g['size'],'crop':crop}
    for index in (44,48,56,60,61,64,65):source(f'original-{index}',index,'full')
    source('can-night',28,'repair')
    source('doll-clue',51,'repair',[450,170,970,850])
    source('doll-face',51,'repair',[510,190,885,455])
    source('cloth-close',53,'repair')
    source('void-head',63,'full',[645,25,875,255])
    registry['wood-hand']={'canonical':'figure','crop':[230,430,325,585]}
    general=('Edit image 1. Remove the foreground handheld torch and the hand holding it entirely. '
        'The foreground contains only natural forest ground and tree trunks. Preserve the original night exposure, '
        'tree geometry and all existing subject details. Keep soft cold illumination on the existing opaque bark and leaves, '
        'with their continuous original texture visible. Erase the bright lens and the cone of light in the air. '
        'It is a real-looking naturalistic night photograph, with deep readable shadows, not a daytime landscape.')
    tasks={
        28: (['can-night'],'Retain the exact plain metal can and camera crop in image 1. It is now a night photograph: lower the ambient exposure, deepen the defocused background into cool forest-black, and let very dim warm ember light touch only a narrow edge of the metal. The can remains physically natural, unlabelled, with its scratches unchanged.'),
        44: (['original-44'],general),
        48: (['original-48'],general+' Preserve the massive oak and its gnarled roots. The illuminated roots keep their real dirt and leaf texture; ground illumination has a feathered edge and does not form a painted white shape.'),
        52: (['doll-face'],'Image 1 is the face of the established cloth doll. Create a closely framed macro photograph of exactly this face, preserving the rectangular sack shape, both black buttons with their exact sizes, the clumsy seams and the short horizontal mouth with its central vertical stitch. Entirely coarse stained tan burlap and passive black buttons. Cold camera-side light; dark blurred oak bark behind. Face fills the photograph.'),
        54: (['cloth-close'],'The small BLUE fabric in image 1 is a separate loose torn scrap between two closed TAN burlap doll mittens. Create a tighter macro view of that same loose blue scrap, with its free curled frayed edges and woven texture. Keep the cloth hand edges visible only at the sides. The blue scrap is completely unattached and hangs freely between the tan cloth stubs. All black seams remain on the tan mittens only. Preserve the dark forest background and cold light of image 1.'),
        56: (['original-56'],general),
        60: (['original-60'],general+' Preserve every towering inhuman bare-wood effigy, its extremely long thin limbs and small featureless black void head. All figures remain visible in the same positions. Their head surfaces remain entirely featureless and matte.'),
        61: (['original-61','doll-clue'],general+' Keep the very tall thin wooden figures from image 1. Each figure holds just ONE much smaller tan cloth doll by a cloth arm; all other wooden hands are empty. Replace those dolls with the exact doll design from image 2: rectangular burlap head, two black buttons, straight cross-stitch mouth and closed plain tan cloth mittens holding a single separate loose blue scrap at the lap. The dolls are small passive objects, their whole bodies tan and their heads uncovered. Preserve the existing tree-trunk occlusion.'),
        62: (['wood-hand','doll-clue'],'Close prop photograph: the irregular dead-wood hand in image 1 grasps the upper cloth arm of ONE much smaller doll from image 2. Keep the doll design exactly: one rectangular sack head with two black buttons, plain tan burlap body, straight cross-stitch mouth and closed cloth mittens holding its loose blue scrap at the lap. The wooden hand curls its long solid bark-covered twig fingers around that one cloth upper arm. Only one wood hand and one small cloth doll fill the image. Every surface is rough dead wood or opaque tan fabric. Cold side light, dark defocused forest leaves.'),
        63: (['void-head'],'Image 1 shows the small matte black head of the established wood effigy between pine trunks. Preserve the exact featureless head and two minute dull glints. Move closer for a tightly framed night photograph with rough bark at the edges. The head remains almost entirely black, with a little subdued cold edge light. Only that shadow shape and nearby tree bark are visible.'),
        64: (['original-64'],general+' Preserve all the existing towering thin wooden effigies, their long branch limbs and small featureless black void heads. Keep the original empty forest ground and existing dense rows of trees.'),
        65: (['original-65'],general+' Also remove the bright nearby bonfire entirely, replacing it with unlit dense pine trunks. Keep the established tall thin wooden effigy and its raised branch arm in the same pointing pose. The pointing hand is entirely irregular dead wood with one slender twig extended; all its surfaces are contiguous bark and natural splinters. Background stays dark, with no nearby warm light.'),
    }
    plan['edit_references']=registry
    for index,(refs,prompt) in tasks.items():
        plan['shots'][index].update(refs=refs,prompt=prompt,engine='klein')
    # Previously generated one-tent night campsite is better than the two-tent repair.
    plan['shots'][68]=dict(full['shots'][68])
    for key in ('image','generation'):plan['shots'][68].pop(key,None)
    return sorted(tasks)
