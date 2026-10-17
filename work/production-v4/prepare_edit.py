"""Freeze an editable film timeline from verified assets and speech timings."""
import argparse
import json
import math
import re
import shutil
import difflib
import textwrap
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FPS = 24
# Cuts follow the actual spoken story, not equal-duration slide allocation.
ANCHORS = {
    0:[None,'The water was','We swam','we grilled','we told ghost'],
    1:[None,'That feeling'],
    2:[None,'The distant','It was a peaceful sound'],
    3:[None],
    4:[None,'It was close','So close'],
    5:[None,'he said poking'],
    6:[None,'A few minutes later','We all went silent'],
    7:[None],
    8:[None,'Probably just weird'],
    9:[None,'We spent the next hour','One from the north','Then another from the east'],
    10:[None,'I have had enough'],
    11:[None,'We watched','until the forest'],
    12:[None,'The silence that fell','Ten minutes'],
    13:[None,'though her voice'],
    14:[None,'you get in the car'],
    15:[None,'I grabbed my own','the trees forming','The air was cold'],
    16:[None,'Only the soft crunch'],
    17:[None,'I found Mark’s flashlight','the gnarled roots','But there was no sign'],
    18:[None],
    19:[None,'two mismatched black buttons','It was holding'],
    20:[None],
    21:[None,'I turned to run','But as I spun around'],
    22:[None],
    23:[None,'Their shapes were indistinct','I could not make out','And I saw that each'],
    24:[None,'One of the figures','not at me'],
    25:[None,'It was immediately followed','It was a sound'],
}
ORDER = {0:[0,1,3,4,5],4:[14,36,33],7:[20],9:[27,39,24,25],11:[30,32,33],
         16:[46,45],17:[46,47,48,49],20:[54],23:[60,64,63,62],24:[63,64,66]}
PAUSES = {0:.65,1:.8,2:.8,3:.7,4:.75,5:.5,6:.65,7:.5,8:.55,9:.75,10:.4,11:.8,
          12:1.0,13:.5,14:.5,15:.7,16:.7,17:.8,18:.5,19:.6,20:.9,21:.4,22:.65,23:.9,24:.8,25:3.0}
DISSOLVES = {1:8, 9:8}  # Day into dusk, then the elapsed-hour transition only.


def tokens(text):
    text = text.casefold().replace('’',"'").replace('‘',"'")
    # Match spelled-out contractions only for finding a cut, never for ASR scoring.
    text = text.replace("i've",'i have').replace("couldn't",'could not')
    return re.findall(r"[a-z]+(?:'[a-z]+)?|\d+",text)


def at_phrase(words,phrase):
    wanted = tokens(phrase)
    sequence = []
    for word in words:
        sequence.extend((part,word['start']) for part in tokens(word['text']))
    values = [s[0] for s in sequence]
    for i in range(len(values)-len(wanted)+1):
        if values[i:i+len(wanted)]==wanted:
            return sequence[i][1]
    return None


def script_timing(source,heard):
    """Preserve script spelling and punctuation; mismatches remain audit flags."""
    written = source.split()
    left = [(token,i) for i,word in enumerate(written) for token in tokens(word)]
    right = [(token,i) for i,word in enumerate(heard) for token in tokens(word['text'])]
    assignments = {}
    for op,a,b,c,d in difflib.SequenceMatcher(None,[x[0] for x in left],[x[0] for x in right],autojunk=False).get_opcodes():
        if op=='equal':
            pairs = zip(left[a:b],right[c:d])
        elif op=='replace' and b>a and d>c:
            pairs = ((left[i],right[c+min(d-c-1,int((i-a)*(d-c)/(b-a)))]) for i in range(a,b))
        else:
            continue
        for (_,i),(_,j) in pairs:
            assignments.setdefault(i,[]).append(heard[j])
    result = []
    for i,word in enumerate(written):
        if i in assignments:
            start = min(w['start'] for w in assignments[i])
            end = max(w['end'] for w in assignments[i])
        else:
            previous = result[-1]['end'] if result else 0
            following = next((min(w['start'] for w in assignments[j]) for j in range(i+1,len(written)) if j in assignments),previous+.1)
            start,end = previous,max(previous+.01,following)
        result.append({'text':word,'start':start,'end':end})
    return result


def subtitle_time(value):
    msec = round(value*1000)
    hours,msec = divmod(msec,3600000)
    minutes,msec = divmod(msec,60000)
    seconds,msec = divmod(msec,1000)
    return f'{hours:02}:{minutes:02}:{seconds:02},{msec:03}'


