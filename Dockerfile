FROM debian:stretch as gildas_worker
RUN apt-get -y update && apt-get install -y \
    libx11-6 \
    libpng16-16 \
    libfftw3-3 \
    libcfitsio5 \
    libforms2 \
    python \
    libpython2.7 \
    python-numpy \
    libgtk2.0

FROM gildas_worker as gildas_builder
RUN apt-get -y update && apt-get install -y \
    libx11-dev \
    libpng-dev \
    libfftw3-dev \
    libcfitsio-dev \
    libforms-dev \
    python-dev \
    libgtk2.0-dev \
    gfortran \
    curl


FROM gildas_builder as builder
ARG release
ENV release=${release}
ARG ARCHIVE
# if --build-arg ARCHIVE=1 set the url to the archive page
ENV GILDAS_URL=${ARCHIVE:+http://www.iram.fr/~gildas/dist/archive/gildas}
# else keep the main directory
ENV GILDAS_URL=${GILDAS_URL:-http://www.iram.fr/~gildas/dist}
CMD sh -c 
RUN curl $GILDAS_URL/gildas-src-$release.tar.xz | tar xJ && \
    bash -c "cd gildas-src-$release && GAG_SEARCH_PATH=/usr/lib/x86_64-linux-gnu source admin/gildas-env.sh -o openmp && \
    make && make -j 4 install" && \
    echo 'export GAG_ROOT_DIR=/gildas-exe-$release' >> /etc/bash.bashrc && \
    echo 'export GAG_EXEC_SYSTEM=x86_64-debian9-gfortran-openmp' >> /etc/bash.bashrc && \
    echo '. $GAG_ROOT_DIR/etc/bash_profile' >> /etc/bash.bashrc && \
    rm -Rf gildas-src-$release && \
    cd gildas-exe-$release && curl $GILDAS_URL/gildas-doc-$release.tar.xz | tar xJ


FROM gildas_worker
ARG release
ENV release=${release}
COPY --from=builder /gildas-exe-$release /gildas-exe-$release
ARG PIIC_ARCHIVE
# if --build-arg ARCHIVE=1 set the url to the archive page
ENV GILDAS_URL=${PIIC_ARCHIVE:+http://www.iram.fr/~gildas/dist/archive/gildas}
# else keep the main directory
ENV GILDAS_URL=${GILDAS_URL:-http://www.iram.fr/~gildas/dist}
RUN curl $GILDAS_URL/piic-exe-$release.tar.xz | tar xJ
RUN echo '# \n\
# Two separate gildas environement (PIIC.README)...\n\
gagpiic () {\n\
export GAG_ROOT_DIR=/piic-exe-$release\n\
export GAG_EXEC_SYSTEM=x86_64-generic\n\
. $GAG_ROOT_DIR/etc/bash_profile\n\
}\n\
gaggildas () {\n\
export GAG_ROOT_DIR=/gildas-exe-$release\n\
export GAG_EXEC_SYSTEM=x86_64-debian9-gfortran-openmp\n\
. $GAG_ROOT_DIR/etc/bash_profile\n\
}\n'\
>> /etc/bash.bashrc
ENTRYPOINT ["/bin/bash", "--rcfile", "/etc/bash.bashrc", "-i", "-c"]
