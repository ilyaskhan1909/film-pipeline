"""Bind actual contact/native observations to exact selected delivery hashes."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
EXCLUDED={2,21,26,31,55,61,65,67}
NOTES={
  0:'Single green tent and distant lake geography; opening establishes location.',
  3:'Small anonymous swimmers; no identity-critical close face.',
  15:'Mark in cobalt shirt, restrained campfire reaction; native face/hand checked.',
  19:'Same Mark face and shirt, stronger tension; native face checked.',
  20:'Chloe in charcoal, straight brown hair; native reaction checked.',
  37:'Jess in olive with curly hair; native face and folded arms checked.',
  39:'Exactly two women, established Chloe/Jess designs; native pair checked.',
  41:'Established Chloe, readable campfire reaction; native face checked.',
  42:'Controlled Z-Image selection: lit leaves retain texture, empty foreground.',
  44:'Reference edit preserves the night path, removes foreground device and air cone.',
  47:'Controlled Klein selection: side-view fallen torch, lens and beam face the same direction.',
  48:'Reference edit preserves massive roots and the fallen torch, no white ground blob.',
  51:'Established burlap doll holds a separate loose blue scrap between tan cloth mittens.',
  52:'Reference macro preserves button eyes and cross-stitch mouth of shot 051.',
  53:'Closed cloth mittens, no exposed skin or fingernails; loose frayed blue scrap.',
  54:'Reference macro shows free blue cloth edges between closed tan cloth hands, not a stitched patch.',
  56:'Reference edit preserves cold night bark and path; no foreground torch or sunshaft.',
  60:'Long bare-wood figures preserved; foreground torch removed, no skull-face redesign.',
  62:'One established doll and one irregular wooden hand; no stacked heads or human skin.',
  63:'Deliberately stylized dark effigy head between bark, not a new human face.',
  64:'Long wooden bodies and empty textured ground preserved; no puddle or ordinary-tree substitution.',
  66:'Warm camp glow remains small and distant; no foreground torch.',
  68:'Original one-tent night camp retained instead of two-tent replacement.',
  69:'Two empty camp chairs beside embers; no duplicated tent.',
  70:'Dark lake and isolated ember flecks provide a restrained final hold.',
}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('assets',type=Path)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    manifest=json.loads((args.assets/'production_manifest.json').read_text(encoding='utf-8'))
    assert {s['index'] for s in manifest['shots']}==set(range(71))-EXCLUDED
    observed={}
    for stage in ('full','repair','focus'):
        folder=ROOT/'outputs/first-film'/stage/'assets'
        old=json.loads((folder/'production_manifest.json').read_text(encoding='utf-8'))
        for shot in old['shots']:
            digest=hashlib.sha256((folder/shot['image']).read_bytes()).hexdigest()
            assert digest==shot['generation']['sha256']
            observed[(shot['index'],digest)]=stage
    decisions=[]
    for shot in manifest['shots']:
        digest=hashlib.sha256((args.assets/shot['image']).read_bytes()).hexdigest()
        assert digest==shot['generation']['sha256']
        assert (shot['index'],digest) in observed,'New unviewed pixels cannot inherit an old decision.'
        note=NOTES.get(shot['index'])
        if note is None:
            note=('Contact review: established actor/camp reaction, no obvious duplicate person or identity break.'
                  if shot['refs'] else
                  'Contact review: readable environment/object insert, no unwanted extra camp objects or overt malformed detail.')
        decisions.append({'id':shot['id'],'sha256':digest,'decision':'accepted_for_this_edit',
                          'observed_source':observed[(shot['index'],digest)],'note':note})
    report={'source_run_id':manifest['run_id'],'shots':decisions,
      'review_method':'Source contact sheets inspected; selected actor, doll, torch and effigy details inspected at native resolution. Current delivery pixels are matched by SHA256.',
      'excluded_indices':sorted(EXCLUDED),'motion_generation':False,
      'limitations':['Selection approval is specific to this narrated illustrated-horror edit, not a universal model-quality score.',
                     'Wooden effigies are intentionally stylized; montage does not show genuine actor motion.',
                     'Continuous film viewing and voice-acting listening approval are not claimed.'],
      'continuous_viewing_approval':False,'listening_approval':False}
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'selected_images':len(decisions),'excluded':sorted(EXCLUDED)}),flush=True)

if __name__=='__main__':main()
