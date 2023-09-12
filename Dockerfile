FROM debian:stable as gildas_worker
RUN apt-get -y update && apt-get install -y \
    libx11-6 \
    libpng16-16 \
    libfftw3-double3 \
    libfftw3-single3 \
    libcfitsio10 \
    libforms2 \
    python3 \
    python-is-python3 \
    python3-numpy \
    python3-scipy \
    python3-emcee \
    libgtk2.0

FROM gildas_worker as gildas_builder
RUN apt-get -y update && apt-get install -y \
    libx11-dev \
    libpng-dev \
    libfftw3-dev \
    libcfitsio-dev \
    libforms-dev \
    python3-dev \
    libgtk2.0-dev \
    python3-setuptools \
    python-dev-is-python3 \
    gfortran \
    curl


FROM gildas_builder as builder
ARG release
ENV release=${release}
ARG ARCHIVE
# if --build-arg ARCHIVE=1 set the url to the archive page
ENV GILDAS_URL=${ARCHIVE:+https://www.iram.fr/~gildas/dist/archive/gildas}
# else keep the main directory
ENV GILDAS_URL=${GILDAS_URL:-https://www.iram.fr/~gildas/dist}
CMD sh -c 
RUN curl $GILDAS_URL/gildas-src-$release.tar.xz | tar xJ && \
    bash -c "cd gildas-src-$release && GAG_SEARCH_PATH=/usr/lib/x86_64-linux-gnu source admin/gildas-env.sh -o openmp && \
    make && make -j 16 install" && \
    rm -Rf gildas-src-$release && \
    cd gildas-exe-$release && curl $GILDAS_URL/gildas-doc-$release.tar.xz | tar xJ


FROM gildas_worker as gildas
ARG release
ENV release=${release}
COPY --from=builder /gildas-exe-$release /gildas-exe-$release
SHELL ["/bin/bash", "-c"]
RUN . /etc/os-release && \
    echo "# Gildas" >> /etc/bash.bashrc && \
    echo "export GAG_ROOT_DIR=/gildas-exe-$release" >> /etc/bash.bashrc && \
    echo "export GAG_EXEC_SYSTEM=x86_64-debian${VERSION_ID}-gfortran-openmp" >> /etc/bash.bashrc  && \
    echo '. $GAG_ROOT_DIR/etc/bash_profile' >> /etc/bash.bashrc
# CMD ["/bin/bash", "--rcfile", "/etc/bash.bashrc"]
ENTRYPOINT ["/bin/bash", "--rcfile", "/etc/bash.bashrc", "-i", "-c"]


from gildas as gildas-piic
COPY --from=builder /etc/bash.bashrc /etc/bash.bashrc
ARG PIIC_ARCHIVE
# if --build-arg ARCHIVE=1 set the url to the archive page
ENV GILDAS_URL=${PIIC_ARCHIVE:+https://www.iram.fr/~gildas/dist/archive/piic}
# else keep the main directory
ENV GILDAS_URL=${GILDAS_URL:-https://www.iram.fr/~gildas/dist}
RUN curl $GILDAS_URL/piic-exe-$release.tar.xz | tar xJ; exit 0
SHELL ["/bin/bash", "-c"]
RUN . /etc/os-release && \
    echo '# Two separate gildas environement (PIIC.README)...' >> /etc/bash.bashrc && \
    echo 'gagpiic () {' >> /etc/bash.bashrc && \
    echo "export GAG_ROOT_DIR=/piic-exe-$release" >> /etc/bash.bashrc && \
    echo "'export GAG_EXEC_SYSTEM=x86_64-generic" >> /etc/bash.bashrc && \
    echo '. $GAG_ROOT_DIR/etc/bash_profile' >> /etc/bash.bashrc && \
    echo '}' >> /etc/bash.bashrc && \
    echo 'gaggildas () {' >> /etc/bash.bashrc && \
    echo "export GAG_ROOT_DIR=/gildas-exe-$release" >> /etc/bash.bashrc && \
    echo "export GAG_EXEC_SYSTEM=x86_64-debian${VERSION_ID}-gfortran-openmp" >> /etc/bash.bashrc && \
    echo '. $GAG_ROOT_DIR/etc/bash_profile' >> /etc/bash.bashrc && \
    echo '}' >> /etc/bash.bashrc
