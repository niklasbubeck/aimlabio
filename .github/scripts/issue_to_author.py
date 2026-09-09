"""Turn a labelled GitHub issue form into a change under content/authors/.

Called by .github/workflows/member-request.yml. The issue body is untrusted
input: every value taken from it is validated, then written into a file as
data. Nothing from the issue is ever executed or interpolated into a shell.

Modes:
  new-member      build content/authors/<Folder>/_index.md from scratch
  update-profile  edit only the fields the submitter filled in, leaving the
                  rest of the file (including its comments) untouched
"""

import json
import os
import pathlib
import re
import sys
import urllib.request

AUTHORS = pathlib.Path("content/authors")
PEOPLE_WIDGET = pathlib.Path("content/home/people.md")

FOLDER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
IMAGE_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_AVATAR_BYTES = 8 * 1024 * 1024

# Social links offered by the form -> (icon, icon_pack, link prefix)
SOCIALS = [
    ("Email", "envelope", "fas", "mailto:"),
    ("GitHub", "github", "fab", ""),
    ("LinkedIn", "linkedin", "fab", ""),
    ("Google Scholar", "google-scholar", "ai", ""),
    ("Website", "globe", "fas", ""),
]


def fail(msg):
    """Fail the job with a message the submitter will see on the issue."""
    pathlib.Path(os.environ["GITHUB_OUTPUT"]).open("a").write(f"error<<EOF\n{msg}\nEOF\n")
    print(f"::error::{msg}")
    sys.exit(1)


def parse_sections(body):
    """GitHub issue forms render each field as '### <label>' + value."""
    sections, current, buf = {}, None, []
    for line in body.splitlines():
        if line.startswith("### "):
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current, buf = line[4:].strip(), []
        else:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    # Optional fields the submitter skipped come through as "_No response_".
    return {k: (None if v in ("", "_No response_") else v) for k, v in sections.items()}


def allowed_groups():
    """Read the valid user_groups out of the People widget, so this script and
    the rendered site can never disagree about which groups exist."""
    text = PEOPLE_WIDGET.read_text(encoding="utf-8")
    block = re.search(r"user_groups\s*=\s*\[(.*?)\]", text, re.S)
    if not block:
        fail(f"Could not read user_groups from {PEOPLE_WIDGET}")
    return re.findall(r'"([^"]+)"', block.group(1))


def y(value):
    """Quote a string as a YAML scalar. JSON strings are valid YAML, so this
    safely handles colons, quotes, umlauts and newlines from the issue."""
    return json.dumps(value, ensure_ascii=False)


def lines_of(value):
    return [ln.strip() for ln in (value or "").splitlines() if ln.strip()]


