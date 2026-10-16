#!/usr/bin/env python3
"""Build/print docker & singularity commands for GILDAS releases."""
import functools
import logging
import re
import shlex
import subprocess
import tarfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

import click
import requests
from bs4 import BeautifulSoup

DOCKER_REPO = "abeelen/gildas"
GILDAS_MAIN_URL = "https://www.iram.fr/~gildas/dist"
GILDAS_ARCHIVE_URL = "https://www.iram.fr/~gildas/dist/archive/gildas"
PIIC_ARCHIVE_URL = "https://www.iram.fr/~gildas/dist/archive/piic"
IMAGER_URL = "https://share.oasu.u-bordeaux.fr/imager"
IMAGER_LAST = "last"
REQUEST_TIMEOUT = 30
LATEST_DEF = "gildas-latest.def"
NATIF_DEF = "gildas-natif.def"

logger = logging.getLogger(__name__)
SECTION_WITHOUT_PIIC = "without-piic"
SECTION_WITH_PIIC = "with-piic"


def _anchors(url: str) -> List[str]:
    r = requests.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return [a.get("href", "") for a in BeautifulSoup(r.text, features="html.parser").find_all("a")]


def gildas_release(package: str, archive: bool = False) -> List[str]:
    """List available GILDAS or PIIC release identifiers.

    Parameters
    ----------
    package : str
        ``"gildas"`` (``gildas-src-*`` tarballs) or ``"piic"``
        (``piic-exe-*`` tarballs).
    archive : bool, optional
        Query the archive tree instead of the main distribution tree.

    Returns
    -------
    list of str
        Sorted release identifiers, e.g. ``"jan26a"``.

    Raises
    ------
    ValueError
        If ``package`` is unknown.
    requests.HTTPError
        If the upstream request fails.
    """
    prefix = {"gildas": "gildas-src", "piic": "piic-exe"}.get(package)
    if prefix is None:
        raise ValueError(f"Unknown package '{package}'")
    url = GILDAS_MAIN_URL + "/"
    if archive:
        url = GILDAS_ARCHIVE_URL if package == "gildas" else PIIC_ARCHIVE_URL
    out = set()
    for href in _anchors(url):
        name = href.rsplit("/", 1)[-1]
        if name.startswith(prefix + "-") and ".tar.xz" in name:
            rel = name[len(prefix) + 1:].split(".tar.xz")[0]
            if rel and not rel.startswith("ifort"):
                out.add(rel)
    return sorted(out)


def imager_release() -> List[str]:
    """List available standalone IMAGER versions.

    Returns
    -------
    list of str
        Sorted IMAGER versions, e.g. ``"oct26"``. Excludes the
        ``"last"``/``"beta"`` aliases and documentation archives.

    Raises
    ------
    requests.HTTPError
        If the upstream request fails.
    """
    out = set()
    for href in _anchors(IMAGER_URL + "/?noscript"):
        name = href.rsplit("/", 1)[-1]
        if name.startswith("imager-") and name.endswith(".tgz"):
            v = name[len("imager-"):-len(".tgz")]
            if v and v not in ("last", "beta") and not v.startswith("doc-"):
                out.add(v)
    return sorted(out)


@functools.lru_cache(maxsize=1)
def _cached_imager_versions() -> tuple:
    return tuple(imager_release())


def imager_version_for_release(release: str, available: Sequence[str] | None = None) -> str:
    """Return the IMAGER version coupled to a GILDAS release.

    Parameters
    ----------
    release : str
        GILDAS release identifier, e.g. ``"oct26a"``.
    available : sequence of str or None, optional
        Known IMAGER versions. Defaults to the live upstream list.

    Returns
    -------
    str
        Matching IMAGER version (trailing letter stripped), or ``"last"``
        when none matches (resolved to a concrete version live when possible).
    """
    live = available is None
    if live:
        available = _cached_imager_versions()
    cand = release[:-1] if release[-1:].isalpha() else release
    if cand in available:
        return cand
    if live:
        resolved = _resolve_imager_alias(IMAGER_LAST)
        if resolved != IMAGER_LAST:
            logger.warning("No IMAGER for '%s', using '%s'", release, resolved)
            return resolved
    logger.warning("No IMAGER for '%s', using '%s'", release, IMAGER_LAST)
    return IMAGER_LAST


