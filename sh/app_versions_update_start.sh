#!/bin/sh

. "/srv/sh/app_versions.sh" > /dev/null 2>&1
vitos_saos_upgrade
exit $?
