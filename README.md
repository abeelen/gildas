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

alias gildas_docker='docker run -it \
       --hostname "gildas" --user $(id -u):$(id -g) \
       --workdir="/home/$USER" --env HOME=${HOME} --env USER=${USER} --env DISPLAY=${DISPLAY} \
       --volume "/etc/passwd:/etc/passwd:ro" \
       --volume "/home/$USER:/home/$USER" \
       --volume "/Users/$USER:/Users/$USER" \
       --volume "/tmp/.X11-unix:/tmp/.X11-unix" \
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

alias gildas_docker='docker run -it \
       --hostname "gildas" --user $(id -u):$(id -g) \
       --workdir="/home/$USER" --env HOME=${HOME} --env USER=${USER} --env DISPLAY=${DISPLAY} \
       --volume "/etc/passwd:/etc/passwd:ro" \
       --volume "/home/$USER:/home/$USER" \
       --volume "/Users/$USER:/Users/$USER" \
       --volume "/tmp/.X11-unix:/tmp/.X11-unix" \
       abeelen/gildas:latest'

alias clic='gildas_docker clic'
alias mapping='gildas_docker mapping'
alias astro='gildas_docker astro'
[...]
alias imager='gildas_docker imager"'
```

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


`Dockerfile` for this project are available at https://git.ias.u-psud.fr/abeelen/gildas

## Check available tags on dockerhub

```bash
curl -L -s 'https://registry.hub.docker.com/v1/repositories/abeelen/gildas/tags' | sed -e 's/[][]//g' -e 's/"//g' -e 's/ //g' | tr '}' '\n'  | awk -F: '{print $3}'
```

on the gildas page : 
```bash
# to get the gildas release
./_gildas_release.py
# to get the piic release
./gildas_release.py --package piic
# To look in the archive directory
./gildas_release.py --archive
```