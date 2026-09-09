"""Turn a labelled GitHub issue form into a change under content/authors/.

Called by .github/workflows/member-request.yml. The issue body is untrusted
input: every value is validated, then written into a file as data. Nothing from
an issue is executed or interpolated into a shell.

The forms ask for as little as possible. The folder name, last name and social
icons are all derived here rather than typed by the submitter, because those
were the fields that silently produced a broken profile when got wrong.

Modes:
  new-member      build content/authors/<Folder>/_index.md from scratch
  update-profile  edit only the fields the submitter filled in, leaving the
                  rest of the file (including its comments) untouched
"""

import difflib
import json
import os
import pathlib
import re
import sys
import unicodedata
import urllib.request

AUTHORS = pathlib.Path("content/authors")
PEOPLE_WIDGET = pathlib.Path("content/home/people.md")

FOLDER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
DEFAULT_ORG = "Technical University of Munich"
DEFAULT_ORG_URL = (
    "https://www.translatum.tum.de/en/translatum/research-groups/"
    "daniel-rueckert-ai-in-healthcare-and-medicine/"
)
OTHER_ROLE = "Other (write it in the box below)"
NO_CHANGE = "No change"

IMAGE_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_AVATAR_BYTES = 8 * 1024 * 1024

# German transliteration first, matching the convention already in the repo
# (Müller -> Mueller, Hölzl -> Hoelzl); remaining accents are then stripped.
UMLAUTS = [("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("Ä", "Ae"), ("Ö", "Oe"),
           ("Ü", "Ue"), ("ß", "ss")]

# Social links are classified by host, so the submitter pastes URLs and never
# picks an icon. (host fragment, icon, icon pack)
LINK_ICONS = [
    ("github.com", "github", "fab"),
    ("gitlab.com", "gitlab", "fab"),
    ("linkedin.com", "linkedin", "fab"),
    ("scholar.google", "google-scholar", "ai"),
    ("orcid.org", "orcid", "ai"),
    ("researchgate.net", "researchgate", "ai"),
    ("twitter.com", "twitter", "fab"),
    ("x.com", "twitter", "fab"),
    ("bsky.app", "bluesky", "fab"),
    ("mastodon", "mastodon", "fab"),
]


def fail(msg):
    """Fail the job with a message the submitter will see on their issue."""
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"error<<AIMLABEOF\n{msg}\nAIMLABEOF\n")
    print(f"::error::{msg}")
    raise SystemExit(1)


def parse_sections(body):
    """GitHub issue forms render each field as '### <label>' followed by its value."""
    sections, current, buf = {}, None, []
    for line in (body or "").splitlines():
        if line.startswith("### "):
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current, buf = line[4:].strip(), []
        else:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    # Optional fields the submitter skipped arrive as "_No response_".
    return {k: (None if v in ("", "_No response_") else v) for k, v in sections.items()}


def allowed_groups():
    """Read valid user_groups from the People widget, so this script and the
    rendered site can never disagree about which groups exist."""
    if not PEOPLE_WIDGET.exists():
        fail(f"{PEOPLE_WIDGET} is missing.")
    block = re.search(r"user_groups\s*=\s*\[(.*?)\]", PEOPLE_WIDGET.read_text(encoding="utf-8"), re.S)
    if not block:
        fail(f"Could not read user_groups from {PEOPLE_WIDGET}")
    return re.findall(r'"([^"]+)"', block.group(1))


def y(value):
    """Quote a string as a YAML scalar. JSON strings are valid YAML, so this
    safely handles colons, quotes, umlauts and newlines coming from an issue."""
    return json.dumps(value, ensure_ascii=False)


def lines_of(value):
    return [ln.strip() for ln in (value or "").splitlines() if ln.strip()]


def clean_name(title):
    """Drop parenthesised nicknames: 'Huaqi (Harvey) Qiu' -> 'Huaqi Qiu'."""
    return re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", " ", title)).strip()


def derive_folder(title):
    """'Tamara Müller' -> 'TamaraMueller'. Matches the repo's existing naming."""
    s = clean_name(title)
    for a, b in UMLAUTS:
        s = s.replace(a, b)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9\- ]", "", s)
    return "".join(w[:1].upper() + w[1:] for w in s.split())


def derive_last_name(title):
    parts = clean_name(title).split()
    return parts[-1] if parts else ""


