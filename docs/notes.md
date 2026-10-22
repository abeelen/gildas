# Developer notes

Investigation log for this repository. User documentation lives in
`README.md` and `docs/` (`building.md`, `automation.md`); this file
records *why* things are the way they are, including dead ends, so
future work does not re-learn them the hard way.

## Singularity interactive freezes (Oct 2026) — ROOT CAUSE FOUND

Symptom: `singularity run … mapping [-nw]` prints banner + `MAPPING>`
prompt, then ignores typing and Ctrl-C; only killing the terminal helps.
Piped stdin always works; `docker run -it` always works.

Root cause is in GILDAS itself: `kernel/lib/sic/getcar.c`,
`search_clients()` (called at every SIC program startup) runs
`setpgrp()`, moving the process into its own group — meant so that
`kill(0, SIGTERM)` on exit (`sic_kill_all_child_processes`) only hits
SIC's own children. Under runtimes that make the payload a session
leader (Docker), `setpgrp()` fails harmlessly (EPERM, ignored) and
everything works. Under Singularity (payload stays in the caller's
session), it succeeds — the process leaves the terminal foreground
group (`pgid == pid ≠ tpgid`, observed live) and its first terminal
read raises SIGTTIN → frozen in `Tl`/`do_signal_stop`, with the
terminal typically left in noecho/raw mode (hence invisible typing and
dead Ctrl-C).

Earlier mislead: a trivial `sleep` payload lands foreground correctly,
which first suggested the runtime — but re-reading that result, it
only proves the runtime places *well-behaved* payloads fine; GILDAS
moves *itself*. Source inspection settled it.

Fix shipped as `patches/sic-foreground.patch` (applied in all four
recipes): after `setpgrp()`, restore our own group to the foreground
with `tcsetpgrp()` when stdin is a tty. Safety properties, all
verified by reading the code (no behavior change except the freeze):

- `kill(0, SIGTERM)` cleanup semantics are untouched (`setpgrp()` still
  runs; only foreground membership is restored).
- Session leaders (Docker): `setpgrp()` already failed there, and
  re-asserting our own group is a no-op.
- Batch/pipes: `isatty()` false → patch is inert.
- Missing terminal: `tcsetpgrp()` fails silently, old behavior kept.

Workarounds for pre-fix images: interact through an inner shell
(`singularity exec … bash`), batch stdin from files/pipes, or
`docker run -it`.

## SIF builds on GitLab runners (Oct 2026)

- Shared runners: `docker:dind` never starts (no privileged mode).
- Direct builds fail in sequence: no `newuidmap` → install `uidmap`;
  `Operation not permitted` → kernel forbids unprivileged user
  namespaces fleet-wide → `--fakeroot` impossible; `proot` fallback
  does not trigger (container creation itself needs userns).
- `docker`-tagged runners: same kernel gate (verified by failure).
- Consequence: shared/docker runners build Docker images only. SIFs are
  built by the manual `sif-build` job on the dedicated `apptainer`
  runner instead, with `APPTAINER_TMPDIR` on the build volume because
  the PIIC rootfs does not fit in the runner's `/tmp`, then pushed to
  the project container registry as `sif:<tag>` OCI artifacts.

## Registry lessons (Oct 2026)

- GitLab generic packages API answers 403 to CI_JOB_TOKEN *and* to a
  project token with `api` scope on this instance → abandoned for SIFs.
  Use the container registry instead (`sif:<tag>`), not the generic
  package API (Docker `latest` mirror via `CI_REGISTRY_*` works fine).
- Plain `oras push` stamps `artifactType:
  application/vnd.unknown.artifact.v1`, which strict registries reject
  at manifest level; `singularity push` omits it (verified layout by
  inspection). `singularity remote login` only manages Sylabs
  endpoints, never generic OCI registries — use a docker `config.json`
  with `push --authfile`.
- SIF layer type matters for pulls: `vnd.oci.image.layer.v1.tar` is
  refused by Singularity, `vnd.sylabs.sif.layer.v1.sif` round-trips
  (both verified against a throwaway registry).

## Native builds gotchas (Oct 2026)

- Host env never reaches `%post`: only `SINGULARITYENV_*` propagates
  (verified with a minimal def). Plain `VAR=...` prefixes are silently
  dropped, then `set -u` aborts — the Alpine native recipe was missing
  the `:=` defaults that the older recipe had.
- Never glob `/tmp` or `/var/tmp` in `%post` cleanup: under
  `singularity build` those hold the builder's own busy mounts and `rm`
  aborts on them (killed a full compile at the trim step; reproduced
  with a 3-line def).

## Why no file-level GILDAS/IMAGER merge (Oct 2026)

Checksum comparison of the two trees: 32/36 libs, 64/243 task
executables, 16 data files, dictionaries and startup scripts differ
under identical paths (e.g. mapping's vs imager's `clean`). A single
prefix cannot serve both; the trees stay separate with per-program
wrappers that never shadow a GILDAS name.
