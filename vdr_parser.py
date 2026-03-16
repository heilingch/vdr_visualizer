"""
VDR Parser - Reads OpenCPN VDR files (CSV or raw NMEA text)
and extracts all available sensor data into a pandas DataFrame.
"""
import pynmea2
import numpy as np
from datetime import datetime, date
import pandas as pd
import logging
import csv
import re

# Category definitions for grouping variables in the UI
VARIABLE_CATEGORIES = {
    'Wind': ['AWA', 'AWS', 'TWA', 'TWS', 'TWD'],
    'Navigation': ['SOG', 'COG', 'Heading', 'HDG_Mag', 'STW', 'Latitude', 'Longitude'],
    'Depth': ['Depth', 'Depth_Offset', 'Depth_Max'],
    'Weather': ['Pressure', 'Air_Temp', 'Water_Temp', 'Humidity', 'Dew_Point'],
    'Vessel': ['Rudder_Angle', 'Rate_of_Turn', 'Pitch', 'Roll', 'Heave'],
    'GPS': ['GPS_Sats', 'HDOP', 'PDOP', 'VDOP', 'GPS_Alt'],
    'Performance': ['VMG', 'Leeway'],
}

def get_category(variable_name):
    """Return the category for a given variable name."""
    for cat, vars_list in VARIABLE_CATEGORIES.items():
        if variable_name in vars_list:
            return cat
    return 'Other'


