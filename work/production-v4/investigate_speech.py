"""Unprompted, independent re-check of a short ambiguous narration passage."""
import argparse
import json
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio

parser = argparse.ArgumentParser()
parser.add_argument('audio')
parser.add_argument('--cache',required=True)
parser.add_argument('--start',type=float,required=True)
args = parser.parse_args()
model = WhisperModel('large-v3-turbo',device='cpu',compute_type='int8',cpu_threads=8,
                     download_root=args.cache,local_files_only=True)
audio = decode_audio(args.audio,sampling_rate=16000)[int(args.start*16000):]
for beam in (1,10):
    segments,_ = model.transcribe(audio,language='en',beam_size=beam,
        condition_on_previous_text=False,vad_filter=False,word_timestamps=True)
    found = list(segments)
    print(json.dumps({'beam_size':beam,'start':args.start,
        'text':' '.join(s.text.strip() for s in found),
        'words':[{'text':w.word,'probability':w.probability} for s in found for w in s.words]},ensure_ascii=False),flush=True)
