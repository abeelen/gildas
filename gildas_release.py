#!/usr/bin/env python3
import functools
import json
import logging
import shlex
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
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

logger = logging.getLogger(__name__)


SECTION_WITHOUT_PIIC = "without-piic"
SECTION_WITH_PIIC = "with-piic"


def gildas_release(package: str, archive: bool = False) -> List[str]:
    """Return available GILDAS or PIIC releases from IRAM website.

    Parameters
    ----------
    package : {"gildas", "piic"}
        Logical package name. "gildas" maps to ``gildas-src-*`` tarballs,
        "piic" maps to ``piic-exe-*`` tarballs.
    archive : bool, optional
        If True, query the corresponding archive directory instead of the
        main distribution directory. Defaults to False.

    Returns
    -------
    list of str
        List of release identifiers (e.g. ``"jan26a"``).

    Raises
    ------
    requests.HTTPError
        If the HTTP request to the IRAM server fails.
    """
    uri = GILDAS_MAIN_URL + "/"

    if archive and package == "gildas":
        uri = GILDAS_ARCHIVE_URL
    elif archive and package == "piic":
        uri = PIIC_ARCHIVE_URL

    if package == "gildas":
        prefix = "gildas-src"
    elif package == "piic":
        prefix = "piic-exe"
    else:
        logger.error("Unknown package '%s' requested in gildas_release", package)
        raise ValueError(f"Unknown package '{package}'")

    r = requests.get(uri, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, features="html.parser")
    releases: List[str] = []
    for link in soup.find_all("a"):
        href = link.get("href", "")
        if not href or ".tar.xz" not in href:
            continue
        filename = href.rsplit("/", 1)[-1]
        if not filename.startswith(prefix + "-"):
            continue
        # gildas-src-<release>.tar.xz -> <release>
        try:
            release = filename[len(prefix) + 1 :].split(".tar.xz")[0]
        except IndexError:
            continue
        if release and not release.startswith("ifort"):
            releases.append(release)

    return sorted(set(releases))


def imager_release() -> List[str]:
    """Return available standalone IMAGER versions.

    Lists ``imager-<version>.tgz`` tarballs from the OASU share server,
    excluding the ``last``/``beta`` aliases and documentation archives.

    Note: the server (dufs) renders a JS UI by default and only serves
    the static file listing at ``?noscript`` (curl gets it via UA
    sniffing), so request that endpoint explicitly.

    Returns
    -------
    list of str
        List of IMAGER version identifiers (e.g. ``"oct26"``).

    Raises
    ------
    requests.HTTPError
        If the HTTP request to the IMAGER server fails.
    """
    r = requests.get(IMAGER_URL + "/?noscript", timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, features="html.parser")
    versions: List[str] = []
    for link in soup.find_all("a"):
        href = link.get("href", "")
        if not href:
            continue
        filename = href.rsplit("/", 1)[-1]
        if not filename.startswith("imager-") or not filename.endswith(".tgz"):
            continue
        version = filename[len("imager-") : -len(".tgz")]
        if version and version not in ("last", "beta") and not version.startswith("doc-"):
            versions.append(version)

    return sorted(set(versions))


@functools.lru_cache(maxsize=1)
def _cached_imager_versions() -> tuple:
    """Cached IMAGER version list (single small index fetch per run)."""
    return tuple(imager_release())


def imager_version_for_release(release: str, available: Sequence[str] | None = None) -> str:
    """Return the IMAGER version coupled to a GILDAS release.

    GILDAS releases are named ``monYYx`` (e.g. ``"oct26a"``) while IMAGER
    versions drop the trailing letter (e.g. ``"oct26"``). When no
    matching IMAGER version exists upstream, fall back to ``"last"``.

    Parameters
    ----------
    release : str
        GILDAS release identifier.
    available : sequence of str or None, optional
        Known IMAGER versions. Defaults to the live upstream list.

    Returns
    -------
    str
        Matching IMAGER version, or ``"last"`` when none matches.
    """
    if available is None:
        available = _cached_imager_versions()
    candidate = release[:-1] if release[-1:].isalpha() else release
    if candidate in available:
        return candidate
    logger.warning("No matching IMAGER version for release '%s', using '%s'", release, IMAGER_LAST)
    return IMAGER_LAST


