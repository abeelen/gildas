# Build

## Two stages build (deprecated)

Build the developpement image :

```bash
export release=mar18c
docker build --tag abeelen/gildas:build  --build-arg release=$release -f Dockerfile.dev .
```

extract the compiled files

```
docker container create --name extract abeelen/gildas:build
docker container cp extract:/gildas-exe-$release gildas-exe-$release
docker container rm -f extract
```

<!---
extract the compiled files
 ```
 docker run -it -u $(id -u) \
     -v "/home/$USER:/home/$USER" \
     abeelen/gildas:build tar cvzf $PWD/gildas-exe-$release.tar.gz /gildas-exe-$release
 ```
--->

Build the execution image :
```bash
docker build --tag abeelen/gildas:$release --tag abeelen/gildas:latest --build-arg release=$release -f Dockerfile .
```

## One stage build

With Docker 17.05 or higher :

```bash
export release=mar18c
docker build --tag abeelen/gildas:$release --tag abeelen/gildas:latest --build-arg release=$release -f Dockerfile.multistage .
```

# Usage


To launch gildas, simply launch :


```bash
docker run -it --hostname "gildas" -u $(id -u) \
       -e DISPLAY=${DISPLAY} -e HOME=${HOME} -e USER=${USER} \
       -v "/etc/passwd:/etc/passwd:ro" \
       -v "/home/$USER:/home/$USER" \
       -v "/Users/$USER:/Users/$USER" \
       -v "/tmp/.X11-unix:/tmp/.X11-unix" \
       abeelen/gildas:latest /bin/bash --rcfile /etc/bash.bashrc
```
to get a working gildas installation

MacOS users should also open remote display access : 
```bash
open -a XQuartz
# (In the XQuartz preferences, go to the “Security” tab and make sure you’ve got “Allow connections from network clients” ticked)
ip=$(ifconfig en0 | grep inet | awk '$1=="inet" {print $2}’)
xhost + $ip
```
