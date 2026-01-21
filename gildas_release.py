#!/usr/bin/env python3
import functools
import logging
from dataclasses import dataclass
from typing import List, Sequence

import click
import requests
from bs4 import BeautifulSoup

DOCKER_REPO = "abeelen/gildas"
GILDAS_MAIN_URL = "https://www.iram.fr/~gildas/dist"
GILDAS_ARCHIVE_URL = "https://www.iram.fr/~gildas/dist/archive/gildas"
PIIC_ARCHIVE_URL = "https://www.iram.fr/~gildas/dist/archive/piic"

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
        package = "gildas-src"
    elif package == "piic":
        package = "piic-exe"
    else:
        logger.error("Unknown package '%s' requested in gildas_release", package)
        raise ValueError(f"Unknown package '{package}'")

    s = requests.Session()
    r = s.get(uri)
    soup = BeautifulSoup(r.text, features="lxml")
    links = [link.attrs["href"] for link in soup.find_all("a") if ".tar.xz" in link.attrs["href"]]
    releases = [filename.split("-")[2].split(".")[0] for filename in links if filename.startswith(package)]

    # Cleaning...
    releases = [release for release in releases if release != "ifort"]

    return releases


def _docker_tags(repo: str = DOCKER_REPO) -> List[str]:
    """Return existing tags for the Docker repository.

    Parameters
    ----------
    repo : str, optional
        Docker Hub repository in the form ``"user/image"``. Defaults to
        ``DOCKER_REPO``.

    Returns
    -------
    list of str
        Tags present on Docker Hub, excluding ``"latest"`` and ``"build"``.

    Raises
    ------
    requests.HTTPError
        If the Docker Hub API request fails.
    """
    s = requests.Session()
    r = s.get(f"https://registry.hub.docker.com/v2/repositories/{repo}/tags/?page_size=1000")
    r.raise_for_status()
    return [item["name"] for item in r.json().get("results", []) if item["name"] not in ["latest", "build"]]


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
        Human‑readable package name used for error messages.

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


