#!/bin/bash
set -e

# Charge l'environnement GILDAS pour toute commande (si présent)
if [ -f /etc/gildas-env.sh ]; then
	# shellcheck disable=SC1091
	source /etc/gildas-env.sh
fi

# Exécute directement la commande passée au conteneur (mapping, clic, bash, etc.)
exec "$@"
