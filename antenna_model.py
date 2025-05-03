import subprocess
from typing import List, Dict, Any, Optional, Tuple
import math
import re
import matplotlib.pyplot as plt
import numpy as np

def feet_to_meters(feet: float) -> float:
    """Convert feet to meters."""
    return feet * 0.3048

def meters_to_feet(meters: float) -> float:
    """Convert meters to feet."""
    return meters / 0.3048

# Define a generic antenna element (straight wire)
class AntennaElement:
    """
    Represents a straight wire segment in 3D space with specified geometry, segmentation, and radius.
    """
    def __init__(self,
                 x1: float, y1: float, z1: float,
                 x2: float, y2: float, z2: float,
                 segments: int,
                 radius: float):
        self.x1 = x1
        self.y1 = y1
        self.z1 = z1
        self.x2 = x2
        self.y2 = y2
        self.z2 = z2
        self.segments = segments
        self.radius = radius

    def to_wire_dict(self) -> Dict[str, Any]:
        """Convert this element into a pymininec wire definition dict."""
        return {
            'segments': self.segments,
            'x1': f"{self.x1:.6f}",
            'y1': f"{self.y1:.6f}",
            'z1': f"{self.z1:.6f}",
            'x2': f"{self.x2:.6f}",
            'y2': f"{self.y2:.6f}",
            'z2': f"{self.z2:.6f}",
            'radius': f"{self.radius:.6f}",
        }

class AntennaModel:
    """
    Represents an antenna model composed of one or more elements and feedpoints.
    """
    def __init__(self):
        # List of AntennaElement instances
        self.elements: List[AntennaElement] = []
        # List of feedpoint definitions as dicts {'element_index': int, 'segment': int}
        self.feedpoints: List[Dict[str, int]] = []

    def add_element(self, element: AntennaElement) -> None:
        """Add an antenna element (straight wire) to the model."""
        self.elements.append(element)

    def add_feedpoint(self, element_index: int, segment: int) -> None:
        """Add a feedpoint on the specified element and segment index."""
        self.feedpoints.append({'element_index': element_index, 'segment': segment})

    @property
    def wires(self) -> List[Dict[str, Any]]:
        """Flatten elements into wire definitions suitable for pymininec."""
        return [e.to_wire_dict() for e in self.elements]

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
    # Create a single straight element for the half-wave dipole
    half_length = total_length / 2.0
    element = AntennaElement(
        x1=0.0, y1=-half_length, z1=0.0,
        x2=0.0, y2=half_length, z2=0.0,
        segments=segments,
        radius=radius,
    )
    model = AntennaModel()
    model.add_element(element)
    # Default feedpoint at center segment of the sole element
    center_seg = (segments + 1) // 2
    model.add_feedpoint(element_index=0, segment=center_seg)
    return model

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

    def simulate_azimuth_pattern(
        self,
        model: AntennaModel,
        freq_mhz: float,
        height_m: float,
        ground: str,
        el: float,
        az_step: float = 5.0,
    ) -> List[Dict[str, float]]:
        """
        Simulate azimuth cut at a fixed elevation (deg) by sweeping phi.
        Returns list of dicts with 'el', 'az', 'gain'.
        """
        ground_opts = get_ground_opts(ground)
        # Convert elevation to zenith angle
        zenith = 90.0 - el
        # Round phi step
        phi_step = self._round_step(az_step, 360.0)
        phi_count = int(360.0 / phi_step) + 1
        pattern_opts = {
            'theta': f'{zenith:.6f},0,1',
            'phi': f'0,{phi_step},{phi_count}'
        }
        result = _run_pymininec(
            model,
            freq_mhz=freq_mhz,
            height_m=height_m,
            ground_opts=ground_opts,
            excitation_pulse='10,1',
            pattern_opts=pattern_opts,
            option='far-field'
        )
        # Return only entries at the requested elevation
        return [p for p in result['pattern'] if abs(p['el'] - el) < 1e-3]

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

# === High-level utilities for antenna analysis and plotting ===

def compute_impedance_vs_heights(
    sim: AntennaSimulator,
    model: AntennaModel,
    freq_mhz: float,
    heights: List[float],
    ground: str,
    el_step: float = 45.0,
    az_step: float = 360.0,
) -> List[Tuple[float, float, float]]:
    """
    Compute feedpoint impedance (R, X) for each height in meters.
    Returns a list of tuples (height, R, X).
    """
    results: List[Tuple[float, float, float]] = []
    for h in heights:
        res = AntennaSimulator().simulate_pattern(
            model,
            freq_mhz=freq_mhz,
            height_m=h,
            ground=ground,
            el_step=el_step,
            az_step=az_step,
        )
        R, X = res['impedance']
        results.append((h, R, X))
    return results


def print_impedance_table(imp_list: List[Tuple[float, float, float]]) -> None:
    """
    Print a table of feedpoint impedance vs. height.
    """
    print("Height (m) |    R (Ω)   |   X (Ω)")
    print("-----------------------------------")
    for h, R, X in imp_list:
        print(f"   {h:6.1f} | {R:9.2f} | {X:8.2f}")


