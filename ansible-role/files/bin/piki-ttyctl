#!/usr/bin/env bash

set -euo pipefail

TTY=$1
FONT=${2:-}

[ -n "$FONT" ] && setfont -C "$TTY" "$FONT"
chvt "${TTY#/dev/tty}"
