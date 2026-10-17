"""Portable reviewed images/workflows, no weights, credentials or runtime folders."""
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/local-production-v6'


def main():
    selection=json.loads((OUT/'editorial-selection.json').read_text(encoding='utf-8'))
    members=[];references={}
    for item in selection['candidates']:
        if item['decision']!='select_for_workprint':continue
        report_path=OUT/'assets'/item['report']
        report=json.loads(report_path.read_text(encoding='utf-8'))
        image=Path(report['image'])
        members.extend([(image,f'images/{item["id"]}.png'),
                        (report_path,f'provenance/{report_path.name}')])
        workflow=OUT/'workflows'/f'{report_path.stem}-api.json'
        members.append((workflow,f'workflows/{workflow.name}'))
        for ref in report['job']['references']:
            members.append((ROOT/'local-comfy/data/input'/ref['image'],f'comfy-input/{ref["image"]}'))
    for name in ('RESEARCH.txt','RUN.txt','DELIVERY.txt','DELIVERY.json','video-validation.json',
                 'editorial-selection.json','local-generation-validation.json','vision-observations.json'):
        members.append((OUT/name,name))
    members.append((OUT/'export-review/inspection.json','inspection.json'))
    for file in (OUT/'research').glob('*LICENSE.txt'):
        members.append((file,'licenses/'+file.name))
    members.extend([(OUT/'research/model-lock.json','models/model-lock.json'),
        (OUT/'research/Comfy-Org--vae-text-encorder-for-flux-klein-4b--README.txt','licenses/Comfy-Org-card.txt')])
    by_name={name:path for path,name in members}
    target=OUT/'The_Last_Firework_v6_local_assets.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as bundle:
        for name,path in sorted(by_name.items()):bundle.write(path,name)
    with zipfile.ZipFile(target) as bundle:
        if bundle.testzip() is not None:raise RuntimeError('Asset archive CRC failed.')
    print('PACKAGED',target.name,len(by_name),'files',target.stat().st_size,'bytes')


if __name__=='__main__':main()
