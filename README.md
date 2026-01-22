
This is a docker container of the [IRAM/gildas](https://www.iram.fr/IRAMFR/GILDAS/) software suite.

Pre-built images are available on Docker Hub: https://hub.docker.com/r/abeelen/gildas

You can find many tags corresponding to several release version of the software. Alternatively you can use the `latest` or `latest-piic` tag to use the most up-to-date version of the software on this repository.

There are two main tag families: regular release tags and the `*-piic` tags containing the `piic` software. Alpine-based variants are available with an additional `-alpine` suffix.

You can use it either with Docker or simply with Singularity.

## Quick start

```bash
# Singularity, GILDAS without PIIC (latest Debian-based image)
singularity run docker://abeelen/gildas:latest mapping

# Singularity, GILDAS with PIIC
singularity run docker://abeelen/gildas:latest-piic "gagpiic; piic"

# Docker, GILDAS without PIIC
docker run --rm -it abeelen/gildas:latest mapping

# Docker, GILDAS with PIIC
docker run --rm -it abeelen/gildas:latest-piic "gagpiic; piic"
```

## Docker tags overview

| Tag example             | Base   | Content       | Notes                         |
|-------------------------|--------|---------------|-------------------------------|
| `latest`                | Debian | GILDAS        | Convenience tag               |
| `jan26a`                | Debian | GILDAS        | Specific release              |
| `latest-piic`           | Debian | GILDAS + PIIC | Convenience tag with PIIC     |
| `jan26a-piic`           | Debian | GILDAS + PIIC | Specific release with PIIC    |
| `latest-alpine`         | Alpine | GILDAS        | Alpine base image             |
| `jan26a-alpine`         | Alpine | GILDAS        | Specific release, Alpine      |
| `latest-piic-alpine`    | Alpine | GILDAS + PIIC | Alpine base image with PIIC   |
| `jan26a-piic-alpine`    | Alpine | GILDAS + PIIC | Specific release, Alpine+PIIC |

## Using the images

### Usage with Singularity

You can simply run any of the gildas application with:

```bash
singularity run docker://abeelen/gildas:latest {application}
```

or, if you want to use piic
```bash
singularity run docker://abeelen/gildas:latest-piic "gagpiic; piic"
```

You can also build a native Singularity image (SIF) from the Docker
image or from one of the provided definition files (`gildas-latest.def`
or `gildas-natif.def`).

```bash
# Build a SIF directly from the Docker image on Docker Hub
singularity build gildas-latest.sif docker://abeelen/gildas:latest

# Or, using the Singularity definition file (keeps custom apprun entries)
singularity build gildas-latest.sif gildas-latest.def

# Native build from tarballs (no Docker involved), with configurable
# release and URLs (see %environment in gildas-natif.def)
export GILDAS_RELEASE=jan26a
export GILDAS_URL=https://www.iram.fr/~gildas/dist
export PIIC_URL=https://www.iram.fr/~gildas/dist
sudo singularity build gildas-${GILDAS_RELEASE}-natif.sif gildas-natif.def

# Then, run interactively (GILDAS shell)
singularity shell gildas-latest.sif

# Run a specific GILDAS application via the default runscript
singularity run gildas-latest.sif "mapping"

# Or via apprun shortcuts (defined in gildas_docker.def)
singularity run --app astro   gildas-latest.sif
singularity run --app class   gildas-latest.sif
singularity run --app clic    gildas-latest.sif
singularity run --app imager  gildas-latest.sif
singularity run --app mapping gildas-latest.sif
singularity run --app piic    gildas-latest.sif
```

### Usage with Docker

To launch the gildas container, type :

```bash
xhost +SI:localuser:$(id -un)
docker run -it \
       --hostname "gildas" --user $(id -u):$(id -g) \
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

You can then use any of the gildas command.

Starting from the oct19a, one has to define which gildas environement to use either `gaggildas` or `gagpiic` before launching gildas command.

It is easier to create usefull aliases in `~/.bashrc`

```bash
# With PIIC
alias gildas_docker='docker run -it \
       --hostname "gildas" --user $(id -u):$(id -g) \
       --workdir="$HOME" \
       --env HOME="$HOME" --env USER="$USER" \
       --env DISPLAY \
       --env WAYLAND_DISPLAY \
       --env XDG_RUNTIME_DIR \
       --env XAUTHORITY \
       --volume "/etc/passwd:/etc/passwd:ro" \
       --volume "$HOME:$HOME" \
       --volume "/tmp/.X11-unix:/tmp/.X11-unix" \
       --volume "$XDG_RUNTIME_DIR:$XDG_RUNTIME_DIR" \
       abeelen/gildas:latest-piic'

alias clic='gildas_docker "gaggildas; clic"'
alias mapping='gildas_docker "gaggildas; mapping"'
alias astro='gildas_docker "gaggildas; astro"'
alias piic='gildas_docker "gagpiic; piic"'
[...]
alias imager='gildas_docker "gaggildas; imager"'
```

Alternatively if you do not need PIIC,

```bash
# Without PIIC
alias gildas_docker_nopiic='docker run -it \
       --hostname "gildas" --user $(id -u):$(id -g) \
       --workdir="$HOME" \
       --env HOME="$HOME" --env USER="$USER" \
       --env DISPLAY \
       --env WAYLAND_DISPLAY \
       --env XDG_RUNTIME_DIR \
       --env XAUTHORITY \
       --volume "/etc/passwd:/etc/passwd:ro" \
       --volume "$HOME:$HOME" \
       --volume "/tmp/.X11-unix:/tmp/.X11-unix" \
       --volume "$XDG_RUNTIME_DIR:$XDG_RUNTIME_DIR" \
       abeelen/gildas:latest'

alias clic='gildas_docker_nopiic clic'
alias mapping='gildas_docker_nopiic mapping'
alias astro='gildas_docker_nopiic astro'
[...]
alias imager='gildas_docker_nopiic imager'
```


## Building images

With Docker 17.05 or higher :

```bash
export release=jan26a
docker build \
       --tag abeelen/gildas:${release} \
       --tag abeelen/gildas:latest \
       --target gildas \
       --build-arg release=${release} \
       -f Dockerfile .
```

### PIIC

Starting with oct19a, PIIC is included in the container. The multi-stage
`Dockerfile` provides two main targets:

- `gildas` : image without PIIC
- `gildas-piic` : image including PIIC

To build the PIIC image for a given release:

```bash
export release=jan26a
docker build \
       --tag abeelen/gildas:${release}-piic \
       --tag abeelen/gildas:latest-piic \
       --target gildas-piic \
       --build-arg release=${release} \
       -f Dockerfile .
```

The default build uses the main GILDAS distribution URLs. For archived
releases, the helper script `gildas_release.py` (see below) will
generate the appropriate `--build-arg GILDAS_URL=...` and
`--build-arg PIIC_URL=...` options to point to the archive trees.

`Dockerfile` for this project are available at https://github.com/abeelen/gildas.git

### Alpine-based images

In addition to the default Debian-based images built from `Dockerfile`,
this repository also provides Alpine variants built from
`Dockerfile.alpine`.

The recommended tags are:

```bash
export release=jan26a

# GILDAS only, Alpine base image
docker build \
       --tag abeelen/gildas:${release}-alpine \
       --tag abeelen/gildas:latest-alpine \
       --target gildas \
       --build-arg release=${release} \
       -f Dockerfile.alpine .

# GILDAS + PIIC, Alpine base image
docker build \
       --tag abeelen/gildas:${release}-piic-alpine \
       --tag abeelen/gildas:latest-piic-alpine \
       --target gildas-piic \
       --build-arg release=${release} \
       -f Dockerfile.alpine .
```

The helper script `gildas_release.py` can also generate commands for the
Alpine images using the `--alpine` toggle:

```bash
# All missing releases (GILDAS and PIIC), Alpine variants
./gildas_release.py --alpine

# Single release, Alpine variants
./gildas_release.py --release jan26a --alpine
```

When `--alpine` is used, the script produces tags with an `-alpine`
suffix (for example `jan26a-alpine`, `jan26a-piic-alpine`, and their
corresponding `latest-*-alpine` tags) and looks for these tags on
Docker Hub.

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
# ordered from oldest to newest
./gildas_release.py

# Same, but including releases that are already present on Docker Hub
./gildas_release.py --force

# Commands for a single release (and its -piic variant if available)
./gildas_release.py --release jan26a
```

In all cases, the script emits commands for both the `gildas` and
`gildas-piic` targets when the corresponding tarballs exist upstream,
and adds the correct `GILDAS_URL` / `PIIC_URL` archive URLs when
necessary.

The legacy wrapper `check_new_release.py` is kept for backward
compatibility; it simply calls the default behaviour of
`gildas_release.py`.

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
       `latest-piic-alpine`) and start the PIIC environment with `gagpiic`
       before launching `piic`.
