"""Synthetic timeline fixture to test editing wiring, NOT generated film assets."""
import ast
import argparse
import json
import shutil
import subprocess
from pathlib import Path

import nbformat
from scipy.io import wavfile
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
EDIT=ROOT/'outputs/first-film/edit/remotion'
HERE=EDIT/'test-contract'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check-render',action='store_true')
    args=parser.parse_args()
    if args.check_render:
        rate,decoded=wavfile.read(HERE/'wiring-decoded.wav')
        master_rate,master=wavfile.read(HERE/'public/sound/master.wav')
        assert rate==master_rate==24000
        n=min(len(decoded),round(6*rate))
        actual=decoded[:n,0].astype(np.float32)
        expected=master[:n,0].astype(np.float32)
        ratio=float(np.sqrt(np.mean(actual**2))/np.sqrt(np.mean(expected**2)))
        correlation=float(np.corrcoef(actual,expected)[0,1])
        assert .9<ratio<1.1 and correlation>.95,(ratio,correlation)
        report={'synthetic_fixture_only':True,'master_not_doubled':True,
                'rms_ratio':ratio,'correlation':correlation,'quality_approval':False}
        (HERE/'wiring-validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report),flush=True)
        return
    nb=nbformat.read(ROOT/'outputs/videogenerator-v4-production-FULL.ipynb',as_version=4)
    plan=next(ast.literal_eval(node.value) for node in ast.parse(nb.cells[1].source).body
              if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='PLAN')
    assets=HERE/'fixture'
    assets.mkdir(parents=True,exist_ok=True)
    shot_file=ROOT/'outputs/first-film/refinement/assets/images/shot-000.png'
    audio=ROOT/'outputs/first-film/pilot/assets/audio/s0000.wav'
    rate,data=wavfile.read(audio)
    duration=len(data)/rate
    scenes,heard=[],[]
    for segment in plan['segments']:
        scenes.append(dict(segment,audio='sample.wav',audio_duration=duration))
        written=segment['text'].split()
        words=[{'text':w,'start':i*duration/len(written),'end':(i+1)*duration/len(written)} for i,w in enumerate(written)]
        heard.append({'index':segment['index'],'words':words,'word_errors':0,'differences':[]})
    manifest={'scope':'full','run_id':'SYNTHETIC_EDIT_CONTRACT_ONLY','failures':[],
              'scenes':scenes,'shots':[dict(s,image='sample.png') for s in plan['shots']]}
    shutil.copy2(shot_file,assets/'sample.png')
    shutil.copy2(audio,assets/'sample.wav')
    (assets/'production_manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    review=HERE/'synthetic-speech.json'
    review.write_text(json.dumps({'run_id':manifest['run_id'],'scenes':heard,'listening_approval':False}),encoding='utf-8')
    subprocess.run(['python','-X','utf8',str(ROOT/'work/production-v4/prepare_edit.py'),str(assets),
                    '--speech-review',str(review),'--directory',str(HERE),'--subtitles',str(HERE/'synthetic.en.srt')],check=True)
    for name in ('CinematicShot','FilmTitle','DryNarration','FilmEnding','FinalFilm'):
        shutil.copy2(EDIT/'src'/(name+'.tsx'),HERE/'src'/(name+'.tsx'))
    shutil.copy2(EDIT/'public/title.webm',HERE/'public/title.webm')
    # Short real audio excerpt only, offset by the real opening breath.
    sound=HERE/'public/sound'
    sound.mkdir(exist_ok=True)
    stereo=np.column_stack((data,data)).astype(np.int16)
    wavfile.write(sound/'master.wav',rate,np.concatenate((np.zeros((round(1.5*rate),2),np.int16),stereo)))
    timeline=json.loads((HERE/'timeline.json').read_text(encoding='utf-8'))
    assert not timeline['review_flags'],timeline['review_flags']
    assert len(timeline['beats'])==26
    assert sum(len(b['shots']) for b in timeline['beats'])==73
    assert len({s['id'] for b in timeline['beats'] for s in b['shots']})==70
    print('SYNTHETIC CONTRACT GENERATED; no image, voice, timing or film-quality approval.',flush=True)


if __name__=='__main__':
    main()
