"""Tests for issue_to_author.py.

Runs against a throwaway copy of a minimal content/ tree, with the avatar
download stubbed, so it needs no network and never touches the real site.

    python3 .github/scripts/test_issue_to_author.py
"""

import importlib.util
import os
import pathlib
import re
import shutil
import sys
import tempfile

MODULE = pathlib.Path(__file__).with_name("issue_to_author.py")

PEOPLE_MD = """+++
widget = "people"
[content]
  user_groups = ["Chair",
                 "Management",
                 "Senior Researchers",
                 "Researchers",
                 "Collaborators",
                 "Visitors",
                 "Alumni"]
+++
"""

EXISTING = """---
title: Tamara Müller
last_name: "Müller"

# Username (this should match the folder name)
authors:
- TamaraMueller

role: Doctoral researcher

organizations:
- name: Technical University of Munich

interests:
- Graph Neural Networks
- Fairness

# Social/Academic Networking
social:
- icon: envelope
  icon_pack: fas
  link: mailto:tamara@tum.de
- icon: github
  icon_pack: fab
  link: https://github.com/tamara

email: "tamara@tum.de"

user_groups:
- "Researchers"
---

Original biography text.
"""

PNG = ("image/png", b"\x89PNG\r\n\x1a\n" + b"x" * 100)
JPG = ("image/jpeg", b"\xff\xd8\xff\xe0" + b"x" * 100)
PDF = ("application/pdf", b"%PDF-1.4")
HUGE = ("image/png", b"x" * (8 * 1024 * 1024 + 1))
FAKE = {
    "https://github.com/user-attachments/assets/png": PNG,
    "https://github.com/user-attachments/assets/jpg": JPG,
    "https://github.com/user-attachments/assets/pdf": PDF,
    "https://github.com/user-attachments/assets/huge": HUGE,
}
IMG = '<img width="500" height="500" alt="Image" src="https://github.com/user-attachments/assets/png" />'
IMG_JPG = "![photo](https://github.com/user-attachments/assets/jpg)"


def body(fields):
    """Render a dict the way a GitHub issue form renders it."""
    out = []
    for label, value in fields.items():
        out.append(f"### {label}\n")
        out.append(f"{value if value not in (None, '') else '_No response_'}\n")
    return "\n".join(out)


def sandbox():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="aimlab-test-"))
    (tmp / "content/home").mkdir(parents=True)
    (tmp / "content/home/people.md").write_text(PEOPLE_MD, encoding="utf-8")
    (tmp / "content/authors/TamaraMueller").mkdir(parents=True)
    (tmp / "content/authors/TamaraMueller/_index.md").write_text(EXISTING, encoding="utf-8")
    (tmp / "content/authors/TamaraMueller/avatar.jpg").write_bytes(b"old")
    return tmp


def run(kind, fields):
    """Run the script end to end. Returns (ok, outputs, error, cwd)."""
    tmp = sandbox()
    cwd = os.getcwd()
    os.chdir(tmp)
    try:
        spec = importlib.util.spec_from_file_location("issue_to_author", MODULE)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.fetch_bytes = lambda url: FAKE[url]
        out_file = tmp / "gh_output"
        out_file.write_text("", encoding="utf-8")
        os.environ.update(
            ISSUE_KIND=kind, ISSUE_BODY=body(fields), GITHUB_OUTPUT=str(out_file)
        )
        ok = True
        try:
            mod.main()
        except SystemExit as exc:
            ok = not exc.code
        raw = out_file.read_text(encoding="utf-8")
        error = ""
        m = re.search(r"error<<AIMLABEOF\n(.*?)\nAIMLABEOF", raw, re.S)
        if m:
            error = m.group(1)
        outputs = dict(
            re.findall(r"^(folder|title|summary)=(.*)$", raw, re.M)
        )
        return ok, outputs, error, tmp
    finally:
        os.chdir(cwd)


RESULTS = []


def case(name, ok, detail=""):
    RESULTS.append((ok, name, detail))


def expect_ok(name, kind, fields, check=None):
    ok, outputs, error, tmp = run(kind, fields)
    if not ok:
        case(name, False, f"expected success, failed with: {error}")
    elif check:
        problem = check(tmp, outputs)
        case(name, not problem, problem or "")
    else:
        case(name, True)
    shutil.rmtree(tmp, ignore_errors=True)


def expect_fail(name, kind, fields, fragment):
    ok, _outputs, error, tmp = run(kind, fields)
    if ok:
        case(name, False, "expected failure, but it succeeded")
    elif fragment.lower() not in error.lower():
        case(name, False, f"wrong message: {error}")
    else:
        case(name, True, error)
    shutil.rmtree(tmp, ignore_errors=True)


def read(tmp, folder):
    return (tmp / "content/authors" / folder / "_index.md").read_text(encoding="utf-8")


NEW_MIN = {"Full name": "Jane Doe", "Photo": IMG, "Role": "Doctoral researcher",
           "Group": "Researchers"}