def _docker_tags(repo: str = DOCKER_REPO) -> List[str]:
    """Return existing tags for the Docker repository.

    Follows Docker Hub pagination instead of assuming a single page.

    Parameters
    ----------
    repo : str, optional
        Docker Hub repository in the form ``"user/image"``. Defaults to
        ``DOCKER_REPO``.

    Returns
    -------
    list of str
        All tags present on Docker Hub.
    """

    tags: List[str] = []
    url: str | None = f"https://registry.hub.docker.com/v2/repositories/{repo}/tags/?page_size=100"
    while url:
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        tags.extend(item["name"] for item in data.get("results", []) if "name" in item)
        url = data.get("next")
    return tags


def _build_arg_for_release(
    release: str,
    main_releases: Sequence[str],
    archived_releases: Sequence[str],
    arg_name: str,
    archive_url: str,
    package_name: str,
) -> str:
    """Return appropriate ``--build-arg`` fragment for a release.

    Parameters
    ----------
    release : str
        Release identifier (e.g. ``"jan26a"``).
    main_releases : sequence of str
        Releases available in the main distribution tree.
    archived_releases : sequence of str
        Releases available only in the archive tree.
    arg_name : str
        Name of the Docker build argument controlling the base URL
        (e.g. ``"GILDAS_URL"``).
    archive_url : str
        Base URL of the archive tree corresponding to ``arg_name``.
    package_name : str
        Human-readable package name used for error messages.

    Returns
    -------
    str
        Empty string if ``release`` is in ``main_releases``, or a fragment
        of the form ``"--build-arg <ARG_NAME>=<ARCHIVE_URL>"`` if it is
        only available in ``archived_releases``.

    Raises
    ------
    FileNotFoundError
        If the release is not found in either main or archive trees.
    """

    if release in main_releases:
        return ""
    if release in archived_releases:
        return f"--build-arg {arg_name}={archive_url}"
    raise FileNotFoundError(f"{package_name} release '{release}' not found in main or archive trees")


def _release_sort_key(release: str) -> tuple[int, int, int, str]:
    """Sort key to order releases chronologically.

    Assumes releases are named like ``monYYx`` where ``mon`` is a
    three-letter English month abbreviation, ``YY`` the two-digit year,
    and ``x`` an optional letter within the month (a, b, c, ...).

    All known releases are post-2000, so ``YY`` always maps to 20YY.
    Unknown patterns sort first but deterministically by name.
    """

    month_map = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }

    try:
        mon = release[:3].lower()
        year_part = release[3:5]
        letter = release[5:6] if len(release) > 5 else "a"

        month = month_map[mon]
        yy = int(year_part)
        year = 2000 + yy
        # Map 'a' -> 1, 'b' -> 2, ...; default to 0 if unexpected
        sub = ord(letter.lower()) - ord("a") + 1 if letter.isalpha() else 0
        return year, month, sub, ""
    except Exception:
        # Fallback: group unknown patterns first, ordered lexicographically
        logger.warning("Unable to parse release name '%s' for sorting", release)
        return 0, 0, 0, release


@dataclass(frozen=True)
class ReleaseSets:
    """Container for Docker tags and known upstream releases."""

    tags: List[str]
    gildas: List[str]
    archived_gildas: List[str]
    piic: List[str]
    archived_piic: List[str]


def _load_release_sets_uncached(
    repo: str = DOCKER_REPO, include_archive: bool = False, archive_gildas: bool = False
) -> ReleaseSets:
    """Fetch Docker tags + IRAM listings in parallel.

    Archive trees are only queried when needed: the PIIC archive when
    ``include_archive`` is True, the GILDAS archive when either flag is
    set (PIIC releases lag behind GILDAS ones, so their matching GILDAS
    tarball is often archived already).
    """

    query_arch_gildas = include_archive or archive_gildas
    with ThreadPoolExecutor(max_workers=5) as pool:
        f_tags = pool.submit(_docker_tags, repo)
        f_gildas = pool.submit(gildas_release, "gildas")
        f_piic = pool.submit(gildas_release, "piic")
        if query_arch_gildas:
            f_arch_gildas = pool.submit(gildas_release, "gildas", True)
        else:
            f_arch_gildas = None
        if include_archive:
            f_arch_piic = pool.submit(gildas_release, "piic", True)
        else:
            f_arch_piic = None
        return ReleaseSets(
            tags=f_tags.result(),
            gildas=f_gildas.result(),
            archived_gildas=f_arch_gildas.result() if f_arch_gildas else [],
            piic=f_piic.result(),
            archived_piic=f_arch_piic.result() if f_arch_piic else [],
        )