def compute_elevation_patterns(
    sim: AntennaSimulator,
    model: AntennaModel,
    freq_mhz: float,
    heights: List[float],
    ground: str,
    el_step: float = 1.0,
    az_step: float = 360.0,
) -> Dict[float, List[Dict[str, float]]]:
    """
    Compute elevation patterns (pattern at az=0) for each height.
    Returns a dict mapping height to list of {{'el', 'az', 'gain'}}.
    """
    patterns: Dict[float, List[Dict[str, float]]] = {}
    for h in heights:
        res = AntennaSimulator().simulate_pattern(
            model,
            freq_mhz=freq_mhz,
            height_m=h,
            ground=ground,
            el_step=el_step,
            az_step=az_step,
        )
        patterns[h] = res['pattern']
    return patterns


def compute_azimuth_patterns(
    sim: AntennaSimulator,
    model: AntennaModel,
    freq_mhz: float,
    heights: List[float],
    ground: str,
    el: float,
    az_step: float = 5.0,
) -> Dict[float, List[Dict[str, float]]]:
    """
    Compute azimuth patterns at fixed elevation for each height.
    Returns a dict mapping height to list of {{'el', 'az', 'gain'}}.
    """
    patterns: Dict[float, List[Dict[str, float]]] = {}
    for h in heights:
        patterns[h] = AntennaSimulator().simulate_azimuth_pattern(
            model,
            freq_mhz=freq_mhz,
            height_m=h,
            ground=ground,
            el=el,
            az_step=az_step,
        )
    return patterns


def print_gain_table(
    patterns: Dict[float, List[Dict[str, float]]],
    heights: List[float],
    el_angles: List[int],
    highlight: bool = True,
) -> None:
    """
    Print a gain table for specified heights and elevation angles.
    Highlight the maximum gain elevation for each height if highlight=True.
    """
    header = "Elevation (deg) |" + "".join([f" {h:>7} m" for h in heights])
    print(header)
    print("----------------|" + "-------" * len(heights))
    max_el: Dict[float, float] = {}
    if highlight:
        for h in heights:
            best = max(patterns[h], key=lambda p: p['gain'])
            max_el[h] = best['el']
    for el in el_angles:
        row = f"{el:8d}         |"
        for h in heights:
            closest = min(patterns[h], key=lambda p: abs(p['el'] - el))
            g = closest['gain']
            if highlight and abs(max_el.get(h, -1) - el) < 1e-6:
                row += f" \033[1;33m{g:7.3f}\033[0m"
            else:
                row += f" {g:7.3f}"
        print(row)


def plot_polar_patterns(
    elevation_patterns: Dict[float, List[Dict[str, float]]],
    azimuth_patterns: Dict[float, List[Dict[str, float]]],
    heights: List[float],
    el_fixed: float,
    output_file: str,
    show_gui: bool = False,
) -> None:
    """
    Generate elevation (az=0) and azimuth (el=el_fixed) polar plots for each height.
    Saves to output_file or displays if show_gui=True.
    """
    fig, (ax_el, ax_az) = plt.subplots(1, 2, subplot_kw={'polar': True}, figsize=(14, 7))
    colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
    # Elevation pattern
    raw_max = max(max(p['gain'] for p in elevation_patterns[h]) for h in heights)
    db_min = -40
    db_max = math.ceil(raw_max / 10.0) * 10
    db_ticks = list(range(db_min, db_max + 10, 10))
    r_ticks = [10**(d/10.0) for d in db_ticks]
    ax_el.set_theta_zero_location('E')
    ax_el.set_theta_direction(1)
    ax_el.set_title('Elevation Pattern (az=0)', va='bottom')
    ax_el.set_rscale('log')
    ax_el.set_rticks(r_ticks)
    ax_el.set_yticklabels([f"{d} dB" for d in db_ticks])
    ax_el.set_ylim(r_ticks[0], r_ticks[-1])
    ax_el.grid(True)
    for idx, h in enumerate(heights):
        data = sorted(elevation_patterns[h], key=lambda p: p['el'])
        theta = np.radians([p['el'] for p in data])
        r = [10**(p['gain']/10.0) for p in data]
        ax_el.plot(theta, r, label=f"h={h}m", color=colors[idx % len(colors)])
    ax_el.legend(loc='upper right', bbox_to_anchor=(1.2, 1.1))
    # Azimuth pattern
    raw_max_az = max(max(p['gain'] for p in azimuth_patterns[h]) for h in heights)
    # Use floor of max gain for tick calculation (no extra padding)
    db_max_az = int(raw_max_az)
    db_ticks_az = list(range(db_min, db_max_az + 1, 10))
    r_ticks_az = [10**(d/10.0) for d in db_ticks_az]
    ax_az.set_theta_zero_location('E')
    ax_az.set_theta_direction(-1)
    ax_az.set_title(f'Azimuth Pattern (el={int(el_fixed)}°)', va='bottom')
    ax_az.set_rscale('log')
    ax_az.set_rticks(r_ticks_az)
    ax_az.set_yticklabels([f"{d} dB" for d in db_ticks_az])
    ax_az.grid(True)
    for idx, h in enumerate(heights):
        data = sorted(azimuth_patterns[h], key=lambda p: p['az'])
        phi = np.radians([p['az'] for p in data])
        r = [10**(p['gain']/10.0) for p in data]
        ax_az.plot(phi, r, label=f"h={h}m", color=colors[idx % len(colors)])
    ax_az.legend(loc='upper right', bbox_to_anchor=(1.2, 1.1))
    plt.tight_layout()
    if show_gui:
        plt.show()
    else:
        plt.savefig(output_file)
        print(f"Saved polar patterns to {output_file}") 