#!/bin/sh
# shellcheck disable=SC2010  # keep the same source-tree scan as the recipes
# Shared runtime setup for the GILDAS Docker images and the native Alpine
# SIF recipe.
#
# Usage: gildas-runtime.sh env|imager|piic
#
# The caller chooses the wrapper order:
#   Docker: env, then imager, then piic
#   Native: env, then piic, then imager
# so an existing wrapper is never overwritten.
#
# Environment:
#   RELEASE          GILDAS release (required)
#   GILDAS_DIR       default /gildas-exe-$RELEASE
#   IMAGER_DIR       default /imager-exe
#   PIIC_DIR         default /piic-exe-$RELEASE
#   FALLBACK_EXEC    exec-system fallback (default x86_64-generic)
#   EXEC_GREP        regex matching the exec-system directory
#   RERESOLVE=1      add the container-start re-resolution block
#   APPEND_BASHRC=1  append the env file to /etc/bash.bashrc
#   ROOT             test-only prefix for /etc and /usr/local

set -eu

usage() {
    echo "usage: $0 env|imager|piic" >&2
    exit 2
}

case "${1:-}" in
    env|imager|piic) ;;
    *) usage ;;
esac

: "${RELEASE:?RELEASE is not set}"

GILDAS_DIR=${GILDAS_DIR:-/gildas-exe-${RELEASE}}
IMAGER_DIR=${IMAGER_DIR:-/imager-exe}
PIIC_DIR=${PIIC_DIR:-/piic-exe-${RELEASE}}
FALLBACK_EXEC=${FALLBACK_EXEC:-x86_64-generic}
EXEC_GREP=${EXEC_GREP:-gfortran-openmp|gfortran|generic|musl|alpine}
RERESOLVE=${RERESOLVE:-0}
APPEND_BASHRC=${APPEND_BASHRC:-0}

# ROOT is only used by the tests; production builds leave it empty.
ETC_DIR="${ROOT:-}/etc"
BIN_DIR="${ROOT:-}/usr/local/bin"
ENV_FILE="${ETC_DIR}/gildas-env.sh"
BASHRC="${ETC_DIR}/bash.bashrc"

mkdir -p "${ETC_DIR}" "${BIN_DIR}"

# Find the directory GILDAS/IMAGER/PIIC installed its executables under,
# e.g. x86_64-debian-gfortran-openmp or x86_64-generic.
detect_exec_system() {
    tree=$1
    candidate=$(ls -1 "${tree}/" 2>/dev/null | grep -E "${EXEC_GREP}" | head -n 1 || true)
    printf '%s\n' "${candidate:-${FALLBACK_EXEC}}"
}

# Write a small program that selects one component tree and runs the real
# binary. Used only when GILDAS does not provide a program of the same name.
write_wrapper() {
    program=$1
    tree=$2
    exec_system=$3
    description=$4

    cat >"${BIN_DIR}/${program}" <<EOF
#!/bin/sh
# ${program}: runs from the ${description}.
export GAG_ROOT_DIR=${tree}
export GAG_EXEC_SYSTEM=${exec_system}
if [ -f "\$GAG_ROOT_DIR/etc/bash_profile" ]; then
  . "\$GAG_ROOT_DIR/etc/bash_profile"
fi
exec "\$GAG_EXEC_DIR/bin/${program}" "\$@"
EOF
    chmod +x "${BIN_DIR}/${program}"
}

# Write /etc/gildas-env.sh (and optionally add it to bash.bashrc).
setup_environment() {
    if [ ! -d "${GILDAS_DIR}" ]; then
        echo "ERROR: ${GILDAS_DIR} does not exist" >&2
        exit 1
    fi

    exec_system=$(detect_exec_system "${GILDAS_DIR}")
    printf '%s\n' "${exec_system}" >"${ETC_DIR}/gildas-exec-system"

    cat >"${ENV_FILE}" <<EOF
# Gildas base environment
export GAG_ROOT_DIR=${GILDAS_DIR}
export GAG_EXEC_SYSTEM=${exec_system}
if [ -f "\$GAG_ROOT_DIR/etc/bash_profile" ]; then
  . "\$GAG_ROOT_DIR/etc/bash_profile"
fi
EOF

    if [ "${RERESOLVE}" = "1" ]; then
        cat >>"${ENV_FILE}" <<'EOF'
# Re-resolve at container start if the selected tree is missing.
if [ ! -d "$GAG_ROOT_DIR/$GAG_EXEC_SYSTEM" ]; then
  _detected=$(ls -1 "$GAG_ROOT_DIR" 2>/dev/null | grep -E 'gfortran-openmp|gfortran|generic' | head -n 1 || true)
  if [ -n "$_detected" ]; then export GAG_EXEC_SYSTEM="$_detected"; fi
fi
EOF
    fi

    if [ "${APPEND_BASHRC}" = "1" ]; then
        cat "${ENV_FILE}" >>"${BASHRC}"
    fi
}

# Install wrappers for IMAGER or PIIC. Existing wrappers win, so the caller
# controls precedence by choosing whether to install PIIC or IMAGER first.
install_wrappers() {
    tree=$1
    kind=$2
    description=$3

    if [ ! -f "${tree}/etc/bash_profile" ]; then
        return 0
    fi

    exec_system=$(detect_exec_system "${tree}")
    printf '%s\n' "${exec_system}" >"${ETC_DIR}/${kind}-exec-system"

    gildas_exec_system=$(cat "${ETC_DIR}/gildas-exec-system" 2>/dev/null || true)
    if [ -z "${gildas_exec_system}" ]; then
        gildas_exec_system=$(detect_exec_system "${GILDAS_DIR}")
    fi

    for binary in "${tree}/${exec_system}/bin/"*; do
        [ -e "${binary}" ] || continue
        program=$(basename "${binary}")
        if [ ! -x "${GILDAS_DIR}/${gildas_exec_system}/bin/${program}" ] &&
           [ ! -e "${BIN_DIR}/${program}" ]; then
            write_wrapper "${program}" "${tree}" "${exec_system}" "${description}"
        fi
    done
}

case "$1" in
    env)
        setup_environment
        ;;
    imager)
        install_wrappers "${IMAGER_DIR}" imager "standalone IMAGER tree (${IMAGER_DIR})"
        ;;
    piic)
        install_wrappers "${PIIC_DIR}" piic "PIIC tree (${PIIC_DIR})"
        ;;
esac
