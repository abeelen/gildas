# Changelog

## [latest]
### Added
- Standalone IMAGER bundled in all images, exposed as
  self-contained `/usr/local/bin` wrappers: every program runs by bare
  name, no `gag*` env switching (entrypoint/runscripts just source the
  default env and exec)
- Every tag names its base (`-alpine` / `-debian` opt-in); unsuffixed
  `latest` / `latest-piic` are aliases of the Alpine rolling tags;
  `--piic` mode
  pairing main-tree PIIC with GILDAS from main or archive
- Self-describing images (`abeelen.gildas.*` labels,
  `/etc/imager-version` / `/etc/piic-version`) and IMAGER-drift
  self-healing rebuilds (`last` resolved to a concrete version)
- `gildas_release.py` overhaul: release/imager coupling, `--native`
  (`--natif` alias), `--singularity`, per-family `latest` tags,
  `--execute --log-dir`, offline pytest suite; simplified (dropped
  `--json`, `--repo`/`--dockerfile`, `--no-tag-latest`)
- SIF recipes grouped under `apptainer/`: `gildas-docker.def` (Docker Hub
  bootstrap) and `gildas-native-alpine.def` (tarball build); native SIFs
  now use `gildas-<release>[-piic]-native-alpine.sif`
- CI: GitHub Actions + GitLab pipeline (scheduled and web-triggered
  builds, print-only plans), SIF publishing to a rolling GitHub release
  plus GitLab container-registry OCI artifacts; native SIF builds require
  `SINGULARITYENV_*`, no `/tmp` globs in def cleanup (builder's own busy
  mounts)
- SIC foreground patch (`patches/sic-foreground.patch`, all recipes):
  GILDAS `setpgrp()` at startup moved interactive sessions out of the
  terminal foreground group (fatal SIGTTIN freeze); foreground restored
  when stdin is a tty, `kill(0)` cleanup semantics untouched
### Changed
- Docker and native SIF recipes share the runtime env/bare-name wrapper
  script (`scripts/gildas-runtime.sh`); both Dockerfiles read package
  lists from `packages/<distro>-{runtime,build}.txt`, and the Alpine
  lists are shared with the native recipe. Same runtime behavior, less
  duplicated logic
- Container recipes are grouped by tool: `docker/Dockerfile.alpine`,
  `docker/Dockerfile.debian`, and `docker/entrypoint.sh` (the Debian
  recipe was previously `Dockerfile`), with SIF definitions under
  `apptainer/` (previously `defs/`). Custom `-f Dockerfile` invocations
  must use `docker/Dockerfile.debian`.
- GitLab `sif-build` now runs automatically on scheduled default-branch
  pipelines and is an optional, non-blocking manual job on default-branch
  push/web pipelines; other pipelines skip it
### Fixed
- `clic` ungated from the upstream `GAG_USE_SANITIZE` build gate;
  `apptainer/gildas-native-alpine.def` parity with `docker/Dockerfile.debian`;
  `latest`/`latest-piic` tracked per family
- IMAGER upstream outage no longer aborts builds: `gildas_release.py`
  skips IMAGER (`IMAGER_VERSION=none`, `WITH_IMAGER=0`) when
  `share.oasu.u-bordeaux.fr` is unreachable, records it in the
  `abeelen.gildas.imager-bundled` label and `/etc/imager-version`, and
  rebuilds the tag with IMAGER once the upstream is back
- Same treatment for PIIC: listing failures are fail-open (GILDAS-only
  builds continue), `-piic` images record `abeelen.gildas.piic-version` /
  `piic-bundled` plus `none (not bundled)` in `/etc/piic-version`, and
  tags built without PIIC are rebuilt once the release reappears
  upstream
- Fail-open IMAGER/PIIC outages now surface as CI warnings: GitHub
  Actions annotations (`::warning title=…`) and colored `WARNING:` lines
  in GitLab job logs
- CI warnings are printed on **stderr**: the GitHub `natif` SIF job
  captured them on stdout while resolving the build command, and the
  `::warning` text (quotes and parens included) then leaked into the
  generated shell and crashed it with `syntax error near unexpected
  token '('`. Annotations still render (Actions scans both streams);
  the `sif.yml` step output is now written heredoc-style and consumed
  via a step env var instead of being inlined into quoted shell text,
  with a clear `::error` when no SIF name can be resolved
- GitLab `sif-build` no longer fills `/tmp`: apptainer's build temp and
  cache moved to job-specific directories under `$CI_PROJECT_DIR`
  (override with `SIF_TMPDIR` / `SIF_CACHEDIR`), cleaned on exit;
  `--disable-cache` and `--force` reduce peak space and make reruns safe
- GitLab `sif-build` now pushes SIFs to the project container registry
  as `sif:<tag>` OCI artifacts (`singularity push` with an authfile from
  `CI_REGISTRY_*`) instead of archiving a ~893 MiB `sifs/` artifact;
  stale local SIFs are removed before the build and after each push
- SIF label parity: Docker-converted SIFs inherit every
  `abeelen.gildas.*` label, native SIF builds now write the same keys
  from `%post`, and `apptainer/gildas-docker.def` no longer claims the source
  is always `abeelen/gildas:latest`
