
This is a docker container of the [IRAM/gildas](https://www.iram.fr/IRAMFR/GILDAS/) software suite.

Pre-built images are available on Docker Hub: https://hub.docker.com/r/abeelen/gildas

You can find many tags corresponding to several release version of the software. Alternatively you can use the `latest` or `latest-piic` tag to use the most up-to-date version of the software on this repository.

There are two main tag families: regular release tags and the `*-piic` tags containing the `piic` software. Alpine is the default base image; Debian-based variants carry an additional `-debian` suffix.

You can use it either with Docker or simply with Singularity.

## Quick start

```bash
# Singularity or Docker: every program runs directly by name.
# GILDAS programs
singularity run docker://abeelen/gildas:latest mapping
docker run --rm -it abeelen/gildas:latest mapping

# PIIC (on a *-piic image)
singularity run docker://abeelen/gildas:latest-piic piic
docker run --rm -it abeelen/gildas:latest-piic piic

# Standalone IMAGER (bundled in all images)
singularity run docker://abeelen/gildas:latest imager
docker run --rm -it abeelen/gildas:latest imager
docker run --rm -it abeelen/gildas:latest viewer
```

## Docker tags overview

| Tag example             | Base   | Content       | Notes                         |
|-------------------------|--------|---------------|-------------------------------|
| `latest`                | Alpine | GILDAS        | Convenience tag (default)     |
| `jan26a`                | Alpine | GILDAS        | Specific release              |
| `latest-piic`           | Alpine | GILDAS + PIIC | Convenience tag with PIIC     |
| `jan26a-piic`           | Alpine | GILDAS + PIIC | Specific release with PIIC    |
| `latest-debian`         | Debian | GILDAS        | Opt-in Debian base image      |
| `jan26a-debian`         | Debian | GILDAS        | Specific release, Debian      |
| `latest-piic-debian`    | Debian | GILDAS + PIIC | Opt-in Debian base with PIIC  |
| `jan26a-piic-debian`    | Debian | GILDAS + PIIC | Specific release, Debian+PIIC |

## Using the images

### Usage with Singularity

You can simply run any of the gildas application with:

```bash
singularity run docker://abeelen/gildas:latest {application}
```

or, on a `*-piic` image, `piic` (and `imager` / `viewer` work on all
images):

```bash
singularity run docker://abeelen/gildas:latest-piic piic
singularity run docker://abeelen/gildas:latest imager
```

Two ways to build a local SIF image (Debian or Alpine base):

| Method | Command | Pros | Cons |
|--------|---------|------|------|
| From Docker Hub | `singularity build gildas-jan26a.sif docker://abeelen/gildas:jan26a` | fast, no compiler needed, bit-identical to Docker | needs the Docker tag to exist |
| Native (`gildas-natif.def`) | `GILDAS_RELEASE=jan26a singularity build gildas-jan26a-natif.sif gildas-natif.def` | no Docker involved, any (incl. archived) release with `GILDAS_URL`/`PIIC_URL` overrides, `MAKE_JOBS`/`WITH_TEXLIVE` tunable | full recompile (~slow), needs root or `--fakeroot` |
| From Docker Hub | `singularity build gildas-jan26a.sif docker://abeelen/gildas:jan26a` | fast, no compiler needed, bit-identical to Docker | needs the Docker tag to exist |
| Native Alpine (`gildas-natif-alpine.def`) | `GILDAS_RELEASE=jan26a singularity build gildas-jan26a-natif-alpine.sif gildas-natif-alpine.def` | no Docker involved, slim musl image with local musl patches | full recompile (~slow), needs root or `--fakeroot` |

The helper script generates the `docker://` commands for you
(`./gildas_release.py --singularity`, add `--debian` for the Debian tags).

```bash
# Build a SIF directly from the Docker image on Docker Hub
singularity build gildas-latest.sif docker://abeelen/gildas:latest

# Or, using the Singularity definition file
singularity build gildas-latest.sif gildas-latest.def

# Native build from tarballs (no Docker involved), with configurable
# release and URLs (see %environment in gildas-natif.def)
export GILDAS_RELEASE=jan26a
export GILDAS_URL=https://www.iram.fr/~gildas/dist
export PIIC_URL=https://www.iram.fr/~gildas/dist
export MAKE_JOBS=$(nproc)
# export WITH_TEXLIVE=1  # only if you need the pipeline (texlive in image)
sudo singularity build gildas-${GILDAS_RELEASE}-natif.sif gildas-natif.def

# Native Alpine build (musl patches from Dockerfile.alpine included)
sudo singularity build gildas-${GILDAS_RELEASE}-natif-alpine.sif gildas-natif-alpine.def

# Then, run interactively (GILDAS shell)
singularity shell gildas-latest.sif

# Run a specific GILDAS application via the default runscript
singularity run gildas-latest.sif "mapping"

# Or via apprun shortcuts (defined in gildas-latest.def / gildas-natif.def)
singularity run --app astro   gildas-latest.sif
singularity run --app class   gildas-latest.sif
singularity run --app clic    gildas-latest.sif
singularity run --app mapping gildas-latest.sif
singularity run --app piic    gildas-latest.sif
singularity run --app imager  gildas-latest.sif
singularity run --app viewer  gildas-latest.sif
```

Every program runs directly by name: GILDAS tools from the default
environment, IMAGER/PIIC tools via self-contained `/usr/local/bin`
wrappers that select their own tree (a flavor never shadows a GILDAS
program of the same name).

### Usage with Docker

To launch the gildas container, type :

```bash
xhost +SI:localuser:$(id -un)
docker run -it \
       --hostname "gildas" --user $(id -u):$(id -g) \
       --ipc=host \
       --workdir="/home/$USER" --env HOME=${HOME} --env USER=${USER}
       --env DISPLAY=${DISPLAY} --env WAYLAND_DISPLAY=${WAYLAND_DISPLAY} \
       --env XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR} --env XAUTHORITY=${XAUTHORITY} \
       --volume "/etc/passwd:/etc/passwd:ro" \
       --volume "/home/$USER:/home/$USER" \
       --volume "/Users/$USER:/Users/$USER" \
       --volume "/tmp/.X11-unix:/tmp/.X11-unix" \
       abeelen/gildas:latest /bin/bash --rcfile /etc/bash.bashrc
```

where
```bash
-volume "/home/$USER:/home/$USER" 
```
will mount the user home for Unix Users
```bash
-volume "/Users/$USER:/Users/$USER"
```
will do the same for MacOS users. MacOS users should also open remote display access : 

```bash
open -a XQuartz
# (In the XQuartz preferences, go to the “Security” tab and make sure you’ve got “Allow connections from network clients” ticked)
ip=$(ifconfig en0 | grep inet | awk '$1=="inet" {print $2}’)
xhost + $ip
```

You can then use any of the gildas command directly by name — GILDAS,
IMAGER and (on `*-piic` images) PIIC programs all work with no prefix,
each selecting its own installation tree behind the scenes.

It is easier to create usefull aliases in `~/.bashrc`

```bash
# With PIIC
alias gildas_docker='docker run -it \
       --hostname "gildas" --user $(id -u):$(id -g) \
       --ipc=host \
       --workdir="$PWD" \
       --env HOME="$HOME" --env USER="$USER" \
       --env DISPLAY \
       --env WAYLAND_DISPLAY \
       --env XDG_RUNTIME_DIR \
       --env XAUTHORITY \
       --volume "/etc/passwd:/etc/passwd:ro" \
       --volume "$HOME:$HOME" \
       --volume "$PWD:$PWD" \
       --volume "/tmp/.X11-unix:/tmp/.X11-unix" \
       --volume "$XDG_RUNTIME_DIR:$XDG_RUNTIME_DIR" \
       abeelen/gildas:latest-piic'

alias clic='gildas_docker clic'
alias mapping='gildas_docker mapping'
alias astro='gildas_docker astro'
alias piic='gildas_docker piic'
alias cube='gildas_docker cube'
[...]
alias imager='gildas_docker imager'
alias viewer='gildas_docker viewer'
```

Alternatively if you do not need PIIC,

```bash
# Without PIIC
alias gildas_docker='docker run -it \
       --hostname "gildas" --user $(id -u):$(id -g) \
       --ipc=host \
       --workdir="$PWD" \
       --env HOME="$HOME" --env USER="$USER" \
       --env DISPLAY \
       --env WAYLAND_DISPLAY \
       --env XDG_RUNTIME_DIR \
       --env XAUTHORITY \
       --volume "/etc/passwd:/etc/passwd:ro" \
       --volume "$HOME:$HOME" \
       --volume "$PWD:$PWD" \
       --volume "/tmp/.X11-unix:/tmp/.X11-unix" \
       --volume "$XDG_RUNTIME_DIR:$XDG_RUNTIME_DIR" \
       abeelen/gildas:latest'

alias clic='gildas_docker clic'
alias mapping='gildas_docker mapping'
alias astro='gildas_docker astro'
alias cube='gildas_docker cube'
[...]
alias imager='gildas_docker imager'
alias viewer='gildas_docker viewer'
```


## Building images

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

(Alpine is the default; append `-debian` to the tags and use
`-f Dockerfile` for the opt-in Debian-based images.)

Build args:

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
  `gildas_release.py` couples them automatically (`oct26a` →
  `--build-arg IMAGER_VERSION=oct26`, fallback `last` with a warning;
  override with `--imager-version`). `IMAGER_URL` overrides its
  download base (`https://share.oasu.u-bordeaux.fr/imager`). The
  resolved version is recorded in the image at `/etc/imager-version`.
- `GAG_USE_SANITIZE=no` (default): leave disabled (crashes otherwise).

### PIIC

Starting with oct19a, PIIC is included in the container. The multi-stage
`Dockerfile` provides two main targets:

- `gildas` : image without PIIC
- `gildas-piic` : image including PIIC

To build the PIIC image for a given release (missing PIIC tarballs now
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
use `./gildas_release.py --piic --archive` to list PIIC build commands
(`--piic` alone lists PIIC commands for all known releases).

The default build uses the main GILDAS distribution URLs. For archived
releases, the helper script `gildas_release.py` (see below) will
generate the appropriate `--build-arg GILDAS_URL=...` and
`--build-arg PIIC_URL=...` options to point to the archive trees.

`Dockerfile` for this project are available at https://github.com/abeelen/gildas.git

### Debian-based images (opt-in)

The default images are Alpine-based, built from `Dockerfile.alpine`
(tracking `alpine:latest`, only `cfitsio` from edge/testing). Debian
variants are built from `Dockerfile` with an additional `-debian`
suffix:

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
(`latest-debian` / `latest-piic-debian` should only be added for the
newest release; `gildas_release.py --debian` does this automatically.)

The helper script `gildas_release.py` targets Alpine by default;
add `--debian` for the Debian tags:

```bash
# All missing releases (GILDAS and PIIC), Debian variants
./gildas_release.py --debian

# Single release, Debian variants
./gildas_release.py --release jan26a --debian
```

### Check available tags on dockerhub

```bash
curl -L -s 'https://registry.hub.docker.com/v1/repositories/abeelen/gildas/tags' | sed -e 's/[][]//g' -e 's/"//g' -e 's/ //g' | tr '}' '\n'  | awk -F: '{print $3}'
```

### Helper script for releases and builds

The script `gildas_release.py` inspects the IRAM GILDAS/PIIC download
directories and the Docker Hub tags for `abeelen/gildas`, then prints
ready-to-run `docker build` / `docker push` commands.

Typical usage:

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

# Commands for a single release (and its -piic variant if available).
# Tags `latest` by default; opt out with --no-tag-latest.
./gildas_release.py --release jan26a
./gildas_release.py --release jan26a --no-tag-latest

# Singularity: emit `singularity build ... docker://...` commands
# (lists all known releases, since SIFs pull from Docker Hub)
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

# Debian variants, custom repo/Dockerfile, JSON output, direct execution
./gildas_release.py --debian
./gildas_release.py --repo myuser/gildas --dockerfile Dockerfile.custom
./gildas_release.py --json
./gildas_release.py --release jan26a --execute
./gildas_release.py -v   # info logs, -vv for debug
```

In all cases, the script emits commands for both the `gildas` and
`gildas-piic` targets when the corresponding tarballs exist upstream,
and adds the correct `GILDAS_URL` / `PIIC_URL` archive URLs when
necessary. Commands no longer use `export release=...;$release` shell
tricks: the release is inlined and quoted, empty `--build-arg`s are
dropped, and `latest*` tags go to the newest release per family
(`latest` for GILDAS, `latest-piic` for GILDAS+PIIC, tracked
independently; single `--release` tags `latest` by default, opt out
with `--no-tag-latest`). Archived releases are excluded unless
`--archive` is given (PIIC commands often need it, as PIIC releases lag
behind GILDAS ones — see `--piic` above).

### Container entrypoint

`docker-entrypoint.sh` sources `/etc/gildas-env.sh` (default GILDAS
environment), then `exec`s the given command. Every program runs
directly by name — no prefixes, no environment switching on your side:

```bash
docker run --rm -it abeelen/gildas:latest mapping
docker run --rm -it abeelen/gildas:latest imager
docker run --rm -it abeelen/gildas:latest viewer
docker run --rm -it abeelen/gildas:latest-piic piic
```

(Programs from the standalone IMAGER tree and the PIIC tree are
self-contained `/usr/local/bin` wrappers selecting their own tree;
a wrapper is only created when it does not shadow a GILDAS program.)

## Troubleshooting / FAQ

- **X11 / display does not work (Docker)**  \
       Ensure you have allowed local X11 connections and mounted the X11
       socket, for example:
       ```bash
       xhost +SI:localuser:$(id -un)
       docker run -it \
                             --env DISPLAY \
                             --volume "/tmp/.X11-unix:/tmp/.X11-unix" \
                             abeelen/gildas:latest clic
       ```

- **I do not see my local files inside the container**  \
       Check that your home directory (or relevant paths) are mounted with
       `--volume` (see the Docker usage examples and aliases).

- **PIIC is not available or not found**  \
       Use a `*-piic` tag (for example `latest-piic`, `jan26a-piic`,
       `latest-piic-debian`) and run `piic` directly. Rebuild the image
       if yours predates the `/usr/local/bin` wrappers.

- **`clic` is missing (images built before the fix)**  \
       Upstream gates `clic` on `GAG_USE_SANITIZE=yes` with gfortran
       (`packages/clic/Makefile` empties its subdirs otherwise), which
       these images keep disabled. Current recipes ungate it
       automatically; rebuild the image to get `clic`.

- **`imager` / `viewer` are missing**  \
       IMAGER left the GILDAS distribution and is now standalone
       (https://imager.oasu.u-bordeaux.fr). Current recipes build and
       bundle it (`/imager-exe`, `WITH_IMAGER` build arg) with
       `/usr/local/bin` wrappers, so `imager` / `viewer` work directly.
       Rebuild the image if yours predates this.

- **`greg` is missing**  \
       Unexpected: `greg` is built and on `PATH` in current images
       (verified in `latest`). Pull the newest tag —
       you are likely running a stale local image.
