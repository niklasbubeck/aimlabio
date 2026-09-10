"""Guard against the issue forms drifting from the script or the site.

Three ways these can silently disagree, all of which produce a profile that
renders nowhere or a form field that is quietly ignored:

  1. a form field whose label the script never reads
  2. a Group option that is not a real user_group in the People widget
  3. a user_group in the People widget that no form offers
  4. the workflow sniffing the issue body for a field label that no longer exists,
     which silently turns every submission into a no-op
"""

import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / ".github/scripts/issue_to_author.py").read_text(encoding="utf-8")
FORMS = sorted((ROOT / ".github/ISSUE_TEMPLATE").glob("*.yml"))
PEOPLE = (ROOT / "content/home/people.md").read_text(encoding="utf-8")

GROUPS = re.findall(r'"([^"]+)"', re.search(r"user_groups\s*=\s*\[(.*?)\]", PEOPLE, re.S).group(1))

problems = []
offered = set()

for form in FORMS:
    doc = yaml.safe_load(form.read_text(encoding="utf-8"))
    if "body" not in doc:
        continue
    for block in doc["body"]:
        if block["type"] == "markdown":
            continue
        label = block["attributes"]["label"]
        if f'"{label}"' not in SCRIPT:
            problems.append(f"{form.name}: field '{label}' is never read by issue_to_author.py")
        if block["type"] == "dropdown" and label == "Group":
            for option in block["attributes"]["options"]:
                if option == "No change":
                    continue
                offered.add(option)
                if option not in GROUPS:
                    problems.append(
                        f"{form.name}: Group option '{option}' is not in content/home/people.md"
                    )

# The workflow identifies which form an issue came from by grepping for a field
# label. Renaming that field without updating the workflow makes every request a
# silent no-op, so tie the two together here.
WORKFLOW = (ROOT / ".github/workflows/member-request.yml").read_text(encoding="utf-8")
sniffed = re.findall(r"grep -q '\^### ([^']+)' <<< \"\$ISSUE_BODY\"; then\n\s*kind=([a-z-]+)", WORKFLOW)
if not sniffed:
    problems.append("member-request.yml: could not find the body-detection greps")
for marker, kind in sniffed:
    owners = [f.stem for f in FORMS if f'label: {marker}' in f.read_text(encoding="utf-8")]
    if not owners:
        problems.append(
            f"member-request.yml greps for '### {marker}' but no issue form has that field"
        )
    elif kind not in owners:
        problems.append(
            f"member-request.yml maps '### {marker}' to {kind}, but that field is on {owners}"
        )

for group in GROUPS:
    if group not in offered:
        problems.append(f"user_group '{group}' exists on the site but no form offers it")

for p in problems:
    print(f"::error::{p}")
print(f"checked {len(FORMS)} forms against {len(GROUPS)} groups: "
      f"{'FAILED' if problems else 'consistent'}")
sys.exit(1 if problems else 0)
