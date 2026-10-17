"""Candidate integrity, sampled telemetry and before/after visual review boards."""
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/local-production-v6'


def main():
    candidates=[]
    for path in sorted((OUT/'assets').glob('*.json')):
        report=json.loads(path.read_text(encoding='utf-8'))
        image=Path(report['image'])
        if hashlib.sha256(image.read_bytes()).hexdigest()!=report['sha256']:
            raise ValueError('Candidate image changed: '+str(image))
        with Image.open(image) as im:
            if list(im.size)!=report['job']['size']:
                raise ValueError('Candidate dimensions changed.')
        samples=[]
        if report.get('telemetry'):
            samples=json.loads(Path(report['telemetry']).read_text())
        samples=[s for s in samples if 'devices' in s]
        candidates.append({'report':path.name,'id':report['id'],'profile':report['profile'],
            'revision':report['job'].get('prompt_revision',1),'seconds':report['seconds'],
            'size':report['job']['size'],'sha256':report['sha256'],
            'sampled_max_total_device_vram_gib':max((
                (d['vram_total']-d['vram_free'])/2**30 for s in samples for d in s['devices']),default=None),
            'sampled_min_container_ram_free_gib':min((s['ram_free']/2**30 for s in samples),default=None),
            'completed_real_inference':True})
    selections=json.loads((OUT/'editorial-selection.json').read_text(encoding='utf-8'))
    selected=[s for s in selections['candidates'] if s['decision']=='select_for_workprint']
    font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',22)
    for group in range(0,len(selected),4):
        rows=selected[group:group+4]
        board=Image.new('RGB',(1536,472*len(rows)),(16,20,22))
        draw=ImageDraw.Draw(board)
        for index,s in enumerate(rows):
            r=json.loads((OUT/'assets'/s['report']).read_text(encoding='utf-8'))
            files=[Path(r['job']['references'][0]['source']),Path(r['image'])]
            for column,file in enumerate(files):
                with Image.open(file) as im:
                    thumb=im.convert('RGB').resize((768,432),Image.Resampling.LANCZOS)
                    board.paste(thumb,(column*768,index*472+40))
                label=s['id']+(' | checkpoint' if column==0 else ' | local v6 selected candidate')
                draw.text((column*768+14,index*472+6),label,font=font,fill=(230,232,229))
        board.save(OUT/f'comparison-{group//4+1:02d}.jpg',quality=94)
    summary={'completed_candidates':len(candidates),'selected_for_workprint':len(selected),
        'candidates':candidates,'original_modified':False,'paid_api_used':False,
        'native_i2v_used':False,'user_approved':False,'production_approved':False,
        'telemetry_note':'Sampled every two seconds; overall device usage, not exact model-only peak.',
        'selection_note':'Visual inspection and explicit decisions; metrics never approve an image.'}
    (OUT/'local-generation-validation.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ('completed_candidates','selected_for_workprint','paid_api_used')}))


if __name__=='__main__':main()
