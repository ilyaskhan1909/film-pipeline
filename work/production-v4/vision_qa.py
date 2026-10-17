"""Optional free local VLM observations, calibrated before use; never approval."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path

os.environ.update(HF_HUB_DISABLE_TELEMETRY='1',HF_HUB_DISABLE_XET='1',USE_TF='0',USE_FLAX='0',
                  TOKENIZERS_PARALLELISM='false',HF_HUB_DOWNLOAD_TIMEOUT='90')
import torch
from PIL import Image
from huggingface_hub import snapshot_download
from transformers import AutoModelForImageTextToText, AutoProcessor

HERE = Path(__file__).resolve().parent
MODEL = 'Qwen/Qwen3.5-2B'
REVISION = '15852e8c16360a2fea060d615a32b45270f8a8fc'
PROMPT = '''Describe only what is visibly present in this image. Do not infer a story or hidden objects.
Output only one JSON object with these keys:
description (one plain sentence), framing (wide/medium/closeup/macro),
recognizable_human_faces (integer), visible_tents (integer),
whole_doll_visible (boolean: a cloth doll's head AND most of its torso are visible),
blue_fabric_location (brief description, or absent),
visible_anomalies (array of clearly visible malformed or impossible details; NOT ordinary objects; empty if uncertain).
A tiny human face is still a human face. Distinguish people from actual wooden branch creatures.
Be uncertain rather than inventing unseen details. No reasoning, only JSON.'''


def parse(raw):
    decoder=json.JSONDecoder()
    for i,char in enumerate(raw):
        if char=='{':
            try:
                value,_=decoder.raw_decode(raw[i:])
                if isinstance(value,dict): return value
            except json.JSONDecodeError:
                pass
    raise ValueError('No JSON observation')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('images',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--ids',nargs='*')
    parser.add_argument('--offline',action='store_true')
    args=parser.parse_args()
    torch.set_num_threads(4)
    assert torch.cuda.is_available(), 'Optional local QA requires the available local GPU.'
    path=snapshot_download(MODEL,revision=REVISION,cache_dir=str(HERE/'vision-cache'),
        allow_patterns=['*.json','*.safetensors','*.jinja','merges.txt','vocab.json','tokenizer.model'],
        max_workers=2,local_files_only=args.offline)
    processor=AutoProcessor.from_pretrained(path,min_pixels=128*128,max_pixels=512*512)
    model=AutoModelForImageTextToText.from_pretrained(path,dtype=torch.bfloat16,
        device_map={'':0},attn_implementation='sdpa',low_cpu_mem_usage=True).eval()
    names=sorted(args.images.glob('*.png'))
    if args.ids: names=[p for p in names if p.stem in args.ids]
    results=[]
    prompt_sha=hashlib.sha256(PROMPT.encode()).hexdigest()
    if args.output.exists():
        previous=json.loads(args.output.read_text(encoding='utf-8'))
        if previous.get('revision')==REVISION and previous.get('prompt_sha256')==prompt_sha:
            results=previous['observations']
    for file in names:
        digest=hashlib.sha256(file.read_bytes()).hexdigest()
        if any(r['sha256']==digest for r in results): continue
        with Image.open(file) as original:
            im=original.convert('RGB'); im.thumbnail((1024,1024))
            messages=[{'role':'user','content':[{'type':'image','image':im},{'type':'text','text':PROMPT}]}]
            inputs=processor.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,
                return_dict=True,return_tensors='pt',enable_thinking=False).to('cuda:0')
        began=time.monotonic()
        with torch.inference_mode():
            output=model.generate(**inputs,max_new_tokens=240,do_sample=False)
        raw=processor.decode(output[0][inputs['input_ids'].shape[-1]:],skip_special_tokens=True)
        try: observation=parse(raw)
        except ValueError: observation={'parse_error':True}
        item={'file':str(file.resolve()),'sha256':digest,'observation':observation,
              'raw':raw,'seconds':round(time.monotonic()-began,2)}
        results.append(item)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        report={'model':MODEL,'revision':REVISION,'prompt_sha256':prompt_sha,
                'paid_api':False,'device':torch.cuda.get_device_name(0),
                'observations':results,'quality_approval':False,
                'limitations':['Small VLM observations may be wrong; calibration and human inspection are required.']}
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'file':file.name,'seconds':item['seconds'],'observation':observation},ensure_ascii=False),flush=True)
    print('VISION QA COMPLETE',flush=True)


if __name__=='__main__':
    main()
