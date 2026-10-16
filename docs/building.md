# Building images

With Docker 17.05 or higher (BuildKit recommended for cache mounts and
`ccache` speedups: `DOCKER_BUILDKIT=1`):

```bash
export release=jan26a
docker build \
       --tag abeelen/gildas:${release} \
       --target gildas \
       --build-arg release=${release} \
       --build-arg MAKE_JOBS=$(nproc) \
       -f Dockerfile.alpine .
# Only add --tag abeelen/gildas:latest for the newest release.
```

Alpine (`Dockerfile.alpine`) is the default; append `-debian` to the
tags and use `-f Dockerfile` for the opt-in Debian-based images.
`Dockerfile`s for this project are available at
https://github.com/abeelen/gildas.git

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
  `/usr/local/bin` wrappers). Set `WITH_IMAGER=0` to skip it.
- `IMAGER_VERSION` (default `last`): IMAGER tarball version, e.g.
  `oct26` (see https://imager.oasu.u-bordeaux.fr). Note the schemes
  differ — GILDAS releases carry a letter suffix (`oct26a`) while
  IMAGER versions do not (`oct26`) — so never reuse the GILDAS
  release name here; leave `last` or pin an explicit IMAGER version.
- `GAG_USE_SANITIZE=no` (default): leave disabled (crashes otherwise).

## PIIC

Starting with oct19a, PIIC is included in the container. The multi-stage
`Dockerfile`s provide two main targets:

- `gildas` : image without PIIC
- `gildas-piic` : image including PIIC

To build the PIIC image for a given release (missing PIIC tarballs
warn instead of silently producing a GILDAS-only image thanks to the
`curl -fSL --retry` check):

```bash
export release=jan26a
docker build \
       --tag abeelen/gildas:${release}-piic \
       --target gildas-piic \
       --build-arg release=${release} \
       -f Dockerfile.alpine .
# Only add --tag abeelen/gildas:latest-piic for the newest release.
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
       -f Dockerfile .

# GILDAS + PIIC, Debian base image
docker build \
       --tag abeelen/gildas:${release}-piic-debian \
       --target gildas-piic \
       --build-arg release=${release} \
       -f Dockerfile .
```

## Check available tags on Docker Hub

```bash
curl -L -s 'https://registry.hub.docker.com/v1/repositories/abeelen/gildas/tags' | sed -e 's/[][]//g' -e 's/"//g' -e 's/ //g' | tr '}' '\n'  | awk -F: '{print $3}'
```

## Native Singularity builds

| Method | Command | Pros | Cons |
|--------|---------|------|------|
| From Docker Hub | `singularity build gildas-jan26a.sif docker://abeelen/gildas:jan26a` | fast, no compiler needed, bit-identical to Docker | needs the Docker tag to exist |
| Native (`gildas-natif.def`) | `SINGULARITYENV_GILDAS_RELEASE=jan26a singularity build gildas-jan26a-natif.sif gildas-natif.def` | no Docker involved, any (incl. archived) release with `SINGULARITYENV_GILDAS_URL`/`SINGULARITYENV_PIIC_URL` overrides, `MAKE_JOBS`/`WITH_TEXLIVE` tunable | full recompile (~slow), needs root or `--fakeroot` |
| Native Alpine (`gildas-natif-alpine.def`) | `SINGULARITYENV_GILDAS_RELEASE=jan26a singularity build gildas-jan26a-natif-alpine.sif gildas-natif-alpine.def` | no Docker involved, slim musl image with local musl patches | full recompile (~slow), needs root or `--fakeroot` |

```bash
# Native build from tarballs (no Docker involved), with configurable
# release and URLs (see %environment in gildas-natif.def).
# NOTE: SINGULARITYENV_ prefix is mandatory, plain VAR=... never reaches
# %post (silently dropped). Easiest: use `./gildas_release.py --natif`,
# which generates the right command (IMAGER pinned, archive URLs added).
export SINGULARITYENV_GILDAS_RELEASE=jan26a
export SINGULARITYENV_GILDAS_URL=https://www.iram.fr/~gildas/dist
export SINGULARITYENV_PIIC_URL=https://www.iram.fr/~gildas/dist
export SINGULARITYENV_MAKE_JOBS=$(nproc)
# export SINGULARITYENV_WITH_TEXLIVE=1  # only if you need the pipeline (texlive in image)
sudo -E singularity build gildas-${SINGULARITYENV_GILDAS_RELEASE}-natif.sif gildas-natif.def

# Native Alpine build (musl patches from Dockerfile.alpine included)
sudo -E singularity build gildas-${SINGULARITYENV_GILDAS_RELEASE}-natif-alpine.sif gildas-natif-alpine.def
```

The `.def` recipes mirror the Dockerfiles: `gildas-latest.def` bootstraps
from Docker Hub (runscript + `%apprun` shortcuts), `gildas-natif*.def`
compile from tarballs (PIIC bundled when its tarball exists upstream).

Never glob `/tmp` or `/var/tmp` in `%post` cleanup: under
`singularity build` those hold the builder's own busy mounts and `rm`
aborts on them. Our own `/tmp` downloads are removed at their use sites.
