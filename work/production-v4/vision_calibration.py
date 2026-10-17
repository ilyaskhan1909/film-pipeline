"""Record narrow observed usefulness, not an artificial all-purpose quality score."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def main():
    films=ROOT/'outputs/first-film'
    reports={name:json.loads((films/name/'vision-observations.json').read_text(encoding='utf-8')) for name in ('pilot','refinement')}
    assert reports['pilot']['revision']==reports['refinement']['revision']
    assert reports['pilot']['prompt_sha256']==reports['refinement']['prompt_sha256']
    expectations=[('pilot','shot-000','visible_tents',5),('refinement','shot-000','visible_tents',1),
                  ('pilot','shot-054','whole_doll_visible',True),('refinement','shot-054','whole_doll_visible',True),
                  ('pilot','shot-061','recognizable_human_faces',3),('refinement','shot-061','recognizable_human_faces',0),
                  ('pilot','shot-015','recognizable_human_faces',1)]
    checks=[]
    for collection,ident,feature,expected in expectations:
        item=next(r for r in reports[collection]['observations'] if Path(r['file']).stem==ident)
        assert hashlib.sha256(Path(item['file']).read_bytes()).hexdigest()==item['sha256']
        observed=item['observation'].get(feature)
        checks.append({'collection':collection,'shot':ident,'feature':feature,'manually_observed':expected,
                       'model_observed':observed,'matched':observed==expected,'image_sha256':item['sha256']})
    report={'model':reports['pilot']['model'],'revision':reports['pilot']['revision'],
            'prompt_sha256':reports['pilot']['prompt_sha256'],'free_local':True,'checks':checks,
            'usage':'Flag obvious structural mismatches for manual review, never approve image quality.',
            'known_failures':['Does not reliably detect human fingers inside the wooden hand in refinement shot-062.',
                'Treats intended wooden anatomy and a black head as possible anomalies.',
                'May invent fabric details; empty anomaly lists do not mean an image is clean.',
                'Framing labels differ between medium and closeup even on similar full-doll images.'],
            'quality_approval':False,'general_accuracy_claim':False}
    output=films/'vision-calibration.json'
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'report':str(output),'narrow_checks':len(checks),'matched':sum(c['matched'] for c in checks),
                      'automatic_quality_approval':False}),flush=True)


if __name__=='__main__':
    main()
