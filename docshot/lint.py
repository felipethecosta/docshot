"""Static checks on a project before a browser is ever opened.

Written for the mistakes that are invisible until the document is in review:
a login regex that matches any URL, a step whose target no config value can
satisfy, a screenshot referenced by a manual that nobody captures.
"""

import json
import os
import re
from typing import Dict, List, Tuple

STEP_KEYS = {
    "goto", "wait", "waitForText", "click", "menu", "hover", "fill", "press",
    "scrollTo", "repeatUntilGone", "screenshot", "evaluate", "settleMs", "timeoutMs",
}
SHOT_KEYS = {
    "name", "goto", "steps", "settleMs", "finalSettleMs", "fullPage",
    "skipScreenshot", "closeWith",
}
TARGET_KEYS = {"selector", "role", "name", "text", "label", "nth"}

Problem = Tuple[str, str]  # (severity, message)


def _target_problems(where: str, target) -> List[Problem]:
    if isinstance(target, str):
        return []
    if not isinstance(target, dict):
        return [("error", "%s: target must be a string selector or an object" % where)]
    unknown = set(target) - TARGET_KEYS
    out = []
    if unknown:
        out.append(("error", "%s: unknown key(s) %s" % (where, ", ".join(sorted(unknown)))))
    if not ({"selector", "role", "text", "label"} & set(target)):
        out.append(("error", "%s: needs one of selector, role, text, label" % where))
    if "name" in target and "role" not in target:
        out.append(("warn", "%s: \"name\" only applies together with \"role\"" % where))
    for key in ("name", "text", "label"):
        if key in target:
            try:
                re.compile(target[key])
            except re.error as error:
                out.append(("error", "%s: %s is not a valid regex (%s)" % (where, key, error)))
    return out


def _auth_problems(auth: Dict) -> List[Problem]:
    out = []
    if not auth.get("fields"):
        out.append(("warn", "auth: no fields — the run will not log in"))
    for selector, value in (auth.get("fields") or {}).items():
        if not str(value).startswith("${"):
            out.append(
                ("error", 'auth.fields["%s"]: literal credential — use ${ENV_VAR}' % selector)
            )
    wait = auth.get("waitForUrl")
    if not wait:
        out.append(
            ("warn", "auth: no waitForUrl — the first screenshot may be taken mid-login")
        )
    else:
        try:
            pattern = re.compile(wait)
        except re.error as error:
            return out + [("error", "auth.waitForUrl: invalid regex (%s)" % error)]
        # The classic: "/(?!login)" matches the "//" in "http://" and declares
        # victory while the browser is still sitting on the login page.
        if pattern.search("http://localhost:3000/login"):
            out.append(
                (
                    "error",
                    "auth.waitForUrl (%r) also matches the login URL itself — "
                    "anchor it, e.g. \"localhost:3000/(?!login)\"" % wait,
                )
            )
    if auth.get("submit"):
        out.extend(_target_problems("auth.submit", auth["submit"]))
    return out


def _shot_problems(shot: Dict, index: int) -> List[Problem]:
    where = "shots[%d]" % index
    out = []
    if not isinstance(shot, dict) or not shot.get("name"):
        return [("error", "%s: every shot needs a name" % where)]
    where = "shot %r" % shot["name"]
    if not re.match(r"^[a-z0-9][a-z0-9._-]*$", shot["name"]):
        out.append(("warn", "%s: name becomes a file name — prefer kebab-case" % where))

    unknown = set(shot) - SHOT_KEYS
    if unknown:
        out.append(("error", "%s: unknown key(s) %s" % (where, ", ".join(sorted(unknown)))))
    if "goto" not in shot and not shot.get("steps"):
        out.append(("warn", "%s: no goto and no steps — captures whatever is on screen" % where))

    for position, step in enumerate(shot.get("steps") or []):
        step_where = "%s step %d" % (where, position + 1)
        if not isinstance(step, dict):
            out.append(("error", "%s: step must be an object" % step_where))
            continue
        keys = set(step) - {"settleMs", "timeoutMs"}
        unknown_step = set(step) - STEP_KEYS
        if unknown_step:
            out.append(
                ("error", "%s: unknown key(s) %s" % (step_where, ", ".join(sorted(unknown_step))))
            )
        if not keys:
            out.append(("error", "%s: empty step" % step_where))
        for key in ("click", "menu", "hover", "scrollTo"):
            if key in step:
                out.extend(_target_problems("%s (%s)" % (step_where, key), step[key]))
        if "repeatUntilGone" in step:
            block = step["repeatUntilGone"]
            if not isinstance(block, dict) or "text" not in block or "click" not in block:
                out.append(("error", "%s: repeatUntilGone needs text and click" % step_where))
            else:
                out.extend(_target_problems("%s (repeatUntilGone.click)" % step_where, block["click"]))
        if "fill" in step and not (
            isinstance(step["fill"], dict) and {"selector", "value"} <= set(step["fill"])
        ):
            out.append(("error", "%s: fill needs selector and value" % step_where))
    return out


