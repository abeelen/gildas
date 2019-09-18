FROM debian:stretch
ARG release
ENV release=${release}
RUN apt-get -y update && apt-get install -y \
    libx11-6 \
    libpng16-16 \
    libfftw3-3 \
    libcfitsio5 \
    libforms2 \
    python \
    python-numpy \
    python-dev \
    libgtk2.0
RUN echo 'export GAG_ROOT_DIR=/gildas-exe-$release' >> /etc/bash.bashrc && \
    echo 'export GAG_EXEC_SYSTEM=x86_64-debian9-gfortran-openmp' >> /etc/bash.bashrc && \
    echo '. $GAG_ROOT_DIR/etc/bash_profile' >> /etc/bash.bashrc
COPY gildas-exe-$release /gildas-exe-$release
# COPY gildas-exe-$release.tar.gz /
# RUN tar xvzf gildas-exe-$release.tar.gz
