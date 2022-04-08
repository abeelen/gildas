#!/usr/bin/env python3
import requests
import click
from bs4 import BeautifulSoup

def gildas_release(package, archive=False):
    uri = 'https://www.iram.fr/~gildas/dist/'

    if archive and package == "gildas":
        uri = 'https://www.iram.fr/~gildas/dist/archive/gildas'
    elif archive and package == "piic":
        uri = 'https://www.iram.fr/~gildas/dist/archive/piic'

    if package == 'gildas':
        package = 'gildas-src'
    elif package == 'piic':
        package = 'piic-exe'
    else:
        click.echo('Unknown package !')

    s = requests.Session()
    r = s.get(uri)
    soup = BeautifulSoup(r.text, features="lxml")
    links = [link.attrs['href'] for link in soup.find_all('a') if '.tar.xz' in link.attrs['href']]
    releases = [filename.split('-')[2].split('.')[0] for filename in links if filename.startswith(package)]

    # Cleaning...
    releases = [release for release in releases if release != 'ifort']
    
    return releases

@click.command()
@click.option('--package', type=click.Choice(['gildas', 'piic']), default='gildas')
@click.option('--archive', is_flag=True)
def gildas_release_click(package, archive=False):
    releases = gildas_release(package, archive)
    click.echo(" ".join(releases))


if __name__ == '__main__':
    gildas_release_click()
