# AI in Medicine — lab website

Hugo site for [aim-lab.io](https://aim-lab.io), built on
[Wowchemy](https://github.com/wowchemy/wowchemy-hugo-modules) (the theme formerly known as
Hugo Academic).

**You never build this site by hand.** Push a change and GitHub Actions builds and deploys it.
No generated HTML lives in this repo.

## Contributing without write access

Lab members do not need to be repository collaborators. They can file a
[form](.github/ISSUE_TEMPLATE/new-member.yml) to add or update a profile, which a maintainer
turns into a pull request with one label, or edit any file through GitHub's web editor, which
forks and opens a pull request for them automatically. See [CONTRIBUTING.md](CONTRIBUTING.md), and [WORKFLOW.md](WORKFLOW.md)
for diagrams of how publishing and contributing actually flow.

## Publishing a change

1. Edit a Markdown file under `content/` — on a branch, or directly in the GitHub web editor.
2. Open a pull request. The **Build check** workflow builds the site and fails the PR if you
   broke something. The built site is attached to the run as a downloadable artifact.
3. Merge to `main`. The **Deploy site** workflow builds and publishes to GitHub Pages, usually
   within a couple of minutes.

That's it. There is no second repo to push to and no local Hugo to keep in sync.

## Where things live

| What | Where |
|---|---|
| Homepage sections (news, people, research, teaching, vacancies, contact) | `content/home/*.md` |
| Team member profiles | `content/authors/<Name>/_index.md` (+ `avatar.jpg`) |
| Publications | `content/publication/` |
| Blog / news posts | `content/post/` |
| Open theses | `content/theses/` |
| Site title, base URL, taxonomies | `config/_default/config.toml` |
| Theme options, colours, contact details | `config/_default/params.toml` |
| Navigation menu | `config/_default/menus.toml` |
| Custom styling | `assets/scss/custom.scss` |
| Custom widget templates | `layouts/partials/widgets/` |
| Images and files served as-is | `static/` |

## Running it locally (optional)

Only needed if you want live preview while editing. Requires **Hugo 0.74.3 extended** and
**Go 1.19** — the theme is pulled as a Hugo Module, so Go must be on your PATH.

```bash
./view.sh          # hugo server --disableFastRender --i18n-warnings
```

Then open <http://localhost:1313>. If you skip this, the PR build artifact gives you the same
thing without installing anything.

## How deployment works

`.github/workflows/deploy.yml` runs on every push to `main`:

```
push to main → checkout → Go 1.19 + Hugo 0.74.3-extended → hugo --gc --minify
             → upload-pages-artifact → deploy-pages → live site
```

Pages is configured with **Settings → Pages → Source: GitHub Actions**, so the deploy comes
from the workflow artifact rather than from a branch. `public/` is gitignored and exists only
on the runner.

Hugo and Go versions are pinned in both workflows to the versions the site was originally built
with. Bump them in a pull request so the build check tells you whether the upgrade is safe.

## Notes

- `static/admin/` is a Netlify CMS admin UI shipped by the `netlify-cms-academic` module. It
  needs Netlify Identity / git-gateway to work and is not wired up on GitHub Pages.
- `CNAME` at the repo root is not published — Hugo only copies `static/` into the build. The
  custom domain is set in the repository's Pages settings. To ship it in the build instead,
  move it to `static/CNAME` containing the bare hostname `aim-lab.io`.
