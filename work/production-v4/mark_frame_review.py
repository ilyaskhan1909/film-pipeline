"""Record the completed inspection of exported contact sheets, not full viewing."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
file=ROOT/'outputs/first-film/export-review/frame-review.json'
report=json.loads(file.read_text(encoding='utf-8'))
assert len(report['frames'])==69
assert report['frames'][0]['shot']=='title' and report['frames'][-1]['shot']=='closing-fade'
assert not {item['shot'] for item in report['frames']} & {f'shot-{i:03}' for i in (2,21,26,31,55,61,65,67)}
report.update(status='all_69_exported_samples_visually_inspected',
    sample_findings=['Title remains visible in the exported opening.',
                     'No missing-image placeholder, unintended black sample or crop fault observed.',
                     'Rejected doll/hand frames and late sunset alternates are absent.',
                     'Last dim sample is the intended closing fade.'],
    sample_visual_approval=True,continuous_viewing_approval=False,listening_approval=False)
file.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'reviewed_samples':69,'continuous_viewing_approval':False}),flush=True)