def download_avatar(section, folder):
    """Pull the image the submitter dragged into the issue into the profile."""
    if not section:
        return None
    m = re.search(r"!\[[^\]]*\]\((https://[^\s)]+)\)", section) or re.search(
        r"(https://\S+)", section
    )
    if not m:
        return None
    url = m.group(1)
    if not url.startswith("https://"):
        fail("The avatar must be an image uploaded to the issue.")
    req = urllib.request.Request(url, headers={"User-Agent": "aimlabio-bot"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        data = resp.read(MAX_AVATAR_BYTES + 1)
    if ctype not in IMAGE_EXT:
        fail(f"The avatar must be a JPEG, PNG or WebP image (got '{ctype or 'unknown'}').")
    if len(data) > MAX_AVATAR_BYTES:
        fail("The avatar is larger than 8 MB. Please resize it (500x500 is plenty).")
    target = AUTHORS / folder
    for old in target.glob("avatar.*"):
        old.unlink()
    path = target / f"avatar{IMAGE_EXT[ctype]}"
    path.write_bytes(data)
    return str(path)


def social_block(f):
    out = []
    for label, icon, pack, prefix in SOCIALS:
        value = f.get(label)
        if not value:
            continue
        value = value.strip().splitlines()[0].strip()
        if prefix == "" and not value.startswith("https://"):
            fail(f"The {label} link must start with https:// (got '{value}').")
        out += [f"- icon: {icon}", f"  icon_pack: {pack}", f"  link: {prefix}{value}"]
    return out


def build_new(f, groups):
    folder = (f.get("Folder name") or "").strip()
    if not FOLDER_RE.match(folder):
        fail(
            f"'{folder}' is not a valid folder name. Use letters, digits, '-' or '_' "
            "and start with a letter, e.g. JaneDoe."
        )
    if (AUTHORS / folder).exists():
        fail(
            f"content/authors/{folder} already exists. Use the "
            "'Update an existing profile' form instead."
        )
    title = (f.get("Display name") or "").strip()
    group = (f.get("Group") or "").strip()
    role = (f.get("Role") or "").strip()
    if not title or not role:
        fail("Display name and Role are required.")
    if group not in groups:
        fail(f"'{group}' is not a valid group. Valid groups: {', '.join(groups)}")

    out = ["---", f"title: {y(title)}"]
    if f.get("Last name"):
        out.append(f"last_name: {y(f['Last name'].strip())}")
    out += ["", "# Must match the folder name under content/authors/.", "authors:", f"- {folder}", ""]
    out.append(f"role: {y(role)}")
    out += ["", "organizations:", f"- name: {y((f.get('Organization') or 'Technical University of Munich').strip())}"]
    if f.get("Organization URL"):
        out.append(f"  url: {y(f['Organization URL'].strip())}")
    if f.get("Short bio"):
        out += ["", f"bio: {y(f['Short bio'].strip())}"]
    if f.get("Interests"):
        out += ["", "interests:"] + [f"- {y(i)}" for i in lines_of(f["Interests"])]
    if f.get("Education"):
        courses = []
        for line in lines_of(f["Education"]):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) != 3:
                fail(
                    f"Could not read the education line '{line}'. Use "
                    "'Course | Institution | Year', one per line."
                )
            courses += [
                f"  - course: {y(parts[0])}",
                f"    institution: {y(parts[1])}",
                f"    year: {parts[2]}",
            ]
        out += ["", "education:", "  courses:"] + courses
    social = social_block(f)
    if social:
        out += ["", "social:"] + social
    if f.get("Email"):
        out += ["", f"email: {y(f['Email'].strip())}"]
    out += ["", "user_groups:", f'- "{group}"', "---", ""]
    if f.get("Biography"):
        out += [f["Biography"].strip(), ""]

    (AUTHORS / folder).mkdir(parents=True, exist_ok=True)
    (AUTHORS / folder / "_index.md").write_text("\n".join(out), encoding="utf-8")
    return folder, title


def split_front_matter(text):
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        fail("The existing profile does not start with YAML front matter.")
    return m.group(1).split("\n"), m.group(2)


def set_scalar(fm, key, value):
    for i, line in enumerate(fm):
        if re.match(rf"^{re.escape(key)}\s*:", line):
            fm[i] = f"{key}: {y(value)}"
            return
    fm.append(f"{key}: {y(value)}")


def set_list(fm, key, items):
    start = next((i for i, l in enumerate(fm) if re.match(rf"^{re.escape(key)}\s*:", l)), None)
    block = [f"{key}:"] + [f"- {y(i)}" for i in items]
    if start is None:
        fm.extend([""] + block)
        return
    end = start + 1
    while end < len(fm) and re.match(r"^\s*-\s", fm[end]):
        end += 1
    fm[start:end] = block


def build_update(f, groups):
    folder = (f.get("Folder name") or "").strip()
    if not FOLDER_RE.match(folder) or not (AUTHORS / folder / "_index.md").exists():
        existing = sorted(p.name for p in AUTHORS.iterdir() if p.is_dir())
        fail(
            f"No profile found at content/authors/{folder}. "
            f"It must be one of: {', '.join(existing[:12])} ..."
        )
    path = AUTHORS / folder / "_index.md"
    fm, body = split_front_matter(path.read_text(encoding="utf-8"))
    changed = []

    if f.get("Role"):
        set_scalar(fm, "role", f["Role"].strip()); changed.append("role")
    if f.get("Short bio"):
        set_scalar(fm, "bio", f["Short bio"].strip()); changed.append("bio")
    if f.get("Email"):
        set_scalar(fm, "email", f["Email"].strip()); changed.append("email")
    group = (f.get("Group") or "").strip()
    if group and group != "No change":
        if group not in groups:
            fail(f"'{group}' is not a valid group. Valid groups: {', '.join(groups)}")
        set_list(fm, "user_groups", [group]); changed.append("user_groups")
    if f.get("Interests"):
        set_list(fm, "interests", lines_of(f["Interests"])); changed.append("interests")
    if f.get("Biography"):
        body = f["Biography"].strip() + "\n"; changed.append("biography")

    path.write_text("---\n" + "\n".join(fm) + "\n---\n\n" + body.lstrip(), encoding="utf-8")
    title = next((l.split(":", 1)[1].strip().strip('"') for l in fm if l.startswith("title:")), folder)
    return folder, title, changed


def main():
    kind = os.environ["ISSUE_KIND"]
    f = parse_sections(os.environ["ISSUE_BODY"])
    groups = allowed_groups()

    if kind == "new-member":
        folder, title = build_new(f, groups)
        avatar = download_avatar(f.get("Photo"), folder)
        if not avatar:
            fail("A photo is required. Drag an image into the 'Photo' field of the issue.")
        summary = f"Add {title} to content/authors/{folder}/"
    elif kind == "update-profile":
        folder, title, changed = build_update(f, groups)
        if download_avatar(f.get("Photo"), folder):
            changed.append("avatar")
        if not changed:
            fail("No fields were filled in, so there is nothing to change.")
        summary = f"Update {title} ({', '.join(changed)})"
    else:
        fail(f"Unknown request kind '{kind}'.")

    with pathlib.Path(os.environ["GITHUB_OUTPUT"]).open("a") as out:
        out.write(f"folder={folder}\n")
        out.write(f"title={title}\n")
        out.write(f"summary={summary}\n")
    print(summary)


if __name__ == "__main__":
    main()
