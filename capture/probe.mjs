#!/usr/bin/env node
/**
 * docshot probe — what a screen offers, so the shot steps are written against
 * the real DOM instead of a guess.
 *
 *   node capture/probe.mjs /studies [--json] [--headed] [--after '<json step>']
 *
 * Logs in the same way `capture` does, opens the route, and lists the targets
 * that can be clicked, together with the exact JSON to paste into a shot.
 */

import process from "node:process";

import { fail, launch, login, readConfig, settle } from "./shared.mjs";

const COLLECT = () => {
  const visible = (el) => {
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return (
      rect.width > 0 &&
      rect.height > 0 &&
      style.visibility !== "hidden" &&
      style.display !== "none" &&
      Number(style.opacity) > 0.05
    );
  };

  const label = (el) =>
    (
      el.getAttribute("aria-label") ||
      el.getAttribute("title") ||
      (el.innerText || "").trim().split("\n")[0] ||
      el.getAttribute("placeholder") ||
      ""
    ).slice(0, 60);

  /** The most stable selector this element can be addressed by. */
  const selector = (el) => {
    for (const attribute of ["data-testid", "data-test", "id", "name"]) {
      const value = el.getAttribute(attribute);
      if (value) {
        return attribute === "id" ? `#${CSS.escape(value)}` : `[${attribute}="${value}"]`;
      }
    }
    const aria = el.getAttribute("aria-label");
    if (aria) return `${el.tagName.toLowerCase()}[aria-label="${aria}"]`;
    const classes = (el.getAttribute("class") || "")
      .split(/\s+/)
      .filter((c) => c && !c.includes("[") && !c.includes(":"))
      .slice(0, 3)
      .map((c) => `.${CSS.escape(c)}`)
      .join("");
    const popup = el.getAttribute("aria-haspopup");
    return (
      el.tagName.toLowerCase() + classes + (popup ? `[aria-haspopup="${popup}"]` : "")
    );
  };

  // A screen's own controls matter; the sidebar and the header are the same on
  // every route and would drown them.
  const chrome = (el) => Boolean(el.closest('nav, aside, header, [role="navigation"], [role="banner"]'));

  const collect = (query, role) =>
    [...document.querySelectorAll(query)]
      .filter(visible)
      .map((el) => ({
        role,
        name: label(el),
        selector: selector(el),
        popup: el.getAttribute("aria-haspopup") || null,
        disabled: el.hasAttribute("disabled") || el.getAttribute("aria-disabled") === "true",
        chrome: chrome(el),
      }));

  const dedupe = (items) => {
    const seen = new Map();
    for (const item of items) {
      const key = `${item.role}|${item.name}|${item.popup}|${item.name ? "" : item.selector}`;
      const found = seen.get(key);
      if (found) {
        found.count += 1;
        found.chrome = found.chrome && item.chrome;
      } else seen.set(key, { ...item, count: 1 });
    }
    return [...seen.values()];
  };

  return {
    url: location.href,
    title: document.title,
    heading: (document.querySelector("h1, h2")?.innerText || "").trim().slice(0, 80),
    buttons: dedupe(collect('button, [role="button"], input[type="submit"]', "button")),
    tabs: dedupe(collect('[role="tab"]', "tab")),
    links: dedupe(collect("nav a[href], aside a[href]", "link")).slice(0, 40),
    fields: dedupe(collect("input:not([type=hidden]), textarea, select", "field")).slice(0, 30),
    overlays: document.querySelectorAll(
      '[role="dialog"], [role="menu"], [data-state="open"], dialog[open]',
    ).length,
  };
};

function asStep(item) {
  if (item.name && !item.popup) {
    return JSON.stringify({
      click: { role: item.role === "tab" ? "tab" : "button", name: `^${item.name}$` },
    });
  }
  // No accessible name, or a menu trigger: address it by selector, and open a
  // menu with the keyboard — icon-only triggers swallow click().
  return JSON.stringify(item.popup ? { menu: { selector: item.selector } } : { click: { selector: item.selector } });
}

function print(report, showChrome) {
  const relevant = (items) => (showChrome ? items : items.filter((i) => !i.chrome));
  console.log(`${report.url}`);
  console.log(`${report.title}${report.heading ? ` · ${report.heading}` : ""}`);
  if (report.overlays) console.log(`${report.overlays} overlay(s) already open`);

  for (const [group, all] of [
    ["buttons", report.buttons],
    ["tabs", report.tabs],
    ["fields", report.fields],
    ["links", report.links],
  ]) {
    const items = relevant(all);
    if (!items.length) continue;
    const hidden = all.length - items.length;
    console.log(`\n${group} (${items.length}${hidden ? `, ${hidden} in the app chrome — --all shows them` : ""})`);
    for (const item of items) {
      const name = item.name || "(no accessible name)";
      const notes = [
        item.count > 1 ? `×${item.count}` : "",
        item.popup ? "menu trigger" : "",
        item.disabled ? "disabled" : "",
      ]
        .filter(Boolean)
        .join(" ");
      const line = `  ${name.padEnd(34)}${notes ? notes.padEnd(16) : "".padEnd(16)}`;
      console.log(group === "fields" ? `${line}${item.selector}` : `${line}${asStep(item)}`);
    }
  }
  console.log(
    "\nPaste a step into the shot's \"steps\", or use a field selector in auth.fields.",
  );
}

async function main() {
  const args = process.argv.slice(2);
  const flag = (name) => {
    const index = args.indexOf(name);
    return index === -1 ? undefined : args[index + 1];
  };
  const route = args.find((a) => !a.startsWith("--") && args[args.indexOf(a) - 1] !== "--config" && args[args.indexOf(a) - 1] !== "--after");
  if (!route) fail("usage: docshot probe <route> [--json] [--headed] [--after '<step json>']");

  const { capture: config } = readConfig(flag("--config"));
  const { browser, page } = await launch(config, { headed: args.includes("--headed") });

  try {
    await login(page, config);
    await page.goto(route);
    await settle(page, config.settleMs ?? 3000);

    // Probe what a screen looks like *after* an interaction, e.g. inside a dialog.
    const after = flag("--after");
    if (after) {
      const step = JSON.parse(after);
      const { pick } = await import("./shared.mjs");
      if (step.click) await pick(page, step.click).click();
      if (step.menu) {
        await pick(page, step.menu).focus();
        await page.keyboard.press("Enter");
      }
      await page.waitForTimeout(step.settleMs ?? 2000);
    }

    const report = await page.evaluate(COLLECT);
    if (args.includes("--json")) console.log(JSON.stringify(report, null, 2));
    else print(report, args.includes("--all"));
    return 0;
  } finally {
    await browser.close();
  }
}

main().then((code) => process.exit(code));