class VDRParser:
    def __init__(self):
        self.current_datetime = None
        self.logger = logging.getLogger(__name__)

    def parse_file(self, filepath: str) -> pd.DataFrame:
        """
        Parses a VDR file containing NMEA 0183 sentences.
        Supports raw text or OpenCPN CSV formatted VDR files.
        Returns a pandas DataFrame indexed by timestamp.
        """
        self.current_datetime = None
        parsed_data = []
        is_csv = False

        # Detect CSV format
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('received_at,') or line.startswith('timestamp,'): # Added 'timestamp,' for new CSV format detection
                    is_csv = True
                break

        if is_csv:
            logging.info(f"Parsing CSV VDR file: {filepath}")
            try:
                # Some files have preamble lines, skip them using comment='#'
                df_raw = pd.read_csv(filepath, comment='#')
                
                # Determine column mapping
                cols = df_raw.columns.tolist()
                time_col = None
                data_col = None

                if 'message' in cols and 'timestamp' in cols:
                    time_col = 'timestamp'
                    data_col = 'message'
                elif 'raw_data' in cols and 'received_at' in cols:
                    time_col = 'received_at'
                    data_col = 'raw_data'
                else:
                    logging.error(f"Unknown CSV format in {filepath}. Found columns: {cols}")
                    return pd.DataFrame()

                # Extract columns as numpy arrays/lists for fast iteration
                timestamps = df_raw[time_col].values
                sentences = df_raw[data_col].values
                for timestamp_val, sentence_val in zip(timestamps, sentences):
                    sentence = str(sentence_val)
                    
                    # Clean up escape characters if present
                    sentence = sentence.replace('<0D><0A>', '').replace('\r', '').replace('\n', '').strip()
                    # If quotes are baked into the string like "$GPRMC...
                    if sentence.startswith('"') and sentence.endswith('"'):
                        sentence = sentence[1:-1]

                    # Set current_datetime for _parse_line to use
                    # We'll convert to datetime objects later in bulk for efficiency
                    self.current_datetime = timestamp_val 
                    self._parse_line(sentence, parsed_data, is_csv_mode=True)

            except Exception as e:
                logging.error(f"Error reading CSV file {filepath}: {e}")
                return pd.DataFrame()
        else:
            logging.info(f"Parsing raw NMEA VDR file: {filepath}")
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line_no, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    self._parse_line(line, parsed_data, is_csv_mode=False, line_no=line_no)

        if not parsed_data:
            return pd.DataFrame()

        # Create DataFrame and set DatetimeIndex
        df = pd.DataFrame(parsed_data)
        if not df.empty:
            # We use mixed format: handles ISO8601 strings and epoch integers.
            # If numeric, pandas treats it as ns, but our epoch might be ms. 
            # We'll normalize to a known state if they're purely numeric.
            time_s = pd.to_datetime(df['timestamp'], format='mixed', errors='coerce')
            
            # If it was interpreted as 1970-01-01 when it should be 2026, it likely means
            # format='mixed' interpreted an integer in ms as nanoseconds (.to_datetime defaults to ns).
            # Let's fix that fallback explicitly if dtype is numeric:
            # Check the original column's dtype if available, or infer from the series
            if is_csv and time_col and df_raw[time_col].dtype in [np.int64, np.float64]:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', errors='coerce')
            else:
                df['timestamp'] = time_s
                
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)
        return df

    def _parse_line(self, line, parsed_data, is_csv_mode=False, line_no=None):
        """Parse a single line containing an NMEA sentence."""
        # Clean OpenCPN CSV hex markers (this is now mostly handled before calling _parse_line for CSV)
        line = line.replace('<0D><0A>', '').replace('\r', '').replace('\n', '')

        # Find start of NMEA sentence
        start_idx = line.find('$')
        if start_idx == -1:
            start_idx = line.find('!')
        if start_idx == -1:
            return

        nmea_str = line[start_idx:]

        # pynmea2 expects 5-char sentence IDs ($AABBB) but some sources
        # emit short IDs like $MTW or $VHW (3 chars). Pad with dummy talker.
        if nmea_str.startswith('$'):
            comma = nmea_str.find(',')
            if comma > 0:
                tag = nmea_str[1:comma]
                if len(tag) == 3:
                    nmea_str = f"$XX{tag}{nmea_str[comma:]}"

        try:
            msg = pynmea2.parse(nmea_str)

            # In raw text mode, derive timestamps from NMEA sentences
            if not is_csv_mode:
                if hasattr(msg, 'datestamp') and hasattr(msg, 'timestamp'):
                    if msg.datestamp and msg.timestamp:
                        self.current_datetime = datetime.combine(msg.datestamp, msg.timestamp)
                elif hasattr(msg, 'timestamp') and msg.timestamp:
                    if self.current_datetime is not None:
                        self.current_datetime = datetime.combine(
                            self.current_datetime.date(), msg.timestamp
                        )
                    else:
                        self.current_datetime = datetime.combine(date.today(), msg.timestamp)

            if self.current_datetime is None:
                return

            data = self._extract_data(msg)
            if data:
                data['timestamp'] = self.current_datetime
                parsed_data.append(data)

        except pynmea2.ParseError:
            pass
        except Exception as e:
            self.logger.debug(f"Parse error at line {line_no}: {e}")

    def _safe_float(self, obj, attr):
        """Safely extract a float attribute from an NMEA message."""
        val = getattr(obj, attr, None)
        if val is None or val == '':
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def _extract_data(self, msg):
        """Extract all available variables from an NMEA sentence."""
        data = {}
        st = msg.sentence_type

        # ── Wind ──────────────────────────────────────────────
        if st == 'MWV':
            angle = self._safe_float(msg, 'wind_angle')
            speed = self._safe_float(msg, 'wind_speed')
            ref = getattr(msg, 'reference', '')
            if angle is not None and speed is not None:
                if ref == 'R':
                    data['AWA'] = angle
                    data['AWS'] = speed
                elif ref == 'T':
                    data['TWA'] = angle
                    data['TWS'] = speed

        elif st == 'MWD':
            twd = self._safe_float(msg, 'direction_true')
            tws = self._safe_float(msg, 'wind_speed_knots')
            if twd is not None:
                data['TWD'] = twd
            if tws is not None:
                data['TWS'] = tws

        # ── Navigation / Position ─────────────────────────────
        elif st == 'RMC':
            sog = self._safe_float(msg, 'spd_over_grnd')
            cog = self._safe_float(msg, 'true_course')
            if sog is not None:
                data['SOG'] = sog
            if cog is not None:
                data['COG'] = cog
            # Lat/Lon
            try:
                lat = msg.latitude
                lon = msg.longitude
                if lat is not None and lon is not None:
                    data['Latitude'] = float(lat)
                    data['Longitude'] = float(lon)
            except Exception:
                pass

        elif st == 'GGA':
            alt = self._safe_float(msg, 'altitude')
            sats = self._safe_float(msg, 'num_sats')
            hdop = self._safe_float(msg, 'horizontal_dil')
            if alt is not None:
                data['GPS_Alt'] = alt
            if sats is not None:
                data['GPS_Sats'] = sats
            if hdop is not None:
                data['HDOP'] = hdop

        elif st == 'GSA':
            pdop = self._safe_float(msg, 'pdop')
            hdop = self._safe_float(msg, 'hdop')
            vdop = self._safe_float(msg, 'vdop')
            if pdop is not None:
                data['PDOP'] = pdop
            if hdop is not None:
                data['HDOP'] = hdop
            if vdop is not None:
                data['VDOP'] = vdop

        elif st == 'VTG':
            cog = self._safe_float(msg, 'true_track')
            sog = self._safe_float(msg, 'spd_over_grnd_kts')
            if cog is not None:
                data['COG'] = cog
            if sog is not None:
                data['SOG'] = sog

        # ── Heading ───────────────────────────────────────────
        elif st in ('HDG', 'HDM', 'HDT'):
            hdg = self._safe_float(msg, 'heading')
            if hdg is not None:
                data['Heading'] = hdg
            # HDG has magnetic deviation/variation
            if st == 'HDG':
                dev = self._safe_float(msg, 'deviation')
                var = self._safe_float(msg, 'variation')
                if dev is not None:
                    data['HDG_Mag'] = hdg + dev if hdg is not None else None

        # ── Speed through water ───────────────────────────────
        elif st == 'VHW':
            stw = self._safe_float(msg, 'water_speed_knots')
            if stw is not None:
                data['STW'] = stw

        # ── Depth ─────────────────────────────────────────────
        elif st == 'DPT':
            depth = self._safe_float(msg, 'depth')
            offset = self._safe_float(msg, 'offset')
            if depth is not None:
                data['Depth'] = depth
            if offset is not None:
                data['Depth_Offset'] = offset

        elif st == 'DBT':
            depth_m = self._safe_float(msg, 'depth_meters')
            if depth_m is not None:
                data['Depth'] = depth_m

        # ── Water Temperature ──────────────────────────────────
        elif st == 'MTW':
            wt = self._safe_float(msg, 'temperature')
            if wt is not None:
                data['Water_Temp'] = wt

        # ── Weather / Meteorological ──────────────────────────
        elif st == 'MDA':
            press = self._safe_float(msg, 'b_pressure_bar')
            if press is None:
                press = self._safe_float(msg, 'b_pressure_bars')
            if press is not None:
                data['Pressure'] = press * 1000.0  # Convert bar to mbar

            air_t = self._safe_float(msg, 'air_temperature')
            if air_t is not None:
                data['Air_Temp'] = air_t

            humidity = self._safe_float(msg, 'rel_humidity')
            if humidity is not None:
                data['Humidity'] = humidity

            dew = self._safe_float(msg, 'dew_point')
            if dew is not None:
                data['Dew_Point'] = dew

        elif st == 'XDR':
            # Transducer measurements - contains many possible values
            # Parse fields in groups of 4: type, value, unit, name
            try:
                fields = msg.data
                for i in range(0, len(fields), 4):
                    if i + 3 >= len(fields):
                        break
                    t_type = fields[i]
                    t_val = fields[i + 1]
                    t_unit = fields[i + 2]
                    t_name = fields[i + 3]
                    if t_val == '':
                        continue
                    fval = float(t_val)

                    # Map common transducer names
                    name_lower = t_name.lower() if t_name else ''
                    if 'pitch' in name_lower:
                        data['Pitch'] = fval
                    elif 'roll' in name_lower:
                        data['Roll'] = fval
                    elif 'heave' in name_lower:
                        data['Heave'] = fval
                    elif 'baro' in name_lower or t_type == 'P':
                        if getattr(t_unit, 'upper', lambda: '')() == 'B' or fval < 10.0:
                            data['Pressure'] = fval * 1000.0
                        else:
                            data['Pressure'] = fval
                    elif 'temp' in name_lower or t_type == 'C':
                        data['Air_Temp'] = fval
                    elif 'humid' in name_lower:
                        data['Humidity'] = fval
                    else:
                        # Store under the transducer name
                        data[f"XDR_{t_name}"] = fval
            except Exception:
                pass

        # ── Rudder ────────────────────────────────────────────
        elif st == 'RSA':
            rudder = self._safe_float(msg, 'rudder_angle')
            if rudder is not None:
                data['Rudder_Angle'] = rudder

        # ── Rate of Turn ──────────────────────────────────────
        elif st == 'ROT':
            rot = self._safe_float(msg, 'rate_of_turn')
            if rot is not None:
                data['Rate_of_Turn'] = rot

        # Remove None values from dict
        data = {k: v for k, v in data.items() if v is not None}
        return data
