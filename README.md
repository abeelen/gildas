
This is a docker container of the [IRAM/gildas](https://www.iram.fr/IRAMFR/GILDAS/) software suite.

Pre-built images are available on Docker Hub: https://hub.docker.com/r/abeelen/gildas

You can find many tags corresponding to several release version of the software. Alternatively you can use the `latest` or `latest-piic` tag to use the most up-to-date version of the software on this repository.

There are two main tag families: regular release tags and the `*-piic` tags containing the `piic` software. Alpine is the default base image; Debian-based variants carry an additional `-debian` suffix.

You can use it either with Docker or simply with Singularity.

## Quick start

Minimal working example (no display needed — `-nw` is no-window mode):

```bash
docker run --rm -it abeelen/gildas:latest mapping -nw
```

Most GILDAS programs need a display (GTK) for their graphic windows,
so let the container use yours — once per session on the host:

```bash
xhost +SI:localuser:$(id -un)
```

Then every program runs directly by name:

```bash
# GILDAS programs
singularity run --bind /tmp/.X11-unix docker://abeelen/gildas:latest mapping

# Docker: full recipe (X shared memory, cookie/Wayland passthrough,
# home mounted) — define once, call per program; details below.
alias gildas_docker='docker run --rm -it \
       --hostname "gildas" --user $(id -u):$(id -g) \
       --ipc=host \
       --workdir="$PWD" \
       --env HOME="$HOME" --env USER="$USER" \
       --env DISPLAY \
       --env WAYLAND_DISPLAY \
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
gildas_docker imager
gildas_docker viewer

# PIIC: same launcher pointed at a *-piic image
alias gildas_docker='docker run --rm -it \
       --hostname "gildas" --user $(id -u):$(id -g) \
       --ipc=host \
       --workdir="$PWD" \
       --env HOME="$HOME" --env USER="$USER" \
       --env DISPLAY \
       --env WAYLAND_DISPLAY \
       --env WAYLAND_DISPLAY \
       --env XDG_RUNTIME_DIR \
       --env XAUTHORITY \
       --volume "/etc/passwd:/etc/passwd:ro" \
       --volume "$HOME:$HOME" \
       --volume "/Users/$USER:/Users/$USER" \
       --volume "$PWD:$PWD" \
       --volume "/tmp/.X11-unix:/tmp/.X11-unix" \
       --volume "$XDG_RUNTIME_DIR:$XDG_RUNTIME_DIR" \
       abeelen/gildas:latest-piic'
singularity run --bind /tmp/.X11-unix docker://abeelen/gildas:latest-piic piic
gildas_docker piic
```

(`DISPLAY` and `~/.Xauthority` pass through into Singularity
automatically; only the X socket needs an explicit `--bind`. The
`atk-bridge` message some programs print is harmless noise.)

Programs with graphics (e.g. `mapping`) also take `-nw` for no-window
mode: pure terminal interaction, no display needed at all —
`gildas_docker mapping -nw`, `singularity run … mapping -nw`.

## Docker tags overview

| Tag example             | Base   | Content       | Notes                         |
|-------------------------|--------|---------------|-------------------------------|
| `latest`                | Alpine | GILDAS        | Convenience tag (default)     |
| `jan26a`                | Alpine | GILDAS        | Specific release              |
| `latest-piic`           | Alpine | GILDAS + PIIC | Convenience tag with PIIC     |
| `jan26a-piic`           | Alpine | GILDAS + PIIC | Specific release with PIIC    |
| `latest-debian`         | Debian | GILDAS        | Opt-in Debian base image      |
| `jan26a-debian`         | Debian | GILDAS        | Specific release, Debian      |
| `latest-piic-debian`    | Debian | GILDAS + PIIC | Opt-in Debian base with PIIC  |
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
GitHub release (and mirrored as GitLab job artifacts via the manual
`sif-mirror` job, for users without github.com access). To build your
own, see [building](docs/building.md) — or generate the exact command
with `./gildas_release.py --singularity` / `--natif`.

Which invocations work depends on how the SIF was built:

| SIF origin | `run <prog>` | `--app <prog>` | bare `exec <prog>` |
|---|---|---|---|
| Converted from `docker://` (manual builds) | yes | no (`%apprun` only exists in `.def` builds) | only self-contained wrappers (`imager`, `viewer`) |
| Built from a `.def` (native images, published artifacts) | yes | yes (see list below) | only self-contained wrappers |

```bash
# Apprun shortcuts (definition-built SIFs only)
singularity run --app astro   gildas-latest.sif
singularity run --app class   gildas-latest.sif
singularity run --app clic    gildas-latest.sif
singularity run --app mapping gildas-latest.sif
singularity run --app piic    gildas-latest.sif
singularity run --app imager  gildas-latest.sif
singularity run --app viewer  gildas-latest.sif
```

Every program runs directly by name: GILDAS tools from the default
environment, IMAGER/PIIC tools via self-contained `/usr/local/bin`
wrappers that select their own tree (a flavor never shadows a GILDAS
program of the same name).

Images are self-describing: `docker inspect` shows `abeelen.gildas.*`
labels (release, base, target, IMAGER version), and
`/etc/imager-version` / `/etc/piic-version` inside the image record the
bundled component versions authoritatively (`none` when absent).

### Usage with Docker

To launch the gildas container, type :

```bash
xhost +SI:localuser:$(id -un)
docker run -it \
       --hostname "gildas" --user $(id -u):$(id -g) \
       --ipc=host \
       --workdir="/home/$USER" --env HOME=${HOME} --env USER=${USER}
       --env DISPLAY=${DISPLAY} --env WAYLAND_DISPLAY=${WAYLAND_DISPLAY} \
       --env XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR} --env XAUTHORITY=${XAUTHORITY} \
       --volume "/etc/passwd:/etc/passwd:ro" \
       --volume "/home/$USER:/home/$USER" \
       --volume "/Users/$USER:/Users/$USER" \
       --volume "/tmp/.X11-unix:/tmp/.X11-unix" \
       abeelen/gildas:latest /bin/bash --rcfile /etc/bash.bashrc
```

where
```bash
-volume "/home/$USER:/home/$USER"
```
will mount the user home for Unix Users
```bash
-volume "/Users/$USER:/Users/$USER"
```
will do the same for MacOS users. MacOS users should also open remote display access :

```bash
open -a XQuartz
# (In the XQuartz preferences, go to the “Security” tab and make sure you’ve got “Allow connections from network clients” ticked)
ip=$(ifconfig en0 | grep inet | awk '$1=="inet" {print $2}’)
xhost + $ip
```

You can then use any of the gildas commands directly by name — GILDAS,
IMAGER and (on `*-piic` images) PIIC programs all work with no prefix,
each selecting its own installation tree behind the scenes.

It is easier to create usefull aliases in `~/.bashrc`

```bash
# With PIIC
alias gildas_docker='docker run -it \
       --hostname "gildas" --user $(id -u):$(id -g) \
       --ipc=host \
       --workdir="$PWD" \
       --env HOME="$HOME" --env USER="$USER" \
       --env DISPLAY \
       --env WAYLAND_DISPLAY \
       --env WAYLAND_DISPLAY \
       --env XDG_RUNTIME_DIR \
       --env XAUTHORITY \
       --volume "/etc/passwd:/etc/passwd:ro" \
       --volume "$HOME:$HOME" \
       --volume "/Users/$USER:/Users/$USER" \
       --volume "$PWD:$PWD" \
       --volume "/tmp/.X11-unix:/tmp/.X11-unix" \
       --volume "$XDG_RUNTIME_DIR:$XDG_RUNTIME_DIR" \
       abeelen/gildas:latest-piic'

alias clic='gildas_docker clic'
alias mapping='gildas_docker mapping'
alias astro='gildas_docker astro'
alias piic='gildas_docker piic'
alias cube='gildas_docker cube'
[...]
alias imager='gildas_docker imager'
alias viewer='gildas_docker viewer'
```

Alternatively if you do not need PIIC,

```bash
# Without PIIC
alias gildas_docker='docker run -it \
       --hostname "gildas" --user $(id -u):$(id -g) \
       --ipc=host \
       --workdir="$PWD" \
       --env HOME="$HOME" --env USER="$USER" \
       --env DISPLAY \
       --env WAYLAND_DISPLAY \
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

alias clic='gildas_docker clic'
alias mapping='gildas_docker mapping'
alias astro='gildas_docker astro'
alias cube='gildas_docker cube'
[...]
alias imager='gildas_docker imager'
alias viewer='gildas_docker viewer'
```

### Container entrypoint

`docker-entrypoint.sh` sources `/etc/gildas-env.sh` (default GILDAS
environment), then `exec`s the given command:

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
        `singularity run <img> <prog>` can leave the payload outside the
        terminal's foreground group (or without a controlling terminal),
        so its first terminal read suspends it — `ps` shows `Tl` /
        `do_signal_stop`, and only killing the terminal helps. Verified
        working instead: interact through a shell first (its job control
        sets the terminal up correctly — full readline interaction,
        tested), or batch mode, which never touches the terminal:
        ```bash
        singularity exec docker://abeelen/gildas:latest bash
        # then inside: mapping -nw
        echo 'say "hi"' | singularity run docker://abeelen/gildas:latest mapping -nw
        ```
        Bare `docker run -it` always works (fresh pty, correct setup).

## Further documentation

- [docs/building.md](docs/building.md): manual Docker builds, build
  args, PIIC, Debian images, native Singularity builds.
- [docs/automation.md](docs/automation.md): `gildas_release.py`
  reference, CI pipelines, SIF publishing.
