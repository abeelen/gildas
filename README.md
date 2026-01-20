
This is a docker container of the [IRAM/gildas](https://www.iram.fr/IRAMFR/GILDAS/) software suite.

You can find many tags corresponding to several release version of the software. Alternatively you can use the `latest` or `piic-latest` tag to use the most update version of the software on this repository.

They are two main branches/tag lines with regular release tag or the `*-piic` tag containing the `piic` software.


You can use it either with docker or simply with singularity.

# Usage with Singularity

You can simply run any of the gildas application with:

```bash
singularity run docker://abeelen/gildas:latest {application}
```

or, if you want to use piic
```bash
singularity run docker://abeelen/gildas:latest-piic "gagpiic; piic"
```


# Usage with Docker

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


# Build

## Two stage build
(Obsolete, see commit older than e86aabb9c4a207889685875f345f1a0b8b0cbdbf) 

## One stage build

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

## PIIC

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

`Dockerfile` for this project are available at https://git.ias.u-psud.fr/abeelen/gildas

## Check available tags on dockerhub

```bash
curl -L -s 'https://registry.hub.docker.com/v1/repositories/abeelen/gildas/tags' | sed -e 's/[][]//g' -e 's/"//g' -e 's/ //g' | tr '}' '\n'  | awk -F: '{print $3}'
```

## Helper script for releases and builds

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
