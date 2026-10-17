const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const root = path.resolve(__dirname, '../..');
const out = path.join(root, 'outputs/graphic-novel-v8');
const edit = path.join(out, 'edit/remotion');
const runtime = createRequire(path.join(edit, 'package.json'));
require(path.join(edit, 'scripts/loopback-only.cjs'));
const {bundle} = runtime('@remotion/bundler');
const {getCompositions, renderStill, openBrowser} = runtime('@remotion/renderer');
const browserExecutable = path.join(root, 'outputs/first-film/edit/remotion/node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe');
const revision = process.argv[2] || 'r1';
if (!/^r[1-9][0-9]*$/.test(revision)) throw new Error('Safe review revision required.');
const reviewFolder = revision === 'r1' ? 'qa' : `qa-${revision}`;
const reportName = revision === 'r1' ? 'preview-render-validation.json' : `preview-render-validation-${revision}.json`;

async function main() {
  if (!fs.existsSync(browserExecutable)) throw new Error('Existing browser required; no download requested.');
  const serveUrl = await bundle({entryPoint: path.join(edit, 'src/index.tsx'),
    rootDir: edit, publicDir: path.join(edit, 'public'),
    outDir: path.join(__dirname, `qa-bundle-${revision}`), enableCaching: false,
    onProgress: () => {}});
  const browser = await openBrowser('chrome', {browserExecutable, logLevel: 'warn'});
  const frames = [0, 108, 216, 217, 374, 375, 553, 731, 732, 980, 981, 1105,
    1106, 1301, 1495, 1496, 1629, 1761, 1762, 1944, 2126];
  const browserErrors = [];
  try {
    const compositions = await getCompositions(serveUrl, {puppeteerInstance: browser,
      logLevel: 'warn', onBrowserLog: (log) => {if (log.type === 'error') browserErrors.push(log.text);}});
    const pilot = compositions.find((item) => item.id === 'InkPilot');
    if (!pilot || pilot.durationInFrames !== 2127 || pilot.fps !== 24 || pilot.width !== 1920 || pilot.height !== 1080) {
      throw new Error('Pilot metadata differs from original frame timing.');
    }
    const expected = {CampConversation: 375, Departure: 606, ForestTrail: 1146};
    for (const [id, duration] of Object.entries(expected)) {
      if (compositions.find((item) => item.id === id)?.durationInFrames !== duration) throw new Error(`Wrong connected scene: ${id}`);
    }
    fs.mkdirSync(path.join(out, reviewFolder), {recursive: true});
    for (const frame of frames) {
      const output = path.join(out, reviewFolder, `frame-${String(frame).padStart(4, '0')}.png`);
      await renderStill({serveUrl, composition: pilot, frame, output, imageFormat: 'png',
        puppeteerInstance: browser, logLevel: 'warn', overwrite: false,
        onBrowserLog: (log) => {if (log.type === 'error') browserErrors.push(log.text);}});
      console.log('QA_FRAME', frame);
    }
    if (browserErrors.length) throw new Error('Browser errors: ' + browserErrors.join('; '));
    fs.writeFileSync(path.join(out, reportName), JSON.stringify({
      revision,
      engine: 'Remotion 4.0.532 / existing headless Chrome', frames_checked: frames,
      composition_ids: compositions.map((item) => item.id),
      dimensions: [1920, 1080], fps: 24, duration_frames: 2127,
      still_renders_completed: true, browser_errors: browserErrors,
      mp4_exported: false, native_video_generation: false,
      audio_playback_human_checked: false,
    }, null, 2) + '\n');
  } finally {
    await browser.close({silent: true});
  }
}
main().catch((err) => {console.error(err); process.exitCode = 1;});