@functools.lru_cache(maxsize=8)
def _load_release_sets(
    repo: str = DOCKER_REPO, include_archive: bool = False, archive_gildas: bool = False
) -> ReleaseSets:
    """Load Docker tags and known releases for GILDAS and PIIC (cached)."""
    return _load_release_sets_uncached(repo, include_archive, archive_gildas)


def _join_parts(parts: List[str]) -> str:
    """Join command parts, dropping empty ``--build-arg`` fragments."""
    return " ".join(p for p in parts if p)


def _tag_suffix(dockerfile: str) -> str:
    """Tag suffix for a Dockerfile.

    Alpine is the default base image and uses no suffix; Debian images
    get a ``-debian`` suffix (e.g. ``jan26a-debian``, ``latest-piic-debian``).
    """
    return "" if dockerfile.endswith("alpine") else "-debian"


def build_without_piic_command(
    gildas: Sequence[str],
    archived_gildas: Sequence[str],
    release: str,
    dockerfile: str = "Dockerfile",
    repo: str = DOCKER_REPO,
    tag_latest: bool = False,
    imager_version: str | None = None,
) -> str:
    """Build docker commands for a GILDAS-only release."""

    arg = _build_arg_for_release(
        release,
        main_releases=gildas,
        archived_releases=archived_gildas,
        arg_name="GILDAS_URL",
        archive_url=GILDAS_ARCHIVE_URL,
        package_name="gildas",
    )

    if imager_version is None:
        imager_version = imager_version_for_release(release)

    is_alpine = dockerfile.endswith("alpine")
    suffix = _tag_suffix(dockerfile)
    main_tag = f"{release}{suffix}"
    latest_tag = f"latest{suffix}"

    parts = [
        "docker build",
        f"--tag {repo}:{main_tag}",
    ]
    if tag_latest:
        parts.append(f"--tag {repo}:{latest_tag}")
    parts += [
        "--target gildas",
        arg,
        f"--build-arg release={shlex.quote(release)}",
        f"--build-arg IMAGER_VERSION={shlex.quote(imager_version)}",
        f"-f {shlex.quote(dockerfile)} .",
    ]
    cmd = _join_parts(parts)
    push = f"docker push {repo}:{main_tag}"
    if tag_latest:
        push += f" && docker push {repo}:{latest_tag}"
    return f"{cmd} && {push}"


def build_with_piic_command(
    gildas: Sequence[str],
    archived_gildas: Sequence[str],
    piic: Sequence[str],
    archived_piic: Sequence[str],
    release: str,
    dockerfile: str = "Dockerfile",
    repo: str = DOCKER_REPO,
    tag_latest: bool = False,
    imager_version: str | None = None,
) -> str | None:
    """Build docker commands for a combined GILDAS+PIIC release."""

    # Check that the corresponding gildas release exists (main or archive)
    try:
        g_arg = _build_arg_for_release(
            release,
            main_releases=gildas,
            archived_releases=archived_gildas,
            arg_name="GILDAS_URL",
            archive_url=GILDAS_ARCHIVE_URL,
            package_name="gildas",
        )
    except FileNotFoundError as exc:
        # Expected for old releases (no matching GILDAS tarball): debug only.
        logger.debug("Skipping PIIC build for %s: %s", release, exc)
        return None

    try:
        p_arg = _build_arg_for_release(
            release,
            main_releases=piic,
            archived_releases=archived_piic,
            arg_name="PIIC_URL",
            archive_url=PIIC_ARCHIVE_URL,
            package_name="piic",
        )
    except FileNotFoundError as exc:
        # Expected for old releases (no PIIC tarball): debug only.
        logger.debug("Skipping PIIC build for %s (no PIIC archive): %s", release, exc)
        return None

    if imager_version is None:
        imager_version = imager_version_for_release(release)

    is_alpine = dockerfile.endswith("alpine")
    suffix = _tag_suffix(dockerfile)
    main_tag = f"{release}-piic{suffix}"
    latest_tag = f"latest-piic{suffix}"

    parts = [
        "docker build",
        f"--tag {repo}:{main_tag}",
    ]
    if tag_latest:
        parts.append(f"--tag {repo}:{latest_tag}")
    parts += [
        "--target gildas-piic",
        g_arg,
        p_arg,
        f"--build-arg release={shlex.quote(release)}",
        f"--build-arg IMAGER_VERSION={shlex.quote(imager_version)}",
        f"-f {shlex.quote(dockerfile)} .",
    ]
    cmd = _join_parts(parts)
    push = f"docker push {repo}:{main_tag}"
    if tag_latest:
        push += f" && docker push {repo}:{latest_tag}"
    return f"{cmd} && {push}"


