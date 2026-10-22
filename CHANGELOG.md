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
- `gildas_release.py` overhaul: release/imager coupling, `--natif`,
  `--singularity`, per-family `latest` tags, `--execute --log-dir`,
  offline pytest suite; simplified (dropped `--json`,
  `--repo`/`--dockerfile`, `--no-tag-latest`)
- CI: GitHub Actions + GitLab pipeline (scheduled, manual, print-only
  plans), SIF publishing to a rolling release plus GitLab artifacts
  mirror; native SIF builds require `SINGULARITYENV_*`, no `/tmp` globs
  in def cleanup (builder's own busy mounts)
- SIC foreground patch (`patches/sic-foreground.patch`, all recipes):
  GILDAS `setpgrp()` at startup moved interactive sessions out of the
  terminal foreground group (fatal SIGTTIN freeze); foreground restored
  when stdin is a tty, `kill(0)` cleanup semantics untouched
### Fixed
- `clic` ungated from the upstream `GAG_USE_SANITIZE` build gate;
  `gildas-natif.def` parity with `Dockerfile`; `latest`/`latest-piic`
  tracked per family
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
- GitLab `sif-build` no longer fills `/tmp`: apptainer's build temp and
  cache moved to job-specific directories under `$CI_PROJECT_DIR`
  (override with `SIF_TMPDIR` / `SIF_CACHEDIR`), cleaned on exit;
  `--disable-cache` and `--force` reduce peak space and make reruns safe
- SIF label parity: Docker-converted SIFs inherit every
  `abeelen.gildas.*` label, native SIF builds now write the same keys
  from `%post`, and `gildas-latest.def` no longer claims the source is
  always `abeelen/gildas:latest`
