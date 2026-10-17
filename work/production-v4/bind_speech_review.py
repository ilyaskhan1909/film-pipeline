"""Reuse measured ASR only after every PCM hash and source excerpt matches."""
import argparse
import copy
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument('assets',type=Path)
    p.add_argument('--previous-assets',type=Path,required=True)
    p.add_argument('--previous-review',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    manifest=json.loads((args.assets/'production_manifest.json').read_text(encoding='utf-8'))
    before=json.loads((args.previous_assets/'production_manifest.json').read_text(encoding='utf-8'))
    review=json.loads(args.previous_review.read_text(encoding='utf-8'))
    assert review['run_id']==before['run_id'] and manifest['story_sha256']==before['story_sha256']
    assert manifest['scope']=='full' and len(manifest['scenes'])==len(review['scenes'])==26
    reviews={s['index']:s for s in review['scenes']}
    originals={s['index']:s for s in before['scenes']}
    for scene in manifest['scenes']:
        index=scene['index']
        assert scene['text']==originals[index]['text']
        assert scene.get('voice_instruction')==originals[index].get('voice_instruction')
        assert hashlib.sha256((args.assets/scene['audio']).read_bytes()).hexdigest()==reviews[index]['audio_sha256']
        assert scene['audio_duration']==originals[index]['audio_duration']
    bound=copy.deepcopy(review)
    bound['run_id']=manifest['run_id']
    bound['measurement_lineage']={'previous_run_id':review['run_id'],
        'previous_review_sha256':hashlib.sha256(args.previous_review.read_bytes()).hexdigest(),
        'method':'All 26 PCM hashes, source excerpts, directions and durations match; no retranscription claimed.'}
    args.output.write_text(json.dumps(bound,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'run_id':manifest['run_id'],'identical_pcm_clips_verified':26}),flush=True)


if __name__=='__main__':main()
