import subprocess
from typing import List, Dict, Any, Optional, Tuple
import math
import re

def feet_to_meters(feet: float) -> float:
    """Convert feet to meters."""
    return feet * 0.3048

def meters_to_feet(meters: float) -> float:
    """Convert meters to feet."""
    return meters / 0.3048

class AntennaModel:
    """
    Represents an antenna model as a set of wires in relative position.
    """
    def __init__(self, wires: List[Dict[str, Any]]):
        self.wires = wires  # List of wire dicts
        # Each wire: dict with keys: segments, x1, y1, z1, x2, y2, z2, radius

    def to_pymininec_args(self, height_m: float = 0.0) -> List[str]:
        args = []
        for w in self.wires:
            # Apply height offset to z1, z2
            z1 = float(w['z1']) + height_m
            z2 = float(w['z2']) + height_m
            args += [
                "-w",
                f"{w['segments']},{w['x1']},{w['y1']},{z1:.6f},{w['x2']},{w['y2']},{z2:.6f},{w['radius']}"
            ]
        return args

def build_dipole_model(
    total_length: float,
    segments: int = 21,
    radius: float = 0.001,
) -> AntennaModel:
    """
    Build a center-fed dipole of given total length (meters), centered at origin (z=0), oriented along the y-axis.
    Returns an AntennaModel instance.
    """
    half_length = total_length / 2.0
    wire = {
        'segments': segments,
        'x1': "0", 'y1': f"{-half_length:.6f}", 'z1': "0",
        'x2': "0",  'y2': f"{half_length:.6f}",  'z2': "0",
        'radius': f"{radius:.6f}"
    }
    return AntennaModel([wire])

def resonant_dipole_length(freq_mhz: float) -> float:
    """
    Return the ARRL handbook resonant half-wave dipole length (meters) for a given frequency (MHz):
    length = (468 / freq_mhz) [ft] converted to meters
    This formula accounts for typical end effects and is more accurate for real wire antennas than the ideal physics formula.
    """
    length_ft = 468 / freq_mhz
    return feet_to_meters(length_ft)

def parse_impedance(output: str) -> Optional[Tuple[float, float]]:
    # Look for 'IMPEDANCE = ( R , X J)'
    m = re.search(r"IMPEDANCE = \( *([-.\deE]+) *, *([-.\deE]+) *J\)", output)
    if m:
        R = float(m.group(1))
        X = float(m.group(2))
        return (R, X)
    return None

def parse_pattern(output: str) -> List[Dict[str, float]]:
    # Parse the TOTAL PATTERN (DB) column directly from pymininec output.
    pattern: List[Dict[str, float]] = []
    in_table = False
    header_lines_to_skip = 0
    for line in output.splitlines():
        if not in_table:
            if 'PATTERN DATA' in line:
                in_table = True
                # Skip the next two header lines (column titles)
                header_lines_to_skip = 2
            continue
        if header_lines_to_skip > 0:
            header_lines_to_skip -= 1
            continue
        parts = line.strip().split()
        # Expect at least: zenith, azimuth, vertical_db, horizontal_db, total_db
        if len(parts) >= 5:
            try:
                zenith = float(parts[0])
                az = float(parts[1])
                total_db = float(parts[4])
                # Convert zenith angle (0=up) to elevation (0–180 horizon-to-horizon)
                el_offset = 90.0 - zenith
                elevation = el_offset if el_offset >= 0.0 else 180.0 + el_offset
                pattern.append({'el': elevation, 'az': az, 'gain': total_db})
            except ValueError:
                continue
    return pattern

def _run_pymininec(
    model: AntennaModel,
    freq_mhz: float,
    height_m: float = 0.0,
    ground_opts: Optional[List[str]] = None,
    excitation_pulse: str = "10,1",
    pattern_opts: Optional[Dict[str, str]] = None,
    option: str = "far-field-absolute",
    ff_distance: int = 1000,
) -> Dict[str, Any]:
    """
    Internal: Run pymininec with the given model, frequency, height, and options.
    """
    cmd = ["pymininec", "-f", str(freq_mhz)]
    cmd += model.to_pymininec_args(height_m=height_m)
    if ground_opts:
        cmd += ground_opts
    cmd += ["--excitation-pulse", excitation_pulse]
    cmd += ["--option", option]
    if option == "far-field-absolute":
        cmd += ["--ff-distance", str(ff_distance)]
    if pattern_opts:
        for k, v in pattern_opts.items():
            cmd += [f"--{k}", v]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    output = proc.stdout
    return {
        'impedance': parse_impedance(output),
        'pattern': parse_pattern(output),
        'raw_output': output
    }

