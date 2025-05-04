#!/usr/bin/env python3
"""
Generate radiation pattern and impedance data for an 8JK antenna:
Two driven elements each 44 ft long, spaced 6 m apart, 180° out-of-phase.
Usage: python3 8_jk.py [--show-gui]
"""
import argparse
import os
import numpy as np
import matplotlib.pyplot as plt
from antenna_model import (
    AntennaModel,
    AntennaElement,
    AntennaSimulator,
    feet_to_meters,
    build_dipole_model,
    compute_impedance_vs_heights,
    compute_elevation_patterns,
    compute_azimuth_patterns,
    plot_polar_patterns,
    Report,
)

def main():
    parser = argparse.ArgumentParser(description="8JK antenna pattern analysis and plotting.")
    parser.add_argument('--show-gui', action='store_true', help='Show plots interactively instead of saving')
    args = parser.parse_args()

    # Simulation setup
    freq_mhz = 14.1
    segments = 21
    radius = 0.001
    ground = 'average'

    # Geometry: two 44 ft elements
    element_length_ft = 44.0
    length_m = feet_to_meters(element_length_ft)
    half_len = length_m / 2.0
    spacing_m = 6.0  # 0.3 λ on 20 m band (approximately)

    # Build the 8JK model
    model = AntennaModel()
    # Element 1 at origin
    el1 = AntennaElement(
        x1=0.0, y1=-half_len, z1=0.0,
        x2=0.0, y2= half_len, z2=0.0,
        segments=segments, radius=radius,
    )
    model.add_element(el1)
    # Element 2 offset along x-axis by spacing_m
    el2 = AntennaElement(
        x1=spacing_m, y1=-half_len, z1=0.0,
        x2=spacing_m, y2= half_len, z2=0.0,
        segments=segments, radius=radius,
    )
    model.add_element(el2)

    # Feed both elements: element 0 at 0°, element 1 at 180° phase shift
    center_seg = (segments + 1) // 2
    # Drive with complex voltages (+1 and -1) for 180° phasing
    model.add_feedpoint(0, center_seg, voltage=1+0j)
    model.add_feedpoint(1, center_seg, voltage=-1+0j)

    sim = AntennaSimulator()
    heights = [5.0, 10.0, 15.0, 20.0]

    # 1) Feedpoint Impedance vs Height
    imp_list = compute_impedance_vs_heights(sim, model, freq_mhz, heights, ground)
    report = Report('8_jk')
    report.add_table('Feedpoint Impedance vs Height', ['Height (m)', 'R (Ω)', 'X (Ω)'], imp_list)

    # 2) Elevation patterns and gain table
    el_pats = compute_elevation_patterns(sim, model, freq_mhz, heights, ground)
    el_angles = list(range(0, 181, 5))
    headers = ['Elevation (deg)'] + [f'{h:.1f} m' for h in heights]
    rows = []
    for el in el_angles:
        vals = [next((p['gain'] for p in el_pats[h] if abs(p['el'] - el) < 1e-6), '') for h in heights]
        rows.append([el] + vals)
    # Bold peak gain per column
    peaks = []
    for col in range(1, len(headers)):
        col_vals = [r[col] for r in rows if isinstance(r[col], (int, float))]
        peaks.append(max(col_vals) if col_vals else None)
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

    # 3) Azimuth patterns at fixed elevation
    el_fixed = 30.0
    az_pats = compute_azimuth_patterns(sim, model, freq_mhz, heights, ground, el=el_fixed)

    # 4) Polar patterns plot
    output_file = os.path.join(report.report_dir, '8_jk_pattern.png')
    plot_polar_patterns(el_pats, az_pats, heights, el_fixed, output_file, args.show_gui)
    report.add_plot('Azimuth and Elevation Patterns', output_file)

    # 5) Comparison with a simple dipole at h=10m
    dipole_model = build_dipole_model(total_length=length_m, segments=segments, radius=radius)
    cmp_height = 10.0
    cmp_heights = [cmp_height]
    jk_el_cmp = compute_elevation_patterns(sim, model, freq_mhz, cmp_heights, ground)[cmp_height]
    jk_az_cmp = compute_azimuth_patterns(sim, model, freq_mhz, cmp_heights, ground, el=el_fixed)[cmp_height]
    dip_el_cmp = compute_elevation_patterns(sim, dipole_model, freq_mhz, cmp_heights, ground)[cmp_height]
    dip_az_cmp = compute_azimuth_patterns(sim, dipole_model, freq_mhz, cmp_heights, ground, el=el_fixed)[cmp_height]

    # Manual comparison polar plot
    fig, (ax_el_cmp, ax_az_cmp) = plt.subplots(1, 2, subplot_kw={'polar': True}, figsize=(14, 7))
    # Elevation comparison
    raw_max_el = max(max(p['gain'] for p in jk_el_cmp), max(p['gain'] for p in dip_el_cmp))
    for label, pat in [('8JK', jk_el_cmp), ('Dipole', dip_el_cmp)]:
        data = sorted(pat, key=lambda p: p['el'])
        theta = np.radians([p['el'] for p in data])
        r = [0.89 ** ((raw_max_el - p['gain']) / 2.0) for p in data]
        ax_el_cmp.plot(theta, r, label=label)
    ax_el_cmp.set_title('Elevation Comparison (az=0)')
    ax_el_cmp.legend()
    # Azimuth comparison
    raw_max_az = max(max(p['gain'] for p in jk_az_cmp), max(p['gain'] for p in dip_az_cmp))
    for label, pat in [('8JK', jk_az_cmp), ('Dipole', dip_az_cmp)]:
        data = sorted(pat, key=lambda p: p['az'])
        phi = np.radians([p['az'] for p in data])
        r = [0.89 ** ((raw_max_az - p['gain']) / 2.0) for p in data]
        ax_az_cmp.plot(phi, r, label=label)
    ax_az_cmp.set_title(f'Azimuth Comparison (el={int(el_fixed)}°)')
    ax_az_cmp.legend()
    plt.tight_layout()
    output_cmp = os.path.join(report.report_dir, '8_jk_vs_dipole.png')
    if args.show_gui:
        plt.show()
    else:
        plt.savefig(output_cmp)
    report.add_plot('8JK vs Dipole Comparison', output_cmp)

    report.save()

if __name__ == '__main__':
    main() 