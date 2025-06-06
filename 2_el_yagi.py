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
    compute_elevation_patterns,
    compute_azimuth_patterns,
    plot_polar_patterns,
    Report,
)
from typing import Dict, List
import os

# Build a 2-element Yagi model: a driven dipole and a passive reflector.
def build_two_element_yagi_model(
    freq_mhz: float,
    segments: int = 21,
    radius: float = 0.001,
    detune_frac: float = 0.05,
    spacing_frac: float = 0.2,
) -> AntennaModel:
    """
    Build a 2-element Yagi model: a driven dipole and a passive reflector.
    detune_frac: fractional increase of reflector length (e.g. 0.05 for 5% longer).
    spacing_frac: spacing between elements in wavelengths (e.g. 0.2 for 0.2λ).
    """
    c = 299792458.0
    wavelength_m = c / (freq_mhz * 1e6)
    spacing_m = spacing_frac * wavelength_m
    half_driven = resonant_dipole_length(freq_mhz) / 2.0
    passive_length = resonant_dipole_length(freq_mhz / (1.0 + detune_frac))
    half_passive = passive_length / 2.0
    model = AntennaModel()
    el1 = AntennaElement(
        x1=0.0, y1=-half_driven, z1=0.0,
        x2=0.0, y2= half_driven, z2=0.0,
        segments=segments, radius=radius,
    )
    model.add_element(el1)
    center_seg = (segments + 1) // 2
    model.add_feedpoint(element_index=0, segment=center_seg)
    el2 = AntennaElement(
        x1=-spacing_m, y1=-half_passive, z1=0.0,
        x2=-spacing_m, y2= half_passive, z2=0.0,
        segments=segments, radius=radius,
    )
    model.add_element(el2)
    return model

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
    # Use our build_two_element_yagi_model helper
    c = 299792458.0
    lambda_m = c / (freq_mhz * 1e6)
    model = build_two_element_yagi_model(freq_mhz, segments, radius)
    driven = model.elements[0]
    center_seg = (segments + 1) // 2
    sim = AntennaSimulator()

    # 1) Feedpoint impedance vs height
    heights = [5.0, 10.0, 15.0, 20.0]
    imp_list = compute_impedance_vs_heights(sim, model, freq_mhz, heights, ground)

    # Create report
    report = Report('2_el_yagi')
    report.add_table('Feedpoint Impedance vs Height', ['Height (m)', 'R (Ω)', 'X (Ω)'], imp_list, parameters="frequency = 14.1 MHz; detune = 5%; spacing = 0.20 λ; ground = average; segments = 21; radius = 0.001 m")

    # 2) Compute elevation patterns and build bolded gain table
    el_pats = compute_elevation_patterns(sim, model, freq_mhz, heights, ground)
    el_angles = list(range(0, 181, 5))
    # Build raw rows
    headers = ['Elevation (deg)'] + [f'{h:.1f} m' for h in heights]
    rows = []
    for el in el_angles:
        vals = [next((p['gain'] for p in el_pats[h] if abs(p['el'] - el) < 1e-6), '') for h in heights]
        rows.append([el] + vals)
    # Determine peak gain per height column
    peaks = []
    for col in range(1, len(headers)):
        col_vals = [r[col] for r in rows if isinstance(r[col], (int, float))]
        peaks.append(max(col_vals) if col_vals else None)
    # Format rows, bold peak values
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
    report.add_table('Gain at az=0 for Elevation 0–180°', headers, formatted_rows, parameters="frequency = 14.1 MHz; detune = 5%; spacing = 0.20 λ; ground = average; segments = 21; radius = 0.001 m; azimuth = 0°; heights = [5.0, 10.0, 15.0, 20.0] m")

    # 3) Compute azimuth patterns at fixed elevation and plot
    el_fixed = 30.0
    az_pats = compute_azimuth_patterns(sim, model, freq_mhz, heights, ground, el=el_fixed)

    # 5) Spacing sweep: Forward Gain and F/B tables across spacing fractions
    detunes = np.linspace(0.0, 0.10, 11)
    spacing_fracs = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
    # Build Forward Gain and F/B matrices
    fg_matrix = []
    fb_matrix = []
    for detune in detunes:
        detuned_len = driven_length * (1 + detune)
        half_detuned = detuned_len / 2.0
        fg_row = []
        fb_row = []
        for frac in spacing_fracs:
            spacing_val = frac * lambda_m
            m2 = AntennaModel()
            m2.add_element(driven)
            m2.add_feedpoint(element_index=0, segment=center_seg)
            ref = AntennaElement(
                x1=-spacing_val, y1=-half_detuned, z1=0.0,
                x2=-spacing_val, y2=half_detuned, z2=0.0,
                segments=segments, radius=radius,
            )
            m2.add_element(ref)
            az_res = sim.simulate_azimuth_pattern(
                m2, freq_mhz=freq_mhz, height_m=10.0,
                ground=ground, el=el_fixed, az_step=5.0
            )
            fwd = next(p['gain'] for p in az_res if abs(p['az']) < 1e-6)
            back = next(p['gain'] for p in az_res if abs(p['az'] - 180.0) < 1e-6)
            fg_row.append(fwd)
            fb_row.append(fwd - back)
        fg_matrix.append(fg_row)
        fb_matrix.append(fb_row)
    # Build sweep tables and add to report
    # Determine column peaks
    fg_peaks = [max(col) for col in zip(*fg_matrix)]
    fb_peaks = [max(col) for col in zip(*fb_matrix)]
    headers_sweep = ['Detune (%)', 'Reflector Length (λ)'] + [f'{frac:.2f}λ' for frac in spacing_fracs]
    # Forward Gain vs Detune (%) and Spacing
    rows_fg = []
    for i, detune in enumerate(detunes):
        # Reflector length in wavelengths: 0.5 * (1 + detune)
        refl_len_wl = 0.5 * (1 + detune)
        row = [f'{detune*100:.2f}', f'{refl_len_wl:.3f}']
        for j, val in enumerate(fg_matrix[i]):
            if abs(val - fg_peaks[j]) < 1e-6:
                row.append(f'**{val:.2f}**')
            else:
                row.append(f'{val:.2f}')
        rows_fg.append(row)
    report.add_table('Forward Gain vs Detune (%) and Spacing', headers_sweep, rows_fg, parameters="frequency = 14.1 MHz; detune steps = 0%–10% in 1% increments; spacing fractions = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40] λ; ground = average; segments = 21; radius = 0.001 m; height = 10.0 m; elevation = 30°")
    # Front-to-Back Ratio vs Detune (%) and Spacing
    rows_fb = []
    for i, detune in enumerate(detunes):
        # Reflector length in wavelengths: 0.5 * (1 + detune)
        refl_len_wl = 0.5 * (1 + detune)
        row = [f'{detune*100:.2f}', f'{refl_len_wl:.3f}']
        for j, val in enumerate(fb_matrix[i]):
            if abs(val - fb_peaks[j]) < 1e-6:
                row.append(f'**{val:.2f}**')
            else:
                row.append(f'{val:.2f}')
        rows_fb.append(row)
    report.add_table('Front-to-Back Ratio vs Detune (%) and Spacing', headers_sweep, rows_fb, parameters="frequency = 14.1 MHz; detune steps = 0%–10% in 1% increments; spacing fractions = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40] λ; ground = average; segments = 21; radius = 0.001 m; height = 10.0 m; elevation = 30°")

    # 6) Plot patterns (main az/el plot FIRST in report)
    output_file = os.path.join(report.report_dir, '2_el_yagi_pattern.png')
    plot_polar_patterns(el_pats, az_pats, heights, el_fixed, output_file, args.show_gui)
    report.add_plot('Azimuth and Elevation Plot (detune=6%, spacing=0.30λ)', output_file, parameters="frequency = 14.1 MHz; detune = 6%; spacing = 0.30 λ; ground = average; segments = 21; radius = 0.001 m; heights = [5.0, 10.0, 15.0, 20.0] m; elevation = 30°")

    # 6a) Comparison plot: Yagi vs Dipole at h=10m, detune=6%, spacing=0.3λ
    # Build Yagi model at detune=6%, spacing=0.3λ
    detune_cmp = 0.06
    spacing_cmp = 0.30
    yagi_len = driven_length * (1 + detune_cmp)
    half_yagi = yagi_len / 2.0
    spacing_val = spacing_cmp * lambda_m
    yagi_model = AntennaModel()
    yagi_model.add_element(driven)
    yagi_model.add_feedpoint(element_index=0, segment=center_seg)
    yagi_reflector = AntennaElement(
        x1=-spacing_val, y1=-half_yagi, z1=0.0,
        x2=-spacing_val, y2=half_yagi, z2=0.0,
        segments=segments, radius=radius,
    )
    yagi_model.add_element(yagi_reflector)
    # Dipole model
    from antenna_model import build_dipole_model
    dipole_model = build_dipole_model(total_length=driven_length, segments=segments, radius=radius)
    # Simulate both at h=10m
    cmp_height = 10.0
    cmp_heights = [cmp_height]
    yagi_el_pat = compute_elevation_patterns(sim, yagi_model, freq_mhz, cmp_heights, ground)[cmp_height]
    yagi_az_pat = compute_azimuth_patterns(sim, yagi_model, freq_mhz, cmp_heights, ground, el=el_fixed)[cmp_height]
    dipole_el_pat = compute_elevation_patterns(sim, dipole_model, freq_mhz, cmp_heights, ground)[cmp_height]
    dipole_az_pat = compute_azimuth_patterns(sim, dipole_model, freq_mhz, cmp_heights, ground, el=el_fixed)[cmp_height]
    cmp_elev_pats = {"Yagi": yagi_el_pat, "Dipole": dipole_el_pat}
    cmp_az_pats = {"Yagi": yagi_az_pat, "Dipole": dipole_az_pat}
    cmp_labels = ["Yagi (detune=6%, spacing=0.30λ)", "Dipole"]
    cmp_plot = os.path.join(report.report_dir, 'yagi_vs_dipole.png')
    plot_polar_patterns(cmp_elev_pats, cmp_az_pats, list(cmp_elev_pats.keys()), el_fixed, cmp_plot, args.show_gui, legend_labels=cmp_labels)
    report.add_plot('Yagi vs Dipole Comparison (h=10m, detune=6%, spacing=0.30λ)', cmp_plot, parameters="frequency = 14.1 MHz; height = 10.0 m; detune = 6%; spacing = 0.30 λ; ground = average; segments = 21; radius = 0.001 m")

    # 7) Spacing-sweep polar patterns at 6% detune, height 10m
    detune_fixed = 0.06
    spacing_elev_pats: Dict[float, List[Dict[str, float]]] = {}
    spacing_az_pats: Dict[float, List[Dict[str, float]]] = {}
    for frac in spacing_fracs:
        # Build detuned two-element model
        detuned_len = driven_length * (1 + detune_fixed)
        half_detuned = detuned_len / 2.0
        m2 = AntennaModel()
        # driven element
        m2.add_element(driven)
        m2.add_feedpoint(element_index=0, segment=center_seg)
        # passive element spaced by frac * λ
        spacing_val = frac * lambda_m
        ref = AntennaElement(
            x1=-spacing_val, y1=-half_detuned, z1=0.0,
            x2=-spacing_val, y2= half_detuned, z2=0.0,
            segments=segments, radius=radius,
        )
        m2.add_element(ref)
        # Simulate elevation (az=0) and azimuth (el=el_fixed) patterns
        res_e = sim.simulate_pattern(m2, freq_mhz=freq_mhz, height_m=10.0, ground=ground, el_step=5.0, az_step=360.0)
        spacing_elev_pats[frac] = res_e['pattern']
        spacing_az_pats[frac] = sim.simulate_azimuth_pattern(
            m2, freq_mhz=freq_mhz, height_m=10.0, ground=ground, el=el_fixed, az_step=5.0
        )
    # Plot spacing-sweep polar patterns
    sweep_plot = os.path.join(report.report_dir, 'spacing_sweep.png')
    spacing_labels = [f"d={frac:.2f}λ" for frac in spacing_fracs]
    plot_polar_patterns(spacing_elev_pats, spacing_az_pats, spacing_fracs, el_fixed, sweep_plot, args.show_gui, legend_labels=spacing_labels)
    report.add_plot('Spacing-Sweep Polar Patterns (h=10m, detune=6%)', sweep_plot, parameters="frequency = 14.1 MHz; height = 10.0 m; detune = 6%; spacing fractions = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40] λ; ground = average; segments = 21; radius = 0.001 m; elevation = 30°")

    # 8) Detune-sweep polar patterns at spacing=0.3λ, height 10m
    spacing_fixed = 0.30
    detune_steps = np.arange(0.0, 0.1001, 0.02)
    detune_elev_pats: Dict[float, List[Dict[str, float]]] = {}
    detune_az_pats: Dict[float, List[Dict[str, float]]] = {}
    for detune in detune_steps:
        detuned_len = driven_length * (1 + detune)
        half_detuned = detuned_len / 2.0
        m2 = AntennaModel()
        m2.add_element(driven)
        m2.add_feedpoint(element_index=0, segment=center_seg)
        spacing_val = spacing_fixed * lambda_m
        ref = AntennaElement(
            x1=-spacing_val, y1=-half_detuned, z1=0.0,
            x2=-spacing_val, y2=half_detuned, z2=0.0,
            segments=segments, radius=radius,
        )
        m2.add_element(ref)
        res_e = sim.simulate_pattern(m2, freq_mhz=freq_mhz, height_m=10.0, ground=ground, el_step=5.0, az_step=360.0)
        detune_elev_pats[detune] = res_e['pattern']
        detune_az_pats[detune] = sim.simulate_azimuth_pattern(
            m2, freq_mhz=freq_mhz, height_m=10.0, ground=ground, el=el_fixed, az_step=5.0
        )
    detune_plot = os.path.join(report.report_dir, 'detune_sweep.png')
    detune_labels = [f"{int(round(d*100))}%" for d in detune_steps]
    plot_polar_patterns(detune_elev_pats, detune_az_pats, detune_steps, el_fixed, detune_plot, args.show_gui, legend_labels=detune_labels)
    report.add_plot('Detune-Sweep Polar Patterns (h=10m, spacing=0.30λ)', detune_plot, parameters="frequency = 14.1 MHz; height = 10.0 m; spacing = 0.30 λ; detune steps = [0.00, 0.02, 0.04, 0.06, 0.08, 0.10]; ground = average; segments = 21; radius = 0.001 m; elevation = 30°")

    report.save()

if __name__ == '__main__':
    main() 