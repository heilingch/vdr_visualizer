"""
VDR Visualizer - Main Application Window
"""
import sys
import os
from typing import List, Dict
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QLabel, QPushButton, QFileDialog, QDockWidget,
    QTreeWidget, QTreeWidgetItem, QCheckBox, QSpinBox, QMessageBox,
    QGroupBox, QSplitter, QStatusBar, QDoubleSpinBox
)
from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QFont, QAction, QActionGroup
import pyqtgraph as pg

from data_model import VDRDataModel
from plot_widget import PlotCanvas
from vdr_parser import VARIABLE_CATEGORIES, get_category
from theme import get_theme, THEMES


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VDR Visualizer  —  OpenCPN Voyage Data Recorder")
        self.resize(1400, 900)

        self.model = VDRDataModel()
        self.current_files: List[str] = []

        self.settings = QSettings("VDRVisualizer", "OpenCPN")
        self.current_theme_name = self.settings.value("theme", "Dark")
        self.theme = get_theme(self.current_theme_name)

        self.splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self.splitter)

        self._build_menu()
        self._build_config_panel()
        self._build_status_bar()
        self._apply_style()

        # Central canvas
        self.canvas = PlotCanvas()
        self.canvas.set_theme(self.theme)
        
        self.splitter.addWidget(self.config_panel)
        self.splitter.addWidget(self.canvas)
        self.splitter.setSizes([320, 1080])

        # Setup collapsible handle over the splitter
        self.splitter.setHandleWidth(14)
        handle = self.splitter.handle(1)
        # Handle layout to center the button vertically
        h_layout = QVBoxLayout(handle)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setAlignment(Qt.AlignCenter)
        
        self.btn_collapse = QPushButton("◀")
        self.btn_collapse.setObjectName("CollapseBtn")
        self.btn_collapse.setFixedSize(14, 40)
        self.btn_collapse.setCursor(Qt.PointingHandCursor)
        self.btn_collapse.clicked.connect(self._toggle_config_panel)
        h_layout.addWidget(self.btn_collapse)

        # Auto-refresh timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.reload_data)

        # Per-plot variable selections  {plot_index: [var_names]}
        self.plot_variables: Dict[int, List[str]] = {}
        # Per-plot orientations {plot_index: 'horizontal' | 'vertical'}
        self.plot_orientations: Dict[int, str] = {}
        # Per-plot newest top tracking {plot_index: bool}
        self.plot_newest_top: Dict[int, bool] = {}

        self.update_grid()

    # ── Menu Bar ──────────────────────────────────────────────
    def _build_menu(self):
        menu = self.menuBar()

        file_menu = menu.addMenu("&File")
        act_open = QAction("&Open VDR File(s)…", self)
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self.load_files_dialog)
        file_menu.addAction(act_open)

        theme_menu = file_menu.addMenu("&Theme")
        self.theme_group = QActionGroup(self)
        for t_name in THEMES:
            act = QAction(t_name, self, checkable=True)
            if t_name == self.current_theme_name:
                act.setChecked(True)
            act.triggered.connect(lambda checked, name=t_name: self.change_theme(name))
            self.theme_group.addAction(act)
            theme_menu.addAction(act)

        file_menu.addSeparator()

        act_quit = QAction("&Quit", self)
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

    # ── Status Bar ────────────────────────────────────────────
    def _build_status_bar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready – load a VDR file to begin.")

    # ── Configuration Panel ───────────────────────────────────
    def _build_config_panel(self):
        self.config_panel = QWidget()
        self.config_panel.setMinimumWidth(280)
        
        main_vl = QVBoxLayout(self.config_panel)
        main_vl.setContentsMargins(0, 0, 0, 0)
        main_vl.setSpacing(0)
        
        title = QLabel("Configuration")
        title.setObjectName("ConfigTitle")
        main_vl.addWidget(title)
        
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(6)

        # ── File Section ──
        grp_file = QGroupBox("File")
        fl = QVBoxLayout(grp_file)

        btn_load = QPushButton("📂  Load VDR File(s)")
        btn_load.clicked.connect(self.load_files_dialog)
        fl.addWidget(btn_load)

        self.lbl_files = QLabel("No files loaded.")
        self.lbl_files.setWordWrap(True)
        self.lbl_files.setStyleSheet("color: #8899aa; font-size: 11px;")
        fl.addWidget(self.lbl_files)

        # Auto-refresh
        rl = QHBoxLayout()
        self.chk_autorefresh = QCheckBox("Auto-Refresh")
        self.chk_autorefresh.stateChanged.connect(self._toggle_autorefresh)
        rl.addWidget(self.chk_autorefresh)

        self.spin_refresh = QSpinBox()
        self.spin_refresh.setRange(1, 300)
        self.spin_refresh.setValue(10)
        self.spin_refresh.setSuffix(" s")
        self.spin_refresh.valueChanged.connect(self._on_refresh_interval_changed)
        rl.addWidget(self.spin_refresh)
        fl.addLayout(rl)
        layout.addWidget(grp_file)

        # ── Layout Section ──
        grp_layout = QGroupBox("Plot Layout")
        ll = QVBoxLayout(grp_layout)

        gl = QHBoxLayout()
        gl.addWidget(QLabel("Rows:"))
        self.spin_rows = QSpinBox()
        self.spin_rows.setRange(1, 4)
        self.spin_rows.setValue(1)
        self.spin_rows.valueChanged.connect(self.update_grid)
        gl.addWidget(self.spin_rows)

        gl.addWidget(QLabel("Cols:"))
        self.spin_cols = QSpinBox()
        self.spin_cols.setRange(1, 4)
        self.spin_cols.setValue(1)
        self.spin_cols.valueChanged.connect(self.update_grid)
        gl.addWidget(self.spin_cols)
        ll.addLayout(gl)
        layout.addWidget(grp_layout)

        # ── Variables Section ──
        grp_vars = QGroupBox("Variable Assignment")
        vl = QVBoxLayout(grp_vars)

        vl.addWidget(QLabel("Target Plot:"))
        self.plot_selector = QComboBox()
        self.plot_selector.currentIndexChanged.connect(self._on_plot_selector_changed)
        vl.addWidget(self.plot_selector)
        
        self.chk_vertical = QCheckBox("Vertical Plot (Time on Y-Axis)")
        self.chk_vertical.stateChanged.connect(self._on_vertical_changed)
        vl.addWidget(self.chk_vertical)

        self.chk_newest_top = QCheckBox("↳ Newest Data on Top")
        self.chk_newest_top.stateChanged.connect(self._on_vertical_changed)
        self.chk_newest_top.setStyleSheet("margin-left: 15px;")
        vl.addWidget(self.chk_newest_top)

        vl.addWidget(QLabel("Select variables (by category):"))

        self.var_tree = QTreeWidget()
        self.var_tree.setHeaderLabels(["Variable"])
        self.var_tree.setRootIsDecorated(True)
        self.var_tree.setIndentation(18)
        self.var_tree.itemChanged.connect(self._on_var_tree_changed)
        vl.addWidget(self.var_tree)

        layout.addWidget(grp_vars)

        # ── Filters Section ──
        grp_filter = QGroupBox("Data Filters")
        flt = QVBoxLayout(grp_filter)

        flt.addWidget(QLabel("Downsample:"))
        self.combo_downsample = QComboBox()
        self.combo_downsample.addItems(
            ["None", "1s", "2s", "5s", "10s", "30s", "1min", "5min", "10min"]
        )
        self.combo_downsample.currentTextChanged.connect(self.update_all_plots)
        flt.addWidget(self.combo_downsample)

        flt.addWidget(QLabel("Moving Average:"))
        self.combo_ma = QComboBox()
        self.combo_ma.addItems(["None"] + [f"{2**i} points" for i in range(1, 10)])
        self.combo_ma.currentTextChanged.connect(self.update_all_plots)
        flt.addWidget(self.combo_ma)

        flt.addWidget(QLabel("Time range (last N hours, 0 = all):"))
        self.spin_hours = QDoubleSpinBox()
        self.spin_hours.setRange(0, 720)
        self.spin_hours.setDecimals(1)
        self.spin_hours.setSingleStep(0.5)
        self.spin_hours.setValue(0)
        self.spin_hours.setSpecialValueText("All data")
        self.spin_hours.valueChanged.connect(self.update_all_plots)
        flt.addWidget(self.spin_hours)

        layout.addWidget(grp_filter)

        layout.addStretch()
        
        main_vl.addWidget(scroll_content)

    def _toggle_config_panel(self):
        sizes = self.splitter.sizes()
        if sizes[0] > 0:
            self._last_config_width = sizes[0]
            # Must drop minimum width to 0 to allow compression
            self.config_panel.setMinimumWidth(0)
            self.splitter.setSizes([0, sizes[0] + sizes[1]])
            self.btn_collapse.setText("▶")
        else:
            restore_w = getattr(self, '_last_config_width', 280)
            self.config_panel.setMinimumWidth(280)
            self.splitter.setSizes([restore_w, sizes[1] - restore_w])
            self.btn_collapse.setText("◀")

    # ── Styling — Dynamic Theme ──────────────────────────────
    def _apply_style(self):
        c_bg_app = self.theme.bg_app
        c_bg_plot = self.theme.bg_plot
        c_fg_text = self.theme.fg_text
        c_fg_dim = self.theme.fg_dim
        # Pick primary color from the theme's curve colors, or fallback to a vibrant option
        c_accent = self.theme.curves[0] if self.theme.curves else "#00D4FF"

        # Tweak some specific borders slightly lighter than backgrounds for contrast
        # Since we just have raw hexes, we will use fg_dim or bg_plot for borders
        
        self.setStyleSheet(f"""
            * {{ color: {c_fg_text}; }}
            QMainWindow {{ background: {c_bg_app}; }}
            QSplitter::handle {{
                background: {c_bg_app};
            }}
            QPushButton#CollapseBtn {{
                background: {c_bg_plot};
                color: {c_fg_text};
                border: 1px solid {c_fg_dim};
                border-radius: 3px;
                font-weight: bold;
                font-size: 10px;
                padding: 0px;
            }}
            QPushButton#CollapseBtn:hover {{
                background: {c_fg_dim};
                color: {c_accent};
            }}
            QLabel#ConfigTitle {{
                background: {c_bg_plot};
                color: {c_fg_text};
                font-weight: bold;
                padding: 6px;
                font-size: 13px;
            }}
            QWidget {{ background: {c_bg_app}; }}
            QGroupBox {{
                font-weight: bold;
                color: {c_accent};
                border: 1px solid {c_fg_dim};
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 16px;
                background: {c_bg_plot};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                color: {c_accent};
            }}
            QPushButton {{
                padding: 6px 14px;
                border: 1px solid {c_fg_dim};
                border-radius: 4px;
                background: {c_bg_plot};
                color: {c_fg_text};
                font-weight: bold;
            }}
            QPushButton:hover {{
                border-color: {c_accent};
            }}
            QPushButton:pressed {{ background: {c_bg_app}; }}
            QLabel {{ color: {c_fg_text}; background: transparent; }}
            QComboBox {{
                background: {c_bg_plot};
                border: 1px solid {c_fg_dim};
                border-radius: 3px;
                padding: 4px 8px;
                color: {c_fg_text};
            }}
            QComboBox::drop-down {{
                border: none;
                background: {c_bg_plot};
            }}
            QComboBox QAbstractItemView {{
                background: {c_bg_plot};
                color: {c_fg_text};
                selection-background-color: {c_fg_dim};
            }}
            QSpinBox, QDoubleSpinBox {{
                background: {c_bg_plot};
                border: 1px solid {c_fg_dim};
                border-radius: 3px;
                padding: 3px 6px;
                color: {c_fg_text};
            }}
            QCheckBox {{ color: {c_fg_text}; background: transparent; }}
            QCheckBox::indicator {{
                border: 1px solid {c_fg_dim};
                background: {c_bg_plot};
                width: 14px; height: 14px;
            }}
            QCheckBox::indicator:checked {{
                background: {c_accent};
                border-color: {c_accent};
            }}
            QTreeWidget {{
                font-size: 12px;
                background: {c_bg_plot};
                border: 1px solid {c_fg_dim};
                color: {c_fg_text};
                alternate-background-color: {c_bg_app};
            }}
            QTreeWidget::item {{ padding: 2px 0; }}
            QTreeWidget::item:selected {{
                background: {c_bg_plot};
                color: {c_accent};
            }}
            QTreeWidget::indicator {{
                border: 1px solid {c_fg_dim};
                background: {c_bg_plot};
            }}
            QTreeWidget::indicator:checked {{
                background: {c_accent};
                border-color: {c_accent};
            }}
            QHeaderView::section {{
                background: {c_bg_plot};
                color: {c_fg_text};
                border: none;
                padding: 4px;
            }}
            QMenuBar {{
                background: {c_bg_plot};
                color: {c_fg_text};
            }}
            QMenuBar::item:selected {{ background: {c_fg_dim}; }}
            QMenu {{
                background: {c_bg_plot};
                color: {c_fg_text};
                border: 1px solid {c_fg_dim};
            }}
            QMenu::item:selected {{ background: {c_bg_app}; }}
            QStatusBar {{
                background: {c_bg_plot};
                color: {c_fg_dim};
            }}
            QScrollBar:vertical {{
                background: {c_bg_app};
                width: 10px;
            }}
            QScrollBar::handle:vertical {{
                background: {c_fg_dim};
                border-radius: 4px;
                min-height: 20px;
            }}
        """)

    def change_theme(self, theme_name: str):
        self.current_theme_name = theme_name
        self.settings.setValue("theme", theme_name)
        self.theme = get_theme(theme_name)
        self._apply_style()
        self.canvas.set_theme(self.theme)
        self.update_all_plots()

    # ── File Loading ──────────────────────────────────────────
    def load_files_dialog(self):
        last_dir = self.settings.value("last_dir", "")
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select VDR Files", last_dir,
            "VDR Files (*.vdr *.txt *.csv);;All Files (*)"
        )
        if files:
            self.settings.setValue("last_dir", os.path.dirname(files[0]))
            self.current_files = list(files)
            names = [os.path.basename(f) for f in files]
            self.lbl_files.setText(
                f"{len(files)} file(s): " + ", ".join(names[:3])
                + ("…" if len(names) > 3 else "")
            )
            self.reload_data()

    def reload_data(self):
        if not self.current_files:
            return
        try:
            self.model.load_files(self.current_files)
            self._refresh_var_tree()
            self.update_all_plots()

            n = len(self.model.available_variables)
            rows = len(self.model.raw_data) if self.model.raw_data is not None else 0
            self.status.showMessage(
                f"Loaded {rows:,} data points  •  {n} variables detected"
            )
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))
            self.chk_autorefresh.setChecked(False)

    # ── Variable Tree ─────────────────────────────────────────
    def _refresh_var_tree(self):
        """Rebuild the category tree from available variables."""
        self.var_tree.blockSignals(True)
        self.var_tree.clear()

        cats = self.model.available_categories
        # Sort categories: known ones first, then Other
        known_order = list(VARIABLE_CATEGORIES.keys())
        sorted_cats = sorted(
            cats.keys(),
            key=lambda c: (known_order.index(c) if c in known_order else 999, c)
        )

        for cat in sorted_cats:
            cat_item = QTreeWidgetItem([cat])
            cat_item.setFlags(
                cat_item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsAutoTristate
            )
            cat_item.setCheckState(0, Qt.CheckState.Unchecked)

            for var in sorted(cats[cat]):
                child = QTreeWidgetItem([var])
                child.setFlags(
                    child.flags() | Qt.ItemFlag.ItemIsUserCheckable
                )
                child.setCheckState(0, Qt.CheckState.Unchecked)
                cat_item.addChild(child)

            self.var_tree.addTopLevelItem(cat_item)

        self.var_tree.expandAll()
        self.var_tree.blockSignals(False)

        # Re-apply existing selections for the current plot
        self._on_plot_selector_changed()

    def _get_checked_vars(self) -> List[str]:
        """Return list of checked variable names from the tree."""
        checked = []
        for i in range(self.var_tree.topLevelItemCount()):
            cat_item = self.var_tree.topLevelItem(i)
            for j in range(cat_item.childCount()):
                child = cat_item.child(j)
                if child.checkState(0) == Qt.CheckState.Checked:
                    checked.append(child.text(0))
        return checked

    def _set_checked_vars(self, var_names: List[str]):
        """Check the given variables in the tree (uncheck everything else)."""
        self.var_tree.blockSignals(True)
        var_set = set(var_names)
        for i in range(self.var_tree.topLevelItemCount()):
            cat_item = self.var_tree.topLevelItem(i)
            for j in range(cat_item.childCount()):
                child = cat_item.child(j)
                state = (
                    Qt.CheckState.Checked
                    if child.text(0) in var_set
                    else Qt.CheckState.Unchecked
                )
                child.setCheckState(0, state)
        self.var_tree.blockSignals(False)

    def _on_var_tree_changed(self, item, column):
        """User toggled a variable checkbox → store and replot."""
        idx = self.plot_selector.currentIndex()
        if idx < 0:
            return
        self.plot_variables[idx] = self._get_checked_vars()
        self.update_plot(idx)

    # ── Plot selector ─────────────────────────────────────────
    def _on_plot_selector_changed(self):
        idx = self.plot_selector.currentIndex()
        if idx < 0:
            return
            
        self.chk_vertical.blockSignals(True)
        self.chk_newest_top.blockSignals(True)
        
        is_vert = (self.plot_orientations.get(idx, 'horizontal') == 'vertical')
        is_top = self.plot_newest_top.get(idx, False)
        
        self.chk_vertical.setChecked(is_vert)
        self.chk_newest_top.setChecked(is_top)
        self.chk_newest_top.setEnabled(is_vert)
        
        self.chk_vertical.blockSignals(False)
        self.chk_newest_top.blockSignals(False)
        
        vars_for = self.plot_variables.get(idx, [])
        self._set_checked_vars(vars_for)

    def _on_vertical_changed(self, state: int):
        idx = self.plot_selector.currentIndex()
        if idx < 0:
            return
            
        is_vert = self.chk_vertical.isChecked()
        is_top = self.chk_newest_top.isChecked()
        
        self.chk_newest_top.setEnabled(is_vert)
        orientation = 'vertical' if is_vert else 'horizontal'
        
        changed = False
        if self.plot_orientations.get(idx, 'horizontal') != orientation:
            self.plot_orientations[idx] = orientation
            changed = True
            
        if self.plot_newest_top.get(idx, False) != is_top:
            self.plot_newest_top[idx] = is_top
            changed = True
            
        if changed:
            self.update_plot(idx)

    # ── Auto-refresh ──────────────────────────────────────────
    def _toggle_autorefresh(self, state: int):
        # stateChanged emits an integer (0 = Unchecked, 2 = Checked)
        if state == 2:  # Qt.CheckState.Checked.value
            ms = self.spin_refresh.value() * 1000
            self.refresh_timer.start(ms)
            self.status.showMessage(
                f"Auto-refresh enabled ({self.spin_refresh.value()}s)"
            )
        else:
            self.refresh_timer.stop()
            self.status.showMessage("Auto-refresh disabled")
            
    def _on_refresh_interval_changed(self, val: int):
        if self.refresh_timer.isActive():
            self.refresh_timer.setInterval(val * 1000)
            self.status.showMessage(f"Auto-refresh updated ({val}s)")

    # ── Grid / plot management ────────────────────────────────
    def update_grid(self):
        r = self.spin_rows.value()
        c = self.spin_cols.value()
        self.canvas.set_grid_layout(r, c)

        self.plot_selector.blockSignals(True)
        self.plot_selector.clear()
        for i in range(r * c):
            self.plot_selector.addItem(f"Plot {i + 1}")
        self.plot_selector.blockSignals(False)

        self.update_all_plots()

    def update_plot(self, plot_idx: int):
        if plot_idx >= len(self.canvas.plots):
            return

        orientation = self.plot_orientations.get(plot_idx, 'horizontal')
        is_top = self.plot_newest_top.get(plot_idx, False)
        # Invert Y is True by default for vertical plots (newest on bottom). 
        # If user wants newest on top, we don't invert y (so it uses normal Cartesian, top=large epoch=new).
        invert_y = not is_top
        
        pw = self.canvas.update_plot_widget(plot_idx, orientation, invert_y)
        
        varlist = self.plot_variables.get(plot_idx, [])

        if not varlist:
            pw.plot_data(None)
            pw.title_label.setText(f"Plot {plot_idx + 1}  —  (empty)")
            return

        ds = self.combo_downsample.currentText()
        downsample = None if ds == "None" else ds
        hours = self.spin_hours.value()
        
        ma_str = self.combo_ma.currentText()
        ma_window = None if ma_str == "None" else int(ma_str.split(' ')[0])

        df = self.model.get_data(
            varlist,
            time_range_hours=hours if hours > 0 else None,
            downsample_str=downsample,
            moving_average_window=ma_window
        )

        pw.plot_data(df)
        pw.title_label.setText(
            f"Plot {plot_idx + 1}  —  " + ", ".join(varlist)
        )

    def update_all_plots(self):
        for i in range(len(self.canvas.plots)):
            self.update_plot(i)


def main():
    pg.setConfigOption('background', '#16213e')
    pg.setConfigOption('foreground', '#e0e0e0')

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