def main():
    # ---------- new member: success ----------
    def check_minimal(tmp, out):
        if out.get("folder") != "JaneDoe":
            return f"folder was {out.get('folder')}"
        text = read(tmp, "JaneDoe")
        for expected in ['title: "Jane Doe"', 'last_name: "Doe"', "- JaneDoe",
                         'role: "Doctoral researcher"', '- "Researchers"',
                         "Technical University of Munich"]:
            if expected not in text:
                return f"missing {expected!r}"
        if not (tmp / "content/authors/JaneDoe/avatar.png").exists():
            return "avatar.png not written"
        return None

    expect_ok("new: minimal submission", "new-member", NEW_MIN, check_minimal)

    expect_ok(
        "new: umlaut name -> transliterated folder", "new-member",
        {**NEW_MIN, "Full name": "Tamara Schröder"},
        lambda t, o: None if o["folder"] == "TamaraSchroeder" else f"folder={o['folder']}",
    )
    expect_ok(
        "new: nickname in parentheses dropped", "new-member",
        {**NEW_MIN, "Full name": "Huaqi (Harvey) Qiu"},
        lambda t, o: None if o["folder"] == "HuaqiQiu" else f"folder={o['folder']}",
    )
    expect_ok(
        "new: accented name stripped", "new-member",
        {**NEW_MIN, "Full name": "Nil Stolt-Ansó"},
        lambda t, o: None if o["folder"] == "NilStolt-Anso" else f"folder={o['folder']}",
    )
    expect_ok(
        "new: initials with dots", "new-member",
        {**NEW_MIN, "Full name": "Johannes C. Paetzold"},
        lambda t, o: None if o["folder"] == "JohannesCPaetzold" else f"folder={o['folder']}",
    )

    def check_full(tmp, out):
        text = read(tmp, "JaneDoe")
        wants = [
            'bio: "Registration, mostly deformable"',
            '- "Medical Image Registration"',
            '  - course: "MSc Computer Science"',
            '    year: "2024"',
            '  - course: "BSc Informatik"',       # two-part education line
            "- icon: envelope",
            "- icon: github",
            "- icon: google-scholar",
            "  icon_pack: ai",
            "- icon: linkedin",
            "- icon: globe",                      # unknown host falls back
            'email: "jane.doe@tum.de"',
            "- name: \"Konrad Zuse School of Excellence in Reliable AI\"",
            "I work on **registration**.",
        ]
        for w in wants:
            if w not in text:
                return f"missing {w!r}"
        return None

    expect_ok(
        "new: every optional field", "new-member",
        {**NEW_MIN,
         "Email": "jane.doe@tum.de",
         "Interests": "Medical Image Registration\nFoundation Models",
         "Education": "MSc Computer Science | TUM | 2024\nBSc Informatik | LMU Munich",
         "Links": ("https://github.com/janedoe\n"
                   "https://scholar.google.com/citations?user=abc\n"
                   "https://linkedin.com/in/janedoe\n"
                   "https://janedoe.example"),
         "Short bio": "Registration, mostly deformable",
         "Biography": "I work on **registration**.",
         "Additional affiliation": "Konrad Zuse School of Excellence in Reliable AI"},
        check_full,
    )
    expect_ok(
        "new: role 'Other' with free text", "new-member",
        {**NEW_MIN, "Role": "Other (write it in the box below)",
         "Role (if you picked Other)": "Guest Professor"},
        lambda t, o: None if 'role: "Guest Professor"' in read(t, "JaneDoe") else "role not set",
    )
    expect_ok(
        "new: markdown photo upload accepted", "new-member",
        {**NEW_MIN, "Photo": IMG_JPG},
        lambda t, o: None if (t / "content/authors/JaneDoe/avatar.jpg").exists() else "no avatar.jpg",
    )

    def check_yaml(tmp, out):
        try:
            import yaml
        except ImportError:
            return None
        text = read(tmp, "JaneDoe")
        fm = re.match(r"^---\n(.*?)\n---\n", text, re.S).group(1)
        data = yaml.safe_load(fm)
        if data["authors"] != ["JaneDoe"]:
            return "authors key does not match folder"
        if data["user_groups"] != ["Researchers"]:
            return "user_groups wrong"
        return None

    expect_ok("new: output is valid YAML", "new-member", NEW_MIN, check_yaml)

    # ---------- new member: failure ----------
    expect_fail("new: missing name", "new-member",
                {**NEW_MIN, "Full name": ""}, "Full name is required")
    expect_fail("new: duplicate profile", "new-member",
                {**NEW_MIN, "Full name": "Tamara Müller"}, "already exists")
    expect_fail("new: invalid group", "new-member",
                {**NEW_MIN, "Group": "Reserchers"}, "not a valid group")
    expect_fail("new: role Other with empty box", "new-member",
                {**NEW_MIN, "Role": "Other (write it in the box below)"}, "left the box below it empty")
    expect_fail("new: unparseable education line", "new-member",
                {**NEW_MIN, "Education": "test"}, "Could not read the education line")
    expect_fail("new: non-https link", "new-member",
                {**NEW_MIN, "Links": "javascript:alert(1)"}, "must start with https")
    expect_fail("new: missing photo", "new-member",
                {**NEW_MIN, "Photo": ""}, "photo is required")
    expect_fail("new: photo is not an image", "new-member",
                {**NEW_MIN, "Photo": "https://github.com/user-attachments/assets/pdf"},
                "must be a JPEG, PNG, WebP or GIF")
    expect_fail("new: photo over 8 MB", "new-member",
                {**NEW_MIN, "Photo": "https://github.com/user-attachments/assets/huge"},
                "larger than 8 MB")
    expect_fail("new: photo linked over http", "new-member",
                {**NEW_MIN, "Photo": "http://example.com/a.png"}, "uploaded to the issue")
    expect_fail("new: name with no Latin characters", "new-member",
                {**NEW_MIN, "Full name": "李雷"}, "Latin alphabet")

    # ---------- update: success ----------
    expect_ok(
        "update: found by display name, group changed", "update-profile",
        {"Your name": "Tamara Müller", "Group": "Alumni"},
        lambda t, o: None if '- "Alumni"' in read(t, "TamaraMueller") else "group not changed",
    )
    expect_ok(
        "update: found by folder name", "update-profile",
        {"Your name": "TamaraMueller", "Role": "Research Scientist"},
        lambda t, o: None if 'role: "Research Scientist"' in read(t, "TamaraMueller") else "role not changed",
    )
    expect_ok(
        "update: found by transliterated name", "update-profile",
        {"Your name": "Tamara Mueller", "Group": "Alumni"},
        lambda t, o: None if o["folder"] == "TamaraMueller" else f"folder={o['folder']}",
    )
    expect_ok(
        "update: case-insensitive lookup", "update-profile",
        {"Your name": "tamara müller", "Group": "Alumni"},
        lambda t, o: None if o["folder"] == "TamaraMueller" else f"folder={o['folder']}",
    )

    def check_untouched(tmp, out):
        text = read(tmp, "TamaraMueller")
        if "# Username (this should match the folder name)" not in text:
            return "comments were lost"
        if "Original biography text." not in text:
            return "biography was clobbered"
        if 'email: "tamara@tum.de"' not in text:
            return "email was clobbered"
        if "Graph Neural Networks" not in text:
            return "interests were clobbered"
        return None

    expect_ok("update: leaves untouched fields and comments alone", "update-profile",
              {"Your name": "Tamara Müller", "Group": "Alumni"}, check_untouched)

    def check_links(tmp, out):
        text = read(tmp, "TamaraMueller")
        if "- icon: orcid" not in text:
            return "orcid link not added"
        if "github.com/tamara" in text:
            return "old links were not replaced"
        if "mailto:tamara@tum.de" not in text:
            return "existing email link was dropped"
        if "interests:" not in text or "Graph Neural Networks" not in text:
            return "block replacement ate the neighbouring key"
        return None

    expect_ok("update: links replaced, email link kept", "update-profile",
              {"Your name": "Tamara Müller", "Links": "https://orcid.org/0000-0002-1825-0097"},
              check_links)
    expect_ok(
        "update: interests replaced", "update-profile",
        {"Your name": "Tamara Müller", "Interests": "Causal Inference"},
        lambda t, o: None if ("Causal Inference" in read(t, "TamaraMueller")
                              and "Graph Neural Networks" not in read(t, "TamaraMueller"))
        else "interests not replaced cleanly",
    )
    expect_ok(
        "update: biography replaced", "update-profile",
        {"Your name": "Tamara Müller", "Biography": "New biography."},
        lambda t, o: None if ("New biography." in read(t, "TamaraMueller")
                              and "Original biography" not in read(t, "TamaraMueller"))
        else "biography not replaced",
    )

    def check_photo_swap(tmp, out):
        d = tmp / "content/authors/TamaraMueller"
        if (d / "avatar.jpg").exists():
            return "old avatar.jpg was not removed"
        if not (d / "avatar.png").exists():
            return "new avatar.png not written"
        return None

    expect_ok("update: photo replaces old file of another extension", "update-profile",
              {"Your name": "Tamara Müller", "Photo": IMG}, check_photo_swap)
    expect_ok(
        "update: summary lists what changed", "update-profile",
        {"Your name": "Tamara Müller", "Group": "Alumni", "Short bio": "New bio"},
        lambda t, o: None if ("user_groups" in o["summary"] and "bio" in o["summary"])
        else f"summary={o['summary']}",
    )

    # ---------- update: failure ----------
    expect_fail("update: unknown person, with suggestion", "update-profile",
                {"Your name": "Tamara Mueler"}, "did you mean")
    expect_fail("update: nothing filled in", "update-profile",
                {"Your name": "Tamara Müller"}, "nothing to change")
    expect_fail("update: invalid group", "update-profile",
                {"Your name": "Tamara Müller", "Group": "Alumny"}, "not a valid group")
    expect_fail("update: empty name", "update-profile",
                {"Your name": ""}, "name is required")

    # ---------- report ----------
    width = max(len(n) for _, n, _ in RESULTS)
    failed = 0
    for ok, name, detail in RESULTS:
        mark = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        note = f"  {detail}" if detail and not ok else ""
        print(f"[{mark}] {name.ljust(width)}{note}")
    print(f"\n{len(RESULTS) - failed}/{len(RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
