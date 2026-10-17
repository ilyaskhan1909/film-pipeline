"""Independent offline transcription, word timing and waveform evidence."""
import argparse
import difflib
import json
import re
import hashlib
import wave
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio


def normalize(text):
    text = text.casefold().replace('’', "'").replace('‘', "'")
    ordinal = {'1st':'first','2nd':'second','3rd':'third','4th':'fourth'}
    return [ordinal.get(w,w) for w in re.findall(r"[a-z]+(?:'[a-z]+)?|\d+(?:st|nd|rd|th)?",text)]


def edits(left,right):
    rows = [list(range(len(right)+1))]
    for i,a in enumerate(left,1):
        row = [i]
        for j,b in enumerate(right,1):
            row.append(min(row[-1]+1,rows[-1][j]+1,rows[-1][j-1]+(a!=b)))
        rows.append(row)
    return rows[-1][-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory',type=Path)
    parser.add_argument('--cache',type=Path,required=True)
    args = parser.parse_args()
    manifest = json.loads((args.directory/'production_manifest.json').read_text(encoding='utf-8'))
    output = args.directory.parent/'speech_review.json'
    results = []
    if output.exists():
        old = json.loads(output.read_text(encoding='utf-8'))
        if old.get('run_id')==manifest['run_id']:
            audio_by_index={s['index']:args.directory/s['audio'] for s in manifest['scenes']}
            results = [r for r in old['scenes'] if r.get('audio_sha256')==hashlib.sha256(audio_by_index[r['index']].read_bytes()).hexdigest()]
    model = WhisperModel('large-v3-turbo',device='cpu',compute_type='int8',cpu_threads=8,
                         download_root=str(args.cache),local_files_only=True)
    for scene in manifest['scenes']:
        if any(r['index']==scene['index'] for r in results):
            continue
        audio = decode_audio(str(args.directory/scene['audio']),sampling_rate=16000)
        with wave.open(str(args.directory/scene['audio']),'rb') as wav:
            assert wav.getnchannels()==1 and wav.getsampwidth()==2
            pcm=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2')
            raw_peak=float(np.max(np.abs(pcm.astype(np.int32)))/32768)
            raw_clipped=int(np.count_nonzero((pcm==32767)|(pcm==-32768)))
        segments,info = model.transcribe(audio,language='en',beam_size=5,
            condition_on_previous_text=False,vad_filter=False,word_timestamps=True)
        found = list(segments)
        text = ' '.join(s.text.strip() for s in found)
        expected,observed = normalize(scene['text']),normalize(text)
        mistakes = edits(expected,observed)
        differences = [{'type':op,'expected':expected[a:b],'heard':observed[c:d]}
            for op,a,b,c,d in difflib.SequenceMatcher(None,expected,observed,autojunk=False).get_opcodes() if op!='equal']
        words = [{'text':w.word.strip(),'start':round(w.start,4),'end':round(w.end,4),
                  'probability':round(w.probability,4)} for s in found for w in (s.words or [])]
        native = scene.get('words',[])
        result = {'index':scene['index'],'expected':scene['text'],'transcript':text,
            'audio_sha256':hashlib.sha256((args.directory/scene['audio']).read_bytes()).hexdigest(),
            'duration':len(audio)/16000,'word_errors':mistakes,'expected_words':len(expected),
            'word_error_rate':mistakes/max(len(expected),1),'differences':differences,
            'words':words,'segments':[{'text':s.text.strip(),'start':s.start,'end':s.end} for s in found],
            'rms_dbfs':float(20*np.log10(np.sqrt(np.mean(audio**2))+1e-10)),
            'peak':float(np.max(np.abs(audio))),
            'clipped_samples':int(np.count_nonzero(np.abs(audio)>=.999)),
            'source_pcm_peak':raw_peak,'source_pcm_rail_samples':raw_clipped,
            'native_aligned_units':len(native),
            'native_unit_coverage':len(normalize(' '.join(w['text'] for w in native)))/max(len(expected),1)}
        results.append(result)
        report = {'run_id':manifest['run_id'],'scope':manifest['scope'],
            'model':'faster-whisper large-v3-turbo, offline CPU int8',
            'normalization':'Punctuation, curly apostrophes, case and equivalent ordinals only; numbers preserved.',
            'scenes':sorted(results,key=lambda r:r['index']),
            'word_error_rate':sum(r['word_errors'] for r in results)/max(sum(r['expected_words'] for r in results),1),
            'listening_approval':False,
            'limitations':['ASR is not a substitute for listening or acting-quality approval.']}
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k not in ('words','segments','expected')},ensure_ascii=False),flush=True)
    print(json.dumps({'report':str(output.resolve()),'scenes':len(results)}),flush=True)


if __name__=='__main__':
    main()
