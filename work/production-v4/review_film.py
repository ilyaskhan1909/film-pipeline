"""Extract real exported shot midpoints for visual QA, never mark auto-approved."""
import argparse
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageStat

ROOT=Path(__file__).resolve().parents[2]
FFMPEG=ROOT/'work/ffmpeg-full/ffmpeg.exe'

def main():
    p=argparse.ArgumentParser()
    p.add_argument('video',type=Path)
    p.add_argument('--timeline',type=Path,required=True)
    p.add_argument('--directory',type=Path,required=True)
    args=p.parse_args()
    timeline=json.loads(args.timeline.read_text(encoding='utf-8'))
    points=[('title',36)]
    points += [(shot['id'],shot['start_frame']+shot['frames']//2)
               for beat in timeline['beats'] for shot in beat['shots']]
    points.append(('closing-fade',timeline['frames']-12))
    args.directory.mkdir(parents=True,exist_ok=True)
    frames=[]
    for i,(label,frame) in enumerate(points):
        file=args.directory/f'{i:03}-{label}.jpg'
        result=subprocess.run([str(FFMPEG),'-hide_banner','-nostdin','-y','-v','error',
            '-ss',f'{frame/timeline["fps"]:.6f}','-i',str(args.video),
            '-frames:v','1','-q:v','2',str(file)],capture_output=True,text=True)
        assert result.returncode==0 and file.is_file(),result.stderr[-1000:]
        with Image.open(file) as image:
            assert image.size==(1920,1080)
            deviation=ImageStat.Stat(image.convert('L')).stddev[0]
        frames.append({'file':file.name,'shot':label,'frame':frame,
                       'seconds':frame/timeline['fps'],'luma_stddev':round(deviation,3)})
    contacts=[]
    for start in range(0,len(frames),20):
        subset=frames[start:start+20]
        sheet=Image.new('RGB',(1600,257*((len(subset)+3)//4)),(15,20,18))
        draw=ImageDraw.Draw(sheet)
        for pos,item in enumerate(subset):
            x,y=(pos%4)*400,(pos//4)*257
            with Image.open(args.directory/item['file']) as image:
                image.thumbnail((400,225));sheet.paste(image,(x,y))
            draw.text((x+7,y+230),f'{item["shot"]}  {item["seconds"]:.2f}s',fill='white')
        target=args.directory/f'film-contact-{start//20:02}.jpg'
        sheet.save(target,quality=92);contacts.append(str(target.resolve()))
    report={'source_run_id':timeline['source_run_id'],'video':str(args.video.resolve()),
            'frames':frames,'contacts':contacts,'continuous_viewing_approval':False,
            'status':'exported_frames_require_visual_inspection'}
    (args.directory/'frame-review.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'samples':len(frames),'contact_sheets':contacts}),flush=True)

if __name__=='__main__':main()
