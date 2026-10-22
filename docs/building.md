# Building images

With Docker 17.05 or higher (BuildKit recommended for cache mounts and
`ccache` speedups: `DOCKER_BUILDKIT=1`):

```bash
export release=jan26a
docker build \
       --tag abeelen/gildas:${release}-alpine \
       --target gildas \
       --build-arg release=${release} \
       --build-arg MAKE_JOBS=$(nproc) \
       -f docker/Dockerfile.alpine .
# Only add --tag abeelen/gildas:latest-alpine (and the latest alias)
# for the newest release.
```

Alpine (`docker/Dockerfile.alpine`) is the default build; every tag
carries its base (`-alpine` / `-debian`, e.g. `${release}-alpine`), with
unsuffixed `latest` / `latest-piic` kept as aliases of the Alpine rolling
tags. Use `-f docker/Dockerfile.debian` for the opt-in Debian images.
Docker recipes live in `docker/`; SIF recipes live in `apptainer/`.
Both Dockerfiles read `packages/<distro>-{runtime,build}.txt` and share
`scripts/gildas-runtime.sh` for the runtime environment and bare-name
wrappers.

In practice, prefer `gildas_release.py` (see
[automation](automation.md)): it picks the right URLs, tags `latest`
correctly and only builds what is missing.

## Build args

- `MAKE_JOBS` (default: `nproc`): parallel `make -j` jobs. `ccache` and
  apt/apk cache mounts are enabled automatically under BuildKit.
- `WITH_TEXLIVE=1` (Debian only, default `0`): keep `texlive`+`ghostscript`
  in the runtime image for the pipeline. Default is a slim runtime.
- `GILDAS_URL` / `PIIC_URL`: override the download base (used for archived
  releases).
- `WITH_IMAGER=1` (default `1`): build and ship the standalone IMAGER
  (`imager`, `viewer`, plus other IMAGER-only programs, exposed as
  `/usr/local/bin` wrappers). Set `WITH_IMAGER=0` to skip it; the image
  then labels itself `abeelen.gildas.imager-version="none"` /
  `abeelen.gildas.imager-bundled="0"` and writes
  `none (not bundled)` to `/etc/imager-version`.
