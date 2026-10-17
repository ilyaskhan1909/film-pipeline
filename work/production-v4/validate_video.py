"""Technical export verification; not a claim of continuous audiovisual viewing."""
import argparse
import json
import re
import subprocess
import struct
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
FFMPEG=ROOT/'work/ffmpeg-full/ffmpeg.exe'
FFPROBE=ROOT/'work/smoke-scratch/node/remotion-c57941070451/node_modules/@remotion/compositor-win32-x64-msvc/ffprobe.exe'


def run(binary,args):
    result=subprocess.run([str(binary),*args],capture_output=True,text=True,encoding='utf-8',errors='replace')
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:])
    return result

def atom_order(file):
    atoms=[]
    with file.open('rb') as stream:
        total=file.stat().st_size
        while stream.tell()<total:
            position=stream.tell()
            header=stream.read(8)
            assert len(header)==8,'Incomplete MP4 atom.'
            size,kind=struct.unpack('>I4s',header)
            header_size=8
            if size==1:
                size=struct.unpack('>Q',stream.read(8))[0];header_size=16
            if size==0:size=total-position
            assert header_size<=size<=total-position
            atoms.append(kind.decode('ascii',errors='replace'))
            stream.seek(position+size)
    return atoms


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('video',type=Path)
    parser.add_argument('--timeline',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    timeline=json.loads(args.timeline.read_text(encoding='utf-8'))
    probe=json.loads(run(FFPROBE,['-v','error','-show_streams','-show_format','-of','json',str(args.video)]).stdout)
    videos=[s for s in probe['streams'] if s['codec_type']=='video']
    audios=[s for s in probe['streams'] if s['codec_type']=='audio']
    assert len(videos)==len(audios)==1
    v,a=videos[0],audios[0]
    assert (v['width'],v['height'],v['codec_name'],v['pix_fmt'])==(1920,1080,'h264','yuv420p')
    assert v['avg_frame_rate']=='24/1' and int(v['nb_frames'])==timeline['frames']
    assert v.get('color_space')==v.get('color_primaries')==v.get('color_transfer')=='bt709'
    assert (a['codec_name'],int(a['sample_rate']),a['channels'])==('aac',48000,2)
    assert abs(float(v['duration'])-timeline['seconds'])<1/24
    assert abs(float(a['duration'])-timeline['seconds'])<.09
    atoms=atom_order(args.video)
    assert atoms.index('moov')<atoms.index('mdat'),'Progressive download metadata is not at the front.'
    decoded=run(FFMPEG,['-hide_banner','-nostdin','-v','error','-xerror','-i',str(args.video),'-f','null','NUL'])
    assert not decoded.stderr.strip(),decoded.stderr[:1000]
    measured=run(FFMPEG,['-hide_banner','-nostdin','-i',str(args.video),'-af',
                         'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json','-vn','-f','null','NUL']).stderr
    loudness=json.loads(re.findall(r'\{[^{}]+\}',measured)[-1])
    assert float(loudness['input_tp'])<=-.9,'AAC true-peak overshoot requires correction.'
    assert abs(float(loudness['input_i'])+16)<1.0,'Unexpected exported loudness.'
    report={'source_run_id':timeline['source_run_id'],'video':str(args.video.resolve()),
            'sha256':hashlib.sha256(args.video.read_bytes()).hexdigest(),'bytes':args.video.stat().st_size,
            'seconds':timeline['seconds'],'frames':timeline['frames'],'fps':24,
            'full_file_decode_passed':True,'video_stream':v,'audio_stream':a,
            'mp4_atom_order':atoms,'fast_start':True,
            'encoded_audio_measured':loudness,'continuous_viewing_approval':False,
            'listening_approval':False,'editorial_flags':timeline['review_flags'],
            'status':'technical_checks_passed_editorial_review_separate'}
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('seconds','frames','bytes','full_file_decode_passed','status')}),flush=True)


if __name__=='__main__':
    main()
