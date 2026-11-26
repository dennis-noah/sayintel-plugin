#!/usr/bin/env python3
"""Validate the OpenAI plugin package under openai/ and build its ZIP.

This is the local stand-in for Plugin Creator's prepare-plugin-submission
checks: Agent Plugins 1.0 schemas, the listing limits in
https://developers.openai.com/plugins/deploy/submission, and the archive
rules from that skill. It does not upload the package or connect the MCP server.
"""

from __future__ import annotations

import json
import re
import struct
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "openai"
SCHEMA_DIR = Path("/tmp")
ZIP_PATH = ROOT / "dist" / "sayintel-openai-plugin-1.0.0.zip"

CATEGORIES = {
    "Business & Operations",
    "Communication",
    "Creativity",
    "Data & Analytics",
    "Developer Tools",
    "Education & Research",
    "Entertainment",
    "Finance",
    "Healthcare",
    "Other",
    "Productivity",
    "Scientific Research",
    "Security",
    "Travel",
}

REQUIRED_DESCRIPTION = (
    "Conference outbound: speaker list, ICP match, and 3-message LinkedIn drafts a person approves."
)
SECRET_RE = re.compile(
    r"(si_[A-Za-z0-9]|sk_live|clientSecret|BEGIN (?:RSA |OPENSSH )?PRIVATE KEY|Authorization:\s*Bearer\s+\S+)",
    re.I,
)
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")

failures: list[str] = []
gaps: list[str] = []


def fail(message: str) -> None:
    failures.append(message)


def gap(message: str) -> None:
    gaps.append(message)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"{path.relative_to(ROOT)} is not valid JSON: {exc}")
        return {}


def fetch_schema(name: str) -> dict:
    path = SCHEMA_DIR / name
    if not path.exists():
        url = f"https://agent-plugins.org/schemas/1.0.0/{name}"
        urllib.request.urlretrieve(url, path)
    return json.loads(path.read_text(encoding="utf-8"))


def validate_schema(instance: dict, schema: dict, label: str) -> None:
    try:
        import jsonschema
    except ImportError:
        fail("jsonschema is not installed; schema validation did not run")
        return
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.path))
    for err in errors:
        where = ".".join(str(part) for part in err.path) or "(root)"
        fail(f"{label} schema: {where}: {err.message}")


def length(value: str) -> int:
    return len(value)


def check_https(url: str, label: str) -> None:
    if not isinstance(url, str) or not url.startswith("https://") or " " in url:
        fail(f"{label} must be an absolute HTTPS URL: {url!r}")
        return
    if urllib.parse.urlparse(url).username or urllib.parse.urlparse(url).password:
        fail(f"{label} must not embed credentials")
    if len(url) > 1024:
        fail(f"{label} is {len(url)} characters; final submission allows 1024")
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "sayintel-plugin-validator"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = response.status
            body = response.read(200_000)
    except Exception as exc:  # noqa: BLE001 - report the live check, keep going
        fail(f"{label} {url} could not be fetched: {exc}")
        return
    if status >= 400:
        fail(f"{label} {url} returned HTTP {status}")
        return
    if len(body) < 200:
        fail(f"{label} {url} returned too little content to be a real page")


def check_png(path: Path) -> None:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        fail(f"{path.name} is not a PNG")
        return
    width, height = struct.unpack(">II", data[16:24])
    if width != height:
        fail(f"{path.name} is {width}x{height}; icons must be square")
    if width < 256 or height < 256:
        fail(f"{path.name} is {width}x{height}; submission logos need at least 256x256")
    if width > 4096 or height > 4096:
        fail(f"{path.name} exceeds 4096 pixels")
    if len(data) > 5 * 1024 * 1024:
        fail(f"{path.name} exceeds 5 MiB")


def parse_frontmatter(text: str, label: str) -> dict:
    if not text.startswith("---\n"):
        fail(f"{label} must start with YAML front matter")
        return {}
    end = text.find("\n---\n", 4)
    if end < 0:
        fail(f"{label} front matter is unclosed")
        return {}
    raw = text[4:end]
    body = text[end + 5 :].strip()
    if not body:
        fail(f"{label} instructions are empty")
    try:
        import yaml
    except ImportError:
        fail("PyYAML is not installed; skill front matter was not parsed")
        return {}
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        fail(f"{label} front matter must be a mapping")
        return {}
    return data


