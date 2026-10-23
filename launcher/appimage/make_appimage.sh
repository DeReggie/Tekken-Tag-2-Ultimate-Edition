#!/bin/bash
# Makes the launcher's AppImage: ttt2-launcher, the kit it builds the game
# program with and the character importer, installed into an AppDir and
# packed with the AppImage type 2 runtime. Nothing of the game is in it: the
# game program is built on the player's PC from their own .wua.
#
#   launcher/appimage/make_appimage.sh [--runtime-cache DIR] OUTPUT BUILD_DIR
#
# OUTPUT      the .AppImage to write
# BUILD_DIR   a build folder of its own (new, empty, or one this script made):
#             configured afresh each time (Release, Clang, Ninja, without the
#             build tree's paths); the AppDir and the image are made in it
# --runtime-cache DIR (else $TTT2_APPIMAGE_CACHE, else BUILD_DIR/appimage-cache):
#             where the runtime is downloaded to, once
#
# Needs CMake 3.24+, Ninja, Clang, mksquashfs (with zstd), and curl or wget
# for the first download; rsvg-convert for a PNG .DirIcon (else the SVG).
#
# The AppImage uses the system's GTK 4, GLib and C++ runtime, and its kit
# needs this system's glibc and libstdc++: for now it runs on the
# distribution it was made on. AppRun changes nothing of the environment, as
# the programs the launcher starts (the compiler, Python, gamescope, Proton,
# the game) must not load anything of the AppImage.

set -eu

runtime_url=https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64
app_id=io.github.petexy.TekkenTag2UltimateEdition

die() {
    echo "make_appimage.sh: $*" >&2
    exit 1
}

usage() {
    echo "usage: $0 [--runtime-cache DIR] OUTPUT BUILD_DIR"
}

cache=${TTT2_APPIMAGE_CACHE:-}
while [ $# -gt 0 ]; do
    case $1 in
        --runtime-cache)
            [ $# -ge 2 ] || die "--runtime-cache needs a folder"
            cache=$2
            shift 2
            ;;
        --runtime-cache=*)
            cache=${1#*=}
            shift
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        --)
            shift
            break
            ;;
        -*) die "unknown option $1" ;;
        *) break ;;
    esac
done
if [ $# -ne 2 ]; then
    usage >&2
    exit 2
fi

repo=$(cd "$(dirname "$0")/../.." && pwd -P)
output=$(realpath -m -- "$1")
build=$(realpath -m -- "$2")
cache=$(realpath -m -- "${cache:-$build/appimage-cache}")
[ -d "$(dirname "$output")" ] || die "$(dirname "$output") is not a folder"
# (The compile flags below are a list split at spaces.)
case $repo$build in
    *[[:space:]]*) die "the source and build folders' paths must not have spaces" ;;
esac

for tool in cmake ninja clang clang++ mksquashfs; do
    command -v "$tool" >/dev/null || die "$tool is not installed"
done

# Only a build folder of its own: reconfiguring another (a build of the game
# program, a developer's) would change what it builds.
if [ -e "$build" ]; then
    [ -d "$build" ] || die "$build is not a folder"
    if [ -f "$build/CMakeCache.txt" ]; then
        grep -qx 'TTT2_LAUNCHER_BUILD_TREE_PATHS:BOOL=OFF' "$build/CMakeCache.txt" ||
            die "$build is another build folder: give this script one of its own"
    elif [ -n "$(ls -A "$build")" ]; then
        die "$build is not empty and not a build folder"
    fi
fi

# 1. The launcher and the kit, without the build and source trees' paths and
# without the game program (TTT2_GENERATED_DIR) or tests that read the game
# (TTT2_RPX). The compilers write source paths relative (the runtime's error
# messages name their files) so that no folder of this computer is in it.
prefix_maps="-ffile-prefix-map=$repo/= -ffile-prefix-map=$build/="
cmake --fresh -S "$repo" -B "$build" -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
    "-DCMAKE_C_FLAGS=$prefix_maps" "-DCMAKE_CXX_FLAGS=$prefix_maps" \
    -DTTT2_LAUNCHER_BUILD_TREE_PATHS=OFF -DTTT2_GENERATED_DIR= -DTTT2_RPX=
grep -qx 'GTK4_FOUND:INTERNAL=1' "$build/CMakeCache.txt" || die "GTK 4.10 or newer (its development files) is needed"
cmake --build "$build" --target ttt2-launcher ttt2_kit

# 2. The AppDir: what cmake --install puts in usr/, and the AppImage's own
# files at its root.
appdir=$build/AppDir
rm -rf "$appdir"
cmake --install "$build" --prefix "$appdir/usr" --strip