def fetch_bytes(url):
    """Download a URL. Separated out so the tests can stub it."""
    req = urllib.request.Request(url, headers={"User-Agent": "aimlabio-bot"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        return ctype, resp.read(MAX_AVATAR_BYTES + 1)


def find_avatar_url(section):
    """GitHub's uploader inserts <img src="...">; pasted markdown gives
    ![...](url). Accept both, and a bare URL."""
    for pattern in (
        r'<img[^>]*\ssrc=["\']([^"\']+)["\']',
        r"!\[[^\]]*\]\((https?://[^\s)]+)\)",
        r'(https?://[^\s"\'<>)]+)',
    ):
        m = re.search(pattern, section or "")
        if m:
            return m.group(1).strip()
    return None


def save_avatar(section, folder):
    url = find_avatar_url(section)
    if not url:
        return None
    if not url.startswith("https://"):
        fail(f"The photo must be an image uploaded to the issue (got '{url}').")
    ctype, data = fetch_bytes(url)
    if ctype not in IMAGE_EXT:
        fail(
            f"The photo must be a JPEG, PNG, WebP or GIF image "
            f"(got '{ctype or 'unknown'}' from {url})."
        )
    if len(data) > MAX_AVATAR_BYTES:
        fail("The photo is larger than 8 MB. Please resize it - 500x500 is plenty.")
    target = AUTHORS / folder
    target.mkdir(parents=True, exist_ok=True)
    for old in target.glob("avatar.*"):
        old.unlink()
    path = target / f"avatar{IMAGE_EXT[ctype]}"
    path.write_bytes(data)
    return str(path)


def social_block(email, links_section):
    """Build the `social:` list from an email plus a list of pasted URLs."""
    out = []
    if email:
        out += ["- icon: envelope", "  icon_pack: fas", f"  link: mailto:{email}"]
    for raw in lines_of(links_section):
        link = raw.split()[0].strip().rstrip(",;")
        if not link.startswith("https://"):
            fail(f"Links must start with https:// (got '{raw}').")
        host = link.split("/")[2].lower()
        icon, pack = "globe", "fas"
        for fragment, i, p in LINK_ICONS:
            if fragment in host:
                icon, pack = i, p
                break
        out += [f"- icon: {icon}", f"  icon_pack: {pack}", f"  link: {link}"]
    return out


def parse_education(section):
    courses = []
    for line in lines_of(section):
        parts = [p.strip() for p in re.split(r"\s*[|;]\s*", line) if p.strip()]
        if len(parts) == 3:
            courses += [f"  - course: {y(parts[0])}",
                        f"    institution: {y(parts[1])}",
                        f"    year: {y(parts[2])}"]
        elif len(parts) == 2:
            courses += [f"  - course: {y(parts[0])}",
                        f"    institution: {y(parts[1])}"]
        else:
            fail(
                f"Could not read the education line '{line}'. Write it as "
                "'Course | Institution | Year', one per line."
            )
    return courses


def resolve_role(f):
    role = (f.get("Role") or "").strip()
    other = (f.get("Role (if you picked Other)") or "").strip()
    if role in ("", OTHER_ROLE, NO_CHANGE):
        if role == OTHER_ROLE and not other:
            fail("You picked 'Other' as the role but left the box below it empty.")
        return other or None
    return role


def build_new(f, groups):
    title = (f.get("Full name") or "").strip()
    if not title:
        fail("Full name is required.")
    folder = derive_folder(title)
    if not FOLDER_RE.match(folder):
        fail(
            f"Could not derive a folder name from '{title}'. Please use the Latin "
            "alphabet for the profile name; a maintainer can add other scripts by hand."
        )
    if (AUTHORS / folder).exists():
        fail(
            f"content/authors/{folder} already exists for '{title}'. Use the "
            "'Update an existing profile' form instead."
        )
    group = (f.get("Group") or "").strip()
    if group not in groups:
        fail(f"'{group}' is not a valid group. Valid groups: {', '.join(groups)}")
    role = resolve_role(f)
    if not role:
        fail("Role is required.")
    email = (f.get("Email") or "").strip()

    out = ["---", f"title: {y(title)}", f"last_name: {y(derive_last_name(title))}", ""]
    out += ["# Must match the folder name under content/authors/.", "authors:", f"- {folder}", ""]
    out += [f"role: {y(role)}", "", "organizations:",
            f"- name: {y(DEFAULT_ORG)}", f"  url: {y(DEFAULT_ORG_URL)}"]
    for extra in lines_of(f.get("Additional affiliation")):
        out.append(f"- name: {y(extra)}")
    if f.get("Short bio"):
        out += ["", f"bio: {y(f['Short bio'].strip())}"]
    if f.get("Interests"):
        out += ["", "interests:"] + [f"- {y(i)}" for i in lines_of(f["Interests"])]
    courses = parse_education(f.get("Education"))
    if courses:
        out += ["", "education:", "  courses:"] + courses
    social = social_block(email, f.get("Links"))
    if social:
        out += ["", "social:"] + social
    if email:
        out += ["", f"email: {y(email)}"]
    out += ["", "user_groups:", f"- {y(group)}", "---", ""]
    if f.get("Biography"):
        out += [f["Biography"].strip(), ""]

    (AUTHORS / folder).mkdir(parents=True, exist_ok=True)
    (AUTHORS / folder / "_index.md").write_text("\n".join(out), encoding="utf-8")
    return folder, title


def profile_titles():
    """Map every existing profile to its display name."""
    found = {}
    for path in sorted(AUTHORS.glob("*/_index.md")):
        m = re.search(r"^title:\s*(.+)$", path.read_text(encoding="utf-8"), re.M)
        found[path.parent.name] = m.group(1).strip().strip('"') if m else path.parent.name
    return found


def find_profile(name):
    """Look a profile up by display name or folder, so nobody has to know the
    folder layout. Falls back to suggesting near matches."""
    name = (name or "").strip()
    if not name:
        fail("Your name is required.")
    titles = profile_titles()
    for folder, title in titles.items():
        if name.lower() in (folder.lower(), title.lower()):
            return folder
    derived = derive_folder(name)
    if derived in titles:
        return derived
    pool = list(titles.values()) + list(titles)
    close = difflib.get_close_matches(name, pool, n=3, cutoff=0.6)
    hint = f" Did you mean: {', '.join(close)}?" if close else ""
    fail(f"No profile found for '{name}'.{hint}")


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


def set_block(fm, key, items):
    """Replace `key:` and the list items under it, leaving everything else alone."""
    start = next((i for i, l in enumerate(fm) if re.match(rf"^{re.escape(key)}\s*:", l)), None)
    block = [f"{key}:"] + items
    if start is None:
        fm.extend([""] + block)
        return
    end = start + 1
    # Consume the list items ("- x") and their indented continuation lines
    # ("  icon_pack: fab"), stopping at the next top-level key or blank line.
    while end < len(fm) and re.match(r"^(-\s|\s+\S)", fm[end]):
        end += 1
    fm[start:end] = block


def build_update(f, groups):
    folder = find_profile(f.get("Your name"))
    path = AUTHORS / folder / "_index.md"
    fm, body = split_front_matter(path.read_text(encoding="utf-8"))
    changed = []

    role = resolve_role(f)
    if role:
        set_scalar(fm, "role", role); changed.append("role")
    if f.get("Short bio"):
        set_scalar(fm, "bio", f["Short bio"].strip()); changed.append("bio")
    email = (f.get("Email") or "").strip()
    if email:
        set_scalar(fm, "email", email); changed.append("email")
    group = (f.get("Group") or "").strip()
    if group and group != NO_CHANGE:
        if group not in groups:
            fail(f"'{group}' is not a valid group. Valid groups: {', '.join(groups)}")
        set_block(fm, "user_groups", [f"- {y(group)}"]); changed.append("user_groups")
    if f.get("Interests"):
        set_block(fm, "interests", [f"- {y(i)}" for i in lines_of(f["Interests"])])
        changed.append("interests")
    if f.get("Links"):
        existing_email = email or next(
            (l.split(":", 1)[1].strip().strip('"') for l in fm if l.startswith("email:")), ""
        )
        set_block(fm, "social", social_block(existing_email, f["Links"]))
        changed.append("links")
    if f.get("Biography"):
        body = f["Biography"].strip() + "\n"; changed.append("biography")

    path.write_text("---\n" + "\n".join(fm) + "\n---\n\n" + body.lstrip(), encoding="utf-8")
    title = next(
        (l.split(":", 1)[1].strip().strip('"') for l in fm if l.startswith("title:")), folder
    )
    return folder, title, changed


def main():
    kind = os.environ["ISSUE_KIND"]
    f = parse_sections(os.environ["ISSUE_BODY"])
    groups = allowed_groups()

    if kind == "new-member":
        folder, title = build_new(f, groups)
        if not save_avatar(f.get("Photo"), folder):
            fail("A photo is required. Drag an image into the 'Photo' box of the issue.")
        summary = f"Add {title} to the People section"
    elif kind == "update-profile":
        folder, title, changed = build_update(f, groups)
        if save_avatar(f.get("Photo"), folder):
            changed.append("photo")
        if not changed:
            fail("Nothing was filled in, so there is nothing to change.")
        summary = f"Update {title} ({', '.join(changed)})"
    else:
        fail(f"Unknown request kind '{kind}'.")

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"folder={folder}\ntitle={title}\nsummary={summary}\n")
    print(summary)


if __name__ == "__main__":
    main()
