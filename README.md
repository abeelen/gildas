# Build

## Two stage build
(Obsolete, see commit older than e86aabb9c4a207889685875f345f1a0b8b0cbdbf) 

## One stage build

With Docker 17.05 or higher :

```bash
export release=mar18c
docker build --tag abeelen/gildas:$release --tag abeelen/gildas:latest --build-arg release=$release -f Dockerfile .
```

## PIIC

Starting with oct19a, PIIC is included in the container, with 2 possible arguments, `ARCHIVE=1` will look for gildas in the archive , while `PIIC_ARCHIVE`, will look for piic in the archive

```bash
export release=oct19a
docker build --tag abeelen/gildas:${release} --tag abeelen/gildas:latest --build-arg ARCHIVE=1 --build-arg release=$release -f Dockerfile .
```
will look for gildas oct19a in the archive, while PIIC will be downloaded from the regular directory

# Usage

To launch the gildas container, type :

```bash
docker run -it \
       --hostname "gildas" --user $(id -u):$(id -g) \
       --workdir="/home/$USER" --env HOME=${HOME} --env USER=${USER} --env DISPLAY=${DISPLAY} \
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
will do the same for MacOS users

Starting from the oct19a, one has to define which gildas environement to use either `gaggildas` or `gagpiic` before launching gildas command. It is easier to create usefull aliases in `~/.bashrc`

```bash

alias gildas_docker='docker run -it \
       --hostname "gildas" --user $(id -u):$(id -g) \
       --workdir="/home/$USER" --env HOME=${HOME} --env USER=${USER} --env DISPLAY=${DISPLAY} \
       --volume "/etc/passwd:/etc/passwd:ro" \
       --volume "/home/$USER:/home/$USER" \
       --volume "/Users/$USER:/Users/$USER" \
       --volume "/tmp/.X11-unix:/tmp/.X11-unix" \
       abeelen/gildas:latest'

alias clic='gildas_docker "gaggildas; clic"'
alias mapping='gildas_docker "gaggildas; mapping"'
alias astro='gildas_docker "gaggildas; astro"'
alias piic='gildas_docker "gagpiic; piic"'
[...]
```