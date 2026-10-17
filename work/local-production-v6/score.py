"""Original quiet ambient piano/strings score; no samples, no paid music API."""
import json
import sys
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.ndimage import gaussian_filter1d

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'work/production-v4'))
from mix_sound import RATE, load, normalise, loudness
PROJECT=ROOT/'outputs/local-production-v6/edit/remotion'
SOUND=PROJECT/'public/sound'
STEMS=ROOT/'outputs/local-production-v6/audio-stems'


def note(canvas,midi,start,seconds,gain,pan,strings=False):
    first=round(start*RATE)
    count=min(round(seconds*RATE),len(canvas)-first)
    if count<=0:
        return
    time=np.arange(count,dtype=np.float32)/RATE
    frequency=440*2**((midi-69)/12)
    phase=2*np.pi*frequency*time
    if strings:
        envelope=np.sin(np.pi*np.minimum(time/seconds,1))**2
        waveform=np.sin(phase)+.13*np.sin(phase*2)+.035*np.sin(phase*3)
        waveform*=1+.012*np.sin(2*np.pi*.13*time)
    else:
        envelope=(1-np.exp(-time*75))*np.exp(-time/3.8)
        envelope*=np.minimum((seconds-time)/.7,1).clip(0,1)
        waveform=np.sin(phase)+.19*np.sin(phase*2+.06)+.06*np.sin(phase*3+.02)
        waveform+=.017*np.sin(phase*5)*np.exp(-time/1.1)
    signal=(waveform*envelope*gain).astype(np.float32)
    canvas[first:first+count,0]+=signal*np.sqrt((1-pan)/2)
    canvas[first:first+count,1]+=signal*np.sqrt((1+pan)/2)


def main():
    timeline=json.loads((PROJECT/'timeline.json').read_text())
    duration=timeline['seconds']
    count=round(duration*RATE)
    score=np.zeros((count,2),np.float32)
    rng=np.random.default_rng(20261005)
    stages=[(12,78,[48,55,59,64]),(78,319,[45,52,59,60]),
            (319,534,[50,57,60,64]),(534,671,[44,51,59,62]),
            (671,duration,[45,52,60,64])]
    events=[]
    for stage,(begin,end,chord) in enumerate(stages):
        for moment in np.arange(begin,end-1,17.5 if stage<3 else 13.4):
            selected=chord[(len(events)+stage)%len(chord)]
            pan=float(rng.uniform(-.28,.28))
            note(score,selected+12,float(moment),13,.009,pan)
            note(score,chord[(len(events)+1)%len(chord)]+12,float(moment+3.2),12,.004,-pan)
            if stage:
                note(score,chord[0],float(moment),26,.003,pan,strings=True)
            events.append({'seconds':round(float(moment),3),'midi':selected+12,'stage':stage})
    # Gentle original stereo reflections, not a reused sample or a short music loop.
    for seconds,gain in ((.31,.10),(.67,.075),(1.11,.045)):
        offset=round(seconds*RATE)
        score[offset:]+=score[:-offset,::-1].copy()*gain
    fade=round(2.0*RATE)
    score[-fade:]*=np.linspace(1,0,fade,dtype=np.float32)[:,None]
    STEMS.mkdir(parents=True,exist_ok=True)
    raw=STEMS/'music-original-raw.wav'
    wavfile.write(raw,RATE,score)
    del score
    normalise(raw,STEMS/'music-unducked.wav',-32)
    voice=load(STEMS/'narration.wav')
    if len(voice)!=count:
        raise RuntimeError('Narration duration differs from the immutable timeline.')
    bed=load(STEMS/'music-unducked.wav')
    if len(bed)!=count:
        raise RuntimeError('Score duration changed after normalization.')
    hop=4800
    rms=np.array([np.sqrt(np.mean(voice[i:i+hop]**2)) for i in range(0,count,hop)],dtype=np.float32)
    activity=(rms>.008).astype(np.float32)
    # Slow recovery makes short intra-sentence pauses stay quiet, avoiding audible pumping.
    activity=gaussian_filter1d(activity,3)
    gains=10**(-(activity*9)/20)
    for index,first in enumerate(range(0,count,hop)):
        last=min(count,first+hop)
        following=gains[min(index+1,len(gains)-1)]
        ramp=np.linspace(gains[index],following,last-first,dtype=np.float32)
        bed[first:last]*=ramp[:,None]
    # Preserve the intentional silence/reveal without abruptly cutting the music.
    silence=timeline['beats'][12]['start_frame']/24
    a,b=round((silence-2)*RATE),round((silence+8)*RATE)
    envelope=np.ones(b-a,np.float32)
    edge=round(2*RATE)
    envelope[:edge]=np.linspace(1,.25,edge)
    envelope[edge:-edge]=.25
    envelope[-edge:]=np.linspace(.25,1,edge)
    bed[a:b]*=envelope[:,None]
    wavfile.write(STEMS/'music-ducked.wav',RATE,bed)
    combined=voice+bed
    del voice,bed
    for name in ('atmosphere.wav','effects.wav'):
        stem=load(STEMS/name)
        if len(stem)!=count:
            raise RuntimeError('Original stem duration mismatch.')
        combined+=stem
        del stem
    if not np.isfinite(combined).all():
        raise RuntimeError('Non-finite mix.')
    peak=float(np.max(np.abs(combined)))
    wavfile.write(STEMS/'v6-pre-master.wav',RATE,combined)
    del combined
    normalise(STEMS/'v6-pre-master.wav',SOUND/'master.wav',-16)
    measured=loudness(SOUND/'master.wav',-16)
    report={'duration':duration,'rate':RATE,'channels':2,'original_score':True,
        'external_samples_used':False,'paid_api_used':False,'narration_regenerated':False,
        'music_target_lufs_before_duck':-32,'voice_duck_db':9,'pre_master_peak':peak,
        'events':events,'master_loudness':measured,'auditory_approved':False,
        'voice_identity_issue_resolved':False,'note':'Listening review is required; loudness is not a quality score.'}
    (PROJECT/'score-review.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='events'},indent=2))


if __name__=='__main__':
    main()
