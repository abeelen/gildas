# Changelog

## [latest]
### Added
- Standalone IMAGER bundled in all images (`/imager-exe`, `WITH_IMAGER`/`IMAGER_VERSION`/`IMAGER_URL` build args): `Dockerfile`, `Dockerfile.alpine`, `gildas-natif.def`, `gildas-natif-alpine.def`
- Direct access to every program by bare name, no env switching for users: self-contained `/usr/local/bin` wrappers for all IMAGER-only and PIIC-only programs (never shadowing a GILDAS program); `gag*` functions, `GILDAS_FLAVOR` and the `bash -c` command shim removed from `docker-entrypoint.sh` and all `.def` runscripts/appruns (now: source env, `exec "$@"`)
- `gildas_release.py --singularity`: emit `singularity build ... docker://...` commands
- `gildas_release.py --natif`: emit native `singularity build ... .def` commands (archive URLs auto-resolved)
- GILDAS/IMAGER coupling in `gildas_release.py`: `imager_release()` lists upstream IMAGER versions, each release auto-maps (`oct26a` → `IMAGER_VERSION=oct26`, fallback `last` + warning, `--imager-version` override)
- `gildas_release.py --archive`: opt-in archived releases (excluded by default)
- `gildas-latest-alpine.def` / `gildas-natif-alpine.def`: Alpine Singularity variants (thin wrapper + native musl build)
### Fixed
- `gildas-natif.def`: parity with `Dockerfile` (robust curl, `nproc` jobs, `WITH_TEXLIVE`, `python3-astropy`, auto-detected `GAG_EXEC_SYSTEM`, multiarch search path)
- `clic` missing from images: ungated upstream `GAG_USE_SANITIZE` build gate in `packages/clic/Makefile` (all 4 recipes); `imager` confirmed removed upstream, `greg` confirmed present
- `gildas-latest.def`: runscript sources `/etc/gildas-env.sh` (bash.bashrc never set up GILDAS), appruns forward `$@`
- `latest`/`latest-piic` tags tracked per family; single `--release` tags latest by default

## [previous]
### Added
- One Dockerfile for two targets, with and without piic
- check_new_release.py gildas_release.py to check for new gildas releases and give corresponding docker command to build images

## [nov19a]
- New gildas release
### BUG
- Do not have a corresponding PIIC package

## [oct19a]

### Added
- PIIC support in `*-piic` images
