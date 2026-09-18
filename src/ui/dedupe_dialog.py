from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.core.dedupe import PREVIEW_CHARS, apply_dedup, find_exact_groups
from src.core.models import ConsolidationFile
from src.ui.strings import tr

KEEP_BOTH = 0
KEEP_FIRST = 1
KEEP_SECOND = 2


class DuplicateReviewDialog(QDialog):
    def __init__(self, files: list[ConsolidationFile], parent=None) -> None:
        super().__init__(parent)
        self.files = list(files)
        self.setWindowTitle(tr("dupes.dlg_title"))
        self.resize(860, 560)

        self._exact_checks: list[tuple[list[int], QCheckBox]] = []
        self._pair_combos: list[tuple[int, int, QComboBox]] = []

        layout = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        scroll.setWidget(body)

        groups = find_exact_groups(self.files)
        result = apply_dedup(self.files, "near")
        if not groups and not result.candidates:
            body_layout.addWidget(QLabel(tr("dupes.none_found")))
        for group in groups:
            names = [self.files[index].name for index in group]
            box = QGroupBox(tr("dupes.exact_group", names=", ".join(names)))
            row = QVBoxLayout(box)
            check = QCheckBox(tr("dupes.keep_first_check", name=names[0]))
            check.setChecked(True)
            row.addWidget(check)
            body_layout.addWidget(box)
            self._exact_checks.append((group, check))
        for pair in result.candidates:
            first = self.files[pair.first]
            second = self.files[pair.second]
            box = QGroupBox(tr("dupes.pair_title", a=first.name, b=second.name, pct=f"{pair.ratio:.0%}"))
            row = QVBoxLayout(box)
            previews = QHBoxLayout()
            for text in (first.text[: PREVIEW_CHARS * 3], second.text[: PREVIEW_CHARS * 3]):
                view = QPlainTextEdit()
                view.setReadOnly(True)
                view.setPlainText(text)
                view.setMaximumHeight(140)
                previews.addWidget(view)
            row.addLayout(previews)
            combo = QComboBox()
            combo.addItem(tr("dupes.keep_both"), KEEP_BOTH)
            combo.addItem(tr("dupes.keep_name", name=first.name), KEEP_FIRST)
            combo.addItem(tr("dupes.keep_name", name=second.name), KEEP_SECOND)
            row.addWidget(combo)
            body_layout.addWidget(box)
            self._pair_combos.append((pair.first, pair.second, combo))

        layout.addWidget(scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("dupes.apply"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("dupes.cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def collect_removals(self) -> list[str]:
        removed: set[int] = set()
        paths: list[str] = []
        for group, check in self._exact_checks:
            if check.isChecked():
                for index in group[1:]:
                    if index not in removed:
                        removed.add(index)
                        paths.append(str(self.files[index].path))
        for first, second, combo in self._pair_combos:
            if first in removed or second in removed:
                continue
            choice = combo.currentData()
            if choice == KEEP_FIRST:
                removed.add(second)
                paths.append(str(self.files[second].path))
            elif choice == KEEP_SECOND:
                removed.add(first)
                paths.append(str(self.files[first].path))
        return paths
