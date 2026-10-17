"""Validate an actual asset archive and create a non-deliverable visual QA sheet."""
import argparse
import hashlib
import json
import math
import wave
import zipfile
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archive',type=Path)
    parser.add_argument('--directory',type=Path,required=True)
    args = parser.parse_args()
    root = args.directory.resolve()
    root.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.archive) as archive:
        assert archive.testzip() is None
        for member in archive.infolist():
            path = (root/member.filename).resolve()
            assert path.is_relative_to(root) and not path.exists(), 'Unsafe extraction or existing file'
        archive.extractall(root)
    expected = json.loads((root/'checksums.json').read_text(encoding='utf-8'))
    for name,digest in expected.items():
        file = (root/name).resolve()
        assert file.is_relative_to(root)
        assert hashlib.sha256(file.read_bytes()).hexdigest() == digest, name
    manifest = json.loads((root/'production_manifest.json').read_text(encoding='utf-8'))
    frames = []
    for shot in manifest['shots']:
        assert shot['image'], 'Missing shot '+shot['id']
        with Image.open(root/shot['image']) as im:
            im.load()
            assert list(im.size) == shot['generation']['size']
            pixels = np.asarray(im.convert('RGB'),dtype=np.float32)
            assert pixels.std()>1
            small = im.convert('L').resize((64,36))
            frames.append((shot,np.asarray(small,dtype=np.float32)))
    similar = []
    for i in range(len(frames)):
        for j in range(i+1,len(frames)):
            a,b=frames[i][1],frames[j][1]
            corr=float(np.corrcoef(a.reshape(-1),b.reshape(-1))[0,1])
            if corr>.93:
                similar.append({'a':frames[i][0]['id'],'b':frames[j][0]['id'],'correlation':corr})
    for scene in manifest['scenes']:
        with wave.open(str(root/scene['audio']),'rb') as wav:
            assert wav.getnchannels()==1 and wav.getsampwidth()==2
            assert abs(wav.getnframes()/wav.getframerate()-scene['audio_duration'])<.002
    paths = [(s['id'],root/s['image']) for s in manifest['shots']]
    paths += [('BASE candidate',p) for p in (root/'comparisons').glob('*.png')]
    paths += [('REF '+p.stem,p) for p in (root/'references').glob('*.png')]
    sheets = []
    for page in range(math.ceil(len(paths)/20)):
        group = paths[page*20:(page+1)*20]
        sheet = Image.new('RGB',(1600,math.ceil(len(group)/4)*257),(18,22,21))
        draw = ImageDraw.Draw(sheet)
        for index,(name,path) in enumerate(group):
            with Image.open(path) as im:
                im=im.convert('RGB'); im.thumbnail((396,223))
                x=(index%4)*400; y=(index//4)*257
                sheet.paste(im,(x+(396-im.width)//2,y))
                draw.text((x+8,y+230),name,fill=(240,231,216))
        output = root.parent/f'contact-{page:02d}.jpg'
        sheet.save(output,quality=95)
        sheets.append(str(output))
    report = {'scope':manifest['scope'],'shots':len(frames),'audio_segments':len(manifest['scenes']),
              'narration_seconds':manifest['narration_seconds'],'checksums_verified':len(expected),
              'similar_frames_for_review':similar,'contact_sheets':sheets,
              'editorial_status':'requires_visual_review_not_automatically_approved'}
    output=root.parent/'asset_validation.json'
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':
    main()
