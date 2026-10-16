# Changelog

## [latest]
### Added
- Standalone IMAGER bundled in all images, exposed as
  self-contained `/usr/local/bin` wrappers: every program runs by bare
  name, no `gag*` env switching (entrypoint/runscripts just source the
  default env and exec)
- Alpine default base image (`-debian` opt-in tags); `--piic` mode
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
  in def cleanup
### Fixed
- `clic` ungated from the upstream `GAG_USE_SANITIZE` build gate;
  `gildas-natif.def` parity with `Dockerfile`; `latest`/`latest-piic`
  tracked per family
