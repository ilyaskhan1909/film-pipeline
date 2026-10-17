"""Check source-preserving subtitle text, timing, line length and bounds."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def seconds(stamp):
    h,m,s,ms=map(int,re.split('[:,]',stamp))
    return h*3600+m*60+s+ms/1000


def main():
    p=argparse.ArgumentParser()
    p.add_argument('subtitles',type=Path)
    p.add_argument('--story',type=Path,required=True)
    p.add_argument('--timeline',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    text=args.subtitles.read_text(encoding='utf-8').strip()
    source=args.story.read_text(encoding='utf-8')
    timeline=json.loads(args.timeline.read_text(encoding='utf-8'))
    blocks=re.split(r'\n\s*\n',text)
    phrases=[];previous=0;warnings=[]
    for expected,block in enumerate(blocks,1):
        lines=block.splitlines()
        assert int(lines[0])==expected
        start,end=map(seconds,lines[1].split(' --> '))
        assert 0<=start<end<=timeline['seconds']
        assert start+0.002>=previous,(expected,start,previous)
        previous=end
        phrases.extend(lines[2:])
        if len(lines[2:])>2 or max(map(len,lines[2:]))>42:
            warnings.append({'cue':expected,'issue':'More than two lines or a long word.'})
        if end-start<.65:
            warnings.append({'cue':expected,'issue':'Short reading interval','seconds':round(end-start,3)})
    assert ' '.join(' '.join(phrases).split())==' '.join(source.split()),'Script text differs.'
    report={'source_run_id':timeline['source_run_id'],'source_text_preserved':True,'cues':len(blocks),
        'last_cue_end':previous,'film_seconds':timeline['seconds'],'warnings':warnings,
        'srt_sha256':hashlib.sha256(args.subtitles.read_bytes()).hexdigest(),
        'source_sha256':hashlib.sha256(args.story.read_bytes()).hexdigest(),'sync_listening_approval':False}
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
