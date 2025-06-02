#!/usr/bin/env python3
"""
Model a center-fed dipole antenna at 10m elevation for 66', 88', and 132' lengths.
Measure pattern (azimuth/elevation) and feedpoint impedance at 3.5MHz and 7.1MHz.
"""
import argparse
import os
import matplotlib.pyplot as plt
import numpy as np
from antenna_model import (
    build_dipole_model,
    AntennaSimulator,
    feet_to_meters,
    compute_elevation_patterns,
    compute_azimuth_patterns,
    plot_polar_patterns,
    Report,
)

def main():
    parser = argparse.ArgumentParser(description="40/80m multiband dipole pattern and impedance analysis.")
    parser.add_argument('--show-gui', action='store_true', help='Show plot in GUI window instead of saving PNG')
    args = parser.parse_args()

    lengths_ft = [66, 88, 96, 102]
    lengths_m = [feet_to_meters(l) for l in lengths_ft]
    freqs_mhz = [3.5, 7.1]
    height_m = 10.0
    segments = 21
    radius = 0.001
    ground = 'average'
    sim = AntennaSimulator()

    report = Report('40_80_multiband')

    for freq in freqs_mhz:
        imp_rows = []
        el_pats = {}
        az_pats = {}
        for l_ft, l_m in zip(lengths_ft, lengths_m):
            seg_count = segments
            model = build_dipole_model(total_length=l_m, segments=seg_count, radius=radius)
            # Feedpoint impedance
            res = sim.simulate_pattern(model, freq_mhz=freq, height_m=height_m, ground=ground, el_step=5, az_step=360)
            R, X = res['impedance']
            imp_rows.append([f"{l_ft}'", f"{l_m:.2f}", f"{R:.2f}", f"{X:.2f}"])
            # Elevation and azimuth patterns
            el_pat = sim.simulate_pattern(model, freq_mhz=freq, height_m=height_m, ground=ground, el_step=5, az_step=360)['pattern']
            az_pat = sim.simulate_azimuth_pattern(model, freq, height_m=height_m, ground=ground, el=30.0, az_step=5.0)
            el_pats[l_ft] = el_pat
            az_pats[l_ft] = az_pat
        # Table: Feedpoint impedance
        report.add_table(
            f'Feedpoint Impedance at 10m (f={freq} MHz)',
            ['Length (ft)', 'Length (m)', 'R (Ω)', 'X (Ω)'],
            imp_rows,
            parameters=f"frequency = {freq} MHz; height = 10 m; ground = average; segments = {segments}; radius = {radius} m"
        )
        # Table: Elevation gain at az=0
        el_angles = list(range(0, 181, 5))
        headers = ['Elevation (deg)'] + [f"{l_ft}'" for l_ft in lengths_ft]
        rows = []
        for el in el_angles:
            row = [el]
            for l_ft in lengths_ft:
                val = next((p['gain'] for p in el_pats[l_ft] if abs(p['el'] - el) < 1e-6 and abs(p['az']) < 1e-6), '')
                row.append(f"{val:.3f}" if val != '' else '')
            rows.append(row)
        # Bold peak gain per column
        peaks = []
        for col in range(1, len(headers)):
            col_vals = [float(r[col]) for r in rows if r[col] != '']
            peaks.append(max(col_vals) if col_vals else None)
        formatted_rows = []
        for r in rows:
            fr = [r[0]]
            for idx, val in enumerate(r[1:], start=1):
                if val != '' and peaks[idx-1] is not None and abs(float(val) - peaks[idx-1]) < 1e-6:
                    fr.append(f"**{val}**")
                else:
                    fr.append(val)
            formatted_rows.append(fr)
        report.add_table(
            f'Gain at az=0 for Elevation 0–180° (f={freq} MHz)',
            headers,
            formatted_rows,
            parameters=f"frequency = {freq} MHz; height = 10 m; ground = average; segments = {segments}; radius = {radius} m; azimuth = 0°"
        )
        # Azimuth gain values at elevation 30°
        az_headers = ['Azimuth (deg)'] + [f"{l_ft}'" for l_ft in lengths_ft]
        az_rows = []
        # assume all patterns share the same azimuth angles
        az_angles = [p['az'] for p in az_pats[lengths_ft[0]]]
        for az in az_angles:
            row = [az]
            for l_ft in lengths_ft:
                g = next((p['gain'] for p in az_pats[l_ft] if abs(p['az'] - az) < 1e-6), None)
                row.append(f"{g:.3f}" if g is not None else '')
            az_rows.append(row)
        report.add_table(
            f'Azimuth Gain at el=30° (f={freq} MHz)',
            az_headers,
            az_rows,
            parameters=f"frequency = {freq} MHz; height = {height_m} m; ground = {ground}; segments = {segments}; radius = {radius} m; elevation = 30°"
        )
        # Polar pattern plots for each length using shared routine
        polar_plot_path = os.path.join(report.report_dir, f'polar_patterns_{freq:.1f}MHz.png')
        plot_polar_patterns(
            el_pats,
            az_pats,
            lengths_ft,
            30.0,
            polar_plot_path,
            args.show_gui,
            legend_labels=[f"{l_ft}'" for l_ft in lengths_ft],
        )
        report.add_plot(
            f'Polar Patterns (f={freq} MHz)',
            polar_plot_path,
            parameters=f'frequency = {freq} MHz; height = {height_m} m; ground = average; segments = {segments}; radius = {radius} m; el=30°; az=0°'
        )
        report.save()

if __name__ == '__main__':
    main() 