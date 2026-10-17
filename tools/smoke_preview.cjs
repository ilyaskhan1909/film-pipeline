// Check a clean clone with its OWN npm dependencies. No MP4 or browser download.
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');

const [projectArg, outputArg, browserArg] = process.argv.slice(2);
if (!projectArg || !outputArg || !browserArg) {
  throw new Error('Usage: node tools/smoke_preview.cjs PROJECT OUTPUT EXISTING_CHROME');
}
const project = path.resolve(projectArg);
const output = path.resolve(outputArg);
const browserExecutable = path.resolve(browserArg);
const runtime = createRequire(path.join(project, 'package.json'));
const {bundle} = runtime('@remotion/bundler');
const {getCompositions, renderStill, openBrowser} = runtime('@remotion/renderer');
const hosts = require(path.join(path.dirname(runtime.resolve('@remotion/renderer')), 'port-config.js'));
hosts.getHostToBind = () => '127.0.0.1';
hosts.getHostsToTry = () => ['127.0.0.1'];

async function main() {
  if (!fs.existsSync(browserExecutable)) throw new Error('An existing Chrome binary is required.');
  if (fs.existsSync(output)) throw new Error('Existing QA output preserved; choose another directory.');
  fs.mkdirSync(output, {recursive: true});
  const serveUrl = await bundle({entryPoint: path.join(project, 'src/index.tsx'),
    rootDir: project, publicDir: path.join(project, 'public'),
    outDir: path.join(output, 'bundle'), enableCaching: false, onProgress: () => {}});
  const browser = await openBrowser('chrome', {browserExecutable, logLevel: 'warn'});
  const errors = [];
  const onBrowserLog = (log) => {if (log.type === 'error') errors.push(log.text);};
  try {
    const compositions = await getCompositions(serveUrl, {puppeteerInstance: browser,
      logLevel: 'warn', onBrowserLog});
    const pilot = compositions.find(c => c.id === 'InkPilot');
    if (!pilot || pilot.durationInFrames !== 2127 || pilot.fps !== 24 ||
        pilot.width !== 1920 || pilot.height !== 1080) throw new Error('Unexpected pilot metadata.');
    const frames = [0, 375, 981, 2126];
    for (const frame of frames) {
      await renderStill({serveUrl, composition: pilot, frame,
        output: path.join(output, `frame-${frame}.png`), imageFormat: 'png',
        puppeteerInstance: browser, logLevel: 'warn', overwrite: false, onBrowserLog});
      console.log('FRAME', frame);
    }
    if (errors.length) throw new Error('Browser errors: ' + errors.join('; '));
    fs.writeFileSync(path.join(output, 'validation.json'), JSON.stringify({
      clean_clone_project: project, local_dependencies: runtime.resolve('remotion'),
      compositions: compositions.map(c => ({id: c.id, frames: c.durationInFrames})),
      frames_checked: frames, browser_errors: errors, mp4_exported: false,
      audio_listening_approval: false, new_machine_gpu_tested: false,
    }, null, 2));
  } finally {
    await browser.close({silent: true});
  }
}
main().catch(error => {console.error(error); process.exitCode = 1;});
