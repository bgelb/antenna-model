#!/usr/bin/env python3
"""
Generate radiation pattern and impedance data for a 2-element Yagi antenna at 30 ft elevation on 14.1 MHz.
The driven element is a half-wave dipole; the passive reflector is 5% longer and spaced 0.2 λ along the x-axis.
Usage: python3 2_el_yagi.py [--show-gui]
"""
import math
import argparse
import matplotlib.pyplot as plt
import numpy as np
from antenna_model import (
    AntennaModel,
    AntennaElement,
    AntennaSimulator,
    resonant_dipole_length,
    compute_impedance_vs_heights,
    print_impedance_table,
    compute_elevation_patterns,
    compute_azimuth_patterns,
    print_gain_table,
    plot_polar_patterns,
)

def main():
    parser = argparse.ArgumentParser(description="2-element Yagi pattern analysis and plotting.")
    parser.add_argument('--show-gui', action='store_true', help='Show plots interactively instead of saving')
    args = parser.parse_args()

    # Simulation setup
    freq_mhz = 14.1
    # Compute lengths using resonant_dipole_length
    driven_length = resonant_dipole_length(freq_mhz)
    segments = 21
    radius = 0.001
    ground = 'average'

    # Build the Yagi model
    model = AntennaModel()

    # Driven element (half-wave dipole) at origin
    half_len = driven_length / 2.0
    driven = AntennaElement(
        x1=0.0, y1=-half_len, z1=0.0,
        x2=0.0, y2= half_len, z2=0.0,
        segments=segments, radius=radius,
    )
    model.add_element(driven)
    # Feedpoint at center segment of driven element
    center_seg = (segments + 1) // 2
    model.add_feedpoint(element_index=0, segment=center_seg)

    # Passive reflector: 5% longer, spaced 0.2 λ along x-axis
    c = 299792458.0
    lambda_m = c / (freq_mhz * 1e6)
    spacing = 0.2 * lambda_m
    # Compute passive element length using resonant_dipole_length at 5% reduced frequency to get 5% longer length
    passive_length = resonant_dipole_length(freq_mhz / 1.05)
    half_pass = passive_length / 2.0
    passive = AntennaElement(
        x1=-spacing, y1=-half_pass, z1=0.0,
        x2=-spacing, y2= half_pass, z2=0.0,
        segments=segments, radius=radius,
    )
    model.add_element(passive)

    sim = AntennaSimulator()
    # 1) Feedpoint impedance vs height
    heights = [5.0, 10.0, 15.0, 20.0]
    print("Feedpoint impedance vs height (average ground):")
    imp_list = compute_impedance_vs_heights(sim, model, freq_mhz, heights, ground)
    print_impedance_table(imp_list)

    # 2) Compute elevation patterns and print gain table
    el_pats = compute_elevation_patterns(sim, model, freq_mhz, heights, ground)
    el_angles = list(range(0, 181, 5))
    print("\nGain at az=0 for el=0 to 180° (average ground), for various heights:")
    print_gain_table(el_pats, heights, el_angles)

    # 3) Compute azimuth patterns at fixed elevation and plot
    el_fixed = 30.0
    az_pats = compute_azimuth_patterns(sim, model, freq_mhz, heights, ground, el=el_fixed)

    # 5) Reflector detuning optimization: vary detune ratio from 0% to 10%
    print("\nDetune (%) | Fwd Gain (dBi) | F/B (dB)")
    results = []
    for detune in np.linspace(0, 0.10, 11):
        model_opt = AntennaModel()
        model_opt.add_element(driven)
        model_opt.add_feedpoint(element_index=0, segment=center_seg)
        detuned_length = driven_length * (1 + detune)
        half_detuned = detuned_length / 2.0
        reflector = AntennaElement(
            x1=-spacing, y1=-half_detuned, z1=0.0,
            x2=-spacing, y2= half_detuned, z2=0.0,
            segments=segments, radius=radius,
        )
        model_opt.add_element(reflector)
        az_res = sim.simulate_azimuth_pattern(
            model_opt, freq_mhz=freq_mhz, height_m=10.0,
            ground=ground, el=30.0, az_step=5.0
        )
        fwd_gain = next(p['gain'] for p in az_res if abs(p['az']) < 1e-6)
        back_gain = next(p['gain'] for p in az_res if abs(p['az'] - 180.0) < 1e-6)
        fbr = fwd_gain - back_gain
        results.append((detune, fwd_gain, fbr))
    # Find peaks
    max_fwd = max(results, key=lambda x: x[1])[1]
    max_fbr = max(results, key=lambda x: x[2])[2]
    for detune, fwd_gain, fbr in results:
        highlight = ""
        if abs(fwd_gain - max_fwd) < 1e-6:
            highlight += " <== max FWD"
        if abs(fbr - max_fbr) < 1e-6:
            highlight += " <== max F/B"
        print(f"{detune*100:8.2f} | {fwd_gain:14.2f} | {fbr:8.2f}{highlight}")

    # 4) Plot patterns
    plot_polar_patterns(el_pats, az_pats, heights, el_fixed, 'output/2_el_yagi_pattern.png', args.show_gui)

if __name__ == '__main__':
    main() 