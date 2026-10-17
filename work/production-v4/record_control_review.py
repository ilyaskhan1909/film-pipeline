"""Record explicit observations from contact sheet and native chosen images."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'outputs/first-film/control/assets/comparisons/control'
DECISIONS={
    'klein-shot-042':'reject: flat white puddle-like shape replaces illuminated leaf texture.',
    'zimage-shot-042':'select: leaf and root texture survives inside a plausible light footprint; empty foreground.',
    'klein-shot-047':'select: fallen side-view torch; handle left, emitting lens right, cone directed toward nearby roots.',
    'zimage-shot-047':'alternate only: correct general torch orientation, but stronger blown highlights and less restrained exposure.',
    'klein-shot-051':'select: entirely tan cloth mittens actually hold a separate loose frayed blue scrap; black button eyes and straight stitched mouth.',
    'zimage-shot-051':'reject for story: blue cloth lies on the torso rather than being held between cloth hands.',
    'klein-shot-053':'select: closed continuous burlap hands and one loose blue scrap; no visible human skin or fingernails.',
    'zimage-shot-053':'reject: human forearms in wearable gloves; bright tabletop/craft setting instead of the dark forest prop.'
}
report={'source_run_id':'production-5c00a79856d18422','review_method':'Eight-image contact sheet; four selected images also inspected at native resolution.',
    'decisions':[{ 'file':name+'.png','sha256':hashlib.sha256((FOLDER/(name+'.png')).read_bytes()).hexdigest(),
        'decision':decision} for name,decision in DECISIONS.items()],
    'limitations':['Only four controlled task types, no claim that one model is universally better.',
        'The selected doll eyes differ only subtly; the source says mismatched, not a specific size ratio.',
        'These observations do not approve any unreviewed new frame or the complete film.']}
(FOLDER.parents[2]/'editorial-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'reviewed_images':len(DECISIONS),'selected':4}),flush=True)
