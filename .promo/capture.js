// Zigora's promo shots are the Android app's own screens: this runs the app's promo screen test (PromoTest, Robolectric) against the
// throwaway server start.sh made, then copies its pictures in as <lang>-<shot>.png (390×844 at 3×). The Tamil and Arabic screens
// come with the English run, as home-ta, topic-ta, home-ar and topic-ar.
//   node .promo/capture.js <shotsDir> <lang>      Env: BASE; the Android SDK in mobile/local.properties, ANDROID_HOME or ANDROID_SDK_ROOT;
//                                                 PROMO_GRADLE_ARGS for extra Gradle flags (e.g. -ProbolectricRepo=…)
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const OUT = process.argv[2];
const LANG = process.argv[3];
const ROOT = process.cwd();
const MOBILE = path.join(ROOT, 'mobile');
const run = (cmd, args, cwd) => execFileSync(cmd, args, { cwd, stdio: 'inherit' });

// the app packs the web's reader page; build it if this checkout hasn't yet
if (!fs.existsSync(path.join(ROOT, 'frontend/dist-reader/reader/reader.html'))) {
  if (!fs.existsSync(path.join(ROOT, 'frontend/node_modules'))) run('npm', ['ci', '--no-audit', '--no-fund'], path.join(ROOT, 'frontend'));
  run('npm', ['run', '-s', 'build:reader'], path.join(ROOT, 'frontend'));
}
const props = path.join(MOBILE, 'local.properties');
if (!fs.existsSync(props)) {
  const sdk = process.env.ANDROID_HOME || process.env.ANDROID_SDK_ROOT;
  if (!sdk) { console.error('No Android SDK: set ANDROID_HOME, or put sdk.dir in mobile/local.properties.'); process.exit(1); }
  fs.writeFileSync(props, `sdk.dir=${sdk}\n`); fs.writeFileSync(path.join(MOBILE, '.promo-made-local-properties'), '');  // cleanup.sh removes both
}

const shots = path.join(MOBILE, 'app/build/screens/promo');
fs.rmSync(shots, { recursive: true, force: true });
const extra = (process.env.PROMO_GRADLE_ARGS || '').split(/\s+/).filter(Boolean);
run('./gradlew', ['-q', 'testDebugUnitTest', '-Pscreens', `-PscreensServer=${process.env.BASE.replace('localhost', '127.0.0.1')}`, '--tests', '*PromoTest', ...extra], MOBILE);

const names = fs.readdirSync(shots).filter((f) => f.endsWith('.png'));
for (const f of names) fs.copyFileSync(path.join(shots, f), path.join(OUT, `${LANG}-${f}`));
console.log(`${LANG}: captured ${names.length} Android screens`);