@dataclass
class BuildCommand:
    """Structured representation of a docker build/push command."""

    section: str
    release: str
    in_dockerhub: bool
    command: str
    alpine: bool = False


def get_release_build_commands(
    release_name: str,
    missing_only: bool = False,
    dockerfile: str = "Dockerfile.alpine",
    repo: str = DOCKER_REPO,
    tag_latest: bool = False,
    sets: ReleaseSets | None = None,
    tag_latest_piic: bool | None = None,
    include_archive: bool = False,
    archive_gildas: bool = False,
    imager_version: str | None = None,
) -> List[BuildCommand]:
    """Return docker commands for a specific release.

    ``tag_latest`` controls the ``latest`` tag on the GILDAS image;
    ``tag_latest_piic`` controls ``latest-piic`` (defaults to the value
    of ``tag_latest`` when not given). Archived releases are only
    considered when ``include_archive`` is True. ``imager_version``
    overrides the coupled IMAGER version (auto-mapped from the release
    when not given).
    """

    if tag_latest_piic is None:
        tag_latest_piic = tag_latest

    if sets is None:
        sets = _load_release_sets(repo, include_archive, archive_gildas)
    tags = sets.tags
    gildas = sets.gildas
    archived_gildas = sets.archived_gildas if (include_archive or archive_gildas) else []
    piic = sets.piic
    archived_piic = sets.archived_piic if include_archive else []

    commands: List[BuildCommand] = []

    is_alpine = dockerfile.endswith("alpine")
    suffix = _tag_suffix(dockerfile)

    # GILDAS only
    if release_name in gildas or release_name in archived_gildas:
        command = build_without_piic_command(
            gildas,
            archived_gildas,
            release_name,
            dockerfile=dockerfile,
            repo=repo,
            tag_latest=tag_latest,
            imager_version=imager_version,
        )
        base_tag = f"{release_name}{suffix}"
        in_dockerhub = base_tag in tags

        if not missing_only or not in_dockerhub:
            commands.append(
                BuildCommand(
                    section=SECTION_WITHOUT_PIIC,
                    release=release_name,
                    in_dockerhub=in_dockerhub,
                    command=command,
                    alpine=is_alpine,
                )
            )

    # GILDAS + PIIC
    if release_name in piic or release_name in archived_piic:
        command = build_with_piic_command(
            gildas,
            archived_gildas,
            piic,
            archived_piic,
            release_name,
            dockerfile=dockerfile,
            repo=repo,
            tag_latest=tag_latest_piic,
            imager_version=imager_version,
        )
        if command:
            piic_tag = f"{release_name}-piic{suffix}"
            in_dockerhub = piic_tag in tags

            if not missing_only or not in_dockerhub:
                commands.append(
                    BuildCommand(
                        section=SECTION_WITH_PIIC,
                        release=release_name,
                        in_dockerhub=in_dockerhub,
                        command=command,
                        alpine=is_alpine,
                    )
                )

    return commands


