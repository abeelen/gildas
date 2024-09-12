#!/usr/bin/env python3
import requests
import click
from bs4 import BeautifulSoup

from gildas_release import gildas_release

s = requests.Session()
r = s.get("https://registry.hub.docker.com/v2/repositories/abeelen/gildas/tags/?page_size=1000")
tags = [item["name"] for item in r.json()["results"] if item["name"] not in ["latest", "build"]]

_gildas = gildas_release("gildas")
_archived_gildas = gildas_release("gildas", archive=True)
_piic = gildas_release("piic")
_archived_piic = gildas_release("piic", archive=True)


def is_in_archive(release, piic=False):

    _main = _gildas
    _archive = _archived_gildas
    if piic is True:
        _main = _piic
        _archive = _archived_piic

    if release in _main:
        return ""
    elif release in _archive:
        if piic is False:
            return "--build-arg ARCHIVE=1 "
        else:
            return "--build-arg PIIC_ARCHIVE=1 "
    else:
        raise FileNotFoundError("gildas release not found in archive")


# With or without PIIC
print("# Without piic")
for release in _archived_gildas + _gildas:
    if release not in tags:
        print("# * {} not in dockerhub".format(release))
        cmd = "export release={}; ".format(release)
        cmd += "docker build --tag abeelen/gildas:${release} "
        cmd += "--target gildas "
        cmd += is_in_archive(release)
        cmd += "--build-arg release=$release -f Dockerfile . "
        cmd += "&& docker push abeelen/gildas:${release}"
        print(cmd)

# Force with PIIC
print("# With piic")
for release in _archived_piic + _piic:
    if "{}-piic".format(release) in tags:
        continue
    try:
        _ = is_in_archive(release)
    except FileNotFoundError:
        continue

    print("# * {} not in dockerhub launch :".format(release))
    cmd = "export release={}; ".format(release)
    cmd += "docker build --tag abeelen/gildas:${release}-piic "
    cmd += "--target gildas-piic "
    cmd += is_in_archive(release) + is_in_archive(release, piic=True)

    cmd += "--build-arg release=$release -f Dockerfile . "
    cmd += "&& docker push abeelen/gildas:${release}-piic"
    print(cmd)