def check_skills(names: set[str]) -> None:
    skills_root = PLUGIN / "skills"
    found = []
    for path in sorted(skills_root.iterdir()):
        if path.name.startswith("."):
            fail(f"skill directory {path.name} is hidden")
            continue
        if not path.is_dir():
            fail(f"skills/{path.name} is not a directory")
            continue
        skill_md = path / "SKILL.md"
        if not skill_md.is_file():
            fail(f"skills/{path.name}/SKILL.md is missing")
            continue
        text = skill_md.read_text(encoding="utf-8")
        if len(text.encode("utf-8")) > 1024 * 1024:
            fail(f"{skill_md} exceeds 1 MiB")
        meta = parse_frontmatter(text, f"skills/{path.name}/SKILL.md")
        name = meta.get("name")
        description = meta.get("description")
        if not isinstance(name, str) or not name.strip():
            fail(f"skills/{path.name} name is missing")
        elif name != path.name:
            fail(f"skills/{path.name} front matter name is {name!r}")
        else:
            found.append(name)
            identity = f"sayintel:{name}"
            if len(identity) > 64:
                fail(f"{identity} exceeds 64 characters")
        if not isinstance(description, str) or not description.strip():
            fail(f"skills/{path.name} description is missing")
        elif len(description) > 1024:
            fail(f"skills/{path.name} description is {len(description)} characters")
        if SECRET_RE.search(text):
            fail(f"skills/{path.name}/SKILL.md matches a secret pattern")
        if re.search(r"(?i)\bclaude\b|\$ARGUMENTS|(?<!sayintel\.com)/mcp\b", text):
            fail(f"skills/{path.name}/SKILL.md still has a host-specific command reference")
    if len(found) != len(set(found)):
        fail("skill names are not unique")
    expected = {"sayintel", "new-conference", "review-drafts", "meeting-brief"}
    if set(found) != expected:
        fail(f"skill set is {found}, expected {sorted(expected)}")
    names.update(found)


def check_listing(plugin: dict) -> None:
    openai = plugin.get("extensions", {}).get("com.openai", {})
    interface = openai.get("interface", {})
    if not isinstance(interface, dict):
        fail("extensions.com.openai.interface is missing")
        return
    limits = {
        "displayName": 30,
        "shortDescription": 30,
        "longDescription": 4000,
        "developerName": 80,
    }
    for field, limit in limits.items():
        value = interface.get(field)
        if not isinstance(value, str) or not value.strip():
            fail(f"interface.{field} is required")
            continue
        if "\n" in value and field != "longDescription":
            fail(f"interface.{field} must be one line")
        if len(value) > limit:
            fail(f"interface.{field} is {len(value)} characters; limit is {limit}")
    if interface.get("displayName") != "SayIntel":
        fail("interface.displayName must be SayIntel")
    if plugin.get("description") != REQUIRED_DESCRIPTION:
        fail("root description must be the directory sentence from the issue")
    if REQUIRED_DESCRIPTION not in str(interface.get("longDescription", "")):
        fail("longDescription must include the directory description")
    if "Done for you by NoBooth" not in str(interface.get("longDescription", "")):
        fail("longDescription is the listing field for the NoBooth mention")
    category = interface.get("category")
    if category not in CATEGORIES:
        fail(f"interface.category {category!r} is not a supported title")
    prompts = interface.get("defaultPrompt")
    if not isinstance(prompts, list) or not 1 <= len(prompts) <= 3:
        fail("defaultPrompt must be an array of 1 to 3 prompts")
    else:
        normalized = []
        for prompt in prompts:
            if not isinstance(prompt, str) or not prompt.strip() or "\n" in prompt:
                fail(f"default prompt is blank or multiline: {prompt!r}")
                continue
            if len(prompt) > 128:
                fail(f"default prompt is {len(prompt)} characters: {prompt}")
            if "@" in prompt:
                fail(f"default prompt contains an @mention: {prompt}")
            normalized.append(" ".join(prompt.split()).casefold())
        if len(normalized) != len(set(normalized)):
            fail("default prompts are not unique")
    for field in ("websiteURL", "supportURL", "privacyPolicyURL", "termsOfServiceURL"):
        check_https(interface.get(field, ""), f"interface.{field}")
    if interface.get("websiteURL") != "https://sayintel.com":
        fail("websiteURL must be https://sayintel.com")
    if interface.get("privacyPolicyURL") != "https://sayintel.com/privacy":
        fail("privacyPolicyURL must be https://sayintel.com/privacy")
    if interface.get("termsOfServiceURL") != "https://sayintel.com/terms":
        fail("termsOfServiceURL must be https://sayintel.com/terms")
    if interface.get("supportURL", "").startswith("mailto:"):
        fail("supportURL must be an HTTPS page, not an email")
    for icon_field in ("logo", "composerIcon"):
        relative = interface.get(icon_field)
        if not isinstance(relative, str) or not relative.startswith("./") or ".." in relative:
            fail(f"interface.{icon_field} must be a contained ./ path")
            continue
        icon_path = PLUGIN / relative[2:]
        if not icon_path.is_file():
            fail(f"interface.{icon_field} file is missing: {relative}")
        else:
            check_png(icon_path)
    capabilities = interface.get("capabilities", [])
    if not isinstance(capabilities, list) or len(capabilities) > 20:
        fail("capabilities must be an array of at most 20 strings")
    else:
        for capability in capabilities:
            if not isinstance(capability, str) or not capability.strip() or len(capability) > 120 or "\n" in capability:
                fail(f"capability is invalid: {capability!r}")
    onboarding = openai.get("onboardingSkill")
    if onboarding != "./skills/sayintel/SKILL.md":
        fail("onboardingSkill must point at ./skills/sayintel/SKILL.md")
    elif not (PLUGIN / "skills/sayintel/SKILL.md").is_file():
        fail("onboarding skill file is missing")
    author = plugin.get("author", {})
    if author.get("email") != "dennis@sayintel.com":
        fail("author.email must be dennis@sayintel.com (supportURL cannot be an email)")
    if not SEMVER_RE.match(str(plugin.get("version", ""))):
        fail("version must be strict semantic version")
    keywords = plugin.get("keywords", [])
    if not isinstance(keywords, list) or len(keywords) > 25:
        fail("keywords must be an array of at most 25 strings")
    if "apps" in openai or (PLUGIN / ".app.json").exists():
        fail("public ZIP must not include apps or .app.json")


