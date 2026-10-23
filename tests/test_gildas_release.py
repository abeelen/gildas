"""Offline tests for gildas_release.py (no network: fake ReleaseSets throughout)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gildas_release import (  # noqa: E402
    SECTION_WITH_PIIC,
    SECTION_WITHOUT_PIIC,
    BuildCommand,
    ReleaseSets,
    _image_tag,
    _tag_suffix,
    build_with_piic_command,
    build_without_piic_command,
    get_build_commands,
    get_natif_commands,
    get_release_build_commands,
    imager_version_for_release,
    natif_command,
    singularity_command,
)


def make_sets(**overrides):
    base = dict(
        tags=[],
        gildas=["oct26a"],
        archived_gildas=["jul26a"],
        piic=["jul26a"],
        archived_piic=["mar26a"],
    )
    base.update(overrides)
    return ReleaseSets(**base)


def test_tag_suffix():
    assert _tag_suffix("docker/Dockerfile.alpine") == "-alpine"
    assert _tag_suffix("docker/Dockerfile.debian") == "-debian"
    assert _tag_suffix("docker/Dockerfile.custom") == "-debian"


def test_image_tag():
    assert _image_tag(BuildCommand(SECTION_WITHOUT_PIIC, "oct26a", False, "x", True)) == "oct26a-alpine"
    assert _image_tag(BuildCommand(SECTION_WITHOUT_PIIC, "oct26a", False, "x", False)) == "oct26a-debian"
    assert _image_tag(BuildCommand(SECTION_WITH_PIIC, "jul26a", False, "x", True)) == "jul26a-piic-alpine"
    assert _image_tag(BuildCommand(SECTION_WITH_PIIC, "jul26a", False, "x", False)) == "jul26a-piic-debian"


def test_imager_version_mapping():
    assert imager_version_for_release("oct26a", ["oct26", "jul26"]) == "oct26"
    assert imager_version_for_release("oct26a", ["jul26"]) == "last"
    assert imager_version_for_release("oct26", ["oct26"]) == "oct26"


def test_cached_imager_versions_fail_open(monkeypatch):
    import gildas_release as gr

    def down():
        raise OSError("upstream unreachable")

    monkeypatch.setattr(gr, "imager_release", down)
    gr._cached_imager_versions.cache_clear()
    try:
        assert gr._cached_imager_versions() is None
    finally:
        gr._cached_imager_versions.cache_clear()


def test_ci_warning_github_annotation(monkeypatch, capsys):
    import gildas_release as gr

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("GITLAB_CI", raising=False)
    gr._ci_warning("IMAGER not bundled", "upstream unreachable")

    captured = capsys.readouterr()
    assert captured.out == ""
    err = captured.err
    assert err.startswith("::warning title=IMAGER not bundled::")
    assert "upstream unreachable" in err


def test_ci_warning_gitlab_log(monkeypatch, capsys):
    import gildas_release as gr

    monkeypatch.setenv("GITLAB_CI", "true")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    gr._ci_warning("PIIC not bundled", "listing failed")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "WARNING: PIIC not bundled: listing failed" in captured.err


def test_ci_warning_plain_terminal(monkeypatch, capsys):
    import gildas_release as gr

    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITLAB_CI", raising=False)
    gr._ci_warning("IMAGER not bundled", "offline")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "WARNING: IMAGER not bundled: offline\n"


def test_imager_listing_failure_emits_ci_warning(monkeypatch, capsys):
    import gildas_release as gr

    def down():
        raise OSError("upstream unreachable")

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("GITLAB_CI", raising=False)
    monkeypatch.setattr(gr, "imager_release", down)
    gr._cached_imager_versions.cache_clear()
    try:
        assert gr._cached_imager_versions() is None
    finally:
        gr._cached_imager_versions.cache_clear()

    captured = capsys.readouterr()
    # stdout must stay clean: workflows capture it to resolve build commands,
    # and a ::warning line there previously broke the generated shell.
    assert captured.out == ""
    assert "::warning title=IMAGER not bundled::" in captured.err
    assert "IMAGER_VERSION=none" in captured.err


def test_imager_lookup_failure_skips_imager_without_second_request(monkeypatch):
    import gildas_release as gr

    monkeypatch.setattr(gr, "_cached_imager_versions", lambda: None)

    def unexpected(*args, **kwargs):
        raise AssertionError("alias resolution must be skipped when listing failed")

    monkeypatch.setattr(gr, "_resolve_imager_alias", unexpected)
    assert imager_version_for_release("oct26a") == "none"


def test_build_sets_with_imager_zero_when_upstream_unreachable():
    cmd = build_without_piic_command(
        ["oct26a"], [], "oct26a", imager_version="none"
    )
    assert "--build-arg IMAGER_VERSION=none" in cmd
    assert "--build-arg WITH_IMAGER=0" in cmd


def test_natif_disables_imager_when_upstream_unreachable():
    sets = make_sets()
    cmd = natif_command("oct26a", sets, imager_version="none")
    assert cmd is not None
    assert "SINGULARITYENV_WITH_IMAGER=0" in cmd.command
    assert "SINGULARITYENV_IMAGER_VERSION=none" in cmd.command


def test_build_without_piic_alpine_is_default():
    cmd = build_without_piic_command(["oct26a"], [], "oct26a", imager_version="oct26")
    assert "--tag abeelen/gildas:oct26a-alpine " in cmd
    assert "-f docker/Dockerfile.alpine ." in cmd
    assert "--target gildas" in cmd
    assert "--build-arg IMAGER_VERSION=oct26" in cmd
    assert "latest" not in cmd


def test_build_without_piic_latest_alias():
    cmd = build_without_piic_command(
        ["oct26a"], [], "oct26a", tag_latest=True, imager_version="oct26"
    )
    assert "--tag abeelen/gildas:oct26a-alpine" in cmd
    assert "--tag abeelen/gildas:latest-alpine" in cmd
    # Unsuffixed latest is an alias of the Alpine image.
    assert "--tag abeelen/gildas:latest " in cmd or cmd.rstrip().endswith("abeelen/gildas:latest")
    assert "docker push abeelen/gildas:latest-alpine" in cmd
    assert "docker push abeelen/gildas:latest" in cmd


def test_build_without_piic_latest_and_debian():
    cmd = build_without_piic_command(
        ["oct26a"], [], "oct26a", dockerfile="docker/Dockerfile.debian", tag_latest=True, imager_version="oct26"
    )
    assert "--tag abeelen/gildas:oct26a-debian" in cmd
    assert "--tag abeelen/gildas:latest-debian" in cmd
    assert "-f docker/Dockerfile.debian ." in cmd


def test_build_with_piic_needs_both_tarballs():
    # No PIIC tarball -> no command.
    assert (
        build_with_piic_command(["oct26a"], [], ["jul26a"], [], "oct26a", imager_version="oct26")
        is None
    )
    # No GILDAS tarball -> no command.
    assert (
        build_with_piic_command(["oct26a"], [], ["oct26a"], [], "jul26a", imager_version="jul26")
        is None
    )
    # Archived GILDAS + main PIIC -> archive URL only for GILDAS.
    cmd = build_with_piic_command(
        ["oct26a"], ["jul26a"], ["jul26a"], [], "jul26a", imager_version="jul26"
    )
    assert "--tag abeelen/gildas:jul26a-piic-alpine " in cmd
    assert "GILDAS_URL=https://www.iram.fr/~gildas/dist/archive/gildas" in cmd
    assert "PIIC_URL" not in cmd
    assert "--build-arg PIIC_VERSION=jul26a" in cmd


def test_release_commands_pair_main_piic_with_archived_gildas():
    cmds = get_release_build_commands(
        "jul26a", sets=make_sets(), archive_gildas=True, imager_version="jul26"
    )
    piic = [c for c in cmds if c.section == SECTION_WITH_PIIC]
    assert len(piic) == 1
    assert "GILDAS_URL=" in piic[0].command and "PIIC_URL" not in piic[0].command


def test_archived_gildas_ignored_without_flag():
    # Same fixture, no flag: jul26a is unknown -> no commands at all.
    assert (
        get_release_build_commands("jul26a", sets=make_sets(), imager_version="jul26") == []
    )


def test_missing_only_hides_present_tags(monkeypatch):
    import gildas_release as gr

    sets = make_sets(tags=["oct26a-alpine"])
    monkeypatch.setattr(
        gr, "_image_labels", lambda tag: {"abeelen.gildas.imager-version": "oct26"}
    )
    cmds = get_release_build_commands("oct26a", missing_only=True, sets=sets, imager_version="oct26")
    assert cmds == []
    cmds = get_release_build_commands("oct26a", missing_only=False, sets=sets, imager_version="oct26")
    assert len(cmds) == 1 and cmds[0].in_dockerhub


def test_latest_tracked_per_family(monkeypatch):
    import gildas_release as gr

    monkeypatch.setattr(gr, "_load_release_sets", lambda *a, **k: make_sets(tags=[]))
    cmds = get_build_commands(archive_gildas=True, imager_version="oct26")
    by_release = {}
    for c in cmds:
        by_release.setdefault(c.release, []).append(c)
    # Newest GILDAS (oct26a) gets :latest ...
    gildas_cmd = next(c for c in by_release["oct26a"] if c.section == SECTION_WITHOUT_PIIC)
    assert gildas_cmd.command.endswith("docker push abeelen/gildas:latest")
    # ... but not :latest-piic (no PIIC tarball for oct26a) ...
    for c in by_release["oct26a"]:
        assert "latest-piic" not in c.command
    # ... while newest with PIIC (jul26a) gets :latest-piic.
    piic_cmd = next(c for c in by_release["jul26a"] if c.section == SECTION_WITH_PIIC)
    assert piic_cmd.command.endswith("docker push abeelen/gildas:latest-piic")


def test_natif_command_bundles_piic_when_available():
    sets = make_sets()
    cmd = natif_command("jul26a", sets, imager_version="jul26")
    assert cmd is not None and cmd.has_piic
    assert "PIIC_URL=https://www.iram.fr/~gildas/dist/archive/piic" not in cmd.command
    assert "GILDAS_URL=https://www.iram.fr/~gildas/dist/archive/gildas" in cmd.command
    assert "apptainer/gildas-native-alpine.def" in cmd.command
    assert "gildas-jul26a-piic-native-alpine.sif" in cmd.command
    cmd = natif_command("oct26a", sets, imager_version="oct26")
    assert cmd is not None and not cmd.has_piic
    assert "gildas-oct26a-native-alpine.sif" in cmd.command
    assert natif_command("nosuch", sets) is None


def test_natif_always_uses_alpine_recipe():
    sets = make_sets()
    cmd = natif_command("oct26a", sets, dockerfile="docker/Dockerfile.debian", imager_version="oct26")
    assert cmd is not None and cmd.alpine is True
    assert "apptainer/gildas-native-alpine.def" in cmd.command
    assert "gildas-oct26a-native-alpine.sif" in cmd.command
    assert "-natif" not in cmd.command


def test_natif_commands_follow_loaded_sets():
    full = make_sets(archived_gildas=["jul26a", "mar26a"])  # as if loaded with archives
    cmds = get_natif_commands(sets=full, imager_version="jul26")
    assert {c.release for c in cmds} >= {"oct26a", "jul26a", "mar26a"}
    main_only = make_sets(archived_gildas=[], archived_piic=[])
    cmds = get_natif_commands(sets=main_only, imager_version="oct26")
    assert [c.release for c in cmds] == ["oct26a"]


def test_singularity_command(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "apptainer").mkdir()
    (tmp_path / "apptainer" / "gildas-docker.def").write_text(
        "Bootstrap: docker\nFrom: abeelen/gildas:latest\n"
    )
    cmd = BuildCommand(SECTION_WITH_PIIC, "jul26a", False, "x", True)
    assert singularity_command(cmd) == (
        "singularity build gildas-jul26a-piic-alpine.sif gildas-jul26a-piic-alpine.def"
    )
    dest = tmp_path / "gildas-jul26a-piic-alpine.def"
    assert "From: abeelen/gildas:jul26a-piic-alpine" in dest.read_text()


def test_print_missing_piic_only(monkeypatch, capsys):
    import gildas_release as gr

    monkeypatch.setattr(gr, "_load_release_sets", lambda *a, **k: make_sets())
    gr.print_missing_build_commands(imager_version="oct26", piic_only=True, archive_gildas=True)
    out = capsys.readouterr().out
    assert "# With piic" in out
    assert "# Without piic" not in out


def _fake_tgz(topdir):
    import gzip
    import io
    import tarfile

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(topdir)
        info.type = tarfile.DIRTYPE
        tar.addfile(info)
    buf.seek(0)
    return buf.read()


class _FakeRawResponse:
    def __init__(self, payload=None, exc=None):
        from io import BytesIO

        self._payload = BytesIO(payload) if payload else None
        self._exc = exc

    def __enter__(self):
        if self._exc:
            raise self._exc
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    @property
    def raw(self):
        return self._payload


def test_resolve_imager_alias_failure_returns_alias(monkeypatch):
    import gildas_release as gr

    monkeypatch.setattr(gr.requests, "get", lambda *a, **k: _FakeRawResponse(exc=OSError("down")))
    assert gr._resolve_imager_alias.__wrapped__("last") == "last"


def test_resolve_imager_alias_reads_top_dir(monkeypatch):
    import gildas_release as gr

    payload = _fake_tgz("imager-src-oct26/")
    monkeypatch.setattr(gr.requests, "get", lambda *a, **k: _FakeRawResponse(payload))
    assert gr._resolve_imager_alias.__wrapped__("last") == "oct26"


def test_imager_stale_matrix(monkeypatch):
    import gildas_release as gr

    cases = [
        (None, "oct26", False),  # unreadable labels: never rebuild on network errors
        ({}, "oct26", True),  # pre-label image: rebuild once
        ({"abeelen.gildas.imager-version": "oct26"}, "oct26", False),
        ({"abeelen.gildas.imager-version": "oct26"}, "nov26", True),
        ({"abeelen.gildas.imager-version": "last"}, "nov26", False),
        ({"abeelen.gildas.imager-version": "oct26"}, "last", False),
        # Built while IMAGER was unreachable: rebuild once it is back.
        ({"abeelen.gildas.imager-version": "none"}, "oct26", True),
        ({"abeelen.gildas.imager-version": "none"}, "last", True),
        ({"abeelen.gildas.imager-version": "none"}, "none", False),
        ({"abeelen.gildas.imager-bundled": "0"}, "oct26", True),
    ]
    for labels, expected, stale in cases:
        monkeypatch.setattr(gr, "_image_labels", lambda tag: labels)
        assert gr._imager_stale("oct26a", expected) is stale


def test_piic_stale_matrix(monkeypatch):
    import gildas_release as gr

    cases = [
        (None, "jul26a", False),  # unreadable labels: never rebuild on network errors
        ({}, "jul26a", False),  # pre-label image: assume it was built with PIIC
        ({"abeelen.gildas.piic-version": "jul26a"}, "jul26a", False),
        ({"abeelen.gildas.piic-version": "jul26a"}, "oct26a", True),
        ({"abeelen.gildas.piic-version": "none"}, "jul26a", True),
        ({"abeelen.gildas.piic-bundled": "0"}, "jul26a", True),
        ({"abeelen.gildas.piic-version": "none"}, "none", False),
    ]
    for labels, expected, stale in cases:
        monkeypatch.setattr(gr, "_image_labels", lambda tag: labels)
        assert gr._piic_stale("jul26a-piic-alpine", expected) is stale


def test_piic_listing_failure_is_fail_open(monkeypatch, capsys):
    import gildas_release as gr

    def fake(package, archive=False):
        if package == "piic":
            raise OSError("upstream unreachable")
        return ["oct26a"]

    monkeypatch.setenv("GITLAB_CI", "true")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr(gr, "gildas_release", fake)
    monkeypatch.setattr(gr, "_docker_tags", lambda: [])
    sets = gr._load_release_sets_uncached()
    assert sets.gildas == ["oct26a"]
    assert sets.piic == [] and sets.archived_piic == []
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "WARNING: PIIC not bundled:" in captured.err


def test_missing_piic_tag_is_rebuilt_when_piic_returns(monkeypatch):
    import gildas_release as gr

    sets = make_sets(tags=["jul26a-piic-alpine"])
    monkeypatch.setattr(
        gr, "_image_labels",
        lambda tag: {"abeelen.gildas.piic-version": "none", "abeelen.gildas.piic-bundled": "0"},
    )
    cmds = get_release_build_commands(
        "jul26a", missing_only=True, sets=sets, archive_gildas=True, imager_version="jul26"
    )
    piic = [c for c in cmds if c.section == SECTION_WITH_PIIC]
    assert len(piic) == 1 and piic[0].stale_piic
    assert "PIIC missing" in gr._format_comment(piic[0])


def test_stale_imager_rebuilds_present_tag(monkeypatch):
    import gildas_release as gr

    sets = make_sets(tags=["oct26a-alpine"])
    monkeypatch.setattr(
        gr, "_image_labels", lambda tag: {"abeelen.gildas.imager-version": "oct26"}
    )
    cmds = get_release_build_commands(
        "oct26a", missing_only=True, sets=sets, imager_version="nov26"
    )
    assert len(cmds) == 1 and cmds[0].stale_imager
    assert "IMAGER outdated" in gr._format_comment(cmds[0])
    # Matching labels: still skipped when missing_only.
    monkeypatch.setattr(
        gr, "_image_labels", lambda tag: {"abeelen.gildas.imager-version": "nov26"}
    )
    cmds = get_release_build_commands(
        "oct26a", missing_only=True, sets=sets, imager_version="nov26"
    )
    assert cmds == []


def test_missing_tag_built_without_imager_is_rebuilt_when_upstream_returns(monkeypatch):
    import gildas_release as gr

    sets = make_sets(tags=["oct26a-alpine"])
    monkeypatch.setattr(
        gr, "_image_labels",
        lambda tag: {"abeelen.gildas.imager-version": "none", "abeelen.gildas.imager-bundled": "0"},
    )
    # Upstream reachable again: the IMAGER-less image is stale.
    cmds = get_release_build_commands(
        "oct26a", missing_only=True, sets=sets, imager_version="oct26"
    )
    assert len(cmds) == 1 and cmds[0].stale_imager
    # Upstream still down: nothing better to build, so keep the image.
    cmds = get_release_build_commands(
        "oct26a", missing_only=True, sets=sets, imager_version="none"
    )
    assert cmds == []


def test_stale_check_only_for_main_releases(monkeypatch):
    import gildas_release as gr

    # Archived release with mocked labels: existence alone decides.
    sets = make_sets(
        tags=["mar26a-alpine", "mar26a-piic-alpine"],
        archived_gildas=["mar26a"],
        archived_piic=["mar26a"],
    )
    monkeypatch.setattr(gr, "_image_labels", lambda tag: {"abeelen.gildas.imager-version": "old"})
    cmds = get_release_build_commands(
        "mar26a", missing_only=True, sets=sets, include_archive=True, imager_version="new"
    )
    assert cmds == []


def test_run_logged_to_file(tmp_path, capsys):
    from gildas_release import _run_logged

    log = tmp_path / "sub" / "x.log"
    _run_logged("echo hello && echo world", str(log), tail=1)
    assert log.read_text().splitlines() == ["hello", "world"]
    out = capsys.readouterr().out
    assert "# log:" in out and out.rstrip().endswith("world")


def test_run_logged_failure_prints_tail_and_raises(tmp_path, capsys):
    import subprocess

    from gildas_release import _run_logged

    with pytest.raises(subprocess.CalledProcessError):
        _run_logged("echo oops && exit 3", str(tmp_path / "f.log"), tail=5)
    out = capsys.readouterr().out
    assert "oops" in out


def test_run_logged_passthrough(capfd):
    from gildas_release import _run_logged

    _run_logged("echo direct")
    assert "direct" in capfd.readouterr().out


def test_natif_tag():
    from gildas_release import NatifCommand, _natif_tag

    assert _natif_tag(NatifCommand("r", True, "c", True, "i")) == "r-piic-native-alpine"
    assert _natif_tag(NatifCommand("r", False, "c", True, "i")) == "r-native-alpine"
    assert _natif_tag(NatifCommand("r", True, "c", False, "i")) == "r-piic-native-debian"


def test_execute_log_paths(monkeypatch, tmp_path):
    import gildas_release as gr

    seen = []
    monkeypatch.setattr(gr, "_run_logged", lambda cmd, log=None: seen.append((cmd, log)))
    cmds = get_release_build_commands(
        "jul26a", sets=make_sets(), archive_gildas=True, imager_version="jul26"
    )
    gr._print_command_sections(cmds, False, True, False, str(tmp_path))
    logs = sorted(log for _, log in seen)
    assert logs == [str(tmp_path / "jul26a-alpine.log"), str(tmp_path / "jul26a-piic-alpine.log")]
    # Without log_dir: plain execution, log None.
    seen.clear()
    gr._print_command_sections(cmds, False, True, False, None)
    assert seen and all(log is None for _, log in seen)
