#!/bin/sh

#
# Script designed to be run for development purposes only.
#

"${SUEXEC:-doas}" make DIRECTOR_VERSION_SUFFIX=+`git rev-parse HEAD`
