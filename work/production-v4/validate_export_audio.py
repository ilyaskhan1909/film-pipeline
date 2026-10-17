"""Compare decoded complete export with master in chunks, no listening claim."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
import numpy as np
from scipy.io import wavfile

ROOT=Path(__file__).resolve().parents[2]
FFMPEG=ROOT/'work/ffmpeg-full/ffmpeg.exe'

def main():
    p=argparse.ArgumentParser()
    p.add_argument('video',type=Path)
    p.add_argument('--master',type=Path,required=True)
    p.add_argument('--decoded',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    result=subprocess.run([str(FFMPEG),'-hide_banner','-nostdin','-v','error','-y',
        '-i',str(args.video),'-vn','-ar','48000','-ac','2','-c:a','pcm_f32le',str(args.decoded)],
        capture_output=True,text=True)
    assert result.returncode==0,result.stderr[-1000:]
    count=0;sx=sy=sxx=syy=sxy=0.0
    rate,original=wavfile.read(args.master)
    decoded_rate,exported=wavfile.read(args.decoded)
    assert rate==decoded_rate==48000
    assert original.ndim==exported.ndim==2 and original.shape[1]==exported.shape[1]==2
    original_frames,exported_frames=len(original),len(exported)
    assert abs(original_frames-exported_frames)<=2048
    def scale(values):
        # SciPy reads PCM24 left-justified in int32 and IEEE-float WAV natively.
        return float(2**(np.iinfo(values.dtype).bits-1)) if np.issubdtype(values.dtype,np.integer) else 1.0
    original_scale,exported_scale=scale(original),scale(exported)
    for offset in range(0,min(original_frames,exported_frames),65536):
        stop=min(offset+65536,original_frames,exported_frames)
        x=original[offset:stop].astype(np.float64).ravel()/original_scale
        y=exported[offset:stop].astype(np.float64).ravel()/exported_scale
        count+=len(x);sx+=float(x.sum());sy+=float(y.sum())
        sxx+=float(np.dot(x,x));syy+=float(np.dot(y,y));sxy+=float(np.dot(x,y))
    correlation=(sxy-sx*sy/count)/np.sqrt((sxx-sx*sx/count)*(syy-sy*sy/count))
    ratio=np.sqrt(syy/sxx)
    assert correlation>.98 and .97<ratio<1.03,'Export differs from the intended master.'
    report={'master_sha256':hashlib.sha256(args.master.read_bytes()).hexdigest(),
       'complete_master_comparison':True,'master_frames':original_frames,'decoded_frames':exported_frames,
       'samples_compared':count,'correlation':float(correlation),'rms_ratio':float(ratio),
       'master_not_doubled':True,'listening_approval':False}
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)

if __name__=='__main__':main()