class AntennaSimulator:
    """
    Abstracts antenna simulation engine (currently only pymininec).
    Provides a simple API for pattern and impedance simulation.
    - If the user requests an elevation range >90°, the simulator will automatically combine data from az=0 and az=180 to provide a full 0–180° elevation cut.
    - If the user requests an elevation step that does not divide evenly into 180, it will be rounded to the nearest value that does.
    """
    def __init__(self, engine: str = "pymininec"):
        if engine != "pymininec":
            raise NotImplementedError("Only pymininec engine is supported currently.")
        self.engine = engine

    def _round_step(self, step: float, total: float = 180.0) -> float:
        # Find the nearest step that divides total evenly
        n_steps = round(total / step)
        if n_steps < 1:
            n_steps = 1
        return total / n_steps

    def simulate_pattern(
        self,
        model: AntennaModel,
        freq_mhz: float,
        height_m: float,
        ground: str = "average",
        el_step: float = 5.0,
        az_step: float = 5.0,
        ff_distance: int = 1000,
    ) -> Dict[str, Any]:
        """
        Simulate the antenna pattern and impedance.
        Returns dict with 'impedance' and 'pattern' (list of dicts with el, az, gain).
        Always returns a full 0-180 deg elevation and 0-360 deg azimuth grid.
        If elevation >90° is requested, combines az=0 and az=180° as needed.
        Step sizes are rounded to values that divide 180 (el) and 360 (az) evenly.
        """
        ground_opts = get_ground_opts(ground)
        # Round step sizes
        el_step = self._round_step(el_step, 180.0)
        az_step = self._round_step(az_step, 360.0)
        # Only simulate zenith 0–90° (elevation 90–0°) at az=0 and az=180
        theta_start = 0
        theta_step = el_step
        theta_count = int(90 / el_step) + 1
        phi_list = [0, 180]
        # Simulate at az=0
        pattern_opts_0 = {
            "theta": f"{theta_start},{theta_step},{theta_count}",
            "phi": "0,0,1"
        }
        result_0 = _run_pymininec(
            model,
            freq_mhz=freq_mhz,
            height_m=height_m,
            ground_opts=ground_opts,
            excitation_pulse="10,1",
            pattern_opts=pattern_opts_0,
            option="far-field",
            ff_distance=ff_distance
        )
        # Simulate at az=180
        pattern_opts_180 = {
            "theta": f"{theta_start},{theta_step},{theta_count}",
            "phi": "180,0,1"
        }
        result_180 = _run_pymininec(
            model,
            freq_mhz=freq_mhz,
            height_m=height_m,
            ground_opts=ground_opts,
            excitation_pulse="10,1",
            pattern_opts=pattern_opts_180,
            option="far-field",
            ff_distance=ff_distance
        )
        # Build full 0–180° elevation cut at az=0
        pattern = []
        # Elevation 0–90° from az=0
        for p in result_0['pattern']:
            el = p['el']
            if 0 <= el <= 90:
                pattern.append({'el': el, 'az': 0.0, 'gain': p['gain']})
        # Elevation 90–180° from az=180 (map el to 180-el)
        for p in result_180['pattern']:
            el = p['el']
            if 0 <= el <= 90:
                pattern.append({'el': 180.0 - el, 'az': 0.0, 'gain': p['gain']})
        # Sort by elevation
        pattern = sorted(pattern, key=lambda x: x['el'])
        # Use impedance from az=0 run
        return {
            'impedance': result_0['impedance'],
            'pattern': pattern
        }

# Standard ground types for pymininec
# Values from NEC/ARRL conventions:
#   'poor':    εr=5,   σ=0.001 S/m
#   'average': εr=13,  σ=0.005 S/m
#   'good':    εr=20,  σ=0.03 S/m
#   'free':    free space (no ground)
def get_ground_opts(ground_type: str = "average") -> Optional[list]:
    """
    Return pymininec ground options for a given ground type.
    ground_type: 'free', 'poor', 'average', 'good'
    Returns a list of CLI args for pymininec, or None for free space.
    """
    ground_type = ground_type.lower()
    if ground_type == "free":
        return None
    elif ground_type == "poor":
        return ["--medium=5,0.001,0"]
    elif ground_type == "average":
        return ["--medium=13,0.005,0"]
    elif ground_type == "good":
        return ["--medium=20,0.03,0"]
    else:
        raise ValueError(f"Unknown ground type: {ground_type}") 