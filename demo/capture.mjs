import { chromium } from "playwright-core";
import { execFileSync } from "node:child_process";
import { mkdirSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { homedir } from "node:os";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRAMES = join(HERE, ".frames");
const CHROME = join(homedir(), "AppData/Local/ms-playwright/chromium-1208/chrome-win64/chrome.exe");
const CAPTURE_FPS = 30;
const GIF_FPS = 12;

const SHOTS = [
  { name: "scribe-demo", page: "terminal.html", end: 12200, width: 940, height: 512, hold: 1600 },
  { name: "statusline-states", page: "states.html", end: 6000, width: 940, height: 210, hold: 800 },
];

function ffmpeg(args) {
  execFileSync("ffmpeg", ["-y", ...args], { stdio: "ignore" });
}

async function shoot(browser, shot) {
  rmSync(FRAMES, { recursive: true, force: true });
  mkdirSync(FRAMES, { recursive: true });
  const page = await browser.newPage({ viewport: { width: shot.width, height: shot.height }, deviceScaleFactor: 2 });
  await page.goto("file:///" + join(HERE, shot.page).replace(/\\/g, "/"));
  const step = 1000 / CAPTURE_FPS;
  let i = 0;
  for (let t = 0; t <= shot.end; t += step) {
    await page.evaluate((ms) => window.renderAt(ms), t);
    await page.screenshot({ path: join(FRAMES, `f${String(i++).padStart(4, "0")}.png`) });
  }
  // Freeze on the final state so the payoff is readable before the loop restarts.
  for (let h = 0; h < Math.round((shot.hold / 1000) * CAPTURE_FPS); h++) {
    await page.screenshot({ path: join(FRAMES, `f${String(i++).padStart(4, "0")}.png`) });
  }
  await page.close();
  return i;
}

function encode(shot) {
  const src = join(FRAMES, "f%04d.png");
  const mp4 = join(HERE, `${shot.name}.mp4`);
  ffmpeg(["-framerate", String(CAPTURE_FPS), "-i", src, "-c:v", "libx264", "-preset", "slow", "-crf", "18",
    "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4]);

  const gif = join(HERE, `${shot.name}.gif`);
  const palette = join(FRAMES, "palette.png");
  const filters = `fps=${GIF_FPS},scale=940:-1:flags=lanczos`;
  ffmpeg(["-i", src, "-vf", `${filters},palettegen=max_colors=128`, palette]);
  ffmpeg(["-framerate", String(CAPTURE_FPS), "-i", src, "-i", palette,
    "-lavfi", `${filters} [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=3`, "-loop", "0", gif]);
  return { mp4, gif };
}

const browser = await chromium.launch({ executablePath: CHROME });
for (const shot of SHOTS) {
  const frames = await shoot(browser, shot);
  const out = encode(shot);
  rmSync(FRAMES, { recursive: true, force: true });
  console.log(`${shot.name}: ${frames} frames -> ${out.mp4}, ${out.gif}`);
}
await browser.close();
