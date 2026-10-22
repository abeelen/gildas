# Automation

## `gildas_release.py`

Inspects the IRAM GILDAS/PIIC download directories and the Docker Hub
tags for `abeelen/gildas`, then prints ready-to-run `docker build` /
`docker push` commands — for both the `gildas` and `gildas-piic` targets
when the corresponding tarballs exist upstream, with the correct
`GILDAS_URL` / `PIIC_URL` archive URLs when necessary. The release is
inlined and quoted, empty `--build-arg`s are dropped, and `latest*`
tags go to the newest release per family (`latest-alpine` for GILDAS,
`latest-piic-alpine` for GILDAS+PIIC, tracked independently, plus the
unsuffixed `latest` / `latest-piic` aliases; single `--release` always
tags `latest`). Archived releases are excluded
unless `--archive` is given (PIIC commands often need it, as PIIC
releases lag behind GILDAS ones — see `--piic`).

```bash
# List build commands for all missing releases (GILDAS and PIIC),
# ordered from oldest to newest (newest per family gets `latest` tags)
./gildas_release.py

# Same, but including releases that are already present on Docker Hub
./gildas_release.py --force

# Also include archived releases (off by default: slower, queries the
# archive trees; often needed for PIIC, whose releases lag behind GILDAS)
./gildas_release.py --archive

# Only PIIC build commands. PIIC releases lag behind GILDAS ones, so
# --piic pairs main-tree PIIC with GILDAS from main or archive;
# add --archive to also search PIIC itself in the archives.
./gildas_release.py --piic
./gildas_release.py --piic --archive
./gildas_release.py --release jul26a --piic

# Commands for a single release (and its -piic variant if available),
# always tagging `latest`.
./gildas_release.py --release jan26a

# Singularity: emit `singularity build ... gildas-latest.def` commands
# (From: rewritten per tag, lists all known releases)
./gildas_release.py --singularity
./gildas_release.py --singularity --debian
./gildas_release.py --release jan26a --singularity

# Singularity, native path: emit `singularity build ... .def` commands
# (one per release, PIIC bundled when available, archive URLs included
# when needed — needs root or --fakeroot to run; Alpine `.def` by default)
./gildas_release.py --natif
./gildas_release.py --natif --debian
./gildas_release.py --natif --archive
./gildas_release.py --release jan26a --natif

# Debian variants and direct execution
./gildas_release.py --debian
./gildas_release.py --release jan26a --execute
./gildas_release.py --release jan26a --execute --log-dir logs
./gildas_release.py -v   # info logs, -vv for debug
```

GILDAS/IMAGER coupling is automatic (`oct26a` →
`--build-arg IMAGER_VERSION=oct26`, `--imager-version` overrides; when
no matching IMAGER exists yet, the floating `last` is resolved to
whatever it currently points to, with a warning). The IMAGER listing is
**fail-open**: if `share.oasu.u-bordeaux.fr` is unreachable (offline CI,
firewall), the script logs a warning and emits
`--build-arg IMAGER_VERSION=none --build-arg WITH_IMAGER=0`, so the image
is built without IMAGER instead of failing on the download. Such images
carry the `abeelen.gildas.imager-version="none"` /
`abeelen.gildas.imager-bundled="0"` labels and `/etc/imager-version`
reads `none (not bundled)`, which is how a later run detects them. Once
the upstream answers again, the drift check rebuilds those tags with
IMAGER. Fail-open is never silent: the script emits a CI warning —
a `::warning title=IMAGER not bundled::` annotation on GitHub Actions
and a yellow `WARNING: IMAGER not bundled: …` line in the GitLab job
log (GitLab has no annotation API). Pass `--imager-version none` to
skip IMAGER explicitly, or a concrete version like `oct26` to pin it
without querying upstream.

