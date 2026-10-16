#!/bin/bash
set -e

# Default GILDAS environment. IMAGER/PIIC programs are self-contained
# /usr/local/bin wrappers selecting their own tree: just run `imager`,
# `viewer`, `piic`, `mapping`, ... directly, no prefix needed.
if [ -f /etc/gildas-env.sh ]; then
	# shellcheck disable=SC1091
	source /etc/gildas-env.sh
fi

if [ "$#" -eq 0 ]; then
	set -- bash
fi

exec "$@"
