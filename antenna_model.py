import subprocess
from typing import List, Dict, Any, Optional
import math

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
    Return the approximate resonant half-wave dipole length (meters) for a given frequency (MHz).
    """
    c = 299792458.0
    wavelength = c / (freq_mhz * 1e6)
    return wavelength / 2.0

def run_pymininec(
    model: AntennaModel,
    freq_mhz: float,
    height_m: float = 0.0,
    ground_opts: Optional[List[str]] = None,
    excitation_pulse: str = "10,1",
    pattern_opts: Optional[Dict[str, str]] = None,
    option: str = "far-field-absolute",
    ff_distance: int = 1000,
) -> str:
    """
    Run pymininec with the given model, frequency, height, and options.
    - model: AntennaModel (relative geometry)
    - freq_mhz: frequency in MHz
    - height_m: height above ground (meters)
    - ground_opts: list of ground-related args (e.g. ["--medium", "0,0,0"])
    - excitation_pulse: feedpoint pulse string
    - pattern_opts: dict of pattern options (e.g. {"theta": "10,10,8", "phi": "0,0,1"})
    - option: pymininec output option
    - ff_distance: far-field distance (if applicable)
    Returns the raw output as a string.
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
    return proc.stdout 