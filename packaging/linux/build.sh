#!/bin/sh
# Build cat_recomp for Linux x86-64 (CPU path) on the Mac: clang and lld
# against the Steam Linux Runtime 3.0 (sniper) sysroot, design D4's route,
# since the amd64 SDK image took over 50 minutes under emulation. The
# binary needs glibc 2.29 at most, within sniper's 2.31.
#
#   SNIPER_SYSROOT  the sysroot from the toolkit's tools/linux/sysroot.sh
#   SNIPER_LLVM     clang and ld.lld (default: the pinned llvm-mingw)
#   XBOXRECOMP_DIR  the toolkit (default ../xboxrecomp)
set -eu
here=$(cd "$(dirname "$0")/../.." && pwd)
tk=${XBOXRECOMP_DIR:-$here/../xboxrecomp}
out=${1:-$here/build-linux}
llvm=${SNIPER_LLVM:-$(ls -d "$here"/third_party/llvm-mingw-*/bin 2>/dev/null | tail -1)}
: "${SNIPER_SYSROOT:?set SNIPER_SYSROOT (from the toolkit tools/linux/sysroot.sh)}"
cmake -S "$here" -B "$out" -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DXBOXRECOMP_DIR="$tk" \
    -DCMAKE_TOOLCHAIN_FILE="$tk/tools/linux/sniper-clang.cmake" \
    -DSNIPER_SYSROOT="$SNIPER_SYSROOT" -DSNIPER_LLVM="$llvm"
cmake --build "$out" -j "${JOBS:-8}"
