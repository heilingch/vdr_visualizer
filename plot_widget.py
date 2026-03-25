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


from theme import get_theme, Theme

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
    crosshair_moved = Signal(float)  # emits epoch time for cross-plot sync

    def __init__(self, theme: Theme, orientation: str = 'horizontal', invert_y: bool = True, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.orientation = orientation
        self.invert_y = invert_y
        self.setStyleSheet(f"background: {self.theme.bg_app};")

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(2, 2, 2, 2)
        self._main_layout.setSpacing(0)

        # Header layout for title and controls
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title label
        self.title_label = QLabel("No data")
        self.title_label.setStyleSheet(
            f"font-weight: bold; padding: 3px 6px; color: {self.theme.fg_text}; "
            f"background: {self.theme.bg_app}; font-size: 12px;"
        )
        header_layout.addWidget(self.title_label)
        
        # Zoom to Fit buttons
        btn_style = (
            f"background: {self.theme.bg_plot}; color: {self.theme.fg_text}; "
            f"border: 1px solid {self.theme.fg_dim}; border-radius: 2px; font-size: 10px;"
        )
        
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

        # pyqtgraph plot with time axis
        if self.orientation == 'vertical':
            self.time_axis = TimeAxisItem(orientation='left')
            self.pg_widget = pg.PlotWidget(axisItems={'left': self.time_axis})
            self.pg_widget.setBackground(self.theme.bg_plot)
            if self.invert_y:
                self.pg_widget.getPlotItem().invertY(True)
        else:
            self.time_axis = TimeAxisItem(orientation='bottom')
            self.pg_widget = pg.PlotWidget(axisItems={'bottom': self.time_axis})
            self.pg_widget.setBackground(self.theme.bg_plot)
        
        # Grid settings
        self.pg_widget.showGrid(x=True, y=True, alpha=0.2)
        grid_alpha = 1.0 if len(self.theme.grid) == 3 else self.theme.grid[3] / 255.0
        r, g, b = self.theme.grid[:3]
        pen_grid = pg.mkPen(color=(r, g, b), width=1)
        self.pg_widget.getAxis('bottom').setGrid(grid_alpha * 255)
        self.pg_widget.getAxis('left').setGrid(grid_alpha * 255)
        
        self.pg_widget.setMouseEnabled(x=True, y=True)
        self.pg_widget.getPlotItem().setContentsMargins(0, 0, 0, 0)

        # Style axes
        for axis_name in ('left', 'bottom'):
            ax = self.pg_widget.getAxis(axis_name)
            ax.setTextPen(pg.mkPen(self.theme.fg_text))
            ax.setPen(pg.mkPen(self.theme.fg_dim))

        # Legend
        self.legend = self.pg_widget.addLegend(
            offset=(10, 10),
            labelTextSize='9pt',
            labelTextColor=self.theme.fg_text,
            brush=pg.mkBrush(QColor(self.theme.bg_app)),
            pen=pg.mkPen(self.theme.fg_dim),
        )

        # Crosshair lines
        pen_cross = pg.mkPen(self.theme.crosshair, width=1,
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
            f"background: {self.theme.bg_plot}; padding: 4px 8px; "
            f"font-family: 'Monospace', 'Consolas', monospace; "
            f"font-size: 11px; color: {self.theme.fg_text}; "
            f"border-top: 1px solid {self.theme.fg_dim}; min-height: 18px;"
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
            
            epoch_time = y if self.orientation == 'vertical' else x
            self._update_value_readout(epoch_time)
            self.crosshair_moved.emit(epoch_time)
        else:
            self.vLine.hide()
            self.hLine.hide()
            self._is_source = False
            self.value_label.setText("")

    def set_sync_time(self, epoch_time):
        """Called from other plots to sync crosshair position + values using epoch time."""
        if self.orientation == 'vertical':
            self.hLine.setPos(epoch_time)
            self.hLine.show()
            self.vLine.hide()
        else:
            self.vLine.setPos(epoch_time)
            self.vLine.show()
            self.hLine.hide()
            
        self._is_source = False
        self._update_value_readout(epoch_time)

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
            return self.theme.curves[idx % len(self.theme.curves)]
        except ValueError:
            return self.theme.fg_text

    def _update_views(self):
        """Scale the overlaying ViewBox to match the primary PlotItem."""
        if hasattr(self, 'vb2'):
            self.vb2.setGeometry(self.pg_widget.getPlotItem().vb.sceneBoundingRect())
            if self.orientation == 'vertical':
                self.vb2.linkedViewChanged(self.pg_widget.getPlotItem().vb, self.vb2.YAxis)
            else:
                self.vb2.linkedViewChanged(self.pg_widget.getPlotItem().vb, self.vb2.XAxis)

    # ── Plotting ──────────────────────────────────────────────
    def plot_data(self, df):
        """Plot a pandas DataFrame with DatetimeIndex. Uses multiple Y axes if units mismatch."""
        self.pg_widget.clear()
        
        # Clean up any existing second Y-axis
        if hasattr(self, 'vb2'):
            p = self.pg_widget.getPlotItem()
            p.scene().removeItem(self.vb2)
            if self.orientation == 'vertical':
                p.hideAxis('top')
            else:
                p.hideAxis('right')
            del self.vb2
            
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

        # Categorize columns by their unit type
        unit_groups = {}
        for col in df.columns:
            u = get_unit(col)
            unit_groups.setdefault(u, []).append(col)
            
        # Determine primary and secondary units
        primary_unit = None
        secondary_unit = None
        
        sorted_units = sorted(unit_groups.items(), key=lambda x: len(x[1]), reverse=True)
        if sorted_units:
            primary_unit = sorted_units[0][0]
        if len(sorted_units) > 1:
            secondary_unit = sorted_units[1][0]
            # Setup secondary axis for secondary units
            p = self.pg_widget.getPlotItem()
            self.vb2 = pg.ViewBox()
            
            if self.orientation == 'vertical':
                p.showAxis('top')
                p.scene().addItem(self.vb2)
                p.getAxis('top').linkToView(self.vb2)
                self.vb2.setYLink(p)
                ax_sec = p.getAxis('top')
            else:
                p.showAxis('right')
                p.scene().addItem(self.vb2)
                p.getAxis('right').linkToView(self.vb2)
                self.vb2.setXLink(p)
                ax_sec = p.getAxis('right')
            
            # Style secondary axis
            ax_sec.setTextPen(pg.mkPen(self.theme.fg_text))
            ax_sec.setPen(pg.mkPen(self.theme.fg_dim))
            
            p.vb.sigResized.connect(self._update_views)

        y_labels_primary = []
        y_labels_secondary = []
        
        col_idx = 0
        for unit, cols in sorted_units:
            for col in cols:
                col_data = df[[col]].dropna()
                if col_data.empty:
                    col_idx += 1
                    continue

                x = _dt_index_to_epoch(col_data.index)
                y = col_data[col].values
                color = self.theme.curves[col_idx % len(self.theme.curves)]

                label_str = f"{col} [{unit}]" if unit else col
                
                # Swap X and Y for vertical orientation
                plot_x = y if self.orientation == 'vertical' else x
                plot_y = x if self.orientation == 'vertical' else y

                if unit == secondary_unit and hasattr(self, 'vb2'):
                    # Plot to secondary axis
                    curve = pg.PlotDataItem(x=plot_x, y=plot_y, pen=pg.mkPen(color, width=2), name=label_str)
                    self.vb2.addItem(curve)
                    y_labels_secondary.append(label_str)
                else:
                    # Plot to primary axis
                    curve = self.pg_widget.plot(
                        x=plot_x, y=plot_y,
                        pen=pg.mkPen(color, width=2),
                        name=label_str,
                    )
                    y_labels_primary.append(label_str)
                    
                self.curves[col] = curve
                col_idx += 1

        if y_labels_primary:
            axis_name = 'bottom' if self.orientation == 'vertical' else 'left'
            self.pg_widget.setLabel(axis_name, ' / '.join(y_labels_primary), color=self.theme.fg_text)
        if y_labels_secondary:
            axis_name = 'top' if self.orientation == 'vertical' else 'right'
            self.pg_widget.setLabel(axis_name, ' / '.join(y_labels_secondary), color=self.theme.fg_text)
        
        if hasattr(self, 'vb2'):
            self._update_views()


class PlotCanvas(QWidget):
    """Dynamic grid container for multiple PlotWidgets (1×1 to 4×4)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = get_theme("Dark")
        self.setStyleSheet(f"background: {self.theme.bg_app};")
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(2, 2, 2, 2)
        self._grid.setSpacing(3)
        self.plots: List[PlotWidget] = []
        self._rows = 1
        self._cols = 1
        self.set_grid_layout(1, 1)

    def set_theme(self, theme: Theme):
        """Update the theme for the canvas and all child plots."""
        self.theme = theme
        self.setStyleSheet(f"background: {self.theme.bg_app};")
        # Rebuild grid to easily apply new theme colors
        self.set_grid_layout(self._rows, self._cols)

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

        self._rows = rows
        self._cols = cols

        for r in range(rows):
            for c in range(cols):
                pw = PlotWidget(theme=self.theme)
                self.plots.append(pw)
                self._grid.addWidget(pw, r, c)

        self._sync_axes()

    def _sync_axes(self):
        """Link Time axes and crosshair positions across all plots."""
        # We manually link X to X for horizontal and Y to Y for vertical, or mixed.
        # But `setXLink` is limited. Actually crosshair syncing handles values perfectly now!
        # For pan/zoom syncing, we can rely on manual ViewBox linking if needed, but omitted for simplicity
        # if orientations are mixed. We'll leave the sync mostly for crosshairs.

        # Cross-plot crosshair sync
        for i, src in enumerate(self.plots):
            for j, dst in enumerate(self.plots):
                if i != j:
                    src.crosshair_moved.connect(dst.set_sync_time)

    def update_plot_widget(self, idx: int, orientation: str, invert_y: bool = True) -> PlotWidget:
        """Replace a PlotWidget in the grid if its orientation needs changing."""
        old_pw = self.plots[idx]
        if getattr(old_pw, 'orientation', 'horizontal') == orientation and getattr(old_pw, 'invert_y', True) == invert_y:
            return old_pw

        # Recreate the PlotWidget
        r = idx // self._cols
        c = idx % self._cols
        
        new_pw = PlotWidget(theme=self.theme, orientation=orientation, invert_y=invert_y)
        
        # Unlink signals from old
        try:
            old_pw.crosshair_moved.disconnect()
        except Exception:
            pass
            
        self._grid.removeWidget(old_pw)
        old_pw.setParent(None)
        old_pw.deleteLater()
        
        self.plots[idx] = new_pw
        self._grid.addWidget(new_pw, r, c)
        
        # Link up the crosshair syncs again
        self._sync_axes()
        return new_pw
