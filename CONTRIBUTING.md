# Contributing to the lab website

You do **not** need write access to this repository to change the site. There are three
routes, easiest first.

## 1. Add yourself, or update your profile — use a form

- [**Add a new team member**](../../issues/new?template=new-member.yml)
- [**Update an existing profile**](../../issues/new?template=update-profile.yml)

Only **two** things need typing: your name and a photo. Your profile URL, last name,
affiliation and social icons are all worked out for you, and role and group are dropdowns
with sensible defaults.

A maintainer reviews the issue and applies the `approved` label; a pull request with your
profile then opens automatically, including your photo, and you get a comment with the link.
Once it is merged the site rebuilds and is live in about a minute.

On the update form, fill in **only what should change** — everything left blank stays as it
is. Moving someone to Alumni is just the Group field. The only thing it always needs is
**Your name**, exactly as it currently appears on the site; you do not need to know where
any file lives.

If something is wrong — a photo that isn't an image, an education line that can't be read —
the bot comments on your issue with the exact reason and removes the `approved` label. Edit
the issue and ask for it to be re-approved.

### What each field becomes on the website

Your details show up in **two** places, and not every field appears in both.

**1. The People section on the homepage** — the grid everyone sees first:

```
Senior Researchers                     <- Group
┌───────────────────────────┐
│         ( photo )         │          <- Photo, cropped to a circle
│        Adrian Test        │          <- Full name
│     Research Scientist    │          <- Role
│ Registration, Foundation Models │    <- Interests, joined with commas
└───────────────────────────┘
```

That is all that appears there. No links, no education, no biography — the card is
deliberately short. Clicking the photo opens your profile page.

**2. Your profile page**, at `aim-lab.io/author/adrian-test/`:

```
( photo )                                  <- Photo
Adrian Test                                <- Full name
Doctoral researcher                        <- Role
Technical University of Munich             <- added for you automatically
Konrad Zuse School of Excellence           <- Additional affiliation
✉  ⌾  in                                   <- Email + Links, as icons
I am a PhD candidate working on ...        <- Biography
Interests
  · Medical Image Registration             <- Interests
Education
  MSc Computer Science, 2024               <- Education
  TUM
```

| Field | People section | Profile page | Notes |
|---|---|---|---|
| Full name | heading | heading | also decides your profile URL |
| Photo | the card | top of the page | square works best — it is cropped to a circle |
| Role | under your name | under your name | free text; purely descriptive |
| Group | **which heading you sit under** | not shown | structural — see below |
| Interests | one comma-separated line | bulleted list | keep them short, they must fit on a card |
| Email | no | envelope icon | |
| Links | no | one icon each | the icon is chosen from the address |
| Education | no | list at the bottom | |
| Biography | no | the main text | Markdown works here |
| Additional affiliation | no | under the TUM line | |
| Short bio | no | no | a one-liner the theme uses beside posts; safe to leave empty |

**Role and Group are different things, and only one of them can break your entry.**

*Role* is free text that is simply printed under your name — "Doctoral researcher",
"Research Scientist". Get it wrong and it says the wrong words.

*Group* decides **which heading you appear under**, and it is matched against a fixed
list (`Chair`, `Management`, `Senior Researchers`, `Researchers`, `Collaborators`,
`Visitors`, `Alumni`). If it does not match one of those exactly, no heading claims you
and **you do not appear on the site at all**. That is why it is a dropdown rather than a
text box, and why the automation rejects an invalid value instead of publishing it.

They often change together, but not always: a promotion changes your Role while your Group
stays `Researchers`; someone leaving changes only their Group to `Alumni`, keeping the Role
as a record of what they did.

**You are never asked for these — they are worked out from your name:** the folder your
profile lives in, the key that links your publications to you, and your last name. These
used to be typed by hand and were the most common cause of a profile that quietly rendered
nowhere.

## 2. Anything else — edit the file and open a pull request

For publications, news posts, open theses or homepage text, edit the Markdown directly. You
do not need to clone anything or install Hugo:

1. Browse to the file on GitHub and click the pencil icon.
2. Make your change and choose **Create a new branch and start a pull request**.

GitHub forks the repository for you automatically. The **Build check** workflow builds the
site on your pull request; if it goes red, the site would not build and the run log says why.

Where things live:

| What | Where |
|---|---|
| People | `content/authors/<Folder>/_index.md` + `avatar.jpg` |
| Publications | `content/publication/` |
| News posts | `content/post/` |
| Open theses | `content/theses/` |
| Homepage sections | `content/home/*.md` |
| Navigation, site title, theme options | `config/_default/` |

Two things that fail *silently* if you edit a profile by hand, so double-check them (the
forms above handle both for you):

- **`authors:` in a profile must equal the folder name.** It is the key that links publications
  to people.
- **`user_groups` must be one of** `Chair`, `Management`, `Senior Researchers`, `Researchers`,
  `Collaborators`, `Visitors`, `Alumni` (defined in `content/home/people.md`). A typo means the
  person renders nowhere at all.

Also: do not copy `superuser: true` from an existing profile. It marks a site owner, not an
ordinary member.

## 3. Not comfortable with any of that

Open a [blank issue](../../issues/new) and describe what should change. Someone will do it.

## For maintainers

- Requests arrive as issues labelled `new-member` or `update-profile`. Read the issue, then add
  the **`approved`** label to turn it into a pull request. That label is the only gate — the
  automation does nothing until it is applied, because issue text is written by anyone with a
  GitHub account and the workflow holds a write token.
- The generated pull request has already been built successfully by CI. Review it for content,
  not correctness of the YAML.
- `python3 .github/scripts/test_issue_to_author.py` runs the automation's test suite locally;
  CI runs it on any change under `.github/scripts/`.
- [`WORKFLOW.md`](WORKFLOW.md) has diagrams of both pipelines.
- Never run the site build by hand and never commit generated HTML. See `README.md`.