def _referenced_images(source_dir: str) -> Dict[str, List[str]]:
    """Image file name -> the sources that reference it."""
    referenced = {}
    if not os.path.isdir(source_dir):
        return referenced
    for name in sorted(os.listdir(source_dir)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(source_dir, name)
        with open(path, encoding="utf-8") as fh:
            for match in re.finditer(r"^!\[(.*?)\]\((.*?)\)", fh.read(), re.M):
                referenced.setdefault(match.group(2), []).append(name)
                if not match.group(1).strip():
                    pass
    return referenced


def check(config: Dict) -> List[Problem]:
    problems = []
    capture = config.get("capture") or {}

    if capture:
        if not capture.get("baseUrl"):
            problems.append(("error", "capture: baseUrl is required"))
        if capture.get("auth"):
            problems.extend(_auth_problems(capture["auth"]))
        shots = capture.get("shots") or []
        if not shots:
            problems.append(("warn", "capture: no shots declared"))
        names = {}
        for index, shot in enumerate(shots):
            problems.extend(_shot_problems(shot, index))
            if isinstance(shot, dict) and shot.get("name"):
                names.setdefault(shot["name"], []).append(index)
        for name, positions in names.items():
            if len(positions) > 1:
                problems.append(
                    ("error", "shot %r declared %d times — later runs overwrite earlier ones"
                     % (name, len(positions)))
                )

    # Cross-check the manual against what the capture produces and what is on disk.
    referenced = _referenced_images(config["sourceDir"])
    captured = {"%s.png" % s["name"] for s in (capture.get("shots") or []) if s.get("name")}
    on_disk = set()
    if os.path.isdir(config["shotsDir"]):
        on_disk = {n for n in os.listdir(config["shotsDir"]) if not n.startswith(".")}

    pending = [i for i in referenced if i not in on_disk and i in captured]
    if not on_disk and pending:
        # Nothing captured yet is one fact, not one warning per image.
        problems.append(
            ("warn", "%s is empty — %d screenshot(s) pending, run: docshot capture"
             % (os.path.basename(config["shotsDir"]), len(pending)))
        )

    for image, sources in sorted(referenced.items()):
        if image in on_disk:
            continue
        if image in captured:
            if not on_disk:
                continue
            problems.append(
                ("warn", "%s is referenced by %s and declared in the config, but not captured yet"
                 % (image, ", ".join(sources)))
            )
        else:
            problems.append(
                ("error", "%s is referenced by %s but no shot produces it"
                 % (image, ", ".join(sources)))
            )

    for image in sorted(captured - set(referenced)):
        problems.append(("warn", "%s is captured but no manual shows it" % image))

    return problems


def report(problems: List[Problem]) -> int:
    errors = [p for p in problems if p[0] == "error"]
    warnings = [p for p in problems if p[0] == "warn"]
    for severity, message in problems:
        print("  %s %s" % ("✗" if severity == "error" else "!", message))
    if not problems:
        print("  ✓ nothing to fix")
    print("\n%d error(s), %d warning(s)" % (len(errors), len(warnings)))
    return 1 if errors else 0
