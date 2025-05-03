#!/usr/bin/env python3
"""
Generate radiation pattern of a half-wave dipole antenna at 30ft elevation and 14.1 MHz.
Usage: python3 dipole_pattern.py [--show-gui]
"""
import math
import argparse
import matplotlib.pyplot as plt
import numpy as np
from antenna_model import (
    build_dipole_model,
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
    parser = argparse.ArgumentParser(description="Dipole pattern analysis and plotting.")
    parser.add_argument('--show-gui', action='store_true', help='Show plot in GUI window instead of saving PNG')
    args = parser.parse_args()

    # Simulation setup
    freq_mhz = 14.1
    dipole_length = resonant_dipole_length(freq_mhz)
    segments = 21
    radius = 0.001
    model = build_dipole_model(total_length=dipole_length, segments=segments, radius=radius)
    sim = AntennaSimulator()
    ground = 'average'

    # 1) Feedpoint impedance vs height
    heights = [5, 10, 15, 20]
    print("Feedpoint impedance vs height (average ground):")
    imp_list = compute_impedance_vs_heights(sim, model, freq_mhz, heights, ground)
    print_impedance_table(imp_list)

    # 2) Gain tables and pattern computation
    el_pats = compute_elevation_patterns(sim, model, freq_mhz, heights, ground)
    el_angles = list(range(0, 181, 5))
    print("\nGain at az=0 for el=0 to 180 deg (average ground), for various heights:")
    print_gain_table(el_pats, heights, el_angles)

    # 3) Azimuth patterns at fixed elevation 30°
    el_fixed = 30.0
    az_pats = compute_azimuth_patterns(sim, model, freq_mhz, heights, ground, el=el_fixed)

    # 4) Plot patterns
    plot_polar_patterns(el_pats, az_pats, heights, el_fixed, 'output/pattern_comparison_all_heights.png', args.show_gui)

if __name__ == '__main__':
    main() 