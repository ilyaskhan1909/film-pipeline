"""Keep raw ASR scores intact; classify only explicit text-form equivalences."""
import argparse
import hashlib
import json
from pathlib import Path

EQUIVALENCES = {
    4: [{'type':'replace','expected':['shockwave'],'heard':['shock','wave']}],
    14: [{'type':'replace','expected':['fifteen'],'heard':['15']}],
    23: [{'type':'replace','expected':["doll's"],'heard':['dolls']}],
}
REASONS = {
    4: 'Compound-word spacing; the spoken phrase is equivalent.',
    14: 'Same number written as an English word or digits.',
    23: 'Possessive singular and plural share the same pronunciation here.',
}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('report',type=Path)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    data=json.loads(args.report.read_text(encoding='utf-8'))
    decisions=[]
    for scene in data['scenes']:
        if not scene['word_errors']:
            continue
        equivalent=scene['differences']==EQUIVALENCES.get(scene['index'])
        decisions.append({'index':scene['index'],'audio_sha256':scene['audio_sha256'],
            'raw_differences':scene['differences'],
            'classification':'text_form_equivalence' if equivalent else 'unresolved_content',
            'reason':REASONS[scene['index']] if equivalent else 'Requires listening and possible retake.'})
    result={'run_id':data['run_id'],'report_sha256':hashlib.sha256(args.report.read_bytes()).hexdigest(),
        'raw_word_error_rate':data['word_error_rate'],'decisions':decisions,
        'unresolved_content_cases':sum(d['classification']=='unresolved_content' for d in decisions),
        'source_pcm_rail_samples':sum(s['source_pcm_rail_samples'] for s in data['scenes']),
        'listening_approval':False,'acting_approval':False,
        'note':'This is text-form adjudication, not a claim of listening or voice-quality approval.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
