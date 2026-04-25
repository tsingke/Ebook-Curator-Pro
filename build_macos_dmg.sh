#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Ebook Curator Pro"
ENTRY="ebook_cleaner_app.py"
DMG_NAME="Ebook-Curator-Pro-Installer.dmg"
VENV_DIR=".venv"
ICONSET_DIR="assets/AppIcon.iconset"
ICNS_FILE="assets/AppIcon.icns"
PNG_FILE="assets/icon_1024.png"

if [[ "$(uname)" != "Darwin" ]]; then
  echo "错误：DMG 只能在 macOS 上构建，因为需要 Apple hdiutil。"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "错误：未找到 python3。请先安装 Python 3。"
  exit 1
fi

echo "==> 创建 Python 虚拟环境"
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

echo "==> 安装依赖"
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "==> 生成 macOS 图标"
rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"

if [[ -f "$PNG_FILE" ]]; then
  sips -z 16 16     "$PNG_FILE" --out "$ICONSET_DIR/icon_16x16.png" >/dev/null
  sips -z 32 32     "$PNG_FILE" --out "$ICONSET_DIR/icon_16x16@2x.png" >/dev/null
  sips -z 32 32     "$PNG_FILE" --out "$ICONSET_DIR/icon_32x32.png" >/dev/null
  sips -z 64 64     "$PNG_FILE" --out "$ICONSET_DIR/icon_32x32@2x.png" >/dev/null
  sips -z 128 128   "$PNG_FILE" --out "$ICONSET_DIR/icon_128x128.png" >/dev/null
  sips -z 256 256   "$PNG_FILE" --out "$ICONSET_DIR/icon_128x128@2x.png" >/dev/null
  sips -z 256 256   "$PNG_FILE" --out "$ICONSET_DIR/icon_256x256.png" >/dev/null
  sips -z 512 512   "$PNG_FILE" --out "$ICONSET_DIR/icon_256x256@2x.png" >/dev/null
  sips -z 512 512   "$PNG_FILE" --out "$ICONSET_DIR/icon_512x512.png" >/dev/null
  sips -z 1024 1024 "$PNG_FILE" --out "$ICONSET_DIR/icon_512x512@2x.png" >/dev/null
  iconutil -c icns "$ICONSET_DIR" -o "$ICNS_FILE"
else
  echo "警告：未发现 $PNG_FILE，将使用默认应用图标。"
fi

echo "==> 清理旧构建文件"
rm -rf build dist "$DMG_NAME" dmg_root

echo "==> 使用 PyInstaller 构建 .app"
if [[ -f "$ICNS_FILE" ]]; then
  pyinstaller --windowed --noconfirm --name "$APP_NAME" --icon "$ICNS_FILE" "$ENTRY"
else
  pyinstaller --windowed --noconfirm --name "$APP_NAME" "$ENTRY"
fi

echo "==> 进行临时代码签名，减少 macOS Gatekeeper 阻拦"
codesign --force --deep --sign - "dist/${APP_NAME}.app" || true

echo "==> 创建 DMG 安装镜像"
mkdir -p dmg_root
cp -R "dist/${APP_NAME}.app" dmg_root/
ln -s /Applications dmg_root/Applications

hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder dmg_root \
  -ov \
  -format UDZO \
  "$DMG_NAME"

rm -rf dmg_root

echo "构建完成：$DMG_NAME"
echo "提示：如果需要分发给其他用户，建议使用 Apple Developer ID 正式签名和 notarization。"