def check_review(plugin: dict) -> None:
    review = plugin.get("extensions", {}).get("com.openai", {}).get("review", {})
    cases = review.get("test_cases", {})
    positive = cases.get("positive", [])
    negative = cases.get("negative", [])
    if len(positive) != 5:
        fail(f"review needs exactly 5 positive cases, found {len(positive)}")
    if len(negative) != 3:
        fail(f"review needs exactly 3 negative cases, found {len(negative)}")
    for index, case in enumerate(positive, start=1):
        for field in ("description", "prompt", "tools_triggered", "expected_behavior"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                fail(f"positive case {index} is missing {field}")
        if isinstance(case.get("tools_triggered"), list):
            fail(f"positive case {index} tools_triggered must be a string")
    for index, case in enumerate(negative, start=1):
        for field in ("description", "prompt"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                fail(f"negative case {index} is missing {field}")
        if "tools_triggered" in case:
            fail(f"negative case {index} must not require a tool")
    if review.get("commerce") is not False:
        fail("review.commerce must be false: the plugin does not take payment")
    if not isinstance(review.get("commerce_description"), str) or not review["commerce_description"].strip():
        fail("review.commerce_description must explain that billing happens outside the plugin")
    prompts = review.get("prompts", [])
    if not isinstance(prompts, list) or len(prompts) > 20:
        fail("review.prompts must be an array of at most 20 strings")
    for forbidden in ("test_credentials", "reviewer_instructions", "demo_recording_url"):
        if forbidden in review and review[forbidden] not in (None, ""):
            if forbidden == "demo_recording_url":
                fail("demo_recording_url is set but this package has no verified recording")
            else:
                fail(f"review.{forbidden} must stay out of the public ZIP")
    if "demo_recording_url" not in review:
        gap("No demo recording URL. Final MCP review requires one. Record a walkthrough on the test account and add review.demo_recording_url after the file is hosted where reviewers can play it.")
    publication = plugin.get("extensions", {}).get("com.openai", {}).get("publication", {})
    notes = publication.get("release_notes")
    if not isinstance(notes, str) or not notes.strip():
        fail("publication.release_notes is missing")
    if "countries" not in publication:
        gap("Country availability is omitted so the portal field stays editable. Choose the country list, or all countries, before submit.")
    gap("Positive and negative cases are drafted from the documented tool loop. They were not executed against a SayIntel test account.")
    gap("Reviewer credentials stay out of the ZIP. Enter a dedicated test account in the portal. It needs sample campaign data, no MFA, no email or SMS code, and permission to run the five positive cases.")
    gap("supportURL is https://sayintel.com because the listing field must be HTTPS. dennis@sayintel.com is author.email. The site publishes dennis@theonemile.com as customer support, and https://sayintel.com/support returns 404.")
    gap("https://sayintel.com/.well-known/openai-apps-challenge returns 404. Host the portal's domain-verification token there before connect.")
    gap("OpenAI organization verification, Apps Management Write, the OAuth connect, and the skill and tool scans happen in the portal. This script cannot run them.")


def check_mcp(mcp: dict) -> None:
    servers = mcp.get("mcpServers", {})
    if list(servers) != ["sayintel"]:
        fail(f"mcpServers must contain only sayintel, found {list(servers)}")
        return
    server = servers["sayintel"]
    if server.get("type") != "streamable-http" or server.get("url") != "https://sayintel.com/mcp":
        fail("sayintel server must be streamable-http at https://sayintel.com/mcp")
    if "headers" in server:
        fail("public submission rejects nonempty server headers; omit headers")
    auth = server.get("extensions", {}).get("com.openai", {}).get("auth", {})
    if auth.get("type") != "oauth":
        fail("protected server auth.type must be oauth, not none")
    client = auth.get("client", {})
    if client != {"mode": "dcr"}:
        fail(f"OAuth client must be dynamic registration only, found {client!r}")
    if auth.get("baseScopes") != ["openid", "email"]:
        fail("baseScopes must be openid and email, matching the authorization server")
    if "clientSecret" in json.dumps(mcp):
        fail("mcp.json must not contain a client secret")
    # The published Agent Plugins schema does not list extensions yet.
    # Validate the transport against that schema, then keep the OpenAI auth object.
    schema = fetch_schema("mcp.schema.json")
    transport = {
        "$schema": mcp["$schema"],
        "mcpServers": {
            "sayintel": {"type": server["type"], "url": server["url"]}
        },
    }
    validate_schema(transport, schema, "mcp.json transport")


def scan_tree() -> None:
    forbidden_names = {".app.json", ".mcp.json", "hooks.json"}
    for path in PLUGIN.rglob("*"):
        if path.name in forbidden_names or path.name.startswith(".app"):
            fail(f"unexpected package file {path.relative_to(PLUGIN)}")
        if path.is_file():
            text = path.read_bytes()
            if b"\x00" not in text[:200]:
                decoded = text.decode("utf-8", errors="replace")
                if SECRET_RE.search(decoded):
                    fail(f"secret pattern in {path.relative_to(ROOT)}")


def build_zip() -> None:
    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PLUGIN.rglob("*")):
            if not path.is_file():
                continue
            if path.name.startswith(".") or path.suffix == ".zip":
                continue
            archive.write(path, path.relative_to(PLUGIN).as_posix())
    with zipfile.ZipFile(ZIP_PATH) as archive:
        names = archive.namelist()
    if "plugin.json" not in names or "mcp.json" not in names:
        fail("ZIP root is missing plugin.json or mcp.json")
    if any(name.startswith("/") or ".." in name.split("/") for name in names):
        fail("ZIP contains unsafe paths")
    if any(name.endswith(".app.json") or "/apps" in name for name in names):
        fail("ZIP contains an app binding")
    print(f"ZIP {ZIP_PATH.relative_to(ROOT)} ({ZIP_PATH.stat().st_size} bytes)")
    for name in names:
        print(f"  {name}")


def main() -> int:
    plugin = load_json(PLUGIN / "plugin.json")
    mcp = load_json(PLUGIN / "mcp.json")
    if plugin:
        validate_schema(plugin, fetch_schema("plugin.schema.json"), "plugin.json")
        check_listing(plugin)
        check_review(plugin)
    if mcp:
        check_mcp(mcp)
    check_skills(set())
    scan_tree()
    build_zip()
    print()
    if failures:
        print(f"FAILED ({len(failures)})")
        for item in failures:
            print(f"  - {item}")
    else:
        print("PACKAGE CHECKS PASSED")
    print()
    print("NOT IN THE ZIP (portal / Dennis):")
    for item in gaps:
        print(f"  - {item}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
