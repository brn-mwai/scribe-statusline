import { chromium } from "playwright-core";
import { execFileSync } from "node:child_process";
import { mkdirSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { homedir } from "node:os";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRAMES = join(HERE, ".frames");
const CHROME = join(homedir(), "AppData/Local/ms-playwright/chromium-1208/chrome-win64/chrome.exe");
const FPS = 12;

const SHOTS = [
  { name: "scribe-demo", page: "terminal.html", start: 0, end: 12200, width: 940, height: 512, hold: 1400 },
  { name: "statusline-states", page: "states.html", start: 0, end: 6000, width: 940, height: 210, hold: 600 },
];

async function capture(browser, shot) {
  rmSync(FRAMES, { recursive: true, force: true });
  mkdirSync(FRAMES, { recursive: true });
  const page = await browser.newPage({ viewport: { width: shot.width, height: shot.height }, deviceScaleFactor: 2 });
  await page.goto("file:///" + join(HERE, shot.page).replace(/\\/g, "/"));
  const step = 1000 / FPS;
  let i = 0;
  for (let t = shot.start; t <= shot.end; t += step) {
    await page.evaluate((ms) => window.renderAt(ms), t);
    await page.screenshot({ path: join(FRAMES, `f${String(i).padStart(4, "0")}.png`) });
    i++;
  }
  // Freeze on the final state so viewers can read the payoff before the loop restarts.
  for (let h = 0; h < Math.round((shot.hold / 1000) * FPS); h++) {
    await page.screenshot({ path: join(FRAMES, `f${String(i++).padStart(4, "0")}.png`) });
  }
  await page.close();

  const out = join(HERE, `${shot.name}.gif`);
  const palette = join(FRAMES, "palette.png");
  const filters = "fps=" + FPS + ",scale=940:-1:flags=lanczos";
  execFileSync("ffmpeg", ["-y", "-i", join(FRAMES, "f%04d.png"), "-vf", filters + ",palettegen=max_colors=128", palette], { stdio: "ignore" });
  execFileSync("ffmpeg", ["-y", "-framerate", String(FPS), "-i", join(FRAMES, "f%04d.png"), "-i", palette,
    "-lavfi", filters + " [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=3", "-loop", "0", out], { stdio: "ignore" });
  rmSync(FRAMES, { recursive: true, force: true });
  console.log("wrote", out, "frames:", i);
}

const browser = await chromium.launch({ executablePath: CHROME });
for (const shot of SHOTS) await capture(browser, shot);
await browser.close();