Missing-tag detection also covers IMAGER and PIIC drift, for main-tree
releases: the script compares the expected IMAGER version against the
`abeelen.gildas.imager-version` image label and re-emits the build when
they differ — so a release built while its IMAGER was not out yet is
rebuilt once the matching IMAGER appears. Likewise, `-piic` images carry
`abeelen.gildas.piic-version` / `abeelen.gildas.piic-bundled`: if a tag
was built without PIIC (`none` / `0`), it is rebuilt once the release
appears in the upstream PIIC tree. Unreadable labels never trigger
rebuilds, pre-label GILDAS images rebuild once (pre-label `-piic` images
are assumed to have PIIC, to avoid churning every existing tag), and
archived releases are immutable snapshots matched by tag existence only.

PIIC listing is fail-open too: when `www.iram.fr` cannot be reached for
the PIIC tree, the script logs a warning and emits GILDAS-only commands
instead of aborting; the same GitHub/GitLab CI warning mechanism as
IMAGER marks the run. `-piic` tags are then built on the next run that
can read the listing. The PIIC download inside the Dockerfile was
already fail-open and now writes `none (not bundled)` to
`/etc/piic-version`.

With `--execute --log-dir logs`, each build tees full output to
`logs/<tag>.log` and prints only the tail. `tests/` covers the tag,
pairing, filtering and drift logic offline (`python -m pytest tests/`).

## GitHub Actions

`.github/workflows/build.yml` runs the same script in CI (Alpine and
Debian families in parallel):

- weekly schedule: builds and pushes whatever is missing on Docker Hub;
- recipe push (`Dockerfile*`, `docker-entrypoint.sh`, `gildas_release.py`,
  `gildas-*.def`): rebuilds on top of the new recipes;
- manual dispatch (`Run workflow`, optional `release` / `debian` /
  `piic` / `archive` inputs);
- pull requests: print-only plan, no build, no push.

Pushing needs two repo secrets: `DOCKERHUB_USERNAME` and
`DOCKERHUB_TOKEN` (a Hub access token with Read & Write permissions).
Builds reuse previously pushed layers (previous tags are pre-pulled),
so unchanged images rebuild in minutes while a new release compiles
from scratch (up to ~1 h per image, jobs run in parallel). Runners are
pinned to `ubuntu-24.04` so the environment never shifts under us.

`.github/workflows/sif.yml` converts Hub tags to Singularity SIFs
(`latest`, `latest-piic` by default, override via manual dispatch) and
attaches them to the rolling `sif-images` GitHub release, rebuilding a
tag only when its Hub push is newer than the published asset. Run it
manually after pushing rebuilt tags; the Friday schedule then just
keeps them fresh. Download with:

```bash
gh release download sif-images -R abeelen/gildas -p 'gildas-*.sif'
```

The same workflow builds one native SIF from the tarballs on demand
(manual dispatch with the `natif` input: newest release by default,
Alpine unless `debian` is set, `release` pins one explicitly, archived
releases included automatically) and on schedule whenever its asset is
still missing. Native assets accumulate per release name on the same
rolling release; the `.def` files remain the manual path for anything
custom.

## GitLab

`.gitlab-ci.yml` mirrors the same design, running on runners tagged
`docker` (host socket, no dind service needed): weekly schedules are
created in the GitLab UI (Build > Pipeline schedules), manual runs via
"Run pipeline" with optional `RELEASE` / `DEBIAN=1` / `PIIC=1` /
`ARCHIVE=1` variables, and merge requests get a print-only plan. It
needs the `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` CI/CD variables. The
Alpine build leg additionally mirrors `abeelen/gildas:latest` to the
project container registry (on LAM:
`registry.lam.fr/abeelen/gildas:latest`, short-lived registry
credentials, nothing to configure).

SIFs are built by the manual `sif-build` job on the `apptainer` runner,
from the GitLab registry, and published as `sifs/*.sif` job artifacts.
Apptainer unpacks OCI layers into its temporary directory, and the PIIC
image is too large for the runner's `/tmp`; the job therefore points
`APPTAINER_TMPDIR` / `SINGULARITY_TMPDIR` and the caches at job-specific
directories under `$CI_PROJECT_DIR`, cleaned up on exit. Set
`SIF_TMPDIR` / `SIF_CACHEDIR` to a larger scratch filesystem if the
build volume is not big enough, and `SIF_MIN_FREE_GB` for a preflight
space check.
