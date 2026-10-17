"""Verify comparison exports without interpreting execution as visual approval."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from PIL import Image,ImageDraw


def main():
    p=argparse.ArgumentParser()
    p.add_argument('archive',type=Path)
    p.add_argument('--directory',type=Path,required=True)
    args=p.parse_args()
    root=args.directory.resolve()
    assert not root.exists(),'Extract into a new directory.'
    with zipfile.ZipFile(args.archive) as z:
        assert z.testzip() is None
        names=z.namelist()
        assert len(names)==len(set(names))
        assert sum(f.file_size for f in z.infolist())<500_000_000
        for f in z.infolist():
            assert (root/f.filename).resolve().is_relative_to(root)
            assert (f.external_attr>>16)&0o170000!=0o120000,'No symlinks.'
        root.mkdir(parents=True)
        z.extractall(root)
    hashes=json.loads((root/'checksums.json').read_text(encoding='utf-8'))
    for name,digest in hashes.items():
        file=(root/name).resolve()
        assert file.is_relative_to(root)
        assert hashlib.sha256(file.read_bytes()).hexdigest()==digest,name
    report=json.loads((root/'control_report.json').read_text(encoding='utf-8'))
    tasks=report['tasks']
    sheet=Image.new('RGB',(1600,480*len(tasks)),(18,22,21))
    draw=ImageDraw.Draw(sheet)
    for row,task in enumerate(tasks):
        seeds=[]
        for column,engine in enumerate(('klein','zimage')):
            file=root/'comparisons/control'/f'{engine}-{task["id"]}.png'
            meta=json.loads(file.with_suffix('.json').read_text(encoding='utf-8'))
            assert meta['sha256']==hashlib.sha256(file.read_bytes()).hexdigest()
            assert meta['prompt']==task['prompt'] and not meta['refs']
            seeds.append(meta['seed'])
            with Image.open(file) as im:
                im.load()
                assert im.size==(1536,864)
                im=im.convert('RGB');im.thumbnail((794,447))
                sheet.paste(im,(column*800,row*480))
            draw.text((column*800+8,row*480+455),f'{engine}  {task["id"]}  {meta["seconds"]}s',fill=(240,231,216))
        assert len(set(seeds))==1
    output=root.parent/'comparison.jpg'
    sheet.save(output,quality=96)
    validation={'run_id':report['run_id'],'checksums_verified':len(hashes),'images':2*len(tasks),
        'same_prompt_seed_size_confirmed':True,'quality_approval':False,'contact_sheet':str(output)}
    (root.parent/'validation.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
    print(json.dumps(validation),flush=True)


if __name__=='__main__':main()
