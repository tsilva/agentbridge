#!/usr/bin/env bash

set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
architecture="$(uname -m)"
output_root="${AGENTBRIDGE_MACOS_BUILD_DIR:-${repository_root}/build/macos/${architecture}}"
app_path="${output_root}/AgentBridge.app"
contents_path="${app_path}/Contents"
resources_path="${contents_path}/Resources"
server_path="${resources_path}/server"
python_path="${server_path}/python"
site_packages_path="${server_path}/site-packages"
package_build_path="${repository_root}/macos/.build"
signing_identity="${CODE_SIGN_IDENTITY:--}"

version="$(uv run --no-project --python 3.12 python - <<'PY'
import tomllib
from pathlib import Path

with Path("pyproject.toml").open("rb") as file:
    print(tomllib.load(file)["project"]["version"])
PY
)"

case "${architecture}" in
    arm64) artifact_architecture="arm64" ;;
    x86_64) artifact_architecture="x86_64" ;;
    *) echo "Unsupported macOS architecture: ${architecture}" >&2; exit 1 ;;
esac

if [[ "${output_root}" != "${repository_root}"/build/macos/* ]]; then
    echo "Refusing to replace unexpected build directory: ${output_root}" >&2
    exit 1
fi

# Finder may recreate .DS_Store while this build folder is open. Treat that
# metadata file as harmless, but fail if any real build output survives.
rm -rf "${output_root}" 2>/dev/null || true
if [[ -d "${output_root}" ]]; then
    surviving_output="$(
        find "${output_root}" -mindepth 1 -maxdepth 1 ! -name .DS_Store -print -quit
    )"
    if [[ -n "${surviving_output}" ]]; then
        echo "Could not clear build output: ${surviving_output}" >&2
        exit 1
    fi
fi
mkdir -p "${contents_path}/MacOS" "${resources_path}"

swift build \
    --package-path "${repository_root}/macos" \
    --configuration release
cp "${package_build_path}/release/AgentBridgeMenuBar" \
    "${contents_path}/MacOS/AgentBridgeMenuBar"
chmod 755 "${contents_path}/MacOS/AgentBridgeMenuBar"

uv build --wheel --out-dir "${output_root}/python-dist" "${repository_root}"

managed_python="$(uv python find --no-project --managed-python --resolve-links 3.12)"
managed_python_root="$(cd "$(dirname "${managed_python}")/.." && pwd)"
ditto "${managed_python_root}" "${python_path}"
mkdir -p "${site_packages_path}"

uv export \
    --project "${repository_root}" \
    --frozen \
    --no-dev \
    --no-emit-project \
    --format requirements.txt \
    --output-file "${output_root}/requirements.txt" >/dev/null
uv pip install \
    --python "${python_path}/bin/python3" \
    --target "${site_packages_path}" \
    --requirements "${output_root}/requirements.txt" \
    --link-mode copy

wheel_path="$(find "${output_root}/python-dist" -maxdepth 1 -name '*.whl' -print -quit)"
if [[ -z "${wheel_path}" ]]; then
    echo "AgentBridge wheel was not built" >&2
    exit 1
fi
uv pip install \
    --python "${python_path}/bin/python3" \
    --target "${site_packages_path}" \
    --no-deps \
    --link-mode copy \
    "${wheel_path}"

# The macOS app deliberately uses the user's installed Claude Code executable.
# The SDK package carries a fallback binary, so remove that build artifact from
# the private runtime while retaining the SDK's Python interface.
rm -f "${site_packages_path}/claude_agent_sdk/_bundled/claude"

info_plist="${contents_path}/Info.plist"
plutil -create xml1 "${info_plist}"
plutil -insert CFBundleDevelopmentRegion -string en "${info_plist}"
plutil -insert CFBundleDisplayName -string AgentBridge "${info_plist}"
plutil -insert CFBundleExecutable -string AgentBridgeMenuBar "${info_plist}"
plutil -insert CFBundleIconFile -string AgentBridge "${info_plist}"
plutil -insert CFBundleIdentifier -string com.tsilva.agentbridge "${info_plist}"
plutil -insert CFBundleInfoDictionaryVersion -string 6.0 "${info_plist}"
plutil -insert CFBundleName -string AgentBridge "${info_plist}"
plutil -insert CFBundlePackageType -string APPL "${info_plist}"
plutil -insert CFBundleShortVersionString -string "${version}" "${info_plist}"
plutil -insert CFBundleVersion -string "${version}" "${info_plist}"
plutil -insert LSMinimumSystemVersion -string 13.0 "${info_plist}"
plutil -insert LSUIElement -bool true "${info_plist}"
plutil -insert NSHighResolutionCapable -bool true "${info_plist}"

iconset_path="${output_root}/AgentBridge.iconset"
mkdir -p "${iconset_path}"
source_icon="${repository_root}/image-assets/icon/icon-1024.png"
sips -z 16 16 "${source_icon}" --out "${iconset_path}/icon_16x16.png" >/dev/null
sips -z 32 32 "${source_icon}" --out "${iconset_path}/icon_16x16@2x.png" >/dev/null
sips -z 32 32 "${source_icon}" --out "${iconset_path}/icon_32x32.png" >/dev/null
sips -z 64 64 "${source_icon}" --out "${iconset_path}/icon_32x32@2x.png" >/dev/null
sips -z 128 128 "${source_icon}" --out "${iconset_path}/icon_128x128.png" >/dev/null
sips -z 256 256 "${source_icon}" --out "${iconset_path}/icon_128x128@2x.png" >/dev/null
sips -z 256 256 "${source_icon}" --out "${iconset_path}/icon_256x256.png" >/dev/null
sips -z 512 512 "${source_icon}" --out "${iconset_path}/icon_256x256@2x.png" >/dev/null
sips -z 512 512 "${source_icon}" --out "${iconset_path}/icon_512x512.png" >/dev/null
cp "${source_icon}" "${iconset_path}/icon_512x512@2x.png"
iconutil --convert icns --output "${resources_path}/AgentBridge.icns" "${iconset_path}"

codesign_arguments=(--force --sign "${signing_identity}")
if [[ "${signing_identity}" != "-" ]]; then
    codesign_arguments+=(--options runtime --timestamp)
fi

while IFS= read -r -d '' candidate; do
    if file "${candidate}" | grep -q 'Mach-O'; then
        codesign "${codesign_arguments[@]}" "${candidate}"
    fi
done < <(find "${server_path}" -type f -print0)
codesign "${codesign_arguments[@]}" "${contents_path}/MacOS/AgentBridgeMenuBar"
codesign "${codesign_arguments[@]}" "${app_path}"
codesign --verify --deep --strict --verbose=2 "${app_path}"

stage_path="${output_root}/dmg-root"
mkdir -p "${stage_path}"
ditto "${app_path}" "${stage_path}/AgentBridge.app"
ln -s /Applications "${stage_path}/Applications"

dmg_path="${output_root}/AgentBridge-${version}-macos-${artifact_architecture}.dmg"
hdiutil create \
    -volname AgentBridge \
    -srcfolder "${stage_path}" \
    -format UDZO \
    -ov \
    "${dmg_path}" >/dev/null

shasum -a 256 "${dmg_path}" > "${dmg_path}.sha256"

echo "Application: ${app_path}"
echo "Disk image:  ${dmg_path}"
