Build
=====

Build the developpement image :

```bash
export release=mar18c
docker build -f Dockerfile.dev . --build-arg release=$release
```

tag it
```bash
docker tag $release abeelen/gildas:build
```

and make a tar from the files
```
docker run -it -u $(id -u) \
    -v "/home/$USER:/home/$USER" \
    abeelen/gildas:build tar cvzf $PWD/gildas-exe-$release.tar.gz /gildas-exe-$release
```

Build the execution image :
```bash
docker build -f Dockerfile . --build-arg release=$release
```

Finally tag this one
```bash
docker tag $release abeelen/gildas:$release
```


Usage
=====

To launch gildas, simply launch :


```bash
docker run -it --hostname "gildas" -u $(id -u) \
       -e DISPLAY=${DISPLAY} -e HOME=${HOME} -e USER=${USER} \
       -v "/etc/passwd:/etc/passwd:ro" \
       -v "/home/$USER:/home/$USER" \
       -v "/tmp/.X11-unix:/tmp/.X11-unix" \
       abeelen/gildas:feb17c /bin/bash
```