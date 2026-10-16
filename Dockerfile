# syntax=docker/dockerfile:1
FROM debian:stable-slim AS gildas_worker

ARG DEBIAN_FRONTEND=noninteractive
# Set to 1 to keep texlive+ghostscript in the runtime image (pipeline support).
# Default 0 keeps the runtime slim for faster pulls; builder still has them if needed.
ARG WITH_TEXLIVE=0

# Slim runtime: only libraries needed to *run* GILDAS.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    xz-utils \
    libx11-6 \
    libpng16-16 \
    libfftw3-double3 \
    libfftw3-single3 \
    libcfitsio10 \
    libforms2 \
    libasan8 \
    libubsan1 \
    python3 \
    libpython3.13 \
    python-is-python3 \
    python3-numpy \
    python3-scipy \
    python3-emcee \
    python3-matplotlib \
    python3-astropy \
    ipython3 \
    python3-ipython \
    libgtk2.0 \
    && if [ "$WITH_TEXLIVE" = "1" ]; then apt-get install -y --no-install-recommends texlive ghostscript; fi \
    && rm -rf /var/lib/apt/lists/*

LABEL org.opencontainers.image.title="GILDAS runtime" \
      org.opencontainers.image.source="https://github.com/abeelen/gildas"


FROM gildas_worker AS gildas_builder

ARG DEBIAN_FRONTEND=noninteractive

# Build deps + ccache for faster recompiles. texlive only if requested.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    make \
    gcc \
    g++ \
    gfortran \
    ccache \
    pkg-config \
    dpkg-dev \
    libx11-dev \
    libpng-dev \
    libfftw3-dev \
    libcfitsio-dev \
    libforms-dev \
    libssl-dev \
    python3-dev \
    libgtk2.0-dev \
    groff-base \
    python3-setuptools \
    python-dev-is-python3 \
    patch \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/usr/lib/ccache:${PATH}" \
    CC="ccache gcc" \
    CXX="ccache g++" \
    FC="ccache gfortran"


FROM gildas_builder AS builder

# Source patches shared by all recipes (kept as files, applied with
# patch(1) so they stay reviewable diffs instead of inline edits).
COPY patches/ /tmp/patches/

ARG release
ENV release=${release}

# Base URL for GILDAS (can be overridden at build time)
ARG GILDAS_URL=https://www.iram.fr/~gildas/dist

# SANATIZE option cause crashes
ARG GAG_USE_SANITIZE=no
ENV GAG_USE_SANITIZE=${GAG_USE_SANITIZE}

# Defaults to host CPU count when empty. Override with --build-arg MAKE_JOBS=N.
ARG MAKE_JOBS=""

WORKDIR /

# 1. Separate download layer: cached unless release/URL changes. Fail fast on 404.
RUN set -eux -o pipefail; \
    curl -fSL --retry 3 --connect-timeout 20 \
      "$GILDAS_URL/gildas-src-$release.tar.xz" -o "/tmp/gildas-src-$release.tar.xz"; \
    curl -fSL --retry 3 --connect-timeout 20 \
      "$GILDAS_URL/gildas-doc-$release.tar.xz" -o "/tmp/gildas-doc-$release.tar.xz" || true; \
    tar xJf "/tmp/gildas-src-$release.tar.xz"; \
    rm -f "/tmp/gildas-src-$release.tar.xz"

# 1b. SIC foreground patch (own layer, like the Alpine patches): keeps
# interactive sessions in the terminal foreground group (see the patch
# file). patch(1) fails loudly on mismatch.
RUN set -eux -o pipefail; \
    cd "gildas-src-$release" && patch -p1 --forward < /tmp/patches/sic-foreground.patch

# 2. Compile layer: uses ccache + apt cache mounts for speed.
# NOTE: the GILDAS env script requires bash (`source`), so the
# source+make sequence runs under an explicit bash -c (/bin/sh is dash).
RUN --mount=type=cache,target=/root/.ccache \
    set -eux -o pipefail; \
    JOBS="${MAKE_JOBS:-$(nproc)}"; \
    MULTIARCH="$(dpkg-architecture -qDEB_HOST_MULTIARCH)"; \
    cd "gildas-src-$release" && \
    CLIC_MK="packages/clic/Makefile"; \
    if grep -q 'GAG_USE_SANITIZE' "$CLIC_MK" 2>/dev/null; then \
      sed -i -e '/^ifeq ($(GAG_COMPILER_FKIND),gfortran)$/d' -e '/^  ifneq ($(GAG_USE_SANITIZE),yes)$/d' -e '/^    subdirs =$/d' -e '/^  endif$/d' -e '/^endif$/d' "$CLIC_MK"; \
      grep -q '^subdirs = lib main' "$CLIC_MK" && ! grep -q 'GAG_USE_SANITIZE' "$CLIC_MK" || { echo "ERROR: clic ungate patch failed" >&2; exit 1; }; \
    fi; \
    JOBS="$JOBS" SEARCH="/usr/lib/$MULTIARCH:/usr/lib/x86_64-linux-gnu" bash -c ' \
      set -ex -o pipefail; \
      GAG_SEARCH_PATH="$SEARCH" source admin/gildas-env.sh -o openmp; \
      make -j "$JOBS" && make install; \
    ' && \
    cd / && rm -rf "gildas-src-$release" && \
    if [ -f "/tmp/gildas-doc-$release.tar.xz" ]; then \
      cd "gildas-exe-$release" && tar xJf "/tmp/gildas-doc-$release.tar.xz" && rm -f "/tmp/gildas-doc-$release.tar.xz"; \
    fi; \
    ccache -s || true

# Standalone IMAGER (https://imager.oasu.u-bordeaux.fr, self-contained tree
# built like GILDAS). Installed to canonical /imager-exe. Skipped when
# WITH_IMAGER=0 (an empty /imager-exe keeps the COPY below valid).
ARG IMAGER_VERSION=last
ARG IMAGER_URL=https://share.oasu.u-bordeaux.fr/imager
ARG WITH_IMAGER=1

RUN set -eux -o pipefail; \
    mkdir -p /imager-exe; \
    echo "${IMAGER_VERSION:-none} (unresolved)" > /etc/imager-version; \
    if [ "${WITH_IMAGER}" != "1" ]; then echo "Skipping IMAGER (WITH_IMAGER=${WITH_IMAGER})"; exit 0; fi; \
    cd /tmp; \
    curl -fSL --retry 3 --connect-timeout 20 "${IMAGER_URL}/imager-${IMAGER_VERSION}.tgz" -o imager-dl.tgz; \
    set +o pipefail; IMDIR="$(tar tzf imager-dl.tgz | head -n 1 | cut -d/ -f1)"; set -o pipefail; \
    case "${IMDIR}" in imager-src-*) ;; *) echo "ERROR: unexpected imager top dir ${IMDIR}" >&2; exit 1;; esac; \
    echo "${IMDIR#imager-src-}" > /etc/imager-version; \
    tar xzf imager-dl.tgz -C /; rm -f imager-dl.tgz; \
    (cd "/${IMDIR}" && patch -p1 --forward < /tmp/patches/sic-foreground.patch) || { echo "ERROR: SIC foreground patch failed" >&2; exit 1; }; \
    IMDIR="${IMDIR}" JOBS="${MAKE_JOBS:-$(nproc)}" SEARCH="/usr/lib/$(dpkg-architecture -qDEB_HOST_MULTIARCH):/usr/lib/x86_64-linux-gnu" bash -c ' \
      set -ex -o pipefail; \
      unset gagsrcdir gagexedir gagadmdir || true; \
      cd "/${IMDIR}"; \
      cd Admin-Source && source substitute.compile.sh && cd ..; \
      GAG_SEARCH_PATH="${SEARCH}" source admin/imager-env.sh -o openmp; \
      export gagexedir=/imager-exe; \
      make -j "${JOBS}" && make install; \
    '; \
    rm -rf "/${IMDIR}"

FROM gildas_worker AS gildas

ARG release
ENV release=${release}
ARG IMAGER_VERSION=last
ENV IMAGER_VERSION=${IMAGER_VERSION}

COPY --from=builder /gildas-exe-$release /gildas-exe-$release
COPY --from=builder /imager-exe /imager-exe
COPY --from=builder /etc/imager-version /etc/imager-version

SHELL ["/bin/bash", "-c"]

# Auto-detect GAG_EXEC_SYSTEM at build time instead of hardcoding
# x86_64-${ID}${VERSION_ID}-gfortran-openmp (breaks on testing/arm64).
RUN set -eux -o pipefail; \
    CANDIDATE="$(ls -1 /gildas-exe-$release/ | grep -E 'gfortran-openmp|gfortran|generic' | head -n 1 || true)"; \
    if [ -z "$CANDIDATE" ]; then CANDIDATE='x86_64-debian-gfortran-openmp'; fi; \
    echo "$CANDIDATE" > /etc/gildas-exec-system; \
    cat /etc/gildas-exec-system; \
    GAG_EXEC_SYSTEM="$(cat /etc/gildas-exec-system)"; \
    cat > /etc/gildas-env.sh <<EOF
# Gildas base environment
export GAG_ROOT_DIR=/gildas-exe-$release
export GAG_EXEC_SYSTEM=$GAG_EXEC_SYSTEM
if [ -f \$GAG_ROOT_DIR/etc/bash_profile ]; then
  . \$GAG_ROOT_DIR/etc/bash_profile
fi
# Re-resolve at container start (image may run on a different Debian point release)
if [ ! -d "\$GAG_ROOT_DIR/\$GAG_EXEC_SYSTEM" ]; then
  _detected=\$(ls -1 "\$GAG_ROOT_DIR" 2>/dev/null | grep -E 'gfortran-openmp|gfortran|generic' | head -n 1 || true)
  if [ -n "\$_detected" ]; then export GAG_EXEC_SYSTEM="\$_detected"; fi
fi
EOF
# Direct-access wrappers: every program shipped by the standalone IMAGER
# tree (https://imager.oasu.u-bordeaux.fr) but missing from GILDAS gets a
# self-contained /usr/local/bin wrapper selecting the IMAGER tree.
# Rule: never shadow a GILDAS program of the same name.
# NOTE: no heredoc here, a RUN cannot continue past a heredoc terminator.
RUN set -eux -o pipefail; \
    if [ -f /imager-exe/etc/bash_profile ]; then \
      IM_EXEC="$(ls -1 /imager-exe/ | grep -E 'gfortran-openmp|gfortran|generic' | head -n 1 || true)"; \
      if [ -z "$IM_EXEC" ]; then IM_EXEC='x86_64-debian-gfortran-openmp'; fi; \
      echo "$IM_EXEC" > /etc/imager-exec-system; \
      GAG_EXEC_SYSTEM="$(cat /etc/gildas-exec-system)"; \
      for _bin in "/imager-exe/$IM_EXEC/bin/"*; do \
        _prog="$(basename "$_bin")"; \
        if [ ! -x "/gildas-exe-$release/$GAG_EXEC_SYSTEM/bin/$_prog" ] && [ ! -e "/usr/local/bin/$_prog" ]; then \
          { echo '#!/bin/sh'; \
            echo "# $_prog: runs from the standalone IMAGER tree (/imager-exe)."; \
            echo 'export GAG_ROOT_DIR=/imager-exe'; \
            echo "export GAG_EXEC_SYSTEM=$IM_EXEC"; \
            echo 'if [ -f "$GAG_ROOT_DIR/etc/bash_profile" ]; then'; \
            echo '  . "$GAG_ROOT_DIR/etc/bash_profile"'; \
            echo 'fi'; \
            echo 'exec "$GAG_EXEC_DIR/bin/'"$_prog"'" "$@"'; \
          } > "/usr/local/bin/$_prog"; \
          chmod +x "/usr/local/bin/$_prog"; \
        fi; \
      done; \
    fi
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh && echo "none" > /etc/piic-version

LABEL org.opencontainers.image.title="GILDAS" \
      org.opencontainers.image.revision="${release}" \
      abeelen.gildas.release="${release}" \
      abeelen.gildas.base="debian" \
      abeelen.gildas.target="gildas" \
      abeelen.gildas.imager-version="${IMAGER_VERSION}"
# NOTE: /etc/imager-version and /etc/piic-version inside the image are
# authoritative for bundled component versions (labels record build args).

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["bash"]


FROM gildas AS gildas-piic

ARG release
ENV release=${release}
ARG PIIC_URL=https://www.iram.fr/~gildas/dist
ENV PIIC_URL=$PIIC_URL

WORKDIR /

# Do not mask real errors with `|| true`: warn when the tarball is missing,
# fail when download is corrupt.
RUN set -eux -o pipefail; \
    if curl -fSL --retry 3 --connect-timeout 20 "$PIIC_URL/piic-exe-$release.tar.xz" -o "/tmp/piic-exe-$release.tar.xz"; then \
      tar xJf "/tmp/piic-exe-$release.tar.xz" && rm -f "/tmp/piic-exe-$release.tar.xz"; \
      echo "$release" > /etc/piic-version; \
    else \
      echo "WARNING: no piic-exe-$release.tar.xz at $PIIC_URL, skipping PIIC layer" >&2; \
      echo "none (unresolved)" > /etc/piic-version; \
    fi

SHELL ["/bin/bash", "-c"]

# Direct-access wrappers: every program shipped by the PIIC tree but
# missing from GILDAS (or IMAGER) gets a self-contained /usr/local/bin
# wrapper selecting the PIIC tree. Same never-shadow rule as above.
RUN set -eux -o pipefail; \
    if [ -f "/piic-exe-$release/etc/bash_profile" ]; then \
      PIIC_EXEC="$(ls -1 "/piic-exe-$release/" | grep -E 'gfortran-openmp|gfortran|generic' | head -n 1 || true)"; \
      if [ -z "$PIIC_EXEC" ]; then PIIC_EXEC='x86_64-generic'; fi; \
      echo "$PIIC_EXEC" > /etc/piic-exec-system; \
      GAG_EXEC_SYSTEM="$(cat /etc/gildas-exec-system)"; \
      for _bin in "/piic-exe-$release/$PIIC_EXEC/bin/"*; do \
        _prog="$(basename "$_bin")"; \
        if [ ! -x "/gildas-exe-$release/$GAG_EXEC_SYSTEM/bin/$_prog" ] && [ ! -e "/usr/local/bin/$_prog" ]; then \
          { echo '#!/bin/sh'; \
            echo "# $_prog: runs from the PIIC tree (/piic-exe-$release)."; \
            echo "export GAG_ROOT_DIR=/piic-exe-$release"; \
            echo "export GAG_EXEC_SYSTEM=$PIIC_EXEC"; \
            echo 'if [ -f "$GAG_ROOT_DIR/etc/bash_profile" ]; then'; \
            echo '  . "$GAG_ROOT_DIR/etc/bash_profile"'; \
            echo 'fi'; \
            echo 'exec "$GAG_EXEC_DIR/bin/'"$_prog"'" "$@"'; \
          } > "/usr/local/bin/$_prog"; \
          chmod +x "/usr/local/bin/$_prog"; \
        fi; \
      done; \
    fi

LABEL abeelen.gildas.target="gildas-piic"
