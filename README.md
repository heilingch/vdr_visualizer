# VDR Visualizer

A specialized, interactive visualization tool built to analyze Voyage Data Recorder (VDR) files from OpenCPN and NMEA 0183 loggers. Designed specifically for sailors, it provides robust time-series plotting of marine sensor data with an interface tuned for onboard nighttime usage.

## Features

- **Multi-Format VDR Support**: Automatically parses both legacy OpenCPN VDR CSV formats and standard NMEA log files (`timestamp, type, id, message`).
- **NMEA 0183 Decoding**: Extracts key navigation data from sentences like `$GPRMC`, `$GPGGA`, `$IIMWV`, `$IIHDG`, `$IIDPT`, and more.
- **Dynamic Grid Layouts**: Reconfigure the plot canvas instantly from a single 1x1 view up to a dense 4x4 matrix.
- **Interactive Data Cursors**: Hover to sync crosshairs across all active plots to correlate metrics (e.g., Wind Speed vs. Boat Speed) at exact timeframes.
- **Dark Sailing Theme**: High-contrast, low-glare dark mode that preserves night vision on deck.
- **Live Auto-Reload**: Actively monitor a growing log file to watch metrics unfold in real time while racing or cruising.
- **Variable Downsampling**: Smooth out high-frequency sensors (like GPS) by downsampling data points to 1s, 10s, or even 10min intervals to reduce visual noise.

## Installation

This application requires Python 3.9+ and uses PySide6 (Qt) for its interface. 

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/vdr_visualizer.git
   cd vdr_visualizer
   ```

2. **Set up a virtual environment (Recommended):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Start the visualizer:
```bash
python main_window.py
```

1. Click **Load VDR File(s)** to open one or more `.csv` or `.vdr` files.
2. Select your desired grid size (e.g., 2 Rows, 1 Column).
3. Use the **Target Plot** dropdown to select a plot, then expand the categories below to check which variables (like `SOG` or `TWS`) should be graphed.
4. If your file is actively being written by OpenCPN, check **Auto-Refresh** to constantly update the data in the background.

## Architecture

- `main_window.py`: Core application, layout management, and user controls.
- `plot_widget.py`: Powered by `pyqtgraph`, handles drawing, interactions, scaling, and the synchronized crosshair logic.
- `data_model.py`: Uses `pandas` for grouping, resampling, downsampling, and safely delivering plotting arrays.
- `vdr_parser.py`: The robust ingest engine. Reads file structures dynamically, strips out NMEA payloads, and yields structured timestamps and values.

## File Format Support

The parser can currently handle two core file styles natively:
- **Style A:** `received_at, protocol, source, msg_type, raw_data`
- **Style B:** `timestamp, type, id, message`

Timestamps can be in UNIX Epoch `ms` integers, or fully qualified `ISO8601` formatted date strings.

## Extensibility

Want to capture new NMEA variables? Open `vdr_parser.py`, locate the `_parse_line` method, and add another rule pointing to your desired `pynmea2` data attribute!
