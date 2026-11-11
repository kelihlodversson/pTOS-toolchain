#!/usr/bin/env bash
# Translate a numeric Git release tag to a Debian version.
set -euo pipefail
[[ $# == 1 ]] || { echo "Usage: $0 <release-tag>" >&2; exit 2; }
version=${1#v}
# Quote the tilde so Bash does not expand it to the home directory.
version=${version/-/\~}
dpkg --validate-version "$version"
printf '%s\n' "$version"
