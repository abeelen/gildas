# Automation

## `gildas_release.py`

Inspects the upstream GILDAS/PIIC trees and Docker Hub tags for
`abeelen/gildas`, then prints ready-to-run `docker build` / `docker
push` commands for the `gildas` and `gildas-piic` targets. It fills
`GILDAS_URL` / `PIIC_URL` for archived releases, drops empty build
args, and keeps `latest*` per family (`latest-alpine` for GILDAS,
`latest-piic-alpine` for GILDAS+PIIC, plus the unsuffixed aliases).
`--debian` selects `docker/Dockerfile.debian`; the default is
`docker/Dockerfile.alpine`.

```bash
# Missing releases (oldest first; newest gets the latest tags)
./gildas_release.py
./gildas_release.py --force          # include tags already on Docker Hub
./gildas_release.py --archive        # include archived releases

# PIIC: pair main-tree PIIC with GILDAS from main or archive
./gildas_release.py --piic
./gildas_release.py --piic --archive
./gildas_release.py --release jul26a --piic

# Single release (and its -piic variant when available)
./gildas_release.py --release jan26a

# SIF commands: Docker-converted (From: rewritten) or native Alpine
./gildas_release.py --singularity
./gildas_release.py --singularity --debian
./gildas_release.py --native          # --natif is an alias
./gildas_release.py --release jan26a --native

# Debian variants, execution, logging
./gildas_release.py --debian
./gildas_release.py --release jan26a --execute
./gildas_release.py --release jan26a --execute --log-dir logs
./gildas_release.py -v               # -vv for debug
```

IMAGER versions are coupled to GILDAS releases (`oct26a` selects
`IMAGER_VERSION=oct26`). The IMAGER listing is fail-open: if upstream
is unreachable, the script warns, emits `IMAGER_VERSION=none` with
`WITH_IMAGER=0`, and the image records
`abeelen.gildas.imager-version="none"` / `imager-bundled="0"` plus
`none (not bundled)` in `/etc/imager-version`. A later run rebuilds the
tag when IMAGER becomes available. `--imager-version none` skips IMAGER
explicitly; a concrete version pins it without querying upstream.

PIIC listing is fail-open too: an unreachable tree yields GILDAS-only
commands instead of an abort, and the next readable run builds the
`-piic` tags. Missing-tag detection also covers IMAGER/PIIC drift by
comparing the expected version with the image labels. Archived releases
are immutable snapshots, matched by tag existence only. Both fail-open
paths emit CI warnings (a GitHub annotation or a GitLab `WARNING:`
log line), never silently.

With `--execute --log-dir logs`, each build tees output to
`logs/<tag>.log` and prints only the tail. Offline tests:
`python -m pytest tests/`.

## GitHub Actions

`.github/workflows/build.yml` runs the script for Alpine and Debian in
parallel:

- weekly schedule: build and push whatever is missing on Docker Hub;
- recipe push (`docker/Dockerfile.alpine`, `docker/Dockerfile.debian`,
  `docker/entrypoint.sh`, `gildas_release.py`, `apptainer/*.def`,
  `packages/*.txt`, `patches/*.patch`, `scripts/*.sh`): rebuild on top
  of the new recipes;
- manual dispatch (optional `release` / `debian` / `piic` / `archive`);
- pull requests: print-only plan, no build or push.

Secrets: `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` (Read & Write).
Previous tags are pre-pulled for layer reuse; runners are pinned to
`ubuntu-24.04`.

`.github/workflows/sif.yml` converts Hub tags to SIFs (`latest` and
`latest-piic` by default) and attaches them to the rolling
`sif-images` GitHub release, rebuilding only when the Hub push is newer
than the published asset. Run it manually after rebuilt tags; the
Friday schedule keeps it fresh. Download with:

```bash
gh release download sif-images -R abeelen/gildas -p 'gildas-*.sif'
```

The same workflow can build one native Alpine SIF on demand (the
`natif` input; `release` pins one, archived releases included) or on
schedule when its asset is missing. Native assets accumulate per
release on the same rolling release; the `.def` files remain the manual
path for custom builds.

## GitLab

`.gitlab-ci.yml` mirrors the GitHub design on `docker`-tagged runners
(host socket, no dind service). Schedules are created in the GitLab UI;
web-triggered runs accept `RELEASE` / `DEBIAN=1` / `PIIC=1` /
`ARCHIVE=1`; merge requests get a print-only plan. Set
`DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN`. The Alpine leg also mirrors
`abeelen/gildas:latest` to the project registry (on LAM:
`registry.lam.fr/abeelen/gildas:latest`).

The `sif-build` job on the `apptainer` runner builds from the GitLab
registry and pushes `sif:<tag>` OCI artifacts with `singularity push`
(`oras push` is rejected by this registry). It runs automatically on
scheduled default-branch pipelines. Default-branch push and web
pipelines expose it as an optional manual job (`allow_failure`), so they
do not wait on it; other pipelines skip it. On LAM:

```bash
singularity pull gildas-latest.sif oras://registry.lam.fr/abeelen/gildas/sif:latest
singularity pull gildas-latest-piic.sif oras://registry.lam.fr/abeelen/gildas/sif:latest-piic
```

SIFs are no longer kept as job artifacts. The job clears `sifs/`,
pushes each tag, then deletes the local SIF; the `SIF_TAGS` schedule or
web-pipeline variable builds a subset (default `latest latest-piic`). Because the
PIIC image does not fit in the runner's `/tmp`,
`APPTAINER_TMPDIR` / `SINGULARITY_TMPDIR` and the caches point under
`$CI_PROJECT_DIR` and are cleaned on exit. Override
`SIF_TMPDIR` / `SIF_CACHEDIR` for larger scratch, and `SIF_MIN_FREE_GB`
for the preflight space check.
