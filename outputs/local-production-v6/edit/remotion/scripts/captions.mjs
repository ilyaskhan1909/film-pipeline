import {readFile, writeFile} from 'node:fs/promises';
import {parseSrt} from '@remotion/captions';

// Import the audited sidecar. No second transcription or spelling changes.
const source = new URL('../public/captions.en.srt', import.meta.url);
const input = await readFile(source, 'utf8');
const {captions} = parseSrt({input});
if (!captions.length) throw new Error('No captions imported');
let previous = 0;
for (const caption of captions) {
  if (caption.startMs < previous || caption.endMs <= caption.startMs) {
    throw new Error('Invalid or overlapping caption timing');
  }
  previous = caption.endMs;
}
const serialized = JSON.stringify(captions, null, 2) + '\n';
await writeFile(new URL('../public/captions.en.json', import.meta.url), serialized);
console.log(JSON.stringify({captions: captions.length, finalEndMs: previous}));
