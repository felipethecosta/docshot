#!/usr/bin/env node
/**
 * docshot capture — screenshots driven by configuration, not by a script per system.
 *
 *   node capture/capture.mjs [--config docshot.config.json] [--only name,name] [--headed]
 *
 * The `capture` block of docshot.config.json says where the app lives, how to
 * log in, and one entry per screenshot. Every value may reference an
 * environment variable as ${VAR}, so credentials stay out of the file.
 */

import fs from "node:fs";
import path from "node:path";
import process from "node:process";

import {
  fail,
  launch,
  login,
  pick,
  readConfig,
  screenSignature,
  settle,
  signatureChanged,
} from "./shared.mjs";

const INTERACTIVE_STEPS = ["click", "menu", "press", "repeatUntilGone"];

class Runner {
  constructor(page, config, outDir) {
    this.page = page;
    this.config = config;
    this.outDir = outDir;
    this.settleMs = config.settleMs ?? 3000;
    this.taken = [];
    this.warnings = [];
  }

  async settle(ms = this.settleMs) {
    await settle(this.page, ms);
  }

  async shoot(name, options = {}) {
    const file = path.join(this.outDir, `${name}.png`);
    const mask = (this.config.mask ?? []).map((selector) => this.page.locator(selector));
    await this.page.screenshot({
      path: file,
      fullPage: Boolean(options.fullPage),
      mask,
      maskColor: this.config.maskColor ?? "#94a3b8",
    });
    this.taken.push(name);
    console.log(`  ✓ ${name}.png`);
  }

  async step(step, shotName) {
    if (step.goto !== undefined) {
      await this.page.goto(step.goto);
      await this.settle(step.settleMs);
      return;
    }
    if (step.wait !== undefined) {
      await this.page.waitForTimeout(step.wait);
      return;
    }
    if (step.waitForText) {
      await this.page
        .getByText(new RegExp(step.waitForText, "i"))
        .first()
        .waitFor({ timeout: step.timeoutMs ?? 20_000 });
      return;
    }
    if (step.click) {
      const target = pick(this.page, step.click);
      if ((await target.count()) === 0) {
        this.warnings.push(`${shotName}: nothing matched ${JSON.stringify(step.click)}`);
        return;
      }
      await target.click();
      await this.page.waitForTimeout(step.settleMs ?? 2000);
      return;
    }
    if (step.menu) {
      // Icon-only Radix/Headless triggers swallow click(): the event lands on
      // the SVG and the menu stays closed. Focus + Enter opens it reliably.
      const target = pick(this.page, step.menu);
      if ((await target.count()) === 0) {
        this.warnings.push(`${shotName}: nothing matched ${JSON.stringify(step.menu)}`);
        return;
      }
      await target.focus();
      await this.page.keyboard.press("Enter");
      await this.page.waitForTimeout(step.settleMs ?? 1200);
      return;
    }
    if (step.hover) {
      await pick(this.page, step.hover).hover();
      await this.page.waitForTimeout(step.settleMs ?? 800);
      return;
    }
    if (step.fill) {
      await this.page.fill(step.fill.selector, step.fill.value);
      return;
    }
    if (step.press) {
      await this.page.keyboard.press(step.press);
      await this.page.waitForTimeout(step.settleMs ?? 600);
      return;
    }
    if (step.scrollTo) {
      await pick(this.page, step.scrollTo).scrollIntoViewIfNeeded();
      await this.page.waitForTimeout(step.settleMs ?? 600);
      return;
    }
    if (step.repeatUntilGone) {
      // Paging forward until the screen has something worth photographing —
      // an empty day, an empty list, a "no results" state.
      const { text, click, max = 10 } = step.repeatUntilGone;
      for (let i = 0; i < max; i += 1) {
        const empty = this.page.getByText(new RegExp(text, "i"));
        if ((await empty.count()) === 0) break;
        await pick(this.page, click).click();
        await this.page.waitForTimeout(step.settleMs ?? 1800);
      }
      return;
    }
    if (step.screenshot) {
      await this.settle(step.settleMs);
      await this.shoot(step.screenshot, step);
      return;
    }
    if (step.evaluate) {
      await this.page.evaluate(step.evaluate);
      await this.page.waitForTimeout(step.settleMs ?? 500);
      return;
    }
    this.warnings.push(`${shotName}: unknown step ${JSON.stringify(step)}`);
  }

  async capture(shot) {
    console.log(`- ${shot.name}`);
    if (shot.goto !== undefined) {
      await this.page.goto(shot.goto);
      await this.settle(shot.settleMs);
    }

    // A click that misses its target photographs the screen behind it, and
    // nobody notices until the document is in review. Compare what is on
    // screen before and after the interaction and say so.
    const interactive = (shot.steps ?? []).some((step) =>
      INTERACTIVE_STEPS.some((key) => key in step),
    );
    const before = interactive ? await screenSignature(this.page) : null;

    for (const step of shot.steps ?? []) {
      await this.step(step, shot.name);
    }

    if (interactive) {
      const after = await screenSignature(this.page);
      if (!signatureChanged(before, after)) {
        this.warnings.push(
          `${shot.name}: the screen did not change after the interaction — ` +
            `the shot may be showing the page behind it`,
        );
      }
    }

    if (shot.skipScreenshot) return;
    await this.settle(shot.finalSettleMs ?? 800);
    await this.shoot(shot.name, shot);
    if (shot.closeWith !== false) {
      await this.page.keyboard.press("Escape").catch(() => {});
      await this.page.waitForTimeout(400);
    }
  }
}

async function main() {
  const args = process.argv.slice(2);
  const flag = (name) => {
    const index = args.indexOf(name);
    return index === -1 ? undefined : args[index + 1];
  };

  const { root, file, capture: config } = readConfig(flag("--config"));
  if (!config.shots?.length) fail(`no "capture.shots" in the configuration`);

  if (args.includes("--list")) {
    for (const shot of config.shots) console.log(shot.name);
    return 0;
  }

  const only = flag("--only")?.split(",").map((s) => s.trim());
  const shots = only ? config.shots.filter((s) => only.includes(s.name)) : config.shots;
  if (!shots.length) fail(`no shot named ${only?.join(", ")}`);

  const outDir = path.resolve(root, config.outDir ?? file.shotsDir ?? "shots");
  fs.mkdirSync(outDir, { recursive: true });

  const { browser, page } = await launch(config, { headed: args.includes("--headed") });
  const runner = new Runner(page, config, outDir);
  const failures = [];

  try {
    await login(page, config);
    for (const shot of shots) {
      try {
        await runner.capture(shot);
      } catch (error) {
        failures.push(`${shot.name}: ${error.message.split("\n")[0]}`);
        console.log(`  ✗ ${shot.name} — ${error.message.split("\n")[0]}`);
        if (config.stopOnError) break;
      }
    }
  } finally {
    await browser.close();
  }

  console.log(`\n${runner.taken.length}/${shots.length} captured in ${outDir}`);
  for (const warning of runner.warnings) console.log(`  ! ${warning}`);
  for (const failure of failures) console.log(`  ✗ ${failure}`);
  return failures.length ? 1 : 0;
}

main().then((code) => process.exit(code));
