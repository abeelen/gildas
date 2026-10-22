"""Offline tests for the shared GILDAS runtime setup script."""

from pathlib import Path
import os
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "gildas-runtime.sh"


def _bin(path: Path, *names: str) -> None:
    path.mkdir(parents=True)
    for name in names:
        prog = path / name
        prog.write_text("#!/bin/sh\n")
        prog.chmod(0o755)


def _tree(tmp_path: Path) -> dict[str, Path]:
    gildas = tmp_path / "gildas-exe-test"
    _bin(gildas / "x86_64-generic" / "bin", "astro")
    (gildas / "etc").mkdir()
    (gildas / "etc" / "bash_profile").write_text("")

    imager = tmp_path / "imager-exe"
    _bin(imager / "x86_64-generic" / "bin", "astro", "imagerprog", "shared")
    (imager / "etc").mkdir()
    (imager / "etc" / "bash_profile").write_text("")

    piic = tmp_path / "piic-exe-test"
    _bin(piic / "x86_64-generic" / "bin", "imagerprog", "piicprog", "shared")
    (piic / "etc").mkdir()
    (piic / "etc" / "bash_profile").write_text("")

    return {"gildas": gildas, "imager": imager, "piic": piic}


def _run(
    tmp_path: Path,
    steps: list[str],
    tree: dict[str, Path],
    *,
    reresolve: str = "0",
    append_bashrc: str = "0",
    fallback: str = "x86_64-generic",
) -> None:
    env = os.environ.copy()
    env.update(
        {
            "ROOT": str(tmp_path),
            "RELEASE": "test",
            "GILDAS_DIR": str(tree["gildas"]),
            "IMAGER_DIR": str(tree["imager"]),
            "PIIC_DIR": str(tree["piic"]),
            "FALLBACK_EXEC": fallback,
            "EXEC_GREP": "gfortran-openmp|gfortran|generic|musl|alpine",
            "RERESOLVE": reresolve,
            "APPEND_BASHRC": append_bashrc,
        }
    )
    for step in steps:
        subprocess.run(
            ["sh", str(SCRIPT), step],
            check=True,
            env=env,
            capture_output=True,
            text=True,
        )


def test_script_syntax() -> None:
    subprocess.run(["sh", "-n", str(SCRIPT)], check=True)


def test_native_order_prefers_piic_wrappers(tmp_path: Path) -> None:
    tree = _tree(tmp_path)
    _run(tmp_path, ["env", "piic", "imager"], tree, append_bashrc="1")

    env_file = (tmp_path / "etc" / "gildas-env.sh").read_text()
    assert f"export GAG_ROOT_DIR={tree['gildas']}" in env_file
    assert "export GAG_EXEC_SYSTEM=x86_64-generic" in env_file
    assert "_detected=" not in env_file
    assert (tmp_path / "etc" / "gildas-exec-system").read_text() == "x86_64-generic\n"
    assert (tmp_path / "etc" / "imager-exec-system").read_text() == "x86_64-generic\n"
    assert (tmp_path / "etc" / "piic-exec-system").read_text() == "x86_64-generic\n"

    bin_dir = tmp_path / "usr" / "local" / "bin"
    assert not (bin_dir / "astro").exists()
    assert "PIIC tree" in (bin_dir / "piicprog").read_text()
    assert "PIIC tree" in (bin_dir / "shared").read_text()
    assert "PIIC tree" in (bin_dir / "imagerprog").read_text()
    assert (bin_dir / "piicprog").stat().st_mode & 0o111

    assert (tmp_path / "etc" / "bash.bashrc").read_text() == env_file


def test_docker_order_prefers_imager_wrappers(tmp_path: Path) -> None:
    tree = _tree(tmp_path)
    _run(tmp_path, ["env", "imager", "piic"], tree)

    bin_dir = tmp_path / "usr" / "local" / "bin"
    assert not (bin_dir / "astro").exists()
    assert "PIIC tree" in (bin_dir / "piicprog").read_text()
    assert "standalone IMAGER tree" in (bin_dir / "shared").read_text()
    assert "standalone IMAGER tree" in (bin_dir / "imagerprog").read_text()
    assert not (tmp_path / "etc" / "bash.bashrc").exists()


def test_reresolve_block_is_opt_in(tmp_path: Path) -> None:
    tree = _tree(tmp_path)
    _run(tmp_path, ["env"], tree, reresolve="1")
    assert "_detected=" in (tmp_path / "etc" / "gildas-env.sh").read_text()

    other = tmp_path / "no-reresolve"
    other.mkdir()
    other_tree = _tree(other)
    _run(other, ["env"], other_tree, reresolve="0")
    assert "_detected=" not in (other / "etc" / "gildas-env.sh").read_text()


def test_fallback_exec_when_no_tree_matches(tmp_path: Path) -> None:
    gildas = tmp_path / "gildas-exe-test"
    (gildas / "etc").mkdir(parents=True)
    (gildas / "etc" / "bash_profile").write_text("")
    _run(
        tmp_path,
        ["env"],
        {"gildas": gildas, "imager": tmp_path / "missing-imager", "piic": tmp_path / "missing-piic"},
        fallback="x86_64-fallback",
    )
    assert (tmp_path / "etc" / "gildas-exec-system").read_text() == "x86_64-fallback\n"


def test_package_lists_are_shared() -> None:
    alpine = (ROOT / "docker/Dockerfile.alpine").read_text()
    debian = (ROOT / "docker/Dockerfile.debian").read_text()
    native = (ROOT / "apptainer" / "gildas-native-alpine.def").read_text()
    alpine_build = (ROOT / "packages" / "alpine-build.txt").read_text().split()
    debian_build = (ROOT / "packages" / "debian-build.txt").read_text().split()

    assert "packages/alpine-runtime.txt" in alpine
    assert "packages/alpine-build.txt" in alpine
    assert "packages/debian-runtime.txt" in debian
    assert "packages/debian-build.txt" in debian
    assert "/opt/packages/alpine-runtime.txt" in native
    assert "/opt/packages/alpine-build.txt" in native

    # ccache is a Docker-only build optimization, not a native dependency.
    assert "ccache" not in alpine_build
    assert "ccache" in alpine
    assert "ccache" in debian_build


def test_missing_optional_trees_are_noops(tmp_path: Path) -> None:
    tree = _tree(tmp_path)
    _run(tmp_path, ["env", "piic", "imager"], tree)
    assert (tmp_path / "usr" / "local" / "bin" / "piicprog").exists()

    # A second root with no IMAGER/PIIC trees must still write the env and
    # return successfully from both wrapper subcommands.
    other = tmp_path / "empty-optional"
    other.mkdir()
    gildas = other / "gildas-exe-test"
    _bin(gildas / "x86_64-generic" / "bin", "astro")
    (gildas / "etc").mkdir()
    (gildas / "etc" / "bash_profile").write_text("")
    _run(
        other,
        ["env", "piic", "imager"],
        {"gildas": gildas, "imager": other / "missing-imager", "piic": other / "missing-piic"},
    )
    assert (other / "etc" / "gildas-env.sh").exists()
    assert not (other / "usr" / "local" / "bin" / "imagerprog").exists()
