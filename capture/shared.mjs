/** Configuration loading, target resolution and login — shared by capture and probe. */

import fs from "node:fs";
import path from "node:path";
import process from "node:process";

export const CONFIG_NAME = "docshot.config.json";

export function fail(message) {
  console.error(`docshot: ${message}`);
  process.exit(1);
}

export function findConfig(start) {
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
export function loadEnvFile(dir) {
  const file = path.join(dir, ".env");
  if (!fs.existsSync(file)) return;
  for (const line of fs.readFileSync(file, "utf8").split("\n")) {
    if (line.trim().startsWith("#")) continue;
    const match = /^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/.exec(line);
    if (!match) continue;
    const value = match[2].replace(/^["']|["']$/g, "");
    if (process.env[match[1]] === undefined) process.env[match[1]] = value;
  }
}

export function expand(value) {
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

export function readConfig(configPath) {
  const resolved = path.resolve(configPath ?? findConfig("."));
  const root = path.dirname(resolved);
  loadEnvFile(root);
  const file = JSON.parse(fs.readFileSync(resolved, "utf8"));
  return { root, file, capture: expand(file.capture ?? file) };
}

/** A step's target: `selector`, or `role` + `name` (a case-insensitive regex). */
export function locate(page, target) {
  if (typeof target === "string") return page.locator(target);
  if (target.selector) return page.locator(target.selector);
  if (target.text) return page.getByText(new RegExp(target.text, "i"));
  if (target.label) return page.getByLabel(new RegExp(target.label, "i"));
  if (target.role) {
    return target.name
      ? page.getByRole(target.role, { name: new RegExp(target.name, "i") })
      : page.getByRole(target.role);
  }
  fail(`target needs one of: selector, role, text, label — got ${JSON.stringify(target)}`);
}

export function pick(page, target) {
  const locator = locate(page, target);
  return typeof target === "object" && target.nth !== undefined
    ? locator.nth(target.nth)
    : locator.first();
}

export async function launch(config, { headed = false } = {}) {
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
    headless: !headed,
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
  return { browser, context, page: await context.newPage() };
}

export async function settle(page, ms) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(ms);
}

export async function login(page, config) {
  const auth = config.auth;
  if (!auth) return;
  await page.goto(auth.url ?? "/login");
  await settle(page, auth.settleMs ?? 1500);
  for (const [selector, value] of Object.entries(auth.fields ?? {})) {
    await page.fill(selector, value);
  }
  if (auth.submit) await pick(page, auth.submit).click();
  if (auth.waitForUrl) {
    try {
      await page.waitForURL(new RegExp(auth.waitForUrl), { timeout: auth.timeoutMs ?? 60_000 });
    } catch {
      // Never a stack trace here: the cause is almost always mundane — wrong
      // credentials, a login throttle after repeated runs, or an API that is
      // not up — and the run cannot produce anything useful either way.
      const message = await page
        .locator('[role="alert"], [data-sonner-toast], .error, [aria-live]')
        .first()
        .innerText()
        .catch(() => "");
      fail(
        `login did not leave ${page.url()}\n` +
          (message ? `  the page says: ${message.split("\n")[0]}\n` : "") +
          "  check the credentials, whether the API is up, and auth.waitForUrl",
      );
    }
  }
  await settle(page, config.settleMs ?? 3000);

  // A login that "succeeded" onto the login page is the classic silent failure:
  // a waitForUrl loose enough to match the "//" in "http://" never waits at all.
  if (auth.url && page.url().includes(auth.url)) {
    console.log(
      `  ! still on ${page.url()} after logging in — check auth.waitForUrl and the credentials`,
    );
  }
}

/** A cheap fingerprint of what is on screen, to tell "nothing happened" from "it opened". */
export async function screenSignature(page) {
  return page.evaluate(() => {
    const open = document.querySelectorAll(
      '[role="dialog"], [role="menu"], [role="alertdialog"], [data-state="open"], dialog[open]',
    ).length;
    return {
      url: location.href,
      nodes: document.querySelectorAll("*").length,
      text: (document.body?.innerText ?? "").length,
      overlays: open,
    };
  });
}

export function signatureChanged(before, after) {
  if (!before || !after) return true;
  return (
    before.url !== after.url ||
    before.overlays !== after.overlays ||
    Math.abs(before.nodes - after.nodes) > 2 ||
    Math.abs(before.text - after.text) > 12
  );
}