def _release_sort_key(release: str) -> tuple[int, int, int]:
    """Sort key to order releases chronologically.

    Assumes releases are named like ``monYYx`` where ``mon`` is a
    three-letter English month abbreviation, ``YY`` the two-digit year,
    and ``x`` an optional letter within the month (a, b, c, ...).
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
        year = int(year_part)
        # Map 'a' -> 1, 'b' -> 2, ...; default to 0 if unexpected
        sub = ord(letter.lower()) - ord("a") + 1 if letter.isalpha() else 0
        return year, month, sub
    except Exception:
        # Fallback: group unknown patterns first, ordered lexicographically
        logger.warning("Unable to parse release name '%s' for sorting", release)
        return 0, 0, 0


@dataclass(frozen=True)
class ReleaseSets:
    """Container for Docker tags and known upstream releases."""

    tags: List[str]
    gildas: List[str]
    archived_gildas: List[str]
    piic: List[str]
    archived_piic: List[str]


@functools.lru_cache(maxsize=1)
def _load_release_sets() -> ReleaseSets:
    """Load Docker tags and all known releases for GILDAS and PIIC.

    Returns
    -------
    tags : list of str
        Existing Docker tags on the configured repository.
    gildas : list of str
        Releases found in the main GILDAS tree.
    archived_gildas : list of str
        Releases found in the GILDAS archive tree.
    piic : list of str
        Releases found in the main PIIC tree.
    archived_piic : list of str
        Releases found in the PIIC archive tree.
    """

    tags = _docker_tags()
    gildas = gildas_release("gildas")
    archived_gildas = gildas_release("gildas", archive=True)
    piic = gildas_release("piic")
    archived_piic = gildas_release("piic", archive=True)
    return ReleaseSets(
        tags=tags,
        gildas=gildas,
        archived_gildas=archived_gildas,
        piic=piic,
        archived_piic=archived_piic,
    )


def build_without_piic_command(
    gildas: Sequence[str],
    archived_gildas: Sequence[str],
    release: str,
    dockerfile: str = "Dockerfile",
) -> str:
    """Build docker commands for a GILDAS-only release.

    Parameters
    ----------
    gildas : sequence of str
        Releases available in the main GILDAS tree.
    archived_gildas : sequence of str
        Releases available in the GILDAS archive tree.
    release : str
        Target release identifier.

    Returns
    -------
    str
        ``docker build``/``docker push`` command line for the release.
    """

    arg = _build_arg_for_release(
        release,
        main_releases=gildas,
        archived_releases=archived_gildas,
        arg_name="GILDAS_URL",
        archive_url=GILDAS_ARCHIVE_URL,
        package_name="gildas",
    )

    is_alpine = dockerfile.endswith("alpine")
    if is_alpine:
        main_tag = "${release}-alpine"
        latest_tag = "latest-alpine"
    else:
        main_tag = "${release}"
        latest_tag = "latest"

    parts = [
        f"export release={release};",
        "docker build",
        f"--tag abeelen/gildas:{main_tag}",
        f"--tag abeelen/gildas:{latest_tag}",
        "--target gildas",
        arg,
        "--build-arg release=$release",
        f"-f {dockerfile} .",
        f"&& docker push abeelen/gildas:{main_tag}",
        f"&& docker push abeelen/gildas:{latest_tag}",
    ]
    return " ".join(parts)


def build_with_piic_command(
    gildas: Sequence[str],
    archived_gildas: Sequence[str],
    piic: Sequence[str],
    archived_piic: Sequence[str],
    release: str,
    dockerfile: str = "Dockerfile",
) -> str | None:
    """Build docker commands for a combined GILDAS+PIIC release.

    Parameters
    ----------
    gildas : sequence of str
        Releases available in the main GILDAS tree.
    archived_gildas : sequence of str
        Releases available in the GILDAS archive tree.
    piic : sequence of str
        Releases available in the main PIIC tree.
    archived_piic : sequence of str
        Releases available in the PIIC archive tree.
    release : str
        Target release identifier.

    Returns
    -------
    str or None
        ``docker build``/``docker push`` command line if both GILDAS and
        PIIC releases are available; otherwise ``None``.
    """

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
        # Silent skip if the corresponding gildas release does not exist
        logger.warning("Skipping PIIC build for %s: %s", release, exc)
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
        # Silent skip if the corresponding piic release does not exist
        logger.warning("Skipping PIIC build for %s (no PIIC archive): %s", release, exc)
        return None

    is_alpine = dockerfile.endswith("alpine")
    if is_alpine:
        main_tag = "${release}-piic-alpine"
        latest_tag = "latest-piic-alpine"
    else:
        main_tag = "${release}-piic"
        latest_tag = "latest-piic"

    parts = [
        f"export release={release};",
        "docker build",
        f"--tag abeelen/gildas:{main_tag}",
        f"--tag abeelen/gildas:{latest_tag}",
        "--target gildas-piic",
        g_arg,
        p_arg,
        "--build-arg release=$release",
        f"-f {dockerfile} .",
        f"&& docker push abeelen/gildas:{main_tag}",
        f"&& docker push abeelen/gildas:{latest_tag}",
    ]
    return " ".join(parts)


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
    dockerfile: str = "Dockerfile",
) -> List[BuildCommand]:
    """Return docker commands for a specific release.

    Parameters
    ----------
    release_name : str
        Target release identifier.

    Parameters
    ----------
    missing_only : bool, optional
        If True, only include commands whose corresponding image tag is
        not yet present on Docker Hub. Defaults to False.

    Returns
    -------
    list of BuildCommand
        Commands for the requested release (GILDAS, PIIC, or both),
        optionally filtered to Docker-missing ones only.
    """

    sets = _load_release_sets()
    tags = sets.tags
    gildas = sets.gildas
    archived_gildas = sets.archived_gildas
    piic = sets.piic
    archived_piic = sets.archived_piic

    commands: List[BuildCommand] = []

    is_alpine = dockerfile.endswith("alpine")

    # GILDAS only
    if release_name in gildas or release_name in archived_gildas:
        command = build_without_piic_command(gildas, archived_gildas, release_name, dockerfile=dockerfile)
        base_tag = f"{release_name}-alpine" if is_alpine else release_name
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
        )
        if command:
            piic_tag = f"{release_name}-piic-alpine" if is_alpine else f"{release_name}-piic"
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


def get_build_commands(missing_only: bool = False, dockerfile: str = "Dockerfile") -> List[BuildCommand]:
    """Return docker commands for all known releases.

    Parameters
    ----------
    missing_only : bool, optional
        If True, only include commands whose corresponding image tag is
        not yet present on Docker Hub. Defaults to False.

    Returns
    -------
    list of BuildCommand
        Commands for all known releases (optionally filtered to
        Docker-missing ones only).
    """

    sets = _load_release_sets()
    all_releases = list(sets.archived_gildas) + list(sets.gildas) + list(sets.archived_piic) + list(sets.piic)

    commands: List[BuildCommand] = []

    for release in all_releases:
        commands.extend(
            get_release_build_commands(release, missing_only=missing_only, dockerfile=dockerfile)
        )

    return commands


def _format_comment(cmd: BuildCommand) -> str:
    """Return a human-readable comment line for a build command."""

    if cmd.section == SECTION_WITHOUT_PIIC:
        tag = f"{cmd.release}-alpine" if cmd.alpine else cmd.release
        if cmd.in_dockerhub:
            return f"# * {tag} already in dockerhub :"
        return f"# * {tag} not in dockerhub"

    if cmd.section == SECTION_WITH_PIIC:
        tag = f"{cmd.release}-piic-alpine" if cmd.alpine else f"{cmd.release}-piic"
        if cmd.in_dockerhub:
            return f"# * {tag} already in dockerhub :"
        return f"# * {tag} not in dockerhub launch :"

    return f"# * {cmd.release}"


def print_missing_build_commands(force: bool = False, dockerfile: str = "Dockerfile") -> None:
    """Print docker commands for missing releases.

    The function inspects available tarballs on the IRAM website and tags
    already present on Docker Hub. By default, it prints build/push
    commands only for releases that are not yet published. When
    ``force=True``, commands are printed for all known releases, even if
    they already have tags on Docker Hub.
    """

    commands = get_build_commands(missing_only=not force, dockerfile=dockerfile)

    without_piic = sorted(
        [cmd for cmd in commands if cmd.section == SECTION_WITHOUT_PIIC],
        key=lambda c: _release_sort_key(c.release),
    )
    with_piic = sorted(
        [cmd for cmd in commands if cmd.section == SECTION_WITH_PIIC],
        key=lambda c: _release_sort_key(c.release),
    )

    if without_piic:
        print("# Without piic")
        for cmd in without_piic:
            print(_format_comment(cmd))
            print(cmd.command)

    if with_piic:
        print("# With piic")
        for cmd in with_piic:
            print(_format_comment(cmd))
            print(cmd.command)


@click.command()
@click.option(
    "--release",
    "release_name",
    help="Specific GILDAS release (e.g. jan26a). If omitted, print commands for all missing releases.",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Enable verbose logging (info and warnings).",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    help="Include releases already present on Docker Hub when listing all.",
)
@click.option(
    "--alpine",
    is_flag=True,
    help="Utiliser l'image basee sur Dockerfile.alpine.",
)
def main(
    release_name: str | None = None,
    verbose: bool = False,
    force: bool = False,
    alpine: bool = False,
) -> None:
    """Command-line entry point.

    Parameters
    ----------
    release_name : str or None, optional
        Specific release identifier to target. If ``None`` (the default),
        commands are printed for all missing releases.
    force : bool, optional
        When ``True`` and no specific release is requested, also include
        releases that already have tags on Docker Hub.

    Notes
    -----
    When ``release_name`` is provided, the script will emit commands for
    the GILDAS image, the PIIC image, or both, depending on what is
    available upstream and already present on Docker Hub.
    """

    # Configure logging
    logging.basicConfig(
        level=logging.INFO if verbose else logging.ERROR,
        format="%(levelname)s:%(name)s:%(message)s",
    )

    dockerfile = "Dockerfile.alpine" if alpine else "Dockerfile"

    if not release_name:
        print_missing_build_commands(force=force, dockerfile=dockerfile)
        return

    # Single release mode
    commands = get_release_build_commands(release_name, dockerfile=dockerfile)

    if any(cmd.section == SECTION_WITHOUT_PIIC for cmd in commands):
        print("# Without piic")
        for cmd in commands:
            if cmd.section != SECTION_WITHOUT_PIIC:
                continue
            print(_format_comment(cmd))
            print(cmd.command)

    if any(cmd.section == SECTION_WITH_PIIC for cmd in commands):
        print("# With piic")
        for cmd in commands:
            if cmd.section != SECTION_WITH_PIIC:
                continue
            print(_format_comment(cmd))
            print(cmd.command)


if __name__ == "__main__":
    main()
