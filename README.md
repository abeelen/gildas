This is a docker container of the [IRAM/gildas](https://www.iram.fr/IRAMFR/GILDAS/) software suite.

Pre-built images are available on Docker Hub: https://hub.docker.com/r/abeelen/gildas

You can find many tags corresponding to several release version of the software. Alternatively you can use the `latest` or `latest-piic` tag to use the most up-to-date version of the software on this repository.

There are two main tag families: regular release tags and the `*-piic` tags containing the `piic` software. Every tag names its base explicitly (`-alpine` / `-debian`); the unsuffixed `latest` and `latest-piic` are aliases of the Alpine rolling tags.

You can use it either with Docker or simply with Singularity.

Alpine (`docker/Dockerfile.alpine`) is the default build recipe; Debian
(`docker/Dockerfile.debian`) is opt-in. See [building](docs/building.md) for
build args, native SIFs, and the shared package-list/runtime layout.

## Quick start

No display needed — `-nw` is no-window mode, pure terminal interaction:

```bash
docker run --rm -it abeelen/gildas:latest mapping -nw
singularity run docker://abeelen/gildas:latest mapping -nw
```

For graphic windows, most programs need your display. Once per host
session:

```bash
xhost +SI:localuser:$(id -un)
```

then add display access to the same commands — for Singularity only
the X socket needs an explicit bind (`DISPLAY` passes through):

```bash
singularity run --bind /tmp/.X11-unix docker://abeelen/gildas:latest mapping
```

For Docker, define the full launcher once (X shared memory,
cookie/Wayland passthrough, home mounted — Linux `/home` and macOS
`/Users` alike) and call it per program:

```bash
alias gildas_docker='docker run --rm -it \
       --hostname "gildas" --user $(id -u):$(id -g) \
       --ipc=host \
       --workdir="$PWD" \
       --env HOME="$HOME" --env USER="$USER" \
       --env DISPLAY \
       --env WAYLAND_DISPLAY \
       --env XDG_RUNTIME_DIR \
       --env XAUTHORITY \
       --volume "/etc/passwd:/etc/passwd:ro" \
       --volume "$HOME:$HOME" \
       --volume "/Users/$USER:/Users/$USER" \
       --volume "$PWD:$PWD" \
       --volume "/tmp/.X11-unix:/tmp/.X11-unix" \
       --volume "$XDG_RUNTIME_DIR:$XDG_RUNTIME_DIR" \
       abeelen/gildas:latest'
gildas_docker mapping
gildas_docker mapping -nw
gildas_docker imager
```

PIIC programs need a `*-piic` image: same launcher pointed at
`abeelen/gildas:latest-piic` (`gildas_docker piic`).

(`DISPLAY` and `~/.Xauthority` pass through into Singularity
automatically. The `atk-bridge` message some programs print is
harmless noise.)

## Docker tags overview

| Tag example             | Base   | Content       | Notes                         |
|-------------------------|--------|---------------|-------------------------------|
| `latest-alpine`         | Alpine | GILDAS        | Rolling Alpine tag            |
| `latest`                | Alpine | GILDAS        | Alias of `latest-alpine`      |
| `jan26a-alpine`         | Alpine | GILDAS        | Specific release              |
| `latest-piic-alpine`    | Alpine | GILDAS + PIIC | Rolling Alpine tag with PIIC  |
| `latest-piic`           | Alpine | GILDAS + PIIC | Alias of `latest-piic-alpine` |
| `jan26a-piic-alpine`    | Alpine | GILDAS + PIIC | Specific release with PIIC    |
| `latest-debian`         | Debian | GILDAS        | Rolling Debian tag            |
| `jan26a-debian`         | Debian | GILDAS        | Specific release, Debian      |
| `latest-piic-debian`    | Debian | GILDAS + PIIC | Rolling Debian tag with PIIC  |
| `jan26a-piic-debian`    | Debian | GILDAS + PIIC | Specific release, Debian+PIIC |

## Using the images

### Usage with Singularity

```bash
# Any program, directly by name (piic needs a *-piic image).
# The --bind is required: most programs need your X11 display.
singularity run --bind /tmp/.X11-unix docker://abeelen/gildas:latest mapping
singularity run --bind /tmp/.X11-unix docker://abeelen/gildas:latest-piic piic
singularity run --bind /tmp/.X11-unix docker://abeelen/gildas:latest imager
```

Prebuilt SIFs are published on the
[sif-images](https://github.com/abeelen/gildas/releases/tag/sif-images)
GitHub release. Scheduled pipelines on the LAM GitLab instance also
build the SIFs and push them to the project container registry as
`sif:<tag>` OCI artifacts (for users without github.com access).
Default-branch pipelines expose the same job as an optional manual
build. Pull them with:

```bash
singularity pull gildas-latest.sif oras://registry.lam.fr/abeelen/gildas/sif:latest
singularity pull gildas-latest-piic.sif oras://registry.lam.fr/abeelen/gildas/sif:latest-piic
```

To build your own, see [building](docs/building.md) — or generate the
exact command with `./gildas_release.py --singularity` / `--native`
(`--natif` is an alias).

Which invocations work depends on how the SIF was built, but both
shipped kinds carry the full `%apprun` list (`apptainer/gildas-docker.def` and
`apptainer/gildas-native-alpine.def` define the same entries):

```bash
# Apprun shortcuts
singularity run --app astro   gildas-latest.sif
singularity run --app class   gildas-latest.sif
singularity run --app classic-read gildas-latest.sif
singularity run --app clic    gildas-latest.sif
singularity run --app cube    gildas-latest.sif
singularity run --app flux    gildas-latest.sif
singularity run --app greg    gildas-latest.sif
singularity run --app hershey gildas-latest.sif
singularity run --app imager  gildas-latest.sif
singularity run --app mapping gildas-latest.sif
singularity run --app orbit   gildas-latest.sif
singularity run --app piic    gildas-latest.sif
singularity run --app point   gildas-latest.sif
singularity run --app sic     gildas-latest.sif
singularity run --app viewer  gildas-latest.sif
```

Bare `singularity exec … <prog>` (no runscript/apprun) only works for
the self-contained `/usr/local/bin` wrappers (`imager`, `viewer`,
PIIC-only tools) — everything else needs `run` or `--app` so the
GILDAS environment is sourced first.

Every program runs directly by name: GILDAS tools from the default
environment, IMAGER/PIIC tools via self-contained `/usr/local/bin`
wrappers that select their own tree (a flavor never shadows a GILDAS
program of the same name).

Images are self-describing: `docker inspect` shows `abeelen.gildas.*`
labels (release, base, target, IMAGER/PIIC version and
`imager-bundled` / `piic-bundled` flags), and
`/etc/imager-version` / `/etc/piic-version` inside the image record the
bundled component versions authoritatively (`none (not bundled)` when
absent, e.g. because the upstream was unreachable at build time).

SIFs converted from these images inherit the same `abeelen.gildas.*`
labels, and native SIF builds write them from `%post`, so
`docker inspect`, `singularity inspect -l` / `apptainer inspect -l`,
and the `/etc` sentinels agree.

### Usage with Docker

Use the `gildas_docker` launcher from Quick start. It runs as your
UID/GID, mounts your home and current directory, and passes X11/Wayland
through. For a terminal-only session the minimum is just:

```bash
docker run --rm -it abeelen/gildas:latest mapping -nw
```

Graphic programs need `--ipc=host`, `DISPLAY`, `XAUTHORITY`, and the X11
socket mount; the alias already includes them. On macOS, start XQuartz
and allow network clients before using X11. Every GILDAS, IMAGER, and
PIIC program is available by bare name (use a `*-piic` image for PIIC).

### Container entrypoint

`docker/entrypoint.sh` (installed as
`/usr/local/bin/docker-entrypoint.sh`) sources `/etc/gildas-env.sh`
(default GILDAS environment), then `exec`s the given command:

```bash
docker run --rm -it abeelen/gildas:latest mapping
docker run --rm -it abeelen/gildas:latest imager
docker run --rm -it abeelen/gildas:latest-piic piic
```

(Programs from the standalone IMAGER tree and the PIIC tree are
self-contained `/usr/local/bin` wrappers selecting their own tree;
a wrapper is only created when it does not shadow a GILDAS program.)

## Troubleshooting / FAQ

- **X11 / display does not work**  \
        Most programs need a display: run `xhost
        +SI:localuser:$(id -un)` on the host once per session and use the
        full `docker run` command (or `gildas_docker` aliases) from
        "Usage with Docker" above — `--ipc=host`, `DISPLAY` /
        `XAUTHORITY` / Wayland passthrough and the X socket mount are all
        required on cookie-authenticated or Wayland desktops. For
        Singularity, `--bind /tmp/.X11-unix` suffices (`DISPLAY` passes
        through). The `atk-bridge` message is harmless.
- **I do not see my local files inside the container**  \
        Check that your home directory (or relevant paths) are mounted with
        `--volume`.
- **PIIC is not available or not found**  \
        Use a `*-piic` tag and run `piic` directly. Rebuild the image
        if yours predates the `/usr/local/bin` wrappers.
- **`clic` is missing (images built before the fix)**  \
        Upstream gates `clic` on `GAG_USE_SANITIZE=yes` with gfortran,
        which these images keep disabled. Current recipes ungate it
        automatically; rebuild the image to get `clic`.
- **`imager` / `viewer` are missing**  \
        IMAGER is standalone (https://imager.oasu.u-bordeaux.fr), bundled
        at `/imager-exe` with `/usr/local/bin` wrappers. Rebuild the
        image if yours predates this.
- **`greg` is missing**  \
        Pull the newest tag — you are likely running a stale local image.
- **Terminal does not interact (`mapping` etc.)**  \
        Graphic programs open an X window and the terminal can go
        unresponsive; run with `-nw` (no-window mode) for a pure
        terminal session, which needs no display at all.
- **Frozen session under Singularity (prompt shows, typing dead,
  Ctrl-C dead)**  \
        Fixed in current images (GILDAS `setpgrp()` at startup moved the
        process out of the terminal foreground group; new builds restore
        it — see `patches/sic-foreground.patch`). On older images,
        interact through a shell first, or batch mode:
        ```bash
        singularity exec docker://abeelen/gildas:latest bash
        # then inside: mapping -nw
        echo 'say "hi"' | singularity run docker://abeelen/gildas:latest mapping -nw
        ```
        Bare `docker run -it` always works. Technical background in
        [docs/notes.md](docs/notes.md).

## Further documentation

- [docs/building.md](docs/building.md): manual Docker builds, build
  args, PIIC, Debian images, native Singularity builds.
- [docs/automation.md](docs/automation.md): `gildas_release.py`
  reference, CI pipelines, SIF publishing.