- `IMAGER_VERSION` (default `last`): IMAGER tarball version, e.g.
  `oct26` (see https://imager.oasu.u-bordeaux.fr). Note the schemes
  differ — GILDAS releases carry a letter suffix (`oct26a`) while
  IMAGER versions do not (`oct26`) — so never reuse the GILDAS
  release name here; leave `last` or pin an explicit IMAGER version.
  `IMAGER_VERSION=none` (used automatically by `gildas_release.py`
  when the upstream is unreachable) implies `WITH_IMAGER=0`.
- `GAG_USE_SANITIZE=no` (default): leave disabled (crashes otherwise).

## PIIC

Starting with oct19a, PIIC is included in the container. The multi-stage
Dockerfiles provide two main targets:

- `gildas` : image without PIIC
- `gildas-piic` : image including PIIC

`-piic` images label `abeelen.gildas.piic-version` /
`abeelen.gildas.piic-bundled` and write `/etc/piic-version` (which reads
`none (not bundled)` when the tarball was unavailable, and is
authoritative). `WITH_PIIC=0` skips the download explicitly;
`PIIC_VERSION` defaults to the release name and is what the label
records, so `gildas_release.py` can later detect a PIIC-less tag and
rebuild it once the tarball appears.

SIFs converted from these images inherit the same `abeelen.gildas.*`
labels. Native SIF builds write them from `%post` as well (through
`APPTAINER_LABELS` / `SINGULARITY_LABELS`), so the Docker, converted-SIF,
and native-SIF labels use the same keys; the `/etc` files remain
authoritative for what was actually bundled.

To build the PIIC image for a given release (missing PIIC tarballs
warn instead of silently producing a GILDAS-only image thanks to the
`curl -fSL --retry` check):

```bash
export release=jan26a
docker build \
       --tag abeelen/gildas:${release}-piic-alpine \
       --target gildas-piic \
       --build-arg release=${release} \
       -f docker/Dockerfile.alpine .
# Only add --tag abeelen/gildas:latest-piic-alpine (and the latest-piic
# alias) for the newest release.
```

PIIC releases often lag behind GILDAS ones (same release name), so the
PIIC tarball of a given release is frequently only in the archives —
use `./gildas_release.py --piic --archive` to list PIIC build commands.

The default build uses the main GILDAS distribution URLs. For archived
releases, the helper script `gildas_release.py` generates the
appropriate `--build-arg GILDAS_URL=...` and `--build-arg PIIC_URL=...`
options to point to the archive trees.

## Debian-based images (opt-in)

```bash
export release=jan26a

# GILDAS only, Debian base image
docker build \
       --tag abeelen/gildas:${release}-debian \
       --target gildas \
       --build-arg release=${release} \
       -f docker/Dockerfile.debian .

# GILDAS + PIIC, Debian base image
docker build \
       --tag abeelen/gildas:${release}-piic-debian \
       --target gildas-piic \
       --build-arg release=${release} \
       -f docker/Dockerfile.debian .
```

## Check available tags on Docker Hub

```bash
curl -L -s 'https://registry.hub.docker.com/v1/repositories/abeelen/gildas/tags' | sed -e 's/[][]//g' -e 's/"//g' -e 's/ //g' | tr '}' '\n'  | awk -F: '{print $3}'
```

## Native Singularity builds

| Method | Command | Pros | Cons |
|--------|---------|------|------|
| From Docker Hub (`apptainer/gildas-docker.def`) | `sed "s\|^From: .*\|From: abeelen/gildas:jan26a-alpine\|" apptainer/gildas-docker.def > /tmp/sif-build.def && singularity build gildas-jan26a-alpine.sif /tmp/sif-build.def` (`./gildas_release.py --singularity`) | fast, no compiler needed, runscript + `%apprun` kept | needs the Docker tag to exist |
| Native Alpine (`apptainer/gildas-native-alpine.def`) | `SINGULARITYENV_GILDAS_RELEASE=jan26a singularity build gildas-jan26a-native-alpine.sif apptainer/gildas-native-alpine.def` | no Docker involved, any (incl. archived) release with `SINGULARITYENV_GILDAS_URL`/`SINGULARITYENV_PIIC_URL` overrides, `MAKE_JOBS`/`WITH_TEXLIVE` tunable, slim musl image with local musl patches | full recompile (~slow), needs root or `--fakeroot` |

There is only one native recipe (Alpine). The Docker-converted path
keeps the Docker tag in the filename (`gildas-<tag>.sif`); native SIFs
use `gildas-<release>[-piic]-native-alpine.sif`, with `-piic` added when
the PIIC tarball was available and bundled.

```bash
# Native build from tarballs (no Docker involved), with configurable
# release and URLs (see %environment in apptainer/gildas-native-alpine.def).
# NOTE: SINGULARITYENV_ prefix is mandatory, plain VAR=... never reaches
# %post (silently dropped). Easiest: use `./gildas_release.py --native`
# (`--natif` is an alias), which generates the right command (IMAGER
# pinned, archive URLs added) and the matching output filename.
export SINGULARITYENV_GILDAS_RELEASE=jan26a
export SINGULARITYENV_GILDAS_URL=https://www.iram.fr/~gildas/dist
export SINGULARITYENV_PIIC_URL=https://www.iram.fr/~gildas/dist
export SINGULARITYENV_MAKE_JOBS=$(nproc)
# export SINGULARITYENV_WITH_TEXLIVE=1  # only if you need the pipeline (texlive in image)
sudo -E singularity build gildas-${SINGULARITYENV_GILDAS_RELEASE}-native-alpine.sif apptainer/gildas-native-alpine.def
# If PIIC was bundled, use the convention ...-piic-native-alpine.sif.
```

The `.def` recipes mirror the Dockerfiles:
`apptainer/gildas-docker.def` bootstraps from Docker Hub (runscript +
`%apprun` shortcuts), `apptainer/gildas-native-alpine.def` compiles from
tarballs (PIIC bundled when its tarball exists upstream). The Alpine
package lists and the runtime helper are shared with the native recipe.

Never glob `/tmp` or `/var/tmp` in `%post` cleanup: under
`singularity build` those hold the builder's own busy mounts and `rm`
aborts on them. Our own `/tmp` downloads are removed at their use sites.
