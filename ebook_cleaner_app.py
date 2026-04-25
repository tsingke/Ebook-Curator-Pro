#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ebook Curator Pro
A macOS-style GUI utility for cleaning duplicate ebooks and generating catalog CSV.

Rule:
- Group files by base filename, ignoring extension.
- If a group contains .epub, keep .epub and move non-.epub files to backup folder.
- If no .epub exists in a group, keep all files unchanged.
"""

from __future__ import annotations

import csv
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QAction, QDesktopServices, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QUrl

BOOK_EXTENSIONS = {
    ".epub", ".pdf", ".mobi", ".azw3", ".txt", ".doc", ".docx", ".djvu", ".fb2"
}

BACKUP_FOLDER_NAME = "_冗余电子书备份"
CATALOG_FILE_NAME = "图书目录清单.csv"


@dataclass
class BookRecord:
    title: str
    suffix: str
    size_mb: float
    modified: str
    filename: str
    path: str


@dataclass
class ScanResult:
    total_files: int
    total_books: int
    duplicate_groups: int
    cleanable_groups: int
    groups: Dict[str, List[Path]]


class Worker(QThread):
    log = Signal(str)
    finished_scan = Signal(object)
    finished_clean = Signal(int)
    finished_catalog = Signal(str, int)
    failed = Signal(str)

    def __init__(self, mode: str, folder: Path, recursive: bool = False, groups=None):
        super().__init__()
        self.mode = mode
        self.folder = folder
        self.recursive = recursive
        self.groups = groups or {}

    def run(self):
        try:
            if self.mode == "scan":
                self._scan()
            elif self.mode == "clean":
                self._clean()
            elif self.mode == "catalog":
                self._catalog()
        except Exception as exc:
            self.failed.emit(str(exc))

    def _iter_files(self):
        if self.recursive:
            yield from (p for p in self.folder.rglob("*") if p.is_file())
        else:
            yield from (p for p in self.folder.iterdir() if p.is_file())

    def _scan(self):
        groups: Dict[str, List[Path]] = {}
        total_files = 0
        self.log.emit("开始扫描电子书文件……")

        for file in self._iter_files():
            if file.suffix.lower() in BOOK_EXTENSIONS:
                groups.setdefault(file.stem.strip(), []).append(file)
                total_files += 1

        duplicate_groups = 0
        cleanable_groups = 0

        for title, files in sorted(groups.items(), key=lambda item: item[0].lower()):
            if len(files) > 1:
                duplicate_groups += 1
                suffixes = ", ".join(sorted({f.suffix.lower() for f in files}))
                has_epub = any(f.suffix.lower() == ".epub" for f in files)
                if has_epub:
                    cleanable_groups += 1
                    self.log.emit(f"可清理：{title}    格式：{suffixes}")
                else:
                    self.log.emit(f"保留：{title}    格式：{suffixes}，未发现 .epub")

        result = ScanResult(
            total_files=total_files,
            total_books=len(groups),
            duplicate_groups=duplicate_groups,
            cleanable_groups=cleanable_groups,
            groups=groups,
        )
        self.log.emit(f"扫描完成：{total_files} 个电子书文件，{len(groups)} 个图书条目。")
        self.finished_scan.emit(result)

    def _clean(self):
        if not self.groups:
            self.log.emit("未发现扫描结果，开始自动扫描……")
            groups: Dict[str, List[Path]] = {}
            for file in self._iter_files():
                if file.suffix.lower() in BOOK_EXTENSIONS:
                    groups.setdefault(file.stem.strip(), []).append(file)
            self.groups = groups

        backup_folder = self.folder / BACKUP_FOLDER_NAME
        backup_folder.mkdir(exist_ok=True)
        moved_count = 0
        self.log.emit(f"备份目录：{backup_folder}")
        self.log.emit("开始移动冗余电子书……")

        for title, files in sorted(self.groups.items(), key=lambda item: item[0].lower()):
            has_epub = any(f.suffix.lower() == ".epub" for f in files)
            if not has_epub:
                continue
            for file in files:
                if file.suffix.lower() == ".epub":
                    continue
                if not file.exists():
                    continue
                # Do not move files already in backup directory during recursive scans.
                if BACKUP_FOLDER_NAME in file.parts:
                    continue
                target = backup_folder / file.name
                if target.exists():
                    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    target = backup_folder / f"{file.stem}_{stamp}{file.suffix}"
                shutil.move(str(file), str(target))
                moved_count += 1
                self.log.emit(f"已移动：{file.name}  →  {target.name}")

        self.log.emit(f"清理完成，共移动冗余文件 {moved_count} 个。")
        self.finished_clean.emit(moved_count)

    def _catalog(self):
        records: List[BookRecord] = []
        self.log.emit("开始生成图书目录……")

        for file in self._iter_files():
            if BACKUP_FOLDER_NAME in file.parts:
                continue
            if file.suffix.lower() in BOOK_EXTENSIONS:
                stat = file.stat()
                records.append(
                    BookRecord(
                        title=file.stem,
                        suffix=file.suffix.lower(),
                        size_mb=round(stat.st_size / 1024 / 1024, 2),
                        modified=datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        filename=file.name,
                        path=str(file),
                    )
                )

        records.sort(key=lambda r: (r.title.lower(), r.suffix.lower(), r.filename.lower()))
        catalog_path = self.folder / CATALOG_FILE_NAME

        with open(catalog_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["序号", "书名", "文件格式", "文件大小MB", "修改时间", "文件名", "完整路径"])
            for idx, record in enumerate(records, start=1):
                writer.writerow([
                    idx,
                    record.title,
                    record.suffix,
                    record.size_mb,
                    record.modified,
                    record.filename,
                    record.path,
                ])

        self.log.emit(f"图书目录生成成功：{catalog_path}")
        self.finished_catalog.emit(str(catalog_path), len(records))


class StatCard(QFrame):
    def __init__(self, title: str, value: str = "0"):
        super().__init__()
        self.setObjectName("StatCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("CardValue")
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: int | str):
        self.value_label.setText(str(value))


class EbookCleanerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ebook Curator Pro")
        self.resize(1120, 760)
        self.folder: Path | None = None
        self.scan_result: ScanResult | None = None
        self.worker: Worker | None = None
        self._setup_ui()
        self._setup_menu()
        self._apply_style()

    def _setup_menu(self):
        open_action = QAction("选择目录", self)
        open_action.triggered.connect(self.choose_folder)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.close)
        menu = self.menuBar().addMenu("文件")
        menu.addAction(open_action)
        menu.addSeparator()
        menu.addAction(quit_action)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(250)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(24, 28, 24, 24)
        side_layout.setSpacing(14)

        app_title = QLabel("Ebook\nCurator Pro")
        app_title.setObjectName("AppTitle")
        app_title.setWordWrap(True)
        subtitle = QLabel("同名电子书去冗余 · EPUB 优先保留 · 图书目录生成")
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)

        self.btn_choose = QPushButton("选择工作目录")
        self.btn_choose.setObjectName("PrimaryButton")
        self.btn_choose.clicked.connect(self.choose_folder)

        self.btn_scan = QPushButton("扫描电子书")
        self.btn_scan.clicked.connect(self.scan_books)

        self.btn_clean = QPushButton("一键清理冗余")
        self.btn_clean.clicked.connect(self.clean_books)

        self.btn_catalog = QPushButton("生成图书目录")
        self.btn_catalog.clicked.connect(self.generate_catalog)

        self.recursive_box = QCheckBox("扫描子文件夹")
        self.recursive_box.setToolTip("开启后会递归扫描当前目录下的子文件夹。")

        side_layout.addWidget(app_title)
        side_layout.addWidget(subtitle)
        side_layout.addSpacing(18)
        side_layout.addWidget(self.btn_choose)
        side_layout.addWidget(self.btn_scan)
        side_layout.addWidget(self.btn_clean)
        side_layout.addWidget(self.btn_catalog)
        side_layout.addWidget(self.recursive_box)
        side_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        version = QLabel("v1.0 · macOS DMG Build Ready")
        version.setObjectName("Version")
        side_layout.addWidget(version)

        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(18)

        header = QVBoxLayout()
        label = QLabel("电子书整理工作台")
        label.setObjectName("MainTitle")
        desc = QLabel("选择目录后，可扫描、清理同名冗余格式，并生成排序后的图书目录 CSV。")
        desc.setObjectName("MainDesc")
        header.addWidget(label)
        header.addWidget(desc)

        path_bar = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("尚未选择工作目录")
        self.path_edit.setReadOnly(True)
        open_folder_btn = QPushButton("在 Finder 中打开")
        open_folder_btn.clicked.connect(self.open_folder)
        path_bar.addWidget(self.path_edit)
        path_bar.addWidget(open_folder_btn)

        cards = QGridLayout()
        cards.setHorizontalSpacing(14)
        self.card_files = StatCard("电子书文件")
        self.card_books = StatCard("图书条目")
        self.card_duplicates = StatCard("同名图书组")
        self.card_cleanable = StatCard("可清理组")
        cards.addWidget(self.card_files, 0, 0)
        cards.addWidget(self.card_books, 0, 1)
        cards.addWidget(self.card_duplicates, 0, 2)
        cards.addWidget(self.card_cleanable, 0, 3)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["书名", "格式", "数量", "处理建议"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setObjectName("ResultTable")

        log_label = QLabel("运行过程")
        log_label.setObjectName("SectionTitle")
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setObjectName("LogBox")

        main_layout.addLayout(header)
        main_layout.addLayout(path_bar)
        main_layout.addLayout(cards)
        main_layout.addWidget(self.table, stretch=5)
        main_layout.addWidget(log_label)
        main_layout.addWidget(self.log_box, stretch=3)

        outer.addWidget(sidebar)
        outer.addWidget(main)

    def _apply_style(self):
        QApplication.setFont(QFont("PingFang SC", 12))
        self.setStyleSheet("""
            QMainWindow { background: #F5F5F7; }
            QMenuBar { background: #F5F5F7; color: #1D1D1F; }
            #Sidebar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 #FFFFFF, stop:1 #ECEEF3);
                border-right: 1px solid #D9DCE3;
            }
            #AppTitle {
                font-size: 31px;
                font-weight: 800;
                color: #111827;
                line-height: 1.05;
            }
            #Subtitle {
                color: #6B7280;
                font-size: 13px;
                line-height: 1.45;
            }
            #Version { color: #9CA3AF; font-size: 12px; }
            #MainTitle {
                font-size: 28px;
                font-weight: 750;
                color: #111827;
            }
            #MainDesc { color: #6B7280; font-size: 14px; }
            #SectionTitle {
                font-size: 15px;
                font-weight: 700;
                color: #374151;
            }
            QPushButton {
                border: 1px solid #D1D5DB;
                border-radius: 12px;
                padding: 10px 14px;
                color: #111827;
                background: #FFFFFF;
                font-weight: 600;
            }
            QPushButton:hover { background: #F3F4F6; }
            QPushButton:pressed { background: #E5E7EB; }
            #PrimaryButton {
                background: #007AFF;
                color: white;
                border: 1px solid #007AFF;
            }
            #PrimaryButton:hover { background: #0A84FF; }
            QLineEdit {
                background: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 12px;
                padding: 10px 12px;
                color: #1F2937;
            }
            QCheckBox { color: #374151; padding: 8px 2px; }
            #StatCard {
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 18px;
            }
            #CardTitle { color: #6B7280; font-size: 13px; }
            #CardValue { color: #111827; font-size: 30px; font-weight: 800; }
            #ResultTable {
                background: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 14px;
                gridline-color: #EEF0F3;
                selection-background-color: #DCEBFF;
                selection-color: #111827;
            }
            QHeaderView::section {
                background: #F9FAFB;
                color: #4B5563;
                border: none;
                border-bottom: 1px solid #E5E7EB;
                padding: 8px;
                font-weight: 700;
            }
            #LogBox {
                background: #111827;
                color: #E5E7EB;
                border-radius: 16px;
                border: 1px solid #1F2937;
                padding: 12px;
                font-family: Menlo, Monaco, Consolas, monospace;
                font-size: 12px;
            }
        """)

    def log(self, text: str):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.append(f"[{stamp}] {text}")

    def choose_folder(self):
        selected = QFileDialog.getExistingDirectory(self, "请选择电子书工作目录")
        if selected:
            self.folder = Path(selected)
            self.path_edit.setText(str(self.folder))
            self.log(f"已选择工作目录：{self.folder}")
            self.scan_result = None
            self.table.setRowCount(0)
            self._set_cards(0, 0, 0, 0)

    def open_folder(self):
        if not self.folder:
            QMessageBox.information(self, "提示", "请先选择工作目录。")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.folder)))

    def _ensure_folder(self) -> bool:
        if not self.folder:
            QMessageBox.warning(self, "提示", "请先选择工作目录。")
            return False
        if not self.folder.exists() or not self.folder.is_dir():
            QMessageBox.critical(self, "错误", "当前工作目录不存在或不是文件夹。")
            return False
        return True

    def _set_busy(self, busy: bool):
        for btn in [self.btn_choose, self.btn_scan, self.btn_clean, self.btn_catalog]:
            btn.setEnabled(not busy)

    def _set_cards(self, files, books, duplicates, cleanable):
        self.card_files.set_value(files)
        self.card_books.set_value(books)
        self.card_duplicates.set_value(duplicates)
        self.card_cleanable.set_value(cleanable)

    def scan_books(self):
        if not self._ensure_folder():
            return
        self._set_busy(True)
        self.log("—— 扫描任务启动 ——")
        self.worker = Worker("scan", self.folder, self.recursive_box.isChecked())
        self.worker.log.connect(self.log)
        self.worker.finished_scan.connect(self._on_scan_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(lambda: self._set_busy(False))
        self.worker.start()

    def _on_scan_finished(self, result: ScanResult):
        self.scan_result = result
        self._set_cards(result.total_files, result.total_books, result.duplicate_groups, result.cleanable_groups)
        self._populate_table(result.groups)

    def _populate_table(self, groups: Dict[str, List[Path]]):
        visible = []
        for title, files in sorted(groups.items(), key=lambda item: item[0].lower()):
            if len(files) > 1:
                suffixes = ", ".join(sorted({f.suffix.lower() for f in files}))
                has_epub = any(f.suffix.lower() == ".epub" for f in files)
                advice = "保留 EPUB，移动其他格式" if has_epub else "未发现 EPUB，全部保留"
                visible.append((title, suffixes, len(files), advice))
        self.table.setRowCount(len(visible))
        for row, (title, suffixes, count, advice) in enumerate(visible):
            for col, value in enumerate([title, suffixes, str(count), advice]):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                self.table.setItem(row, col, item)

    def clean_books(self):
        if not self._ensure_folder():
            return
        reply = QMessageBox.question(
            self,
            "确认清理",
            "将把同名图书中的非 EPUB 文件移动到 _冗余电子书备份 文件夹。\n\n"
            "该操作不是永久删除，可以从备份目录恢复。是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            self.log("用户取消清理任务。")
            return
        self._set_busy(True)
        groups = self.scan_result.groups if self.scan_result else {}
        self.log("—— 清理任务启动 ——")
        self.worker = Worker("clean", self.folder, self.recursive_box.isChecked(), groups=groups)
        self.worker.log.connect(self.log)
        self.worker.finished_clean.connect(self._on_clean_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(lambda: self._set_busy(False))
        self.worker.start()

    def _on_clean_finished(self, count: int):
        QMessageBox.information(self, "清理完成", f"共移动冗余文件 {count} 个。")
        self.scan_books()

    def generate_catalog(self):
        if not self._ensure_folder():
            return
        self._set_busy(True)
        self.log("—— 目录生成任务启动 ——")
        self.worker = Worker("catalog", self.folder, self.recursive_box.isChecked())
        self.worker.log.connect(self.log)
        self.worker.finished_catalog.connect(self._on_catalog_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(lambda: self._set_busy(False))
        self.worker.start()

    def _on_catalog_finished(self, path: str, count: int):
        QMessageBox.information(self, "生成成功", f"图书目录已生成。\n\n记录数量：{count}\n路径：{path}")

    def _on_failed(self, message: str):
        self.log(f"错误：{message}")
        QMessageBox.critical(self, "运行错误", message)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Ebook Curator Pro")
    app.setOrganizationName("Tsingke Tools")
    window = EbookCleanerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
