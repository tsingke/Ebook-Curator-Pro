# Ebook Curator Pro：电子书冗余清理与图书目录生成工具

该软件是一款电子书整理小工具，可将同一目录下“同名但不同格式”的电子书进行归并处理：如果同名文件中存在 `.epub`，则保留 `.epub`，并将其他格式移动到备份目录；如果没有同名 `.epub`，则所有文件保持不变。

## 一、核心功能

- 图形化选择电子书工作目录；
- 支持一键扫描电子书文件；
- 支持识别同名不同格式电子书；
- `.epub` 优先保留；
- 非 `.epub` 冗余文件默认移动到 `_冗余电子书备份`，不是永久删除；
- 支持生成 `图书目录清单.csv`；
- 目录清单包含序号、书名、文件格式、文件大小、修改时间、文件名、完整路径；
- 支持可选递归扫描子文件夹；
- 界面采用接近 macOS 的轻量卡片式布局。

## 二、支持格式

当前支持：

```text
.epub, .pdf, .mobi, .azw3, .txt, .doc, .docx, .djvu, .fb2
```

如需增加格式，可在 `ebook_cleaner_app.py` 中修改：

```python
BOOK_EXTENSIONS = {
    ".epub", ".pdf", ".mobi", ".azw3", ".txt", ".doc", ".docx", ".djvu", ".fb2"
}
```

## 三、开发运行

在 macOS 终端进入本项目目录后执行：

```bash
chmod +x run_dev.sh
./run_dev.sh
```

脚本会自动创建虚拟环境、安装依赖并启动软件。

## 四、生成 DMG 安装包

在 macOS 终端进入本项目目录后执行：

```bash
chmod +x build_macos_dmg.sh
./build_macos_dmg.sh
```

构建完成后，会生成：

```text
Ebook-Curator-Pro-Installer.dmg
```

双击该 DMG 后，将 `Ebook Curator Pro.app` 拖入 `Applications` 即可安装。

## 五、注意事项

1. DMG 只能在 macOS 上构建，因为需要 Apple 官方的 `hdiutil` 工具。
2. 当前脚本使用临时代码签名，适合个人使用或内部使用。
3. 若要公开分发给其他用户，建议使用 Apple Developer ID 进行正式签名和 notarization，否则其他 Mac 可能会提示“无法验证开发者”。
4. 清理操作默认移动到 `_冗余电子书备份`，不会永久删除，便于恢复。

## 六、处理示例

原始目录：

```text
深度学习.pdf
深度学习.epub
深度学习.mobi
算法导论.pdf
机器学习.azw3
机器学习.epub
```

清理后保留：

```text
深度学习.epub
算法导论.pdf
机器学习.epub
```

移动到 `_冗余电子书备份`：

```text
深度学习.pdf
深度学习.mobi
机器学习.azw3
```

其中 `算法导论.pdf` 因为没有同名 `.epub`，所以不会被处理。
