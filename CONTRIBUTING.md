# Contributing to the lab website

You do **not** need write access to this repository to change the site. There are three
routes, easiest first.

## 1. Add yourself, or update your profile — use a form

- [**Add a new team member**](../../issues/new?template=new-member.yml)
- [**Update an existing profile**](../../issues/new?template=update-profile.yml)

Fill the form in and submit it. A maintainer reviews it, applies the `approved` label, and a
pull request with your profile is opened automatically — including your photo. You get a
comment with the link. Once it is merged the site rebuilds and is live in about a minute.

On the update form, fill in **only what should change**. Everything you leave blank stays as
it is. Moving someone to Alumni is just the Group field.

If something in your submission is wrong — a group that doesn't exist, a folder name with
spaces, a photo that isn't an image — the bot comments on your issue saying exactly what to
fix, and removes the `approved` label. Edit the issue and ask for it to be re-approved.

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

Two things that fail *silently*, so double-check them:

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
- Never run the site build by hand and never commit generated HTML. See `README.md`.
