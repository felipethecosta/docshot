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

const CONFIG_NAME = "docshot.config.json";

// -- configuration ---------------------------------------------------------

function findConfig(start) {
  let current = path.resolve(start);
  for (;;) {
    const candidate = path.join(current, CONFIG_NAME);
    if (fs.existsSync(candidate)) return candidate;
    const parent = path.dirname(current);
    if (parent === current) {
      fail(`no ${CONFIG_NAME} found (looked from ${path.resolve(start)} upwards)`);
    }
    current = parent;
  }
}

/** `KEY=value` lines from a .env next to the config, without overriding the shell. */
function loadEnvFile(dir) {
  const file = path.join(dir, ".env");
  if (!fs.existsSync(file)) return;
  for (const line of fs.readFileSync(file, "utf8").split("\n")) {
    const match = /^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/.exec(line);
    if (!match || line.trim().startsWith("#")) continue;
    const value = match[2].replace(/^["']|["']$/g, "");
    if (process.env[match[1]] === undefined) process.env[match[1]] = value;
  }
}

function expand(value) {
  if (typeof value === "string") {
    return value.replace(/\$\{([A-Za-z_][A-Za-z0-9_]*)\}/g, (whole, name) => {
      if (process.env[name] === undefined) {
        fail(`environment variable ${name} is not set (referenced as ${whole})`);
      }
      return process.env[name];
    });
  }
  if (Array.isArray(value)) return value.map(expand);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, expand(v)]));
  }
  return value;
}

function fail(message) {
  console.error(`docshot: ${message}`);
  process.exit(1);
}

// -- locators --------------------------------------------------------------

/** A step's target: `selector`, or `role` + `name` (name is a regex, case-insensitive). */
function locate(page, target) {
  if (typeof target === "string") return page.locator(target);
  if (target.selector) return page.locator(target.selector);
  if (target.text) return page.getByText(new RegExp(target.text, "i"));
  if (target.label) return page.getByLabel(new RegExp(target.label, "i"));
  if (target.role) {
    return target.name
      ? page.getByRole(target.role, { name: new RegExp(target.name, "i") })
      : page.getByRole(target.role);
  }
  fail(`step target needs one of: selector, role, text, label — got ${JSON.stringify(target)}`);
}

function pick(page, target) {
  const locator = locate(page, target);
  return typeof target === "object" && target.nth !== undefined
    ? locator.nth(target.nth)
    : locator.first();
}

// -- runner ----------------------------------------------------------------

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
    await this.page.waitForLoadState("networkidle").catch(() => {});
    await this.page.waitForTimeout(ms);
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

  async login() {
    const auth = this.config.auth;
    if (!auth) return;
    await this.page.goto(auth.url ?? "/login");
    await this.settle(auth.settleMs ?? 1500);

    for (const [selector, value] of Object.entries(auth.fields ?? {})) {
      await this.page.fill(selector, value);
    }
    if (auth.submit) await pick(this.page, auth.submit).click();
    if (auth.waitForUrl) {
      await this.page.waitForURL(new RegExp(auth.waitForUrl), {
        timeout: auth.timeoutMs ?? 60_000,
      });
    }
    await this.settle();
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
    for (const step of shot.steps ?? []) {
      await this.step(step, shot.name);
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

// -- entry point -----------------------------------------------------------

async function main() {
  const args = process.argv.slice(2);
  const flag = (name) => {
    const index = args.indexOf(name);
    return index === -1 ? undefined : args[index + 1];
  };

  const configPath = path.resolve(flag("--config") ?? findConfig("."));
  const root = path.dirname(configPath);
  loadEnvFile(root);

  const file = JSON.parse(fs.readFileSync(configPath, "utf8"));
  const config = expand(file.capture ?? file);
  if (!config.shots?.length) fail(`no "capture.shots" in ${configPath}`);

  const only = flag("--only")?.split(",").map((s) => s.trim());
  const shots = only ? config.shots.filter((s) => only.includes(s.name)) : config.shots;
  if (!shots.length) fail(`no shot named ${only?.join(", ")}`);

  if (args.includes("--list")) {
    for (const shot of config.shots) console.log(shot.name);
    return 0;
  }

  const outDir = path.resolve(root, config.outDir ?? file.shotsDir ?? "shots");
  fs.mkdirSync(outDir, { recursive: true });

  // Either package works: a standalone `playwright`, or the `@playwright/test`
  // a project already has for its end-to-end suite.
  let chromium;
  for (const candidate of ["playwright", "@playwright/test"]) {
    try {
      ({ chromium } = await import(candidate));
      break;
    } catch {
      /* try the next one */
    }
  }
  if (!chromium) {
    fail("playwright is not installed — run: npm install playwright && npx playwright install chromium");
  }

  const browser = await chromium.launch({
    headless: !args.includes("--headed"),
    slowMo: config.slowMo ?? 0,
    args: config.browserArgs ?? [],
  });
  const context = await browser.newContext({
    baseURL: config.baseUrl,
    viewport: config.viewport ?? { width: 1440, height: 900 },
    deviceScaleFactor: config.deviceScaleFactor ?? 2,
    colorScheme: config.colorScheme ?? "light",
    locale: config.locale,
    timezoneId: config.timezone,
    ignoreHTTPSErrors: config.ignoreHTTPSErrors ?? false,
  });
  context.setDefaultTimeout(config.timeoutMs ?? 30_000);

  const page = await context.newPage();
  const runner = new Runner(page, config, outDir);
  const failures = [];

  try {
    await runner.login();
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
