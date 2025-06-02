#!/usr/bin/env python3
"""
Model a 2-element beam with 88' driven element and a resonant passive reflector
cut for resonance at 7.1 MHz, detuned slightly. Spacing is 20' behind the driven.
Plot azimuth and elevation patterns at 7.1 and 3.5 MHz with reflector detuned by 3%, 4%, 5%, and 6%.
Add a table of feedpoint impedance at both frequencies for each detune.
"""
import argparse
import os
from typing import Dict, List
import numpy as np
import math
import matplotlib.pyplot as plt
from antenna_model import (
    feet_to_meters,
    resonant_dipole_length,
    AntennaElement,
    AntennaModel,
    AntennaSimulator,
    plot_polar_patterns,
    Report,
    build_dipole_model
)

def build_two_element_beam_88ft(
    detune_frac: float,
    driven_length_ft: float = 88.0,
    spacing_ft: float = 20.0,
    reflector_resonant_freq_mhz: float = 7.1,
    segments: int = 21,
    radius: float = 0.001,
) -> AntennaModel:
    """
    Build a 2-element beam model: an 88' driven wire and a passive reflector cut
    for resonance at reflector_resonant_freq_mhz, then detuned by detune_frac.
    Spacing is spacing_ft behind the driven element.
    """
    # Convert lengths
    spacing_m = feet_to_meters(spacing_ft)
    driven_length_m = feet_to_meters(driven_length_ft)
    # Driven element
    half_driven = driven_length_m / 2.0
    # Reflector base resonant length
    base_reflector_length = resonant_dipole_length(reflector_resonant_freq_mhz)
    # Apply detune
    detuned_reflector_length = base_reflector_length * (1.0 + detune_frac)
    half_reflector = detuned_reflector_length / 2.0

    model = AntennaModel()
    # Add driven element
    el1 = AntennaElement(
        x1=0.0, y1=-half_driven, z1=0.0,
        x2=0.0, y2= half_driven, z2=0.0,
        segments=segments, radius=radius
    )
    model.add_element(el1)
    center_seg = (segments + 1) // 2
    model.add_feedpoint(element_index=0, segment=center_seg)
    # Add passive reflector behind along x-axis
    el2 = AntennaElement(
        x1=-spacing_m, y1=-half_reflector, z1=0.0,
        x2=-spacing_m, y2= half_reflector, z2=0.0,
        segments=segments, radius=radius
    )
    model.add_element(el2)
    return model