def get_build_commands(
    missing_only: bool = False,
    dockerfile: str = "Dockerfile.alpine",
    repo: str = DOCKER_REPO,
    tag_latest: bool | None = None,
    include_archive: bool = False,
    archive_gildas: bool = False,
    imager_version: str | None = None,
) -> List[BuildCommand]:
    """Return docker commands for all known releases (deduplicated).

    When ``tag_latest`` is None (the default), the newest GILDAS release
    gets the ``latest`` tag and the newest GILDAS+PIIC release gets the
    ``latest-piic`` tag (tracked independently, so a newer GILDAS-only
    release does not steal ``latest-piic`` from the newest PIIC one).
    Pass True to tag every command with ``latest``, False for none.
    """

    sets = _load_release_sets(repo, include_archive, archive_gildas)
    # Deduplicate: the same release appears in main+archive and gildas+piic.
    all_releases = sorted(
        set(sets.archived_gildas) | set(sets.gildas) | set(sets.archived_piic) | set(sets.piic),
        key=_release_sort_key,
    )
    gildas_releases = sorted(set(sets.gildas) | set(sets.archived_gildas), key=_release_sort_key)
    piic_releases = sorted(
        # A PIIC image needs both tarballs, so intersect with GILDAS ones.
        (set(sets.piic) | set(sets.archived_piic)) & (set(sets.gildas) | set(sets.archived_gildas)),
        key=_release_sort_key,
    )
    newest_gildas = gildas_releases[-1] if gildas_releases else None
    newest_piic = piic_releases[-1] if piic_releases else None

    commands: List[BuildCommand] = []

    for release in all_releases:
        if tag_latest is None:
            g_latest = release == newest_gildas
            p_latest = release == newest_piic
        else:
            g_latest = p_latest = tag_latest
        commands.extend(
            get_release_build_commands(
                release,
                missing_only=missing_only,
                dockerfile=dockerfile,
                repo=repo,
                tag_latest=g_latest,
                tag_latest_piic=p_latest,
                sets=sets,
                include_archive=include_archive,
                archive_gildas=archive_gildas,
                imager_version=imager_version,
            )
        )

    return commands


@dataclass
class NatifCommand:
    """Structured representation of a native `singularity build` command."""

    release: str
    has_piic: bool
    command: str
    alpine: bool = False
    imager_version: str = IMAGER_LAST


def natif_command(
    release: str,
    sets: ReleaseSets,
    dockerfile: str = "Dockerfile",
    imager_version: str | None = None,
) -> NatifCommand | None:
    """Return the native SIF build command for a release, if buildable.

    Unlike the Docker targets, a native build always bundles PIIC when
    the corresponding tarball exists upstream, so there is a single
    command per release. Archive URL overrides are included only when
    the release is not in the main distribution tree. The coupled
    IMAGER version is pinned explicitly (auto-mapped when not given).
    """

    gildas = set(sets.gildas) | set(sets.archived_gildas)
    if release not in gildas:
        return None

    has_piic = release in sets.piic or release in sets.archived_piic

    if imager_version is None:
        imager_version = imager_version_for_release(release)

    env = [f"GILDAS_RELEASE={shlex.quote(release)}", f"IMAGER_VERSION={shlex.quote(imager_version)}"]
    if release not in sets.gildas:
        env.append(f"GILDAS_URL={GILDAS_ARCHIVE_URL}")
    if has_piic and release not in sets.piic:
        env.append(f"PIIC_URL={PIIC_ARCHIVE_URL}")

    alpine = dockerfile.endswith("alpine")
    deffile = "gildas-natif-alpine.def" if alpine else "gildas-natif.def"
    sif = f"gildas-{release}-natif-alpine.sif" if alpine else f"gildas-{release}-natif.sif"
    return NatifCommand(
        release=release, has_piic=has_piic, command=f"{' '.join(env)} singularity build {sif} {deffile}", alpine=alpine, imager_version=imager_version
    )


def get_natif_commands(
    dockerfile: str = "Dockerfile.alpine",
    repo: str = DOCKER_REPO,
    include_archive: bool = False,
    archive_gildas: bool = False,
    sets: ReleaseSets | None = None,
    imager_version: str | None = None,
) -> List[NatifCommand]:
    """Return native SIF build commands for all known releases."""

    if sets is None:
        sets = _load_release_sets(repo, include_archive, archive_gildas)
    all_releases = sorted(
        set(sets.archived_gildas) | set(sets.gildas) | set(sets.archived_piic) | set(sets.piic),
        key=_release_sort_key,
    )
    commands: List[NatifCommand] = []
    for release in all_releases:
        cmd = natif_command(release, sets, dockerfile=dockerfile, imager_version=imager_version)
        if cmd:
            commands.append(cmd)
    return commands


