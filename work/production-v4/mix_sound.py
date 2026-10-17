"""Separate reproducible 48 kHz stems; no effects are added to dry QA probes."""
import argparse
import json
import re
import subprocess
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, resample_poly, sosfilt

ROOT = Path(__file__).resolve().parents[2]
RATE = 48000
FFMPEG = ROOT/'work/ffmpeg-full/ffmpeg.exe'


def call(args):
    result = subprocess.run([str(FFMPEG),'-hide_banner','-nostdin','-y']+args,
                            capture_output=True,text=True,encoding='utf-8',errors='replace')
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:])
    return result.stderr


def load(path):
    rate,data = wavfile.read(path)
    if data.dtype.kind=='i':
        data = data.astype(np.float32)/float(2**(data.dtype.itemsize*8-1))
    else:
        data = data.astype(np.float32)
    if data.ndim==1:
        data = np.column_stack((data,data))
    assert data.shape[1]==2 and np.isfinite(data).all()
    if rate!=RATE:
        from math import gcd
        common = gcd(rate,RATE)
        data = resample_poly(data,RATE//common,rate//common,axis=0).astype(np.float32)
    return data


def loudness(path,target):
    stderr = call(['-i',str(path),'-af',f'loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json','-f','null','NUL'])
    return json.loads(re.findall(r'\{[^{}]+\}',stderr)[-1])


def normalise(source,dest,target):
    measured = loudness(source,target)
    chain = (f'loudnorm=I={target}:TP=-1.5:LRA=11:'
        f'measured_I={measured["input_i"]}:measured_TP={measured["input_tp"]}:'
        f'measured_LRA={measured["input_lra"]}:measured_thresh={measured["input_thresh"]}:'
        f'offset={measured["target_offset"]}:linear=true:print_format=json')
    call(['-i',str(source),'-af',chain,'-ar',str(RATE),'-ac','2','-c:a','pcm_s24le',str(dest)])
    return measured


def add(canvas,data,seconds,gain=1.0):
    start = max(0,round(seconds*RATE))
    count = min(len(data),len(canvas)-start)
    if count>0:
        canvas[start:start+count] += data[:count]*gain


def filtered_noise(rng,seconds,low,high):
    data = rng.standard_normal(round(seconds*RATE)).astype(np.float32)
    data = sosfilt(butter(2,[low,high],btype='bandpass',fs=RATE,output='sos'),data).astype(np.float32)
    return data/(float(np.max(np.abs(data)))+1e-8)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,default=ROOT/'outputs/first-film/edit/remotion')
    parser.add_argument('--speech-review',type=Path,required=True)
    args = parser.parse_args()
    timeline = json.loads((args.directory/'timeline.json').read_text(encoding='utf-8'))
    review = json.loads(args.speech_review.read_text(encoding='utf-8'))
    assert timeline['source_run_id']==review['run_id']
    duration = timeline['seconds']
    count = round(duration*RATE)
    sound = args.directory/'public/sound'
    sound.mkdir(parents=True,exist_ok=True)
    voice = np.zeros((count,2),np.float32)
    atmosphere = np.zeros_like(voice)
    effects = np.zeros_like(voice)
    beats = {b['beat']:b for b in timeline['beats']}
    rng = np.random.default_rng(20180704)
    notes = []
    for beat in timeline['beats']:
        add(voice,load(args.directory/'public'/beat['dry_audio']),beat['start_frame']/timeline['fps'])
    wavfile.write(sound/'narration-raw48.wav',RATE,voice)
    voice_measure = normalise(sound/'narration-raw48.wav',sound/'narration.wav',-18)

    # One real, non-looped field-recording excerpt establishes daytime only.
    day_end = (beats[0]['start_frame']+beats[0]['frames'])/24
    forest = sound/'forest-nille.ogg'
    if forest.exists():
        excerpt = sound/'forest-day.wav'
        call(['-i',str(forest),'-t',str(day_end),'-af',
            f'highpass=f=80,lowpass=f=6000,afade=t=in:d=2,afade=t=out:st={max(2,day_end-4)}:d=4',
            '-ar',str(RATE),'-ac','2','-c:a','pcm_f32le',str(excerpt)])
        recording = load(excerpt)
        rms = float(np.sqrt(np.mean(recording**2)))
        add(atmosphere,recording,0,10**(-38/20)/max(rms,1e-8))
        notes.append('Daytime: one non-looped nille forest excerpt; no daytime birds under night scenes.')

    # Original procedural textures, not falsely described as field recordings.
    night_start = beats[2]['start_frame']/24
    quiet_start = beats[12]['start_frame']/24
    for moment in np.arange(night_start,quiet_start-1,1.17):
        seconds = .20+rng.uniform(0,.12)
        t = np.arange(round(seconds*RATE))/RATE
        envelope = np.sin(np.pi*np.minimum(t/seconds,1))**2
        carrier = np.sin(2*np.pi*(4050+rng.uniform(-90,90))*t)
        chirp = (carrier*envelope*.0014).astype(np.float32)
        stereo = np.column_stack((chirp*.65,chirp))
        add(atmosphere,stereo,float(moment))
    notes.append('Very quiet synthetic insect texture stops when Mark enters the woods; no repeated music loop.')

    for moment in np.arange(beats[1]['start_frame']/24,quiet_start,.75):
        if rng.random()<.48:
            tick = filtered_noise(rng,.085,1100,9500)
            t = np.arange(len(tick))/RATE
            tick *= np.exp(-t*55)*.005
            add(atmosphere,np.column_stack((tick,tick*.78)),float(moment+rng.uniform(0,.35)))
    notes.append('Sparse original fire ticks, removed during the deliberate silence beat.')

    cue_list = []
    for scene in review['scenes']:
        for word in scene['words']:
            if re.sub(r'[^a-z]','',word['text'].casefold())!='crack':
                continue
            moment = beats[scene['index']]['start_frame']/24+word['start']+.10
            snap = filtered_noise(rng,.32,450,12000)
            t = np.arange(len(snap))/RATE
            snap *= np.exp(-t*42)*.095
            snap += (np.sin(2*np.pi*83*t)*np.exp(-t*22)*.035).astype(np.float32)
            pan = -.22 if len(cue_list)%2==0 else .22
            stereo = np.column_stack((snap*(1-pan),snap*(1+pan)))
            add(effects,stereo,moment)
            cue_list.append({'type':'original illustrative wood snap','seconds':round(moment,3),'beat':scene['index']})

    # Restrained tonal pressure appears only around the reveal, never the calm opening.
    pressure_start = beats[21]['start_frame']/24
    pressure_end = beats[25]['start_frame']/24
    t = np.arange(max(0,round((pressure_end-pressure_start)*RATE)))/RATE
    if len(t):
        envelope = np.minimum(t/15,1)*np.minimum((t[-1]-t)/3,1)
        tone = ((np.sin(2*np.pi*53*t)+.45*np.sin(2*np.pi*61.3*t))*envelope*.0018).astype(np.float32)
        add(atmosphere,np.column_stack((tone,tone*.85)),pressure_start)
    wavfile.write(sound/'atmosphere.wav',RATE,atmosphere)
    wavfile.write(sound/'effects.wav',RATE,effects)
    mix = load(sound/'narration.wav')[:count]+atmosphere+effects
    fade = np.linspace(1,0,min(count,round(1.5*RATE)),dtype=np.float32)
    mix[-len(fade):] *= fade[:,None]
    assert np.isfinite(mix).all()
    wavfile.write(sound/'mix-pre-master.wav',RATE,mix)
    mix_measure = normalise(sound/'mix-pre-master.wav',sound/'master.wav',-16)
    actual = loudness(sound/'master.wav',-16)
    report = {'source_run_id':timeline['source_run_id'],'rate':RATE,'channels':2,'duration':duration,'voice_before':voice_measure,
        'mix_before':mix_measure,'master_measured':actual,'cues':cue_list,'notes':notes,
        'auditory_approval':False,'warning':'Stems require listening; measured loudness alone is not sound-quality approval.'}
    (args.directory/'sound_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'master':str(sound/'master.wav'),'seconds':duration,
        'lufs':actual['input_i'],'true_peak_db':actual['input_tp'],'cues':len(cue_list)},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
