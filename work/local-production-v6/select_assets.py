"""Explicit reviewed selections only; never touch the checkpoint or upload candidates."""
import hashlib
import json
import re
import shutil
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/local-production-v6'
PUBLIC=OUT/'edit/remotion/public/assets'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(selection,report):
    if not re.fullmatch(r'shot-[0-9]{3}',selection['id']):
        raise ValueError('Unsafe shot identifier.')
    if selection['decision']!='select_for_workprint':
        raise ValueError('Only explicit workprint selections can be installed.')
    if selection['id']!=report['id'] or selection['sha256']!=report['sha256']:
        raise ValueError('Selection and candidate provenance do not match.')
    if not selection.get('review_notes') or selection.get('user_approved',False):
        raise ValueError('Review notes required; do not invent user approval.')
    return True


def main():
    manifest=json.loads((OUT/'editorial-selection.json').read_text(encoding='utf-8'))
    installed=[]
    selected_ids=set()
    for selection in manifest['candidates']:
        if selection['decision']!='select_for_workprint':
            continue
        report_path=(OUT/'assets'/selection['report']).resolve()
        if report_path.parent!=(OUT/'assets').resolve():
            raise ValueError('Candidate report is outside this production folder.')
        report=json.loads(report_path.read_text(encoding='utf-8'))
        validate(selection,report)
        if selection['id'] in selected_ids:
            raise ValueError('More than one selected candidate for the same shot.')
        selected_ids.add(selection['id'])
        image=Path(report['image']).resolve()
        if image.parent!=(OUT/'assets').resolve() or digest(image)!=selection['sha256']:
            raise ValueError('Candidate bytes changed or path is out of scope.')
        with Image.open(image) as im:
            if im.size!=(1536,864):
                raise ValueError('Workprint requires native 16:9 candidates.')
        original=ROOT/'outputs/first-film/curated/assets/images'/f'{selection["id"]}.png'
        if digest(original)!=report['job']['references'][0]['sha256']:
            raise ValueError('Original no longer matches the reviewed input.')
        destination=PUBLIC/f'{selection["id"]}.png'
        shutil.copy2(image,destination)
        installed.append({'id':selection['id'],'sha256':digest(destination),
                          'candidate':str(image),'original_sha256':digest(original)})
    report={'installed':installed,'original_modified':False,'user_approved':False,
            'production_approved':False,'native_i2v':False,'automatic_upload':False}
    (OUT/'edit/asset-installation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('INSTALLED',len(installed),'reviewed images into the separate workprint.')


if __name__=='__main__':
    main()
