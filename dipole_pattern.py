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
    compute_elevation_patterns,
    compute_azimuth_patterns,
    plot_polar_patterns,
    Report,
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
    imp_list = compute_impedance_vs_heights(sim, model, freq_mhz, heights, ground)

    # Initialize report
    report = Report('dipole_pattern')
    report.add_table('Feedpoint Impedance vs Height', ['Height (m)', 'R (Ω)', 'X (Ω)'], imp_list)

    # 2) Gain tables and pattern computation
    el_pats = compute_elevation_patterns(sim, model, freq_mhz, heights, ground)
    el_angles = list(range(0, 181, 5))
    # Build and bolded gain table
    headers = ['Elevation (deg)'] + [f'{h:.1f} m' for h in heights]
    rows = []
    for el in el_angles:
        row = [el]
        for h in heights:
            val = next((p['gain'] for p in el_pats[h] if abs(p['el'] - el) < 1e-6), '')
            row.append(val)
        rows.append(row)
    # Determine peaks per height column
    peaks = []
    for col_idx in range(1, len(headers)):
        col_vals = [r[col_idx] for r in rows if isinstance(r[col_idx], (int, float))]
        peaks.append(max(col_vals) if col_vals else None)
    # Format rows with bold peaks
    formatted_rows = []
    for r in rows:
        fr = [r[0]]
        for idx, val in enumerate(r[1:], start=1):
            if isinstance(val, (int, float)) and peaks[idx-1] is not None and abs(val - peaks[idx-1]) < 1e-6:
                fr.append(f"**{val:.3f}**")
            elif isinstance(val, (int, float)):
                fr.append(f"{val:.3f}")
            else:
                fr.append('')
        formatted_rows.append(fr)
    report.add_table('Gain at az=0 for Elevation 0–180°', headers, formatted_rows)

    # 3) Azimuth patterns at fixed elevation 30°
    el_fixed = 30.0
    az_pats = compute_azimuth_patterns(sim, model, freq_mhz, heights, ground, el=el_fixed)

    # 4) Plot patterns
    output_file = 'output/pattern_comparison_all_heights.png'
    plot_polar_patterns(el_pats, az_pats, heights, el_fixed, output_file, args.show_gui)
    report.add_plot(f'Azimuth Pattern (el={int(el_fixed)}°)', output_file)
    report.save()

if __name__ == '__main__':
    main() 