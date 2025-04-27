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
    Build a center-fed dipole of given total length (meters), centered at origin (z=0).
    Returns an AntennaModel instance.
    """
    half_length = total_length / 2.0
    wire = {
        'segments': segments,
        'x1': f"{-half_length:.6f}", 'y1': "0", 'z1': "0",
        'x2': f"{half_length:.6f}",  'y2': "0", 'z2': "0",
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
    # Look for PATTERN DATA table and parse lines: theta phi ... TOTAL
    # Return [{'el': elevation, 'az': azimuth, 'gain': gain}, ...]
    pattern = []
    in_table = False
    for line in output.splitlines():
        if not in_table:
            if 'PATTERN DATA' in line:
                in_table = True
            continue
        # skip header lines
        if re.search(r'ZENITH|AZIMUTH|VERTICAL|HORIZONTAL|TOTAL', line):
            continue
        parts = line.strip().split()
        if len(parts) >= 5:
            try:
                zenith = float(parts[0])
                az = float(parts[1])
                gain = float(parts[-1])
                elevation = 90.0 - zenith  # convert to elevation above horizon
                pattern.append({'el': elevation, 'az': az, 'gain': gain})
            except Exception:
                continue
    return pattern

def run_pymininec(
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
    Run pymininec with the given model, frequency, height, and options.
    Returns a dict with at least:
      - 'impedance': (R, X) tuple (ohms)
      - 'pattern': list of dicts with keys: el, az, gain (dBi)
      - 'raw_output': the full stdout string
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