def _format_natif_comment(cmd: NatifCommand) -> str:
    """Return a human-readable comment line for a native build command."""

    tag = f"{cmd.release}-natif-alpine" if cmd.alpine else f"{cmd.release}-natif"
    extra = " (+piic bundled)" if cmd.has_piic else " (no piic upstream)"
    return f"# * {tag}{extra} [imager {cmd.imager_version}]"


def _image_tag(cmd: BuildCommand) -> str:
    """Return the Docker Hub tag implied by a build command."""

    suffix = "" if cmd.alpine else "-debian"
    if cmd.section == SECTION_WITHOUT_PIIC:
        return f"{cmd.release}{suffix}"
    if cmd.section == SECTION_WITH_PIIC:
        return f"{cmd.release}-piic{suffix}"
    return cmd.release


def singularity_command(cmd: BuildCommand, repo: str = DOCKER_REPO) -> str:
    """Return a `singularity build` command pulling the Docker Hub image."""

    tag = _image_tag(cmd)
    image = repo.split("/")[-1]
    return f"singularity build {image}-{tag}.sif docker://{repo}:{tag}"


def _render_command(cmd: BuildCommand, repo: str, singularity: bool) -> str:
    """Return the printable/runnable command for a build entry."""

    return singularity_command(cmd, repo) if singularity else cmd.command


def _format_comment(cmd: BuildCommand) -> str:
    """Return a human-readable comment line for a build command."""

    tag = _image_tag(cmd)

    if cmd.section == SECTION_WITHOUT_PIIC:
        if cmd.in_dockerhub:
            return f"# * {tag} already in dockerhub :"
        return f"# * {tag} not in dockerhub"

    if cmd.section == SECTION_WITH_PIIC:
        if cmd.in_dockerhub:
            return f"# * {tag} already in dockerhub :"
        return f"# * {tag} not in dockerhub launch :"

    return f"# * {cmd.release}"


def print_natif_build_commands(
    dockerfile: str = "Dockerfile.alpine",
    repo: str = DOCKER_REPO,
    as_json: bool = False,
    execute: bool = False,
    include_archive: bool = False,
    imager_version: str | None = None,
    piic_only: bool = False,
    archive_gildas: bool = False,
) -> None:
    """Print (or execute) native `singularity build ... .def` commands."""

    commands = get_natif_commands(
        dockerfile=dockerfile,
        repo=repo,
        include_archive=include_archive,
        archive_gildas=archive_gildas,
        imager_version=imager_version,
    )
    if piic_only:
        commands = [c for c in commands if c.has_piic]

    if as_json:
        print(
            json.dumps(
                [
                    {
                        "section": "natif",
                        "release": c.release,
                        "has_piic": c.has_piic,
                        "alpine": c.alpine,
                        "imager_version": c.imager_version,
                        "command": c.command,
                    }
                    for c in commands
                ],
                indent=2,
            )
        )
        return

    print("# Natif (from tarballs, PIIC bundled when available)")
    for cmd in commands:
        print(_format_natif_comment(cmd))
        print(cmd.command)
        if execute:
            subprocess.run(cmd.command, shell=True, check=True)


def print_missing_build_commands(
    force: bool = False,
    dockerfile: str = "Dockerfile.alpine",
    repo: str = DOCKER_REPO,
    tag_latest: bool | None = None,
    as_json: bool = False,
    execute: bool = False,
    include_archive: bool = False,
    singularity: bool = False,
    natif: bool = False,
    imager_version: str | None = None,
    piic_only: bool = False,
    archive_gildas: bool = False,
) -> None:
    """Print (or execute) docker commands for missing releases.

    With ``singularity=True``, emit ``singularity build ... docker://...``
    commands instead. Singularity images pull from Docker Hub, so all
    known releases are listed (``missing_only`` is ignored).

    With ``natif=True``, emit native ``singularity build ... .def``
    commands (one per release, PIIC bundled when available) instead.

    With ``piic_only=True``, only emit PIIC commands (native: only
    releases with a PIIC tarball upstream).

    ``imager_version`` overrides the coupled IMAGER version (auto-mapped
    from each release when not given).
    """

    if natif:
        print_natif_build_commands(
            dockerfile=dockerfile,
            repo=repo,
            as_json=as_json,
            execute=execute,
            include_archive=include_archive,
            imager_version=imager_version,
            piic_only=piic_only,
            archive_gildas=archive_gildas,
        )
        return

    commands = get_build_commands(
        missing_only=not force and not singularity,
        dockerfile=dockerfile,
        repo=repo,
        tag_latest=tag_latest,
        include_archive=include_archive,
        archive_gildas=archive_gildas,
        imager_version=imager_version,
    )

    if as_json:
        print(
            json.dumps(
                [
                    {
                        "section": c.section,
                        "release": c.release,
                        "in_dockerhub": c.in_dockerhub,
                        "alpine": c.alpine,
                        "command": _render_command(c, repo, singularity),
                    }
                    for c in commands
                    if not piic_only or c.section == SECTION_WITH_PIIC
                ],
                indent=2,
            )
        )
        return

    without_piic = sorted(
        [cmd for cmd in commands if cmd.section == SECTION_WITHOUT_PIIC],
        key=lambda c: _release_sort_key(c.release),
    )
    with_piic = sorted(
        [cmd for cmd in commands if cmd.section == SECTION_WITH_PIIC],
        key=lambda c: _release_sort_key(c.release),
    )

    sections = ((with_piic, "# With piic"),) if piic_only else ((without_piic, "# Without piic"), (with_piic, "# With piic"))
    for section_cmds, title in sections:
        if not section_cmds:
            continue
        print(title)
        for cmd in section_cmds:
            print(_format_comment(cmd))
            rendered = _render_command(cmd, repo, singularity)
            print(rendered)
            if execute:
                subprocess.run(rendered, shell=True, check=True)


