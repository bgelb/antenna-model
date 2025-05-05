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
    configure_polar_axes,
    Report,
    resonant_dipole_length,
)
import importlib.util

# Dynamically import build_two_element_yagi_model from 2_el_yagi.py
spec = importlib.util.spec_from_file_location(
    "two_el_yagi",
    os.path.join(os.path.dirname(__file__), "2_el_yagi.py")
)
two_el_yagi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(two_el_yagi)
build_two_element_yagi_model = two_el_yagi.build_two_element_yagi_model

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

    # Build additional 8JK model with half-wave dipoles
    half_wl = resonant_dipole_length(freq_mhz)  # full half-wave dipole length
    half_len_wl = half_wl / 2.0
    model_half = AntennaModel()
    # Element 1 (half-wave) at origin
    el1_hw = AntennaElement(
        x1=0.0, y1=-half_len_wl, z1=0.0,
        x2=0.0, y2= half_len_wl, z2=0.0,
        segments=segments, radius=radius,
    )
    model_half.add_element(el1_hw)
    # Element 2 offset along x-axis by same spacing
    el2_hw = AntennaElement(
        x1=spacing_m, y1=-half_len_wl, z1=0.0,
        x2=spacing_m, y2= half_len_wl, z2=0.0,
        segments=segments, radius=radius,
    )
    model_half.add_element(el2_hw)
    # Feed half-wave model
    model_half.add_feedpoint(0, center_seg, voltage=1+0j)
    model_half.add_feedpoint(1, center_seg, voltage=-1+0j)

    sim = AntennaSimulator()
    heights = [5.0, 10.0, 15.0, 20.0]

    # 1) Feedpoint Impedance vs Height (44' elements)
    imp_list = compute_impedance_vs_heights(sim, model, freq_mhz, heights, ground)
    report = Report('8_jk')
    report.add_table("Feedpoint Impedance vs Height (8JK - 44')", ['Height (m)', 'R (Ω)', 'X (Ω)'], imp_list)
    # 1a) Feedpoint Impedance vs Height (8JK - 0.5 wl)
    imp_list_hw = compute_impedance_vs_heights(sim, model_half, freq_mhz, heights, ground)
    report.add_table('Feedpoint Impedance vs Height (8JK - 0.5 wl)', ['Height (m)', 'R (Ω)', 'X (Ω)'], imp_list_hw)

    # 2) Elevation patterns and gain table (44' elements)
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
    report.add_table('Gain at az=0 for Elevation 0–180° (8JK - 44\')', headers, formatted_rows)
    # 2a) Elevation patterns and gain table (8JK - 0.5 wl)
    el_pats_hw = compute_elevation_patterns(sim, model_half, freq_mhz, heights, ground)
    rows_hw = []
    for el in el_angles:
        vals = [next((p['gain'] for p in el_pats_hw[h] if abs(p['el'] - el) < 1e-6), '') for h in heights]
        rows_hw.append([el] + vals)
    # Bold peaks per height for half-wave
    peaks_hw = []
    for col in range(1, len(headers)):
        col_vals = [r[col] for r in rows_hw if isinstance(r[col], (int, float))]
        peaks_hw.append(max(col_vals) if col_vals else None)
    formatted_hw = []
    for r in rows_hw:
        fr = [r[0]]
        for idx, val in enumerate(r[1:], start=1):
            if isinstance(val, (int, float)) and peaks_hw[idx-1] is not None and abs(val - peaks_hw[idx-1]) < 1e-6:
                fr.append(f"**{val:.3f}**")
            elif isinstance(val, (int, float)):
                fr.append(f"{val:.3f}")
            else:
                fr.append('')
        formatted_hw.append(fr)
    report.add_table('Gain at az=0 for Elevation 0–180° (8JK - 0.5 wl)', headers, formatted_hw)

    # 3) Azimuth patterns at fixed elevation
    el_fixed = 30.0
    az_pats = compute_azimuth_patterns(sim, model, freq_mhz, heights, ground, el=el_fixed)

    # 4) Polar patterns plot (44' elements)
    output_file = os.path.join(report.report_dir, '8_jk_pattern.png')
    plot_polar_patterns(el_pats, az_pats, heights, el_fixed, output_file, args.show_gui)
    report.add_plot('Azimuth and Elevation Patterns (8JK - 44\')', output_file)
    # 4a) Polar patterns plot for half-wave model
    el_pats_hw = el_pats_hw
    az_pats_hw = compute_azimuth_patterns(sim, model_half, freq_mhz, heights, ground, el=el_fixed)
    output_hw = os.path.join(report.report_dir, '8_jk_pattern_05wl.png')
    plot_polar_patterns(el_pats_hw, az_pats_hw, heights, el_fixed, output_hw, args.show_gui)
    report.add_plot('Azimuth and Elevation Patterns (8JK - 0.5 wl)', output_hw)

    # 5) Comparison with dipole and Yagi at h=10m
    cmp_height = 10.0
    cmp_heights = [cmp_height]
    # Patterns for 44' 8JK
    jk_el_cmp = compute_elevation_patterns(sim, model, freq_mhz, cmp_heights, ground)[cmp_height]
    jk_az_cmp = compute_azimuth_patterns(sim, model, freq_mhz, cmp_heights, ground, el=el_fixed)[cmp_height]
    # Patterns for 0.5 wl dipole
    dip05 = build_dipole_model(total_length=resonant_dipole_length(freq_mhz), segments=segments, radius=radius)
    dip05_el = compute_elevation_patterns(sim, dip05, freq_mhz, cmp_heights, ground)[cmp_height]
    dip05_az = compute_azimuth_patterns(sim, dip05, freq_mhz, cmp_heights, ground, el=el_fixed)[cmp_height]
    # Patterns for 2-element Yagi (6% detune, 0.3 wl spacing)
    yagi_model = build_two_element_yagi_model(freq_mhz, segments, radius, detune_frac=0.06, spacing_frac=0.3)
    yagi_el = compute_elevation_patterns(sim, yagi_model, freq_mhz, cmp_heights, ground)[cmp_height]
    yagi_az = compute_azimuth_patterns(sim, yagi_model, freq_mhz, cmp_heights, ground, el=el_fixed)[cmp_height]

    # Combined comparison polar plot: 8JK 44', 8JK 0.5 wl, Dipole 0.5 wl, Yagi (6%,0.3 wl)
    fig, (ax_el_cmp, ax_az_cmp) = plt.subplots(1, 2, subplot_kw={'polar': True}, figsize=(14, 7))
    # Prepare patterns
    jk44_el = jk_el_cmp; jk44_az = jk_az_cmp
    jk05_el = el_pats_hw[cmp_height]
    jk05_az = compute_azimuth_patterns(sim, model_half, freq_mhz, [cmp_height], ground, el=el_fixed)[cmp_height]
    dip05_el = dip05_el; dip05_az = dip05_az
    yagi_el = yagi_el; yagi_az = yagi_az
    # Elevation comparison
    raw_max_el_all = max(
        max(p['gain'] for p in jk44_el),
        max(p['gain'] for p in jk05_el),
        max(p['gain'] for p in dip05_el),
        max(p['gain'] for p in yagi_el),
    )
    configure_polar_axes(ax_el_cmp, 'Elevation Comparison (az=0)', raw_max_el_all)
    for label, pat in [
        ("8JK - 44'", jk44_el),
        ("8JK - 0.5 wl", jk05_el),
        ("Dipole - 0.5 wl", dip05_el),
        ("Yagi (6%,0.3 wl)", yagi_el),
    ]:
        data = sorted(pat, key=lambda p: p['el'])
        theta = np.radians([p['el'] for p in data])
        r = [0.89 ** ((raw_max_el_all - p['gain']) / 2.0) for p in data]
        ax_el_cmp.plot(theta, r, label=label)
    ax_el_cmp.legend(loc='upper right', bbox_to_anchor=(1.2, 1.1))
    # Azimuth comparison
    raw_max_az_all = max(
        max(p['gain'] for p in jk44_az),
        max(p['gain'] for p in jk05_az),
        max(p['gain'] for p in dip05_az),
        max(p['gain'] for p in yagi_az),
    )
    configure_polar_axes(ax_az_cmp, f'Azimuth Comparison (el={int(el_fixed)}°)', raw_max_az_all, direction=-1)
    for label, pat in [
        ("8JK - 44'", jk44_az),
        ("8JK - 0.5 wl", jk05_az),
        ("Dipole - 0.5 wl", dip05_az),
        ("Yagi (6%,0.3 wl)", yagi_az),
    ]:
        data = sorted(pat, key=lambda p: p['az'])
        phi = np.radians([p['az'] for p in data])
        r = [0.89 ** ((raw_max_az_all - p['gain']) / 2.0) for p in data]
        ax_az_cmp.plot(phi, r, label=label)
    ax_az_cmp.legend(loc='upper right', bbox_to_anchor=(1.2, 1.1))
    plt.tight_layout()
    output_comb = os.path.join(report.report_dir, '8_jk_vs_dipole_vs_yagi_combined.png')
    if args.show_gui:
        plt.show()
    else:
        plt.savefig(output_comb)
    report.add_plot("8JK vs Dipole vs Yagi Comparison", output_comb)

    # 6) Forward gain table at elevation 15°–35° in 5° steps
    fwd_els = list(range(15, 36, 5))
    fwd_rows = []
    for el in fwd_els:
        row = [el]
        for pat in [jk44_el, jk05_el, dip05_el, yagi_el]:
            gain = next(p['gain'] for p in pat if abs(p['el'] - el) < 1e-6)
            row.append(f"{gain:.3f}")
        fwd_rows.append(row)
    fwd_headers = ["Elevation (deg)", "8JK - 44'", "8JK - 0.5 wl", "Dipole - 0.5 wl", "Yagi (6%,0.3 wl)"]
    report.add_table("Forward Gain vs Elevation (15°–35°)", fwd_headers, fwd_rows)

    report.save()

if __name__ == '__main__':
    main() 