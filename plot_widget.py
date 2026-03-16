"""
Plot Widget - PySide6/pyqtgraph based plotting components.
Dark sailing theme with interactive crosshair and value readout.
"""
from typing import List, Dict, Optional
import time as _time
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout,
    QHBoxLayout, QLabel, QPushButton
)
from PySide6.QtGui import QFont, QColor
from PySide6.QtCore import Signal, Qt


def _dt_index_to_epoch(idx: pd.DatetimeIndex) -> np.ndarray:
    """Convert a DatetimeIndex to unix epoch seconds (float64).
    Works correctly with any pandas datetime64 resolution (ns, us, ms, s)."""
    raw = idx.view(np.int64)
    reso = idx.dtype  # e.g. datetime64[ms], datetime64[ns]
    reso_str = str(reso)
    if 'ns' in reso_str:
        return raw / 1e9
    elif 'us' in reso_str:
        return raw / 1e6
    elif 'ms' in reso_str:
        return raw / 1e3
    else:  # 's'
        return raw.astype(np.float64)


# ── Unit definitions ──────────────────────────────────────────
VARIABLE_UNITS = {
    'AWA': '°', 'AWS': 'kn', 'TWA': '°', 'TWS': 'kn', 'TWD': '°',
    'SOG': 'kn', 'COG': '°', 'Heading': '°', 'HDG_Mag': '°', 'STW': 'kn',
    'Latitude': '°', 'Longitude': '°',
    'Depth': 'm', 'Depth_Offset': 'm', 'Depth_Max': 'm',
    'Pressure': 'mbar', 'Air_Temp': '°C', 'Water_Temp': '°C',
    'Humidity': '%', 'Dew_Point': '°C',
    'Rudder_Angle': '°', 'Rate_of_Turn': '°/min',
    'Pitch': '°', 'Roll': '°', 'Heave': 'm',
    'GPS_Sats': '', 'HDOP': '', 'PDOP': '', 'VDOP': '', 'GPS_Alt': 'm',
    'VMG': 'kn', 'Leeway': '°',
}

def get_unit(variable_name: str) -> str:
    """Return the unit string for a variable."""
    return VARIABLE_UNITS.get(variable_name, '')


# ── Dark-theme colour palette ────────────────────────────────
# Bright, high-contrast colours that pop on dark backgrounds
PLOT_COLORS = [
    '#00D4FF',  # cyan
    '#FF6B6B',  # coral red
    '#51CF66',  # green
    '#FFD43B',  # yellow
    '#CC5DE8',  # violet
    '#FF922B',  # orange
    '#20C997',  # teal
    '#F06595',  # pink
    '#74C0FC',  # light blue
    '#A9E34B',  # lime
]

# Dark background colours
BG_DARK = '#1a1a2e'
BG_PLOT = '#16213e'
FG_TEXT = '#e0e0e0'
FG_DIM = '#888'
GRID_COLOR = (60, 60, 90, 100)
CROSSHAIR_COLOR = '#aaa'


class TimeAxisItem(pg.AxisItem):
    """Custom axis that converts UNIX timestamps to readable time strings."""
    def tickStrings(self, values, scale, spacing):
        result = []
        for val in values:
            try:
                result.append(_time.strftime("%H:%M:%S", _time.gmtime(val)))
            except (OSError, OverflowError, ValueError):
                result.append("")
        return result


class PlotWidget(QWidget):
    """
    A single interactive plot with crosshair, value readout, and unit display.
    Dark themed for sailing / night use.
    """
    crosshair_moved = Signal(float)  # emits x-position for cross-plot sync

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_DARK};")

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(2, 2, 2, 2)
        self._main_layout.setSpacing(0)

        # Header layout for title and controls
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title label
        self.title_label = QLabel("No data")
        self.title_label.setStyleSheet(
            f"font-weight: bold; padding: 3px 6px; color: {FG_TEXT}; "
            f"background: {BG_DARK}; font-size: 12px;"
        )
        header_layout.addWidget(self.title_label)
        
        # Zoom to Fit buttons
        btn_style = f"background: #0f3460; color: {FG_TEXT}; border: 1px solid #2a4a7f; border-radius: 2px; font-size: 10px;"
        
        self.btn_fit_x = QPushButton("⛶ Fit X")
        self.btn_fit_x.setFixedSize(50, 20)
        self.btn_fit_x.setStyleSheet(btn_style)
        self.btn_fit_x.clicked.connect(lambda: self.pg_widget.enableAutoRange(axis=pg.ViewBox.XAxis))
        header_layout.addWidget(self.btn_fit_x)
        
        self.btn_fit_y = QPushButton("⛶ Fit Y")
        self.btn_fit_y.setFixedSize(50, 20)
        self.btn_fit_y.setStyleSheet(btn_style)
        self.btn_fit_y.clicked.connect(lambda: self.pg_widget.enableAutoRange(axis=pg.ViewBox.YAxis))
        header_layout.addWidget(self.btn_fit_y)

        self.btn_fit = QPushButton("⛶ Fit All")
        self.btn_fit.setFixedSize(55, 20)
        self.btn_fit.setStyleSheet(btn_style)
        self.btn_fit.clicked.connect(self._auto_range)
        header_layout.addWidget(self.btn_fit)
        
        header_layout.addStretch()
        self._main_layout.addLayout(header_layout)

        # pyqtgraph plot with time axis (dark themed)
        self.time_axis = TimeAxisItem(orientation='bottom')
        self.pg_widget = pg.PlotWidget(axisItems={'bottom': self.time_axis})
        self.pg_widget.setBackground(BG_PLOT)
        self.pg_widget.showGrid(x=True, y=True, alpha=0.2)
        self.pg_widget.setMouseEnabled(x=True, y=True)
        self.pg_widget.getPlotItem().setContentsMargins(0, 0, 0, 0)

        # Style axes for dark theme
        for axis_name in ('left', 'bottom'):
            ax = self.pg_widget.getAxis(axis_name)
            ax.setTextPen(pg.mkPen(FG_TEXT))
            ax.setPen(pg.mkPen(FG_DIM))

        # Legend
        self.legend = self.pg_widget.addLegend(
            offset=(10, 10),
            labelTextSize='9pt',
            labelTextColor=FG_TEXT,
            brush=pg.mkBrush(QColor(26, 26, 46, 200)),
            pen=pg.mkPen(FG_DIM),
        )

        # Crosshair lines
        pen_cross = pg.mkPen(CROSSHAIR_COLOR, width=1,
                             style=Qt.PenStyle.DashLine)
        self.vLine = pg.InfiniteLine(angle=90, movable=False, pen=pen_cross)
        self.hLine = pg.InfiniteLine(angle=0, movable=False, pen=pen_cross)
        self.pg_widget.addItem(self.vLine, ignoreBounds=True)
        self.pg_widget.addItem(self.hLine, ignoreBounds=True)
        self.vLine.hide()
        self.hLine.hide()

        self._main_layout.addWidget(self.pg_widget)

        # ── Value readout bar below the plot ──
        self.value_label = QLabel("")
        self.value_label.setStyleSheet(
            f"background: #0f3460; padding: 4px 8px; "
            f"font-family: 'Monospace', 'Consolas', monospace; "
            f"font-size: 11px; color: #00D4FF; "
            f"border-top: 1px solid #2a4a7f; min-height: 18px;"
        )
        self.value_label.setTextFormat(Qt.TextFormat.RichText)
        self._main_layout.addWidget(self.value_label)

        # Mouse tracking — only on THIS plot's scene
        self._proxy = pg.SignalProxy(
            self.pg_widget.scene().sigMouseMoved,
            rateLimit=30, slot=self._on_mouse_moved
        )

        self.curves: Dict[str, pg.PlotDataItem] = {}
        self._df: Optional[pd.DataFrame] = None
        self._x_data: Optional[np.ndarray] = None
        self._is_source = False  # True when this is the plot being moused

    # ── Mouse / crosshair ─────────────────────────────────────
    def _on_mouse_moved(self, evt):
        pos = evt[0]
        if self.pg_widget.sceneBoundingRect().contains(pos):
            mouse_pt = self.pg_widget.plotItem.vb.mapSceneToView(pos)
            x = mouse_pt.x()
            y = mouse_pt.y()
            self.vLine.setPos(x)
            self.hLine.setPos(y)
            self.vLine.show()
            self.hLine.show()
            self._is_source = True
            self._update_value_readout(x)
            self.crosshair_moved.emit(x)
        else:
            self.vLine.hide()
            self.hLine.hide()
            self._is_source = False
            self.value_label.setText("")

    def set_sync_x(self, x_val):
        """Called from other plots to sync crosshair position + values."""
        self.vLine.setPos(x_val)
        self.vLine.show()
        # Don't show hLine on synced plots (it's only meaningful on source)
        self.hLine.hide()
        self._is_source = False
        self._update_value_readout(x_val)

    def _auto_range(self):
        """Reset the plot view to fit all data."""
        self.pg_widget.enableAutoRange(axis=pg.ViewBox.XYAxes)

    def _update_value_readout(self, x_epoch: float):
        """Look up nearest data values at the given unix timestamp and display."""
        if self._df is None or self._df.empty or self._x_data is None:
            self.value_label.setText("")
            return
        try:
            # Find closest index using numpy (avoids pandas InvalidIndexError on duplicates)
            idx = np.abs(self._x_data - x_epoch).argmin()
            
            if idx < 0 or idx >= len(self._df):
                return
            row = self._df.iloc[idx]
            actual_time = self._df.index[idx]

            # Build rich-text readout
            time_str = actual_time.strftime("%H:%M:%S.%f")[:-3]  # ms precision
            parts = [f'<span style="color:#aaa;">⏱ {time_str}</span>']
            for col in self._df.columns:
                v = row[col]
                if pd.notna(v):
                    unit = get_unit(col)
                    color = self._get_curve_color(col)
                    parts.append(
                        f'<span style="color:{color}; font-weight:bold;">'
                        f'{col}</span>: {v:.2f}{unit}'
                    )
            self.value_label.setText("  &nbsp;│&nbsp;  ".join(parts))
        except Exception:
            self.value_label.setText("")

    def _get_curve_color(self, col_name: str) -> str:
        """Return the hex colour used for a given column's curve."""
        cols = list(self.curves.keys())
        try:
            idx = cols.index(col_name)
            return PLOT_COLORS[idx % len(PLOT_COLORS)]
        except ValueError:
            return FG_TEXT

    # ── Plotting ──────────────────────────────────────────────
    def plot_data(self, df):
        """Plot a pandas DataFrame with DatetimeIndex."""
        self.pg_widget.clear()
        self.curves.clear()
        self.legend.clear()

        # Re-add crosshair items after clear
        self.pg_widget.addItem(self.vLine, ignoreBounds=True)
        self.pg_widget.addItem(self.hLine, ignoreBounds=True)

        self._df = df
        if df is None or df.empty:
            self.value_label.setText("")
            self._x_data = None
            return

        self._x_data = _dt_index_to_epoch(df.index)

        # Build Y-axis label with units
        y_labels = []
        for i, col in enumerate(df.columns):
            col_data = df[[col]].dropna()
            if col_data.empty:
                continue

            x = _dt_index_to_epoch(col_data.index)
            y = col_data[col].values
            color = PLOT_COLORS[i % len(PLOT_COLORS)]

            unit = get_unit(col)
            label_str = f"{col} [{unit}]" if unit else col

            curve = self.pg_widget.plot(
                x=x, y=y,
                pen=pg.mkPen(color, width=2),
                name=label_str,
            )
            self.curves[col] = curve
            y_labels.append(label_str)

        # Set Y-axis label showing all plotted variables with units
        if y_labels:
            self.pg_widget.setLabel('left', ' / '.join(y_labels),
                                    color=FG_TEXT)


class PlotCanvas(QWidget):
    """Dynamic grid container for multiple PlotWidgets (1×1 to 4×4)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_DARK};")
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(2, 2, 2, 2)
        self._grid.setSpacing(3)
        self.plots: List[PlotWidget] = []
        self.set_grid_layout(1, 1)

    def set_grid_layout(self, rows: int, cols: int):
        # Disconnect old signals and remove widgets
        for pw in self.plots:
            try:
                pw.crosshair_moved.disconnect()
            except (RuntimeError, TypeError):
                pass

        for i in reversed(range(self._grid.count())):
            w = self._grid.itemAt(i).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        self.plots.clear()

        for r in range(rows):
            for c in range(cols):
                pw = PlotWidget()
                self.plots.append(pw)
                self._grid.addWidget(pw, r, c)

        self._sync_axes()

    def _sync_axes(self):
        """Link X-axes and crosshair positions across all plots."""
        if len(self.plots) > 1:
            base = self.plots[0].pg_widget
            for pw in self.plots[1:]:
                pw.pg_widget.setXLink(base)

        # Cross-plot crosshair sync
        for i, src in enumerate(self.plots):
            for j, dst in enumerate(self.plots):
                if i != j:
                    src.crosshair_moved.connect(dst.set_sync_x)