def readable_subtitles(cues,film_end):
    """Merge stranded short words within the same beat, without changing text."""
    merged=[]
    for start,end,text,beat in cues:
        flat=text.replace('\n',' ')
        if merged and end-start<.65 and merged[-1][3]==beat:
            previous=merged[-1]
            combined=previous[2].replace('\n',' ')+' '+flat
            wrapped=textwrap.wrap(combined,42)
            if len(wrapped)<=2 and end-previous[0]<=5.7:
                merged[-1]=(previous[0],end,'\n'.join(wrapped),beat)
                continue
        merged.append((start,end,text,beat))
    result=[]
    for i,(start,end,text,_) in enumerate(merged):
        latest=merged[i+1][0]-.04 if i+1<len(merged) else film_end-.1
        # Keep the measured onset. Only use a following speech-free gap for reading.
        end=max(end,min(latest,start+.9))
        result.append((start,end,text))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('assets',type=Path)
    parser.add_argument('--speech-review',type=Path,required=True)
    parser.add_argument('--directory',type=Path,default=ROOT/'outputs/first-film/edit/remotion')
    parser.add_argument('--subtitles',type=Path)
    parser.add_argument('--speech-adjudication',type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.assets/'production_manifest.json').read_text(encoding='utf-8'))
    assert manifest['scope']=='full', 'The complete edit requires the full narration and selected storyboard.'
    assert not any(f.get('required') for f in manifest['failures'])
    review = json.loads(args.speech_review.read_text(encoding='utf-8'))
    assert review['run_id']==manifest['run_id']
    speech = {s['index']:s for s in review['scenes']}
    assert len(speech)==26, 'Independent transcription is incomplete.'
    adjudicated={}
    if args.speech_adjudication:
        assessment=json.loads(args.speech_adjudication.read_text(encoding='utf-8'))
        assert assessment['run_id']==review['run_id']
        assert assessment['report_sha256']==hashlib.sha256(args.speech_review.read_bytes()).hexdigest()
        for decision in assessment['decisions']:
            assert decision['audio_sha256']==speech[decision['index']]['audio_sha256']
            assert decision['raw_differences']==speech[decision['index']]['differences']
            adjudicated[decision['index']]=decision
    folder = args.directory
    public = folder/'public/assets'
    scenes_dir = folder/'src/scenes'
    public.mkdir(parents=True,exist_ok=True)
    scenes_dir.mkdir(parents=True,exist_ok=True)
    for shot in manifest['shots']:
        assert shot['image'], shot['id']
        shutil.copy2(args.assets/shot['image'],public/(shot['id']+'.png'))
    scene_by_index = {s['index']:s for s in manifest['scenes']}
    shot_by_index = {s['index']:s for s in manifest['shots']}
    timeline,flags,subtitles = [],[],[]
    # Short natural breath before narration; title plays over the actual opening.
    current = 36
    root_imports,root_compositions,film_sequences,bridges = [],[],[],[]
    for beat in range(26):
        scene = scene_by_index[beat]
        voice = speech[beat]
        if voice['word_errors']:
            decision=adjudicated.get(beat)
            if not decision or decision['classification']!='text_form_equivalence':
                flags.append({'beat':beat,'issue':'ASR mismatch requires human listening','differences':voice['differences']})
        audio_frames = math.ceil(scene['audio_duration']*FPS)
        gap = round(PAUSES[beat]*FPS)
        frames = audio_frames+gap
        selected = [s['index'] for s in manifest['shots'] if s['beat']==beat]
        selected = ORDER.get(beat,selected)
        anchors = ANCHORS[beat]
        assert len(anchors)==len(selected),(beat,len(anchors),len(selected))
        starts = [0]
        for pos,anchor in enumerate(anchors[1:],1):
            seconds = at_phrase(voice['words'],anchor)
            if seconds is None:
                seconds = scene['audio_duration']*pos/len(selected)
                flags.append({'beat':beat,'anchor':anchor,'issue':'Cut anchor missing; proportional fallback needs review.'})
            starts.append(max(starts[-1]+12,min(audio_frames-12,round(seconds*FPS))))
        assert starts[-1]<frames
        ends = starts[1:]+[frames]
        name = f'Beat{beat:02d}'
        dissolve=DISSOLVES.get(beat,0)
        if dissolve:
            previous=timeline[-1]['shots'][-1]['id']
            bridges.append(f'    <Sequence name="Time transition {beat:02d}" from={{{current}}} durationInFrames={{{dissolve}}}><CinematicShot image="assets/{previous}.png" frames={{{dissolve}}} motion="hold" /></Sequence>')
        lines = ["import React from 'react';", "import {AbsoluteFill, Sequence} from 'remotion';",
                 "import {DryNarration} from '../DryNarration';", "import {CinematicShot} from '../CinematicShot';",
                 f'export const {name}: React.FC = () => (', '  <AbsoluteFill>']
        for pos,(index,start,end) in enumerate(zip(selected,starts,ends)):
            shot = shot_by_index[index]
            # Hard cuts intentionally preserve geography / reactions; no carousel wipes.
            lines += [f'    <Sequence name={{{json.dumps(shot["id"]+" — "+shot["lens"],ensure_ascii=False)}}} from={{{start}}} durationInFrames={{{end-start}}}>',
                      f'      <CinematicShot image="assets/{shot["id"]}.png" frames={{{end-start}}} motion="{shot["motion"]}" dissolve={{{dissolve if pos==0 else 0}}} />',
                      '    </Sequence>']
        audio_name = Path(scene['audio']).name
        shutil.copy2(args.assets/scene['audio'],public/audio_name)
        lines += [f'    <DryNarration name="Dry narration {beat:02d}" file="assets/{audio_name}" frames={{{audio_frames}}} />',
                  '  </AbsoluteFill>',');']
        (scenes_dir/(name+'.tsx')).write_text('\n'.join(lines)+'\n',encoding='utf-8')
        root_imports.append(f"import {{{name}}} from './scenes/{name}';")
        root_compositions.append(f'      <Composition id="{name}" component={{{name}}} durationInFrames={{{frames}}} fps={{24}} width={{1920}} height={{1080}} />')
        film_sequences.append(f'    <Sequence name="Beat {beat:02d}" from={{{current}}} durationInFrames={{{frames}}}><{name} /></Sequence>')
        timeline.append({'beat':beat,'start_frame':current,'frames':frames,'audio_frames':audio_frames,
                         'gap_frames':gap,'dry_audio':'assets/'+audio_name,
                         'shots':[{'id':shot_by_index[i]['id'],'start_frame':current+s,'frames':e-s,
                                   'anchor':a,'dissolve_frames':dissolve if j==0 else 0}
                                  for j,(i,s,e,a) in enumerate(zip(selected,starts,ends,anchors))]})
        # Original spelling/punctuation with independently measured timing; audit flags stay visible.
        block = []
        for word in script_timing(scene['text'],voice['words']):
            if not block: block_start = word['start']
            block.append(word)
            text = ' '.join(w['text'] for w in block)
            if len(text)>=65 or word['end']-block_start>=4.2 or text.endswith(('.', '?', '!')):
                subtitles.append((current/FPS+block_start,current/FPS+word['end'],'\n'.join(textwrap.wrap(text,42)),beat))
                block=[]
        if block:
            subtitles.append((current/FPS+block_start,current/FPS+block[-1]['end'],'\n'.join(textwrap.wrap(' '.join(w['text'] for w in block),42)),beat))
        current += frames
    # Opening image holds beneath the title; no black placeholder before story.
    film = ["import React from 'react';", "import {AbsoluteFill, Sequence} from 'remotion';",
            "import {CinematicShot} from './CinematicShot';", "import {FilmTitle} from './FilmTitle';",
            "import {FilmEnding} from './FilmEnding';"]+root_imports
    film += [f'export const FILM_FRAMES = {current};', 'export const Film: React.FC = () => (','  <AbsoluteFill style={{backgroundColor: "#101A17"}}> ',
             '    <Sequence name="Opening breath" from={0} durationInFrames={36}><CinematicShot image="assets/shot-000.png" frames={36} motion="hold" /></Sequence>']
    film += bridges+film_sequences
    film += ['    <Sequence name="HyperFrames film title" from={0} durationInFrames={144}><FilmTitle /></Sequence>',
             f'    <FilmEnding frames={{{current}}} />',
             '  </AbsoluteFill>',');']
    (folder/'src/Film.tsx').write_text('\n'.join(film)+'\n',encoding='utf-8')
    root = ["import React from 'react';", "import {Composition, Folder} from 'remotion';",
            "import {Film} from './Film';", "import {FinalFilm} from './FinalFilm';"]+root_imports
    root += ['export const RemotionRoot: React.FC = () => (','  <>',
             f'    <Composition id="Film" component={{FinalFilm}} durationInFrames={{{current}}} fps={{24}} width={{1920}} height={{1080}} />',
             f'    <Composition id="Dry-Film" component={{Film}} durationInFrames={{{current}}} fps={{24}} width={{1920}} height={{1080}} />',
             '    <Folder name="Story-beats">']+root_compositions+['    </Folder>','  </>',');']
    (folder/'src/Root.tsx').write_text('\n'.join(root)+'\n',encoding='utf-8')
    (folder/'src/index.tsx').write_text("import {registerRoot} from 'remotion';\nimport {RemotionRoot} from './Root';\nregisterRoot(RemotionRoot);\n",encoding='utf-8')
    edit = {'source_run_id':manifest['run_id'],'fps':FPS,'frames':current,'seconds':current/FPS,
            'beats':timeline,'review_flags':flags,'status':'editorial_review_required',
            'text_form_adjudications':list(adjudicated.values()),'listening_approval':False,
            'resolution_note':'Generated sources are 1536×864; delivery is gently scaled to 1920×1080, not native 1080 generation.'}
    (folder/'timeline.json').write_text(json.dumps(edit,ensure_ascii=False,indent=2),encoding='utf-8')
    subtitles=readable_subtitles(subtitles,current/FPS)
    srt = '\n\n'.join(f'{i}\n{subtitle_time(a)} --> {subtitle_time(b)}\n{text}' for i,(a,b,text) in enumerate(subtitles,1))+'\n'
    subtitle_file=args.subtitles or folder.parents[1]/'The_Last_Firework.en.srt'
    subtitle_file.write_text(srt,encoding='utf-8')
    (folder/'public/captions.en.srt').write_text(srt,encoding='utf-8')
    print(json.dumps({'folder':str(folder),'duration_seconds':current/FPS,'flags':flags},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