@functools.lru_cache(maxsize=4)
def _resolve_imager_alias(alias: str = IMAGER_LAST) -> str:
    """Resolve floating IMAGER alias via first member of its tgz."""
    try:
        with requests.get(f"{IMAGER_URL}/imager-{alias}.tgz", stream=True, timeout=REQUEST_TIMEOUT) as r:
            r.raise_for_status()
            r.raw.decode_content = True
            with tarfile.open(fileobj=r.raw, mode="r|gz") as tar:
                m = tar.next()
                if m and m.name.startswith("imager-src-"):
                    return m.name[len("imager-src-"):].strip("/")
    except Exception as exc:
        logger.debug("Could not resolve IMAGER alias '%s': %s", alias, exc)
    return alias


@functools.lru_cache(maxsize=32)
def _image_labels(tag: str) -> dict | None:
    """Hub image labels, or None on any failure (never fail builds on net errors)."""
    try:
        s = requests.Session()
        url = f"https://registry-1.docker.io/v2/{DOCKER_REPO}/manifests/{tag}"
        h = {"Accept": "application/vnd.docker.distribution.manifest.v2+json,application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.oci.image.index.v1+json"}
        r = s.get(url, headers=h, timeout=REQUEST_TIMEOUT)
        if r.status_code == 401:
            a = r.headers.get("WWW-Authenticate", "")
            realm = re.search(r'realm="([^"]+)"', a).group(1)
            svc = re.search(r'service="([^"]+)"', a).group(1)
            scope = re.search(r'scope="([^"]+)"', a).group(1)
            h["Authorization"] = f"Bearer {s.get(realm, params={'service': svc, 'scope': scope}, timeout=REQUEST_TIMEOUT).json()['token']}"
            r = s.get(url, headers=h, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        man = r.json()
        if "manifests" in man:
            d = man["manifests"][0]["digest"]
            r = s.get(f"https://registry-1.docker.io/v2/{DOCKER_REPO}/manifests/{d}", headers=h, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            man = r.json()
        d = man.get("config", {}).get("digest", "")
        if not d:
            return None
        b = s.get(f"https://registry-1.docker.io/v2/{DOCKER_REPO}/blobs/{d}", headers=h, timeout=REQUEST_TIMEOUT)
        b.raise_for_status()
        return b.json().get("config", {}).get("Labels") or {}
    except Exception as exc:
        logger.debug("Could not read labels of %s:%s: %s", DOCKER_REPO, tag, exc)
        return None


def _imager_stale(tag: str, expected: str) -> bool:
    """True if published tag bundles an outdated IMAGER (fail-open: False)."""
    if expected == IMAGER_LAST:
        return False
    labels = _image_labels(tag)
    if labels is None:
        return False
    rec = labels.get("abeelen.gildas.imager-version", "")
    if not rec:
        return True
    return rec != expected and rec != IMAGER_LAST


def _docker_tags() -> List[str]:
    """All Hub tags (follows pagination)."""
    tags, url = [], f"https://registry.hub.docker.com/v2/repositories/{DOCKER_REPO}/tags/?page_size=100"
    while url:
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        d = r.json()
        tags += [i["name"] for i in d.get("results", []) if "name" in i]
        url = d.get("next")
    return tags


def _build_arg_for_release(release, main, archived, arg_name, archive_url, package_name="") -> str:
    if release in main:
        return ""
    if release in archived:
        return f"--build-arg {arg_name}={archive_url}"
    raise FileNotFoundError(f"{package_name} release '{release}' not found in main or archive")


def _release_sort_key(release: str):
    """monYYx -> (year, month, sub); unknown sorts first."""
    months = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
    try:
        m, yy = release[:3].lower(), int(release[3:5])
        letter = release[5:6] if len(release) > 5 else "a"
        sub = ord(letter.lower()) - 96 if letter.isalpha() else 0
        return 2000 + yy, months[m], sub, ""
    except Exception:
        logger.warning("Unable to parse release name '%s'", release)
        return 0, 0, 0, release


@dataclass(frozen=True)
class ReleaseSets:
    """Upstream state used to derive build commands.

    Parameters
    ----------
    tags : list of str
        Existing Docker Hub tags.
    gildas : list of str
        Main-tree GILDAS releases.
    archived_gildas : list of str
        Archive-only GILDAS releases.
    piic : list of str
        Main-tree PIIC releases.
    archived_piic : list of str
        Archive-only PIIC releases.
    """
    tags: List[str]
    gildas: List[str]
    archived_gildas: List[str]
    piic: List[str]
    archived_piic: List[str]

    def all_releases(self):
        return sorted(set(self.gildas) | set(self.archived_gildas) | set(self.piic) | set(self.archived_piic), key=_release_sort_key)


def _load_release_sets_uncached(include_archive=False, archive_gildas=False) -> ReleaseSets:
    """Fetch Hub tags + IRAM listings in parallel (archives only when needed)."""
    need_g = include_archive or archive_gildas
    with ThreadPoolExecutor(max_workers=5) as p:
        jobs = {"tags": p.submit(_docker_tags), "gildas": p.submit(gildas_release, "gildas"),
                "piic": p.submit(gildas_release, "piic")}
        if need_g:
            jobs["ag"] = p.submit(gildas_release, "gildas", True)
        if include_archive:
            jobs["ap"] = p.submit(gildas_release, "piic", True)
        g = lambda k: jobs[k].result() if k in jobs else []
        return ReleaseSets(g("tags"), g("gildas"), g("ag"), g("piic"), g("ap"))


@functools.lru_cache(maxsize=8)
def _load_release_sets(include_archive=False, archive_gildas=False) -> ReleaseSets:
    return _load_release_sets_uncached(include_archive, archive_gildas)


def _tag_suffix(dockerfile: str) -> str:
    return "-alpine" if dockerfile.endswith("alpine") else "-debian"


@dataclass
class BuildCommand:
    """Docker build/push command for one release variant.

    Parameters
    ----------
    section : str
        ``"without-piic"`` or ``"with-piic"``.
    release : str
        GILDAS release identifier.
    in_dockerhub : bool
        Whether the tag already exists on Docker Hub.
    command : str
        Shell command to build and push the image.
    alpine : bool, optional
        Alpine base (default False = Debian).
    stale_imager : bool, optional
        Published tag bundles an outdated IMAGER.
    """
    section: str
    release: str
    in_dockerhub: bool
    command: str
    alpine: bool = False
    stale_imager: bool = False


@dataclass
class NatifCommand:
    """Native ``singularity build`` command for one release.

    Parameters
    ----------
    release : str
        GILDAS release identifier.
    has_piic : bool
        PIIC tarball available upstream (bundled).
    command : str
        Shell command to build the SIF.
    alpine : bool, optional
        Alpine base.
    imager_version : str, optional
        Pinned IMAGER version.
    """
    release: str
    has_piic: bool
    command: str
    alpine: bool = False
    imager_version: str = IMAGER_LAST


def _image_tag(cmd: BuildCommand) -> str:
    suf = "-alpine" if cmd.alpine else "-debian"
    return f"{cmd.release}-piic{suf}" if cmd.section == SECTION_WITH_PIIC else f"{cmd.release}{suf}"


def _natif_tag(cmd: NatifCommand) -> str:
    return f"{cmd.release}-natif-alpine" if cmd.alpine else f"{cmd.release}-natif"


def _docker_build_push(main_tag, latest_tag, middle, dockerfile, tag_latest, alias=None) -> str:
    tags = [main_tag] + ([latest_tag] + ([alias] if alias else []) if tag_latest else [])
    build = f"docker build {' '.join(f'--tag {DOCKER_REPO}:{t}' for t in tags)} {' '.join(p for p in middle if p)} -f {shlex.quote(dockerfile)} ."
    return f"{build} && {' && '.join(f'docker push {DOCKER_REPO}:{t}' for t in tags)}"


def _docker_cmd(gildas, agildas, piic, apiic, release, *, with_piic, dockerfile, tag_latest, imager) -> str | None:
    """Shared docker builder; None when a needed tarball is missing."""
    try:
        g_arg = _build_arg_for_release(release, gildas, agildas, "GILDAS_URL", GILDAS_ARCHIVE_URL, "gildas")
        p_arg = _build_arg_for_release(release, piic, apiic, "PIIC_URL", PIIC_ARCHIVE_URL, "piic") if with_piic else ""
    except FileNotFoundError as exc:
        logger.debug("Skipping %s: %s", release, exc)
        return None
    suf = _tag_suffix(dockerfile)
    alpine = dockerfile.endswith("alpine")
    if with_piic:
        main, latest, alias, target = f"{release}-piic{suf}", f"latest-piic{suf}", "latest-piic" if alpine else None, "gildas-piic"
    else:
        main, latest, alias, target = f"{release}{suf}", f"latest{suf}", "latest" if alpine else None, "gildas"
    imager = imager or imager_version_for_release(release)
    return _docker_build_push(main, latest, ["--target " + target, g_arg, p_arg, f"--build-arg release={shlex.quote(release)}", f"--build-arg IMAGER_VERSION={shlex.quote(imager)}"], dockerfile, tag_latest, alias)


def build_without_piic_command(gildas, archived_gildas, release, dockerfile="Dockerfile.alpine", tag_latest=False, imager_version=None) -> str:
    """Build the docker command for a GILDAS-only release.

    Parameters
    ----------
    gildas : sequence of str
        Main-tree GILDAS releases.
    archived_gildas : sequence of str
        Archive-only GILDAS releases.
    release : str
        Release identifier.
    dockerfile : str, optional
        Dockerfile variant.
    tag_latest : bool, optional
        Also tag ``latest``.
    imager_version : str or None, optional
        Pinned IMAGER version (auto-mapped when None).

    Returns
    -------
    str
        Shell command.
    """
    return _docker_cmd(gildas, archived_gildas, [], [], release, with_piic=False, dockerfile=dockerfile, tag_latest=tag_latest, imager=imager_version)


def build_with_piic_command(gildas, archived_gildas, piic, archived_piic, release, dockerfile="Dockerfile.alpine", tag_latest=False, imager_version=None) -> str | None:
    """Build the docker command for a GILDAS+PIIC release.

    Parameters
    ----------
    gildas, archived_gildas, piic, archived_piic : sequence of str
        Known releases per tree.
    release : str
        Release identifier.
    dockerfile : str, optional
        Dockerfile variant.
    tag_latest : bool, optional
        Also tag ``latest-piic``.
    imager_version : str or None, optional
        Pinned IMAGER version (auto-mapped when None).

    Returns
    -------
    str or None
        Shell command, or None when a needed tarball is missing.
    """
    return _docker_cmd(gildas, archived_gildas, piic, archived_piic, release, with_piic=True, dockerfile=dockerfile, tag_latest=tag_latest, imager=imager_version)


def get_release_build_commands(release_name, missing_only=False, dockerfile="Dockerfile.alpine", tag_latest=False, sets=None, tag_latest_piic=None, include_archive=False, archive_gildas=False, imager_version=None) -> List[BuildCommand]:
    """Return docker commands for a specific release.

    Parameters
    ----------
    release_name : str
        Release identifier.
    missing_only : bool, optional
        Skip tags already on Hub (unless IMAGER is stale).
    dockerfile : str, optional
        Dockerfile variant.
    tag_latest : bool, optional
        Tag ``latest`` on the GILDAS image.
    sets : ReleaseSets or None, optional
        Upstream state (loaded when None).
    tag_latest_piic : bool or None, optional
        Tag ``latest-piic`` (defaults to ``tag_latest``).
    include_archive, archive_gildas : bool, optional
        Consider archived releases.
    imager_version : str or None, optional
        Pinned IMAGER version.

    Returns
    -------
    list of BuildCommand
    """
    tag_latest_piic = tag_latest if tag_latest_piic is None else tag_latest_piic
    sets = sets or _load_release_sets(include_archive, archive_gildas)
    ag = sets.archived_gildas if (include_archive or archive_gildas) else []
    ap = sets.archived_piic if include_archive else []
    alpine = dockerfile.endswith("alpine")
    expected = imager_version or imager_version_for_release(release_name)
    fresh = release_name in sets.gildas or release_name in sets.piic
    out = []
    specs = [(SECTION_WITHOUT_PIIC, release_name in sets.gildas or release_name in ag, tag_latest, False),
             (SECTION_WITH_PIIC, release_name in sets.piic or release_name in ap, tag_latest_piic, True)]
    for section, known, latest, with_piic in specs:
        if not known:
            continue
        cmd = _docker_cmd(sets.gildas, ag, sets.piic, ap, release_name, with_piic=with_piic, dockerfile=dockerfile, tag_latest=latest, imager=expected)
        if not cmd:
            continue
        c = BuildCommand(section, release_name, False, cmd, alpine)
        tag = _image_tag(c)
        c = BuildCommand(section, release_name, tag in sets.tags, cmd, alpine,
                         fresh and tag in sets.tags and _imager_stale(tag, expected))
        if not missing_only or not c.in_dockerhub or c.stale_imager:
            out.append(c)
    return out


def get_build_commands(missing_only=False, dockerfile="Dockerfile.alpine", tag_latest=None, include_archive=False, archive_gildas=False, imager_version=None) -> List[BuildCommand]:
    """Return docker commands for all known releases.

    Parameters
    ----------
    missing_only : bool, optional
        Skip tags already on Hub.
    dockerfile : str, optional
        Dockerfile variant.
    tag_latest : bool or None, optional
        None tags the newest release per family; True/False forces it.
    include_archive, archive_gildas : bool, optional
        Consider archived releases.
    imager_version : str or None, optional
        Pinned IMAGER version.

    Returns
    -------
    list of BuildCommand
    """
    sets = _load_release_sets(include_archive, archive_gildas)
    g = sorted(set(sets.gildas) | set(sets.archived_gildas), key=_release_sort_key)
    p = sorted((set(sets.piic) | set(sets.archived_piic)) & (set(sets.gildas) | set(sets.archived_gildas)), key=_release_sort_key)
    cmds = []
    for rel in sets.all_releases():
        gl = pl = tag_latest if tag_latest is not None else None
        if tag_latest is None:
            gl, pl = rel == (g[-1] if g else None), rel == (p[-1] if p else None)
        cmds += get_release_build_commands(rel, missing_only, dockerfile, gl, sets, pl, include_archive, archive_gildas, imager_version)
    return cmds


def natif_command(release, sets, dockerfile="Dockerfile.alpine", imager_version=None) -> NatifCommand | None:
    """Return the native SIF build command for a release.

    Parameters
    ----------
    release : str
        Release identifier.
    sets : ReleaseSets
        Upstream state.
    dockerfile : str, optional
        Dockerfile variant (selects base).
    imager_version : str or None, optional
        Pinned IMAGER version.

    Returns
    -------
    NatifCommand or None
        None when the GILDAS tarball is unknown.
    """
    if release not in set(sets.gildas) | set(sets.archived_gildas):
        return None
    has_piic = release in sets.piic or release in sets.archived_piic
    imager_version = imager_version or imager_version_for_release(release)
    env = [f"SINGULARITYENV_GILDAS_RELEASE={shlex.quote(release)}", f"SINGULARITYENV_IMAGER_VERSION={shlex.quote(imager_version)}"]
    if release not in sets.gildas:
        env.append(f"SINGULARITYENV_GILDAS_URL={GILDAS_ARCHIVE_URL}")
    if has_piic and release not in sets.piic:
        env.append(f"SINGULARITYENV_PIIC_URL={PIIC_ARCHIVE_URL}")
    alpine = dockerfile.endswith("alpine")
    sif = f"gildas-{release}-natif-alpine.sif" if alpine else f"gildas-{release}-natif.sif"
    return NatifCommand(release, has_piic, f"{' '.join(env)} singularity build {sif} {NATIF_DEF}", alpine, imager_version)


def get_natif_commands(dockerfile="Dockerfile.alpine", include_archive=False, archive_gildas=False, sets=None, imager_version=None) -> List[NatifCommand]:
    """Return native SIF build commands for all known releases.

    Parameters
    ----------
    dockerfile : str, optional
        Dockerfile variant.
    include_archive, archive_gildas : bool, optional
        Consider archived releases.
    sets : ReleaseSets or None, optional
        Upstream state (loaded when None).
    imager_version : str or None, optional
        Pinned IMAGER version.

    Returns
    -------
    list of NatifCommand
    """
    sets = sets or _load_release_sets(include_archive, archive_gildas)
    return [c for rel in sets.all_releases() if (c := natif_command(rel, sets, dockerfile, imager_version))]


def singularity_command(cmd: BuildCommand, deffile: str = LATEST_DEF) -> str:
    """Return a SIF build command via ``gildas-latest.def``.

    Parameters
    ----------
    cmd : BuildCommand
        Release variant to convert.
    deffile : str, optional
        Definition recipe.

    Returns
    -------
    str
        Shell command (``From:`` rewritten per tag).
    """
    tag = _image_tag(cmd)
    image = DOCKER_REPO.split("/")[-1]
    return f"sed \"s|^From: .*|From: {DOCKER_REPO}:{tag}|\" {deffile} > /tmp/sif-build.def && singularity build {image}-{tag}.sif /tmp/sif-build.def"


def _format_comment(cmd: BuildCommand) -> str:
    tag = _image_tag(cmd)
    tail = "launch :" if cmd.section == SECTION_WITH_PIIC and not cmd.in_dockerhub else ":"
    if cmd.in_dockerhub:
        base = f"# * {tag} already in dockerhub"
        return f"{base} but IMAGER outdated, rebuilding :" if cmd.stale_imager else f"{base} {tail}"
    return f"# * {tag} not in dockerhub{' launch :' if cmd.section == SECTION_WITH_PIIC else ''}"


def _format_natif_comment(cmd: NatifCommand) -> str:
    return f"# * {_natif_tag(cmd)}{' (+piic bundled)' if cmd.has_piic else ' (no piic upstream)'} [imager {cmd.imager_version}]"


def _run_logged(command: str, log_path: str | None = None, tail: int = 15) -> None:
    """Run shell cmd; with log_path tee to file and print tail only."""
    if log_path is None:
        subprocess.run(command, shell=True, check=True)
        return
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as h:
        proc = subprocess.run(command, shell=True, stdout=h, stderr=subprocess.STDOUT)
    print(f"# log: {path}")
    print("\n".join(path.read_text(errors="replace").splitlines()[-tail:]))
    if proc.returncode:
        raise subprocess.CalledProcessError(proc.returncode, command)


def _emit(texts, execute, log_for):
    for text, cmd, obj in texts:
        print(text)
        print(cmd)
        if execute:
            _run_logged(cmd, log_for(obj) if log_for else None)


def _print_command_sections(commands, singularity, execute, piic_only, log_dir=None) -> None:
    for section, title in [(SECTION_WITHOUT_PIIC, "# Without piic"), (SECTION_WITH_PIIC, "# With piic")]:
        if piic_only and section == SECTION_WITHOUT_PIIC:
            continue
        sel = sorted([c for c in commands if c.section == section], key=lambda c: _release_sort_key(c.release))
        if not sel:
            continue
        print(title)
        _emit([(_format_comment(c), singularity_command(c) if singularity else c.command, c) for c in sel],
              execute, (lambda c: str(Path(log_dir) / f"{_image_tag(c)}.log")) if log_dir else (lambda c: None) if execute else None)


def print_natif_build_commands(dockerfile="Dockerfile.alpine", execute=False, include_archive=False, imager_version=None, piic_only=False, archive_gildas=False, log_dir=None) -> None:
    """Print (or execute) native singularity build commands.

    Parameters
    ----------
    dockerfile : str, optional
        Dockerfile variant.
    execute : bool, optional
        Run commands instead of printing.
    include_archive, archive_gildas : bool, optional
        Consider archived releases.
    imager_version : str or None, optional
        Pinned IMAGER version.
    piic_only : bool, optional
        Only releases with PIIC.
    log_dir : str or None, optional
        Tee outputs to ``<dir>/<tag>.log`` when executing.
    """
    cmds = get_natif_commands(dockerfile, include_archive, archive_gildas, None, imager_version)
    if piic_only:
        cmds = [c for c in cmds if c.has_piic]
    print("# Natif (from tarballs, PIIC bundled when available)")
    _emit([(_format_natif_comment(c), c.command, c) for c in cmds], execute,
          (lambda c: str(Path(log_dir) / f"{_natif_tag(c)}.log")) if log_dir else (lambda c: None) if execute else None)


def print_missing_build_commands(force=False, dockerfile="Dockerfile.alpine", execute=False, include_archive=False, singularity=False, natif=False, imager_version=None, piic_only=False, archive_gildas=False, log_dir=None) -> None:
    """Print (or execute) commands for missing releases.

    Parameters
    ----------
    force : bool, optional
        Include releases already on Hub.
    dockerfile : str, optional
        Dockerfile variant.
    execute : bool, optional
        Run commands instead of printing.
    include_archive, archive_gildas : bool, optional
        Consider archived releases.
    singularity : bool, optional
        Emit SIF builds via ``gildas-latest.def``.
    natif : bool, optional
        Emit native SIF builds.
    imager_version : str or None, optional
        Pinned IMAGER version.
    piic_only : bool, optional
        Only PIIC variants.
    log_dir : str or None, optional
        Tee outputs to ``<dir>/<tag>.log`` when executing.
    """
    if natif:
        return print_natif_build_commands(dockerfile, execute, include_archive, imager_version, piic_only, archive_gildas, log_dir)
    _print_command_sections(get_build_commands(not force and not singularity, dockerfile, None, include_archive, archive_gildas, imager_version), singularity, execute, piic_only, log_dir)


@click.command()
@click.option("--release", "release_name", default=None, help="Specific release (e.g. jan26a). Omit for all missing.")
@click.option("-v", "--verbose", count=True, help="Verbosity (-v/-vv).")
@click.option("-f", "--force", is_flag=True, help="Include releases already on Hub.")
@click.option("--debian", is_flag=True, help="Debian Dockerfile (default Alpine).")
@click.option("--piic", "piic_only", is_flag=True, help="Only PIIC commands.")
@click.option("--archive", "include_archive", is_flag=True, default=False, help="Include archived releases.")
@click.option("--singularity", "singularity", is_flag=True, default=False, help="Emit singularity builds via gildas-latest.def (From: rewritten per tag).")
@click.option("--natif", "natif", is_flag=True, default=False, help="Emit native singularity builds (.def from tarballs).")
@click.option("--imager-version", "imager_version", default=None, help="Pin IMAGER version (default auto-mapped).")
@click.option("--execute", is_flag=True, help="Run commands instead of printing.")
@click.option("--log-dir", "log_dir", default=None, help="With --execute, tee output to <dir>/<tag>.log.")
def main(release_name=None, verbose=0, force=False, debian=False, piic_only=False, execute=False, log_dir=None, include_archive=False, singularity=False, natif=False, imager_version=None) -> None:
    """Print (or run) docker/singularity build commands for GILDAS releases.

    Parameters
    ----------
    release_name : str or None, optional
        Single release, or None for all missing.
    verbose : int, optional
        Verbosity counter.
    force, debian, piic_only, execute : bool, optional
        CLI flags (see ``--help``).
    log_dir : str or None, optional
        Log directory with ``--execute``.
    include_archive, singularity, natif : bool, optional
        CLI flags (see ``--help``).
    imager_version : str or None, optional
        Pinned IMAGER version.
    """
    logging.basicConfig(level=[logging.WARNING, logging.INFO, logging.DEBUG][min(verbose, 2)], format="%(levelname)s:%(name)s:%(message)s")
    dockerfile = "Dockerfile" if debian else "Dockerfile.alpine"
    archive_gildas = include_archive or piic_only
    if not release_name:
        return print_missing_build_commands(force, dockerfile, execute, include_archive, singularity, natif, imager_version, piic_only, archive_gildas, log_dir)
    sets = _load_release_sets(include_archive, archive_gildas)
    if release_name not in set(sets.gildas) | set(sets.archived_gildas) | set(sets.piic) | set(sets.archived_piic):
        logger.warning("Release '%s' not found upstream%s; emitting nothing", release_name, "" if include_archive else " (retry with --archive)")
    if natif:
        c = natif_command(release_name, sets, dockerfile, imager_version)
        if c is None or (piic_only and not c.has_piic):
            return
        print("# Natif (from tarballs, PIIC bundled when available)")
        return _emit([(_format_natif_comment(c), c.command, c)], execute, (lambda o: str(Path(log_dir) / f"{_natif_tag(o)}.log")) if log_dir and execute else None)
    _print_command_sections(get_release_build_commands(release_name, False, dockerfile, True, sets, True, include_archive, archive_gildas, imager_version), singularity, execute, piic_only, log_dir)


if __name__ == "__main__":
    main()