# Only the launcher's files: never anything of the game, the tests or
# Python's caches (the first matching pattern decides).
unexpected() {
    (cd "$appdir" && find . -mindepth 1 \( -type f -o -type l \) -print) | while IFS= read -r file; do
        case $file in
            */generated/* | */tests/* | */__pycache__/* | */.pytest_cache/* | *.pyc | *.rpx | *.rpl | *.wua) echo "$file" ;;
            ./usr/bin/ttt2-launcher) ;;
            ./usr/lib/ttt2/kit/bin/ttt2-build | ./usr/lib/ttt2/kit/bin/cafe-recomp) ;;
            ./usr/lib/ttt2/kit/include/cafe/*.h) ;;
            ./usr/lib/ttt2/kit/lib/*.a | ./usr/lib/ttt2/kit/lib/generated_stub.o) ;;
            ./usr/lib/ttt2/kit/kit.ini | ./usr/lib/ttt2/kit/VERSION | ./usr/lib/ttt2/kit/t7helper.exe) ;;
            ./usr/share/ttt2/characters/*.py | ./usr/share/ttt2/characters/t7helper/t7helper.c) ;;
            "./usr/share/applications/$app_id.desktop") ;;
            "./usr/share/icons/hicolor/scalable/apps/$app_id.svg") ;;
            *) echo "$file" ;;
        esac
    done
}
found=$(unexpected)
[ -z "$found" ] || die "the AppDir holds files it must not: $found"
[ -x "$appdir/usr/lib/ttt2/kit/bin/ttt2-build" ] || die "the kit was not installed"

# The kit's programs are copied as built: stripped like the launcher.
strip=$(sed -n 's/^CMAKE_STRIP:FILEPATH=//p' "$build/CMakeCache.txt")
if [ -n "$strip" ] && [ -x "$strip" ]; then
    "$strip" "$appdir/usr/lib/ttt2/kit/bin/ttt2-build" "$appdir/usr/lib/ttt2/kit/bin/cafe-recomp"
fi

cat >"$appdir/AppRun" <<'EOF'
#!/bin/sh
# The AppImage's entry: the launcher, with the environment as it is.
here=$(dirname "$(readlink -f "$0")")
exec "$here/usr/bin/ttt2-launcher" "$@"
EOF
chmod 755 "$appdir/AppRun"
cp "$appdir/usr/share/applications/$app_id.desktop" "$appdir/"
cp "$appdir/usr/share/icons/hicolor/scalable/apps/$app_id.svg" "$appdir/"
if command -v rsvg-convert >/dev/null; then
    rsvg-convert -w 256 -h 256 -o "$appdir/.DirIcon" "$appdir/$app_id.svg"
else
    ln -s "$app_id.svg" "$appdir/.DirIcon"
fi

# 3. The runtime, downloaded once.
runtime=$cache/runtime-x86_64
if [ ! -f "$runtime" ]; then
    mkdir -p "$cache"
    echo "Downloading the AppImage runtime from $runtime_url"
    if command -v curl >/dev/null; then
        curl -fL --retry 3 -o "$runtime.part" "$runtime_url" || die "cannot download $runtime_url"
    elif command -v wget >/dev/null; then
        wget -O "$runtime.part" "$runtime_url" || die "cannot download $runtime_url"
    else
        die "curl or wget is needed to download the AppImage runtime"
    fi
    mv -f "$runtime.part" "$runtime"
fi
# An x86-64 ELF program (not an error page): its magic, then e_machine 62.
if [ "$(head -c 4 "$runtime")" != "$(printf '\177ELF')" ] ||
    [ "$(od -An -tx1 -j18 -N2 "$runtime" | tr -d ' \n')" != "3e00" ]; then
    rm -f "$runtime"
    die "$runtime_url did not give an x86-64 program (deleted; run again)"
fi

# 4. The image: the runtime, then the AppDir as squashfs, in zstd (which the
# runtime reads).
image=$build/appimage
rm -rf "$image"
mkdir -p "$image"
mksquashfs "$appdir" "$image/AppDir.squashfs" -root-owned -noappend -no-xattrs -comp zstd -b 1M -no-progress
cat "$runtime" "$image/AppDir.squashfs" >"$output.part"
chmod 755 "$output.part"

# The runtime itself reads it back.
mkdir "$image/check"
(cd "$image/check" && "$output.part" --appimage-extract AppRun >/dev/null)
cmp -s "$image/check/squashfs-root/AppRun" "$appdir/AppRun" || die "the runtime cannot read the image it was given"
rm -rf "$image"

mv -f "$output.part" "$output"
echo "Made $output ($(du -h "$output" | cut -f1))"