@click.command()
@click.option(
    "--release",
    "release_name",
    default=None,
    help="Specific GILDAS release (e.g. jan26a). If omitted, print commands for all missing releases.",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (-v info, -vv debug).",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    help="Include releases already present on Docker Hub when listing all.",
)
@click.option(
    "--debian",
    is_flag=True,
    help="Use the Debian-based Dockerfile (default is Alpine/Dockerfile.alpine).",
)
@click.option(
    "--piic",
    "piic_only",
    is_flag=True,
    help="Only emit PIIC build commands. Pairs main-tree PIIC releases with GILDAS from main or archive (add --archive to also search PIIC in the archives).",
)
@click.option(
    "--dockerfile",
    "dockerfile_opt",
    default=None,
    help="Dockerfile to use (overrides the Alpine default / --debian).",
)
@click.option(
    "--repo",
    "repo",
    default=DOCKER_REPO,
    show_default=True,
    help="Docker Hub repository (user/image).",
)
@click.option(
    "--tag-latest/--no-tag-latest",
    "tag_latest",
    default=None,
    help="Also tag/push 'latest'. Default: newest release per family gets 'latest'; single --release always tags.",
)
@click.option(
    "--archive",
    "include_archive",
    is_flag=True,
    default=False,
    help="Also include archived releases (slower: queries the archive trees).",
)
@click.option(
    "--singularity",
    "singularity",
    is_flag=True,
    default=False,
    help="Emit 'singularity build ... docker://...' commands instead of docker build/push.",
)
@click.option(
    "--natif",
    "natif",
    is_flag=True,
    default=False,
    help="Emit native 'singularity build ... .def' commands (from tarballs, PIIC bundled when available).",
)
@click.option(
    "--imager-version",
    "imager_version",
    default=None,
    help="Pin the coupled IMAGER version (default: auto-mapped from the release, e.g. oct26a -> oct26, fallback 'last').",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Emit machine-readable JSON instead of shell commands.",
)
@click.option(
    "--execute",
    is_flag=True,
    help="Run the generated docker build/push commands instead of only printing them.",
)
def main(
    release_name: str | None = None,
    verbose: int = 0,
    force: bool = False,
    debian: bool = False,
    piic_only: bool = False,
    dockerfile_opt: str | None = None,
    repo: str = DOCKER_REPO,
    tag_latest: bool | None = None,
    as_json: bool = False,
    execute: bool = False,
    include_archive: bool = False,
    singularity: bool = False,
    natif: bool = False,
    imager_version: str | None = None,
) -> None:
    """Print (or run) docker build/push commands for GILDAS releases.

    With --singularity, print `singularity build ... docker://...`
    commands instead. With --natif, print native
    `singularity build ... .def` commands instead. The coupled IMAGER
    version is auto-mapped from each release unless --imager-version
    overrides it.
    """

    # Configure logging
    level = logging.WARNING
    if verbose == 1:
        level = logging.INFO
    elif verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)s:%(name)s:%(message)s")

    if dockerfile_opt:
        dockerfile = dockerfile_opt
    else:
        dockerfile = "Dockerfile" if debian else "Dockerfile.alpine"

    # PIIC releases lag behind GILDAS ones, so pairing a main-tree PIIC
    # with its GILDAS tarball usually requires the GILDAS archive.
    archive_gildas = include_archive or piic_only

    if not release_name:
        print_missing_build_commands(
            force=force,
            dockerfile=dockerfile,
            repo=repo,
            tag_latest=tag_latest,
            as_json=as_json,
            execute=execute,
            include_archive=include_archive,
            singularity=singularity,
            natif=natif,
            imager_version=imager_version,
            piic_only=piic_only,
            archive_gildas=archive_gildas,
        )
        return

    # Single release mode: tag latest by default (opt out with --no-tag-latest).
    if tag_latest is None:
        tag_latest = True
    sets = _load_release_sets(repo, include_archive, archive_gildas)
    all_known = set(sets.gildas) | set(sets.archived_gildas) | set(sets.piic) | set(sets.archived_piic)
    if release_name not in all_known:
        hint = "" if include_archive else " (retry with --archive for archived releases)"
        logger.warning("Release '%s' not found upstream%s; emitting nothing", release_name, hint)

    if natif:
        cmd = natif_command(release_name, sets, dockerfile=dockerfile, imager_version=imager_version)
        if piic_only and (cmd is None or not cmd.has_piic):
            if as_json:
                print(json.dumps([]))
            return
        if as_json:
            print(json.dumps([] if cmd is None else [{"release": cmd.release, "has_piic": cmd.has_piic, "alpine": cmd.alpine, "imager_version": cmd.imager_version, "command": cmd.command}], indent=2))
            return
        if cmd is None:
            return
        print("# Natif (from tarballs, PIIC bundled when available)")
        print(_format_natif_comment(cmd))
        print(cmd.command)
        if execute:
            subprocess.run(cmd.command, shell=True, check=True)
        return

    commands = get_release_build_commands(
        release_name,
        dockerfile=dockerfile,
        repo=repo,
        tag_latest=tag_latest,
        sets=sets,
        include_archive=include_archive,
        archive_gildas=archive_gildas,
        imager_version=imager_version,
    )

    if as_json:
        print(
            json.dumps(
                [
                    {
                        "section": c.section,
                        "release": c.release,
                        "in_dockerhub": c.in_dockerhub,
                        "alpine": c.alpine,
                        "command": _render_command(c, repo, singularity),
                    }
                    for c in commands
                    if not piic_only or c.section == SECTION_WITH_PIIC
                ],
                indent=2,
            )
        )
        return

    if not piic_only and any(cmd.section == SECTION_WITHOUT_PIIC for cmd in commands):
        print("# Without piic")
        for cmd in commands:
            if cmd.section != SECTION_WITHOUT_PIIC:
                continue
            print(_format_comment(cmd))
            rendered = _render_command(cmd, repo, singularity)
            print(rendered)
            if execute:
                subprocess.run(rendered, shell=True, check=True)

    if any(cmd.section == SECTION_WITH_PIIC for cmd in commands):
        print("# With piic")
        for cmd in commands:
            if cmd.section != SECTION_WITH_PIIC:
                continue
            print(_format_comment(cmd))
            rendered = _render_command(cmd, repo, singularity)
            print(rendered)
            if execute:
                subprocess.run(rendered, shell=True, check=True)


if __name__ == "__main__":
    main()
