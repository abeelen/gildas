FROM debian:stable-slim AS gildas_worker

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get -y update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    xz-utils \
    libx11-6 \
    libpng16-16 \
    libfftw3-double3 \
    libfftw3-single3 \
    libcfitsio10 \
    libforms2 \
    # new packages 25... \
    libasan8 \
    libubsan1 \
    # python modules
    python3 \
    libpython3.13 \
    python-is-python3 \
    python3-numpy \
    python3-scipy \
    python3-emcee \
    python3-matplotlib \
    ipython3 \
    python3-ipython \
    libgtk2.0 \
    # for the pipeline
    texlive \
    ghostscript \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


FROM gildas_worker AS gildas_builder

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get -y update && apt-get install -y --no-install-recommends \
    ca-certificates \
    make \
    gcc \
    g++ \
    gfortran \
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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


FROM gildas_builder AS builder

ARG release
ENV release=${release}

# Base URL for GILDAS (can be overridden at build time)
ARG GILDAS_URL=https://www.iram.fr/~gildas/dist
ENV GILDAS_URL=$GILDAS_URL

# SANATIZE option cause crashes
ARG GAG_USE_SANITIZE
ENV GAG_USE_SANITIZE=${GAG_USE_SANITIZE:-no}

ARG MAKE_JOBS=8

WORKDIR /

RUN curl "$GILDAS_URL/gildas-src-$release.tar.xz" | tar xJ && \
    bash -c "cd gildas-src-$release && GAG_SEARCH_PATH=/usr/lib/x86_64-linux-gnu source admin/gildas-env.sh -o openmp && make -j ${MAKE_JOBS} && make install" && \
    rm -Rf "gildas-src-$release" && cd "gildas-exe-$release" && curl "$GILDAS_URL/gildas-doc-$release.tar.xz" | tar xJ

FROM gildas_worker AS gildas

ARG release
ENV release=${release}

COPY --from=builder /gildas-exe-$release /gildas-exe-$release

SHELL ["/bin/bash", "-c"]

RUN . /etc/os-release && \
    cat <<EOF >> /etc/bash.bashrc
# Gildas
export GAG_ROOT_DIR=/gildas-exe-$release
export GAG_EXEC_SYSTEM=x86_64-${ID}${VERSION_ID}-gfortran-openmp
. $GAG_ROOT_DIR/etc/bash_profile
EOF

ENTRYPOINT ["/bin/bash", "--rcfile", "/etc/bash.bashrc", "-i", "-c"]


FROM gildas AS gildas-piic

ARG PIIC_URL=https://www.iram.fr/~gildas/dist
ENV GILDAS_URL=$PIIC_URL

WORKDIR /

RUN curl "$GILDAS_URL/piic-exe-$release.tar.xz" | tar xJ || true

SHELL ["/bin/bash", "-c"]

RUN . /etc/os-release && \
        cat <<EOF >> /etc/bash.bashrc
# Two separate gildas environement (PIIC.README)...
gagpiic () {
    export GAG_ROOT_DIR=/piic-exe-$release
    export GAG_EXEC_SYSTEM=x86_64-generic
    . $GAG_ROOT_DIR/etc/bash_profile
}
gaggildas () {
    export GAG_ROOT_DIR=/gildas-exe-$release
    export GAG_EXEC_SYSTEM=x86_64-${ID}${VERSION_ID}-gfortran-openmp
    . $GAG_ROOT_DIR/etc/bash_profile
}
EOF