def main():
    parser = argparse.ArgumentParser(
        description="2-element beam: 88' driven, resonant reflector at 7.1 MHz detuned by 3-6%."
    )
    parser.add_argument('--show-gui', action='store_true',
                        help='Display plots interactively instead of saving PNG.')
    args = parser.parse_args()

    # Simulation parameters
    height_m = 20.0
    freqs_mhz = [7.1, 3.5]
    detune_fracs = [0.03, 0.04, 0.05, 0.055, 0.06]
    # Define cases: (label, detune_frac), None detune_frac means no reflector
    cases = [
        ("No reflector", None),
        ("3%", 0.03),
        ("4%", 0.04),
        ("5%", 0.05),
        ("5.5%", 0.055),
        ("6%", 0.06),
    ]
    segments = 21
    radius = 0.001
    ground = 'average'
    el_fixed = 30.0  # elevation for azimuth cut

    sim = AntennaSimulator()
    report = Report('2_el_beam_88ft')

    # Split feedpoint impedance into separate tables per frequency
    imp7_rows: List[List[str]] = []
    imp3_rows: List[List[str]] = []
    for label, detune in cases:
        # Build model: dipole only or two-element beam
        if detune is None:
            driven_length_m = feet_to_meters(88.0)
            model = build_dipole_model(total_length=driven_length_m, segments=segments, radius=radius)
        else:
            model = build_two_element_beam_88ft(detune, segments=segments, radius=radius)
        # Impedance at 7.1 MHz
        R7, X7 = sim.simulate_pattern(
            model, freq_mhz=7.1, height_m=height_m, ground=ground,
            el_step=45.0, az_step=360.0
        )['impedance']
        # Impedance at 3.5 MHz
        R3, X3 = sim.simulate_pattern(
            model, freq_mhz=3.5, height_m=height_m, ground=ground,
            el_step=45.0, az_step=360.0
        )['impedance']
        # Series compensation for 7.1
        if X7 > 0:
            C7 = 1/(2*math.pi*7.1e6*X7)
            match7 = f"C={C7*1e12:.1f} pF"
        else:
            L7 = abs(X7)/(2*math.pi*7.1e6)
            match7 = f"L={L7*1e9:.1f} nH"
        # Series compensation for 3.5
        if X3 > 0:
            C3 = 1/(2*math.pi*3.5e6*X3)
            match3 = f"C={C3*1e12:.1f} pF"
        else:
            L3 = abs(X3)/(2*math.pi*3.5e6)
            match3 = f"L={L3*1e9:.1f} nH"
        imp7_rows.append([label, f"{R7:.2f}", f"{X7:.2f}", match7])
        imp3_rows.append([label, f"{R3:.2f}", f"{X3:.2f}", match3])
    report.add_table(
        "Feedpoint Impedance at 7.1 MHz vs Case",
        ["Case", "R (Ω)", "X (Ω)", "Match"],
        imp7_rows,
        parameters=f"driven=88'; spacing=20'; height={height_m} m; segments={segments}; radius={radius} m; ground={ground}"
    )
    report.add_table(
        "Feedpoint Impedance at 3.5 MHz vs Case",
        ["Case", "R (Ω)", "X (Ω)", "Match"],
        imp3_rows,
        parameters=f"driven=88'; spacing=20'; height={height_m} m; segments={segments}; radius={radius} m; ground={ground}"
    )
    # Forward Gain and Front-to-Back Ratio at 7.1 MHz
    fgfb_rows: List[List[str]] = []
    for label, detune in cases:
        # Build model for each case
        if detune is None:
            driven_length_m = feet_to_meters(88.0)
            model = build_dipole_model(total_length=driven_length_m, segments=segments, radius=radius)
        else:
            model = build_two_element_beam_88ft(detune, segments=segments, radius=radius)
        az_res = sim.simulate_azimuth_pattern(
            model, freq_mhz=7.1, height_m=height_m, ground=ground, el=el_fixed, az_step=5.0
        )
        fwd_gain = next(p['gain'] for p in az_res if abs(p['az'] - 0.0) < 1e-6)
        back_gain = next(p['gain'] for p in az_res if abs(p['az'] - 180.0) < 1e-6)
        fgfb_rows.append([label, f"{fwd_gain:.2f}", f"{(fwd_gain - back_gain):.2f}"])
    report.add_table(
        "Forward Gain and Front-to-Back at 7.1 MHz",
        ["Case", "Fwd Gain (dB)", "F/B (dB)"],
        fgfb_rows,
        parameters=f"height={height_m} m; el={el_fixed}°; ground={ground}; segments={segments}; radius={radius} m"
    )

    # Pattern plots for each frequency (including no-reflector case)
    for freq in freqs_mhz:
        elev_pats: Dict[str, List[Dict[str, float]]] = {}
        az_pats: Dict[str, List[Dict[str, float]]] = {}
        for label, detune in cases:
            # Build model for each case
            if detune is None:
                driven_length_m = feet_to_meters(88.0)
                model = build_dipole_model(total_length=driven_length_m, segments=segments, radius=radius)
            else:
                model = build_two_element_beam_88ft(detune, segments=segments, radius=radius)
            # Elevation pattern (az=0)
            res = sim.simulate_pattern(
                model, freq_mhz=freq, height_m=height_m, ground=ground,
                el_step=1.0, az_step=360.0
            )
            elev_pats[label] = res['pattern']
            # Azimuth pattern (el=fixed)
            az_pats[label] = sim.simulate_azimuth_pattern(
                model, freq_mhz=freq, height_m=height_m, ground=ground,
                el=el_fixed, az_step=5.0
            )
        # Plot polar patterns
        case_labels = [label for label, _ in cases]
        output_file = os.path.join(report.report_dir, f'polar_patterns_{freq:.1f}MHz.png')
        plot_polar_patterns(
            elev_pats, az_pats, case_labels, el_fixed,
            output_file, args.show_gui, legend_labels=case_labels
        )
        report.add_plot(
            f'Polar Patterns at {freq:.1f} MHz',
            output_file,
            parameters=f"height={height_m} m; ground={ground}; segments={segments}; radius={radius} m; el={el_fixed}°"
        )

    report.save()

if __name__ == "__main__":
    main() 