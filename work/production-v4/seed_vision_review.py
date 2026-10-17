"""Reuse optional observations only for exactly identical pixels/model/prompt."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument('images',type=Path)
    p.add_argument('--sources',type=Path,nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    reports=[json.loads(path.read_text(encoding='utf-8')) for path in args.sources]
    key=lambda report:(report['model'],report['revision'],report['prompt_sha256'])
    assert all(key(report)==key(reports[0]) for report in reports)
    known={item['sha256']:item for report in reports for item in report['observations']}
    selected=[]
    for file in sorted(args.images.glob('*.png')):
        digest=hashlib.sha256(file.read_bytes()).hexdigest()
        if digest in known:
            item=copy.deepcopy(known[digest])
            item['measurement_source_file']=item['file']
            item['file']=str(file.resolve())
            selected.append(item)
    result=copy.deepcopy(reports[0]);result['observations']=selected
    result['measurement_lineage']=[str(path.resolve()) for path in args.sources]
    result['quality_approval']=False
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'identical_pixel_observations_reused':len(selected)}),flush=True)

if __name__=='__main__':main()
