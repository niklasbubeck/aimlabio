# Migrating the live site off local builds

This repo is a proving ground for `danielrueckert/website_source`. Everything below has been
verified here; this is the change list to replay on the real repo.

## What the old setup did

`website_source` held the Hugo project with `public/` as a **git submodule** pointing at
`danielrueckert/danielrueckert.github.io`, which held nothing but build output. Publishing meant:

```
edit content/ → hugo (locally, correct version) → cd public && git push → cd .. && git push
```

Miss either push and the two repos drift. The output repo's `.git` reached 175 MB, and a one
paragraph bio edit (`3101af58`) rewrote several thousand generated files, because the nav and
author lists are baked into every page.

## What replaced it

One repo, no submodule, no committed HTML. GitHub Actions builds and deploys on push;
`public/` exists only on the runner and is gitignored.

## Verified in this repo

Run [#4](https://github.com/niklasbubeck/aimlabio/actions/runs/34332002441), 2026-09-09:

- Build **49 s**, deploy 10 s.
- Hugo 0.74.3-extended resolves the Oct-2020 Wowchemy modules through the Go proxy without
  pinning changes.
- The CI build produces a **page-for-page identical** site to production: both sitemaps list
  242 URLs and the path sets match exactly.
- 99 of 104 homepage asset references resolve. The 5 that don't are `<img src="/home/*.png">`
  tags hardcoded in `content/home/publications.md`; they work in production because it is served
  at a domain root, and only 404 here because this repo is served from a subpath. Same for four
  hardcoded `](/author/...)` links in that file. Worth fixing with Hugo shortcodes eventually,
  but not a migration blocker.

## Steps to replay on `website_source`

1. `git rm --cached public && rm -f .gitmodules` — the submodule is the thing being removed.
2. `.gitignore`: uncomment `public/`, add `.hugo_build.lock`.
3. Copy `.github/workflows/deploy.yml` and `.github/workflows/preview.yml` from this repo.
4. `git mv CNAME static/CNAME` and change its contents from `https://aim-lab.io` to the bare
   hostname `aim-lab.io`. A root-level `CNAME` is **not** published — Hugo only copies `static/`
   into the build — so this must move or the custom domain is dropped from the artifact.
5. Delete `netlify.toml` (Netlify is unused; `aim-lab.io` resolves to GitHub Pages) and
   `update-academic.sh` (it operates on `themes/academic/`, which does not exist under Hugo
   Modules).
6. Settings → Pages → Source: **GitHub Actions**. The `enablement: true` flag in the workflow
   cannot do this for you — `GITHUB_TOKEN` gets `Resource not accessible by integration` when
   creating a Pages site.
7. Move the `aim-lab.io` custom domain from `danielrueckert.github.io` to `website_source`, and
   turn on Enforce HTTPS. DNS needs no change: the apex already points at the Pages IPs
   (`185.199.108–111.153`) and `www` is a CNAME to `danielrueckert.github.io`, which should be
   repointed to `danielrueckert/website_source`'s Pages host.
8. Archive `danielrueckert.github.io` rather than deleting it — it is the rollback.

## Differences between this repo and the real migration

- Production is served at a **domain root**, so the hardcoded `/home/*.png` and `/author/...`
  paths that 404 here will keep working there.
- `steps.pages.outputs.base_url` resolved to `http://niklasbubeck.com/aimlabio/` here, because
  this account has a user-level custom domain. On `website_source` it will resolve to
  `https://aim-lab.io/` once the custom domain and Enforce HTTPS are set.

## Deliberately not done

Upgrading Wowchemy 5.0.0-beta.0 / Hugo 0.74.3 (both from 2020). Versions are pinned in both
workflows so CI reproduces the current site exactly. Do the upgrade **after** this migration, in
a pull request, so `preview.yml` shows what breaks before it is live.
