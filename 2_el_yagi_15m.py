#!/usr/bin/env python3
"""
Simulate a 2-element Yagi for 15m (21 MHz), sweeping boom length from 2 to 8 feet in 1 ft increments.
For each boom length, optimize the reflector detune for both max forward gain and max F/B ratio.
Outputs tables and plots similar to 2_el_yagi.py, focusing on half-wavelength height.
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
    build_dipole_model,
    compute_elevation_patterns,
    compute_azimuth_patterns,
    plot_polar_patterns,
    Report,
)
import os

# Constants
FEET_TO_METERS = 0.3048
FREQ_MHZ = 21.0
SEGMENTS = 21
RADIUS = 0.001
GROUND = 'average'
c = 299792458.0
wavelength_m_global = c / (FREQ_MHZ * 1e6)
HEIGHT_M = 0.5 * wavelength_m_global  # 0.5 λ height (~half-wavelength)

# Helper to build Yagi

def build_two_element_yagi_model(freq_mhz, detune_frac, spacing_m, segments=SEGMENTS, radius=RADIUS):
    driven_length = resonant_dipole_length(freq_mhz)
    half_driven = driven_length / 2.0
    passive_length = resonant_dipole_length(freq_mhz / (1.0 + detune_frac))
    half_passive = passive_length / 2.0
    model = AntennaModel()
    el1 = AntennaElement(
        x1=0.0, y1=-half_driven, z1=0.0,
        x2=0.0, y2=half_driven, z2=0.0,
        segments=segments, radius=radius,
    )
    model.add_element(el1)
    center_seg = (segments + 1) // 2
    model.add_feedpoint(element_index=0, segment=center_seg)
    el2 = AntennaElement(
        x1=-spacing_m, y1=-half_passive, z1=0.0,
        x2=-spacing_m, y2=half_passive, z2=0.0,
        segments=segments, radius=radius,
    )
    model.add_element(el2)
    return model

def main():
    parser = argparse.ArgumentParser(description="2-el Yagi 15m optimization sweep")
    parser.add_argument('--show-gui', action='store_true', help='Show plots interactively instead of saving')
    args = parser.parse_args()

    wavelength_m = wavelength_m_global
    driven_length = resonant_dipole_length(FREQ_MHZ)
    center_seg = (SEGMENTS + 1) // 2
    sim = AntennaSimulator()

    # Sweep boom length (spacing) in 1 ft increments from 2 to 10 ft
    boom_lengths_ft = np.arange(2, 11, 1)  # 2, 3, ..., 10
    boom_lengths_m = boom_lengths_ft * FEET_TO_METERS
    boom_lengths_lambda = boom_lengths_m / wavelength_m

    detune_fracs = np.linspace(0.00, 0.10, 21)  # 0% to 10% in 0.5% steps

    # Store results
    results = []  # Each entry: dict with boom_ft, boom_m, boom_lambda, best_gain, best_gain_detune, best_fb, best_fb_detune
    sweep_table = []  # For detailed table: boom_ft, detune, gain, fb

    for boom_ft, boom_m, boom_lam in zip(boom_lengths_ft, boom_lengths_m, boom_lengths_lambda):
        best_gain = -999
        best_gain_detune = None
        best_fb = -999
        best_fb_detune = None
        gain_vs_detune = []
        fb_vs_detune = []
        for detune in detune_fracs:
            model = build_two_element_yagi_model(FREQ_MHZ, detune, boom_m)
            az_pat = sim.simulate_azimuth_pattern(
                model, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el=30.0, az_step=5.0
            )
            fwd = next(p['gain'] for p in az_pat if abs(p['az']) < 1e-6)
            back = next(p['gain'] for p in az_pat if abs(p['az'] - 180.0) < 1e-6)
            fb = fwd - back
            gain_vs_detune.append(fwd)
            fb_vs_detune.append(fb)
            sweep_table.append([boom_ft, detune, fwd, fb])
            if fwd > best_gain:
                best_gain = fwd
                best_gain_detune = detune
            if fb > best_fb:
                best_fb = fb
                best_fb_detune = detune
        results.append({
            'boom_ft': boom_ft,
            'boom_m': boom_m,
            'boom_lambda': boom_lam,
            'best_gain': best_gain,
            'best_gain_detune': best_gain_detune,
            'best_fb': best_fb,
            'best_fb_detune': best_fb_detune,
            'gain_vs_detune': gain_vs_detune,
            'fb_vs_detune': fb_vs_detune,
        })

    # Create report
    report = Report('2_el_yagi_15m')

    # Table: Best gain and F/B for each boom length
    table_rows = []
    for r in results:
        boom_annot = f"{r['boom_ft']:.1f} ({r['boom_lambda']:.3f}λ)"
        table_rows.append([
            boom_annot,
            f"{r['best_gain']:.2f}",
            f"{r['best_gain_detune']*100:.2f}",
            f"{r['best_fb']:.2f}",
            f"{r['best_fb_detune']*100:.2f}",
        ])
    report.add_table(
        'Best Gain and F/B vs Boom Length',
        ['Boom (ft, λ)', 'Max Gain (dBi)', 'Detune for Max Gain (%)', 'Max F/B (dB)', 'Detune for Max F/B (%)'],
        table_rows,
        parameters=f"frequency = {FREQ_MHZ} MHz; height = {HEIGHT_M:.2f} m (~0.5λ); ground = {GROUND}; segments = {SEGMENTS}; radius = {RADIUS} m; elevation = 30° (azimuth pattern)"
    )

    # === Detune vs Spacing sweep tables (mirrors original 20 m script) ===
    detune_steps = np.arange(0.00, 0.11, 0.01)  # 0–10 % in 1 % steps
    spacing_fracs = [0.05, 0.075, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]

    fg_matrix = []  # forward gain (dBi)
    fb_matrix = []  # F/B (dB)

    # Pre-build the driven element once
    half_driven_len = driven_length / 2.0
    driven_elem = AntennaElement(
        x1=0.0, y1=-half_driven_len, z1=0.0,
        x2=0.0, y2=half_driven_len, z2=0.0,
        segments=SEGMENTS, radius=RADIUS,
    )

    for detune in detune_steps:
        # Lengthen reflector
        passive_length = resonant_dipole_length(FREQ_MHZ / (1.0 + detune))
        half_passive_len = passive_length / 2.0

        fg_row = []
        fb_row = []
        for frac in spacing_fracs:
            spacing_m = frac * wavelength_m

            model = AntennaModel()
            model.add_element(driven_elem)
            model.add_feedpoint(element_index=0, segment=center_seg)
            # Reflector
            ref = AntennaElement(
                x1=-spacing_m, y1=-half_passive_len, z1=0.0,
                x2=-spacing_m, y2=half_passive_len, z2=0.0,
                segments=SEGMENTS, radius=RADIUS,
            )
            model.add_element(ref)

            az_res = sim.simulate_azimuth_pattern(
                model, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el=30.0, az_step=5.0
            )
            fwd = next(p['gain'] for p in az_res if abs(p['az']) < 1e-6)
            back = next(p['gain'] for p in az_res if abs(p['az'] - 180.0) < 1e-6)
            fg_row.append(fwd)
            fb_row.append(fwd - back)
        fg_matrix.append(fg_row)
        fb_matrix.append(fb_row)

    # Bold peaks per spacing column
    fg_peaks = [max(col) for col in zip(*fg_matrix)]
    fb_peaks = [max(col) for col in zip(*fb_matrix)]

    headers_sweep = ['Detune (%)', 'Reflector Length (λ)'] + [
        f"{frac:.2f}λ ({(frac * wavelength_m * 3.28084):.1f} ft)" for frac in spacing_fracs
    ]

    # Forward Gain table
    rows_fg = []
    for i, detune in enumerate(detune_steps):
        refl_len_wl = 0.5 * (1 + detune)
        row = [f'{detune*100:.2f}', f'{refl_len_wl:.3f}']
        for j, val in enumerate(fg_matrix[i]):
            if abs(val - fg_peaks[j]) < 1e-6:
                row.append(f'**{val:.2f}**')
            else:
                row.append(f'{val:.2f}')
        rows_fg.append(row)

    report.add_table(
        'Forward Gain vs Detune (%) and Spacing',
        headers_sweep,
        rows_fg,
        parameters=f"frequency = {FREQ_MHZ} MHz; detune steps = 0%–10% in 1% increments; spacing fractions = {spacing_fracs} λ; ground = {GROUND}; segments = {SEGMENTS}; radius = {RADIUS} m; height = {HEIGHT_M:.1f} m (~0.5λ); elevation = 30°"
    )

    # F/B table
    rows_fb = []
    for i, detune in enumerate(detune_steps):
        refl_len_wl = 0.5 * (1 + detune)
        row = [f'{detune*100:.2f}', f'{refl_len_wl:.3f}']
        for j, val in enumerate(fb_matrix[i]):
            if abs(val - fb_peaks[j]) < 1e-6:
                row.append(f'**{val:.2f}**')
            else:
                row.append(f'{val:.2f}')
        rows_fb.append(row)

    report.add_table(
        'Front-to-Back Ratio vs Detune (%) and Spacing',
        headers_sweep,
        rows_fb,
        parameters=f"frequency = {FREQ_MHZ} MHz; detune steps = 0%–10% in 1% increments; spacing fractions = {spacing_fracs} λ; ground = {GROUND}; segments = {SEGMENTS}; radius = {RADIUS} m; height = {HEIGHT_M:.1f} m (~0.5λ); elevation = 30°"
    )

    # --- Half-wave dipole reference at same height/elevation ---
    dipole_length = resonant_dipole_length(FREQ_MHZ)
    dipole_model = build_dipole_model(total_length=dipole_length, segments=SEGMENTS, radius=RADIUS)
    dip_az = sim.simulate_azimuth_pattern(dipole_model, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el=30.0, az_step=5.0)
    dip_fwd_gain = next(p['gain'] for p in dip_az if abs(p['az']) < 1e-6)
    dip_back_gain = next(p['gain'] for p in dip_az if abs(p['az'] - 180.0) < 1e-6)
    dip_fb = dip_fwd_gain - dip_back_gain

    # --- Half-wave dipole reference table ---
    report.add_table(
        'Half-wave Dipole Reference',
        ['Gain (dBi)', 'F/B (dB)'],
        [[f"{dip_fwd_gain:.2f}", f"{dip_fb:.2f}"]],
        parameters=f"frequency = {FREQ_MHZ} MHz; height = {HEIGHT_M:.2f} m (~0.5λ); ground = {GROUND}; segments = {SEGMENTS}; radius = {RADIUS} m; elevation = 30°"
    )

    # === Polar pattern comparison for spacing subset (0.05–0.20 λ) ===
    spacing_subset = [f for f in spacing_fracs if 0.05 <= f <= 0.20]
    idx_subset = [spacing_fracs.index(f) for f in spacing_subset]
    # Lists to track optimal detunes
    detune_gain_list = []
    detune_fb_list = []

    spacing_elev_gain = {}
    spacing_az_gain = {}
    spacing_elev_fb = {}
    spacing_az_fb = {}

    for j_idx, frac in zip(idx_subset, spacing_subset):
        # Determine detune for max gain and max F/B
        best_gain = fg_peaks[j_idx]
        i_detune_gain = next(i for i, val in enumerate(fg_matrix) if abs(val[j_idx] - best_gain) < 1e-6)
        detune_gain = detune_steps[i_detune_gain]
        detune_gain_list.append(detune_gain)

        best_fb = fb_peaks[j_idx]
        i_detune_fb = next(i for i, val in enumerate(fb_matrix) if abs(val[j_idx] - best_fb) < 1e-6)
        detune_fb = detune_steps[i_detune_fb]
        detune_fb_list.append(detune_fb)

        # Build model for best gain
        passive_len_gain = resonant_dipole_length(FREQ_MHZ / (1.0 + detune_gain))
        half_passive_gain = passive_len_gain / 2.0
        # Build model for best F/B
        passive_len_fb = resonant_dipole_length(FREQ_MHZ / (1.0 + detune_fb))
        half_passive_fb = passive_len_fb / 2.0

        spacing_m = frac * wavelength_m

        # ---- Best gain model ----
        model = AntennaModel()
        model.add_element(driven_elem)
        model.add_feedpoint(element_index=0, segment=center_seg)
        ref = AntennaElement(
            x1=-spacing_m, y1=-half_passive_gain, z1=0.0,
            x2=-spacing_m, y2=half_passive_gain, z2=0.0,
            segments=SEGMENTS, radius=RADIUS,
        )
        model.add_element(ref)

        elev_pat_res = sim.simulate_pattern(model, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el_step=5.0, az_step=360.0)
        spacing_elev_gain[frac] = elev_pat_res['pattern']

        az_pat_res = sim.simulate_azimuth_pattern(model, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el=30.0, az_step=5.0)
        spacing_az_gain[frac] = az_pat_res

        # ---- Best F/B model ----
        model_fb = AntennaModel()
        model_fb.add_element(driven_elem)
        model_fb.add_feedpoint(element_index=0, segment=center_seg)
        ref_fb = AntennaElement(
            x1=-spacing_m, y1=-half_passive_fb, z1=0.0,
            x2=-spacing_m, y2=half_passive_fb, z2=0.0,
            segments=SEGMENTS, radius=RADIUS,
        )
        model_fb.add_element(ref_fb)

        elev_fb = sim.simulate_pattern(model_fb, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el_step=5.0, az_step=360.0)
        spacing_elev_fb[frac] = elev_fb['pattern']

        az_fb = sim.simulate_azimuth_pattern(model_fb, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el=30.0, az_step=5.0)
        spacing_az_fb[frac] = az_fb

    # Legend labels include optimal detune percentage
    labels_gain = [f"{frac:.3f}λ ({dg*100:.0f}%)" for frac, dg in zip(spacing_subset, detune_gain_list)]
    labels_fb = [f"{frac:.3f}λ ({df*100:.0f}%)" for frac, df in zip(spacing_subset, detune_fb_list)]
    # Compute dipole elevation and azimuth patterns for reference
    dip_elev_res = sim.simulate_pattern(dipole_model, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el_step=5.0, az_step=360.0)
    dip_elev_pat = dip_elev_res['pattern']
    dip_az_res = dip_az  # already simulated earlier
    # Add dipole to dictionaries
    spacing_elev_gain['dipole'] = dip_elev_pat
    spacing_az_gain['dipole'] = dip_az_res
    spacing_elev_fb['dipole'] = dip_elev_pat
    spacing_az_fb['dipole'] = dip_az_res
    # Extend keys and labels
    keys_gain = spacing_subset + ['dipole']
    labels_gain.append('Dipole')
    keys_fb = spacing_subset + ['dipole']
    labels_fb.append('Dipole')

    # Custom polar plots for Max Gain per Spacing with dipole dashed
    polar_gain_plot = os.path.join('output/2_el_yagi_15m', 'spacing_subset_polar_gain.png')
    fig, (ax_el, ax_az) = plt.subplots(1, 2, subplot_kw={'polar': True}, figsize=(14, 7))
    colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
    # Elevation patterns
    raw_max = max(max(p['gain'] for p in spacing_elev_gain[f]) for f in keys_gain)
    from antenna_model import configure_polar_axes
    configure_polar_axes(ax_el, 'Elevation Pattern (az=0)', raw_max)
    for idx, key in enumerate(keys_gain):
        data = sorted(spacing_elev_gain[key], key=lambda p: p['el'])
        theta = np.radians([p['el'] for p in data])
        r = [0.89 ** ((raw_max - p['gain']) / 2.0) for p in data]
        style = '--' if key == 'dipole' else '-'
        ax_el.plot(theta, r, label=labels_gain[idx], color=colors[idx % len(colors)], linestyle=style)
    ax_el.legend(loc='upper right', bbox_to_anchor=(1.2, 1.1))
    # Azimuth patterns
    raw_max_az = max(max(p['gain'] for p in spacing_az_gain[f]) for f in keys_gain)
    configure_polar_axes(ax_az, f'Azimuth Pattern (el=30°)', raw_max_az, zero_loc='E', direction=-1)
    for idx, key in enumerate(keys_gain):
        data = sorted(spacing_az_gain[key], key=lambda p: p['az'])
        phi = np.radians([p['az'] for p in data])
        r = [0.89 ** ((raw_max_az - p['gain']) / 2.0) for p in data]
        style = '--' if key == 'dipole' else '-'
        ax_az.plot(phi, r, label=labels_gain[idx], color=colors[idx % len(colors)], linestyle=style)
    ax_az.legend(loc='upper right', bbox_to_anchor=(1.2, 1.1))
    plt.tight_layout()
    plt.savefig(polar_gain_plot)
    report.add_plot('Polar Patterns (Max Gain per Spacing)', polar_gain_plot, parameters=f"frequency = {FREQ_MHZ} MHz; height = {HEIGHT_M:.1f} m (~0.5λ); ground = {GROUND}; segments = {SEGMENTS}; radius = {RADIUS} m; elevation cut = 30°; dipole dashed")
    plt.close(fig)

    polar_fb_plot = os.path.join('output/2_el_yagi_15m', 'spacing_subset_polar_fb.png')
    fig, (ax_el, ax_az) = plt.subplots(1, 2, subplot_kw={'polar': True}, figsize=(14, 7))
    # Elevation patterns
    raw_max = max(max(p['gain'] for p in spacing_elev_fb[f]) for f in keys_fb)
    configure_polar_axes(ax_el, 'Elevation Pattern (az=0)', raw_max)
    for idx, key in enumerate(keys_fb):
        data = sorted(spacing_elev_fb[key], key=lambda p: p['el'])
        theta = np.radians([p['el'] for p in data])
        r = [0.89 ** ((raw_max - p['gain']) / 2.0) for p in data]
        style = '--' if key == 'dipole' else '-'
        ax_el.plot(theta, r, label=labels_fb[idx], color=colors[idx % len(colors)], linestyle=style)
    ax_el.legend(loc='upper right', bbox_to_anchor=(1.2, 1.1))
    # Azimuth patterns
    raw_max_az = max(max(p['gain'] for p in spacing_az_fb[f]) for f in keys_fb)
    configure_polar_axes(ax_az, f'Azimuth Pattern (el=30°)', raw_max_az, zero_loc='E', direction=-1)
    for idx, key in enumerate(keys_fb):
        data = sorted(spacing_az_fb[key], key=lambda p: p['az'])
        phi = np.radians([p['az'] for p in data])
        r = [0.89 ** ((raw_max_az - p['gain']) / 2.0) for p in data]
        style = '--' if key == 'dipole' else '-'
        ax_az.plot(phi, r, label=labels_fb[idx], color=colors[idx % len(colors)], linestyle=style)
    ax_az.legend(loc='upper right', bbox_to_anchor=(1.2, 1.1))
    plt.tight_layout()
    plt.savefig(polar_fb_plot)
    report.add_plot('Polar Patterns (Max F/B per Spacing)', polar_fb_plot, parameters=f"frequency = {FREQ_MHZ} MHz; height = {HEIGHT_M:.1f} m (~0.5λ); ground = {GROUND}; segments = {SEGMENTS}; radius = {RADIUS} m; elevation cut = 30°; dipole dashed")
    plt.close(fig)

    # Plot: Gain and F/B vs Detune for each boom length
    plt.figure(figsize=(10,6))
    for j, frac in enumerate(spacing_fracs):
        gains_curve = [fg_matrix[i][j] for i in range(len(detune_steps))]
        plt.plot(detune_steps*100, gains_curve, label=f"{frac:.3f}λ")
    # Dipole reference line
    plt.axhline(dip_fwd_gain, color='k', linestyle='--', label='Dipole')
    plt.xlabel('Reflector Detune (%)')
    plt.ylabel('Forward Gain (dBi)')
    plt.title('Forward Gain vs Detune for Each Spacing Fraction (15m Yagi)')
    plt.legend(ncol=2)
    plt.grid(True)
    gain_detune_plot = os.path.join('output/2_el_yagi_15m', 'gain_vs_detune.png')
    os.makedirs('output/2_el_yagi_15m', exist_ok=True)
    plt.savefig(gain_detune_plot)
    report.add_plot('Forward Gain vs Detune for Each Spacing Fraction', gain_detune_plot, parameters=f"frequency = {FREQ_MHZ} MHz; height = {HEIGHT_M:.2f} m (~0.5λ); ground = {GROUND}; segments = {SEGMENTS}; radius = {RADIUS} m; elevation = 30° (azimuth pattern)")
    plt.close()

    plt.figure(figsize=(10,6))
    for j, frac in enumerate(spacing_fracs):
        fb_curve = [fb_matrix[i][j] for i in range(len(detune_steps))]
        plt.plot(detune_steps*100, fb_curve, label=f"{frac:.3f}λ")
    # Dipole reference F/B = 0 dB
    plt.axhline(dip_fb, color='k', linestyle='--', label='Dipole')
    plt.xlabel('Reflector Detune (%)')
    plt.ylabel('Front-to-Back Ratio (dB)')
    plt.title('F/B Ratio vs Detune for Each Spacing Fraction (15m Yagi)')
    plt.legend(ncol=2)
    plt.grid(True)
    fb_detune_plot = os.path.join('output/2_el_yagi_15m', 'fb_vs_detune.png')
    plt.savefig(fb_detune_plot)
    report.add_plot('Front-to-Back Ratio vs Detune for Each Spacing Fraction', fb_detune_plot, parameters=f"frequency = {FREQ_MHZ} MHz; height = {HEIGHT_M:.2f} m (~0.5λ); ground = {GROUND}; segments = {SEGMENTS}; radius = {RADIUS} m; elevation = 30° (azimuth pattern)")
    plt.close()

    # === Tuning criticality analysis ===
    critical_spacings = [0.05, 0.075, 0.10, 0.15]
    offsets_khz = np.array([-100, -50, -25, 0, 25, 50, 100])
    freqs = FREQ_MHZ + offsets_khz / 1e3
    labels = [f"{int(off)} kHz" if off != 0 else "0 kHz" for off in offsets_khz]
    # Find best detune for max F/B at nominal frequency
    best_detunes = {}
    for frac in critical_spacings:
        best_fb = -1e9
        best_det = 0.0
        spacing_m = frac * wavelength_m
        for det in detune_fracs:
            model = build_two_element_yagi_model(FREQ_MHZ, det, spacing_m)
            az_pat = sim.simulate_azimuth_pattern(
                model, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el=30.0, az_step=5.0
            )
            fwd = next(p['gain'] for p in az_pat if abs(p['az']) < 1e-6)
            back = next(p['gain'] for p in az_pat if abs(p['az'] - 180.0) < 1e-6)
            fb = fwd - back
            if fb > best_fb:
                best_fb = fb
                best_det = det
        best_detunes[frac] = best_det
    # Generate and include criticality plots
    for frac in critical_spacings:
        det = best_detunes[frac]
        spacing_m = frac * wavelength_m
        elev_pats = {}
        az_pats = {}
        for freq in freqs:
            model = build_two_element_yagi_model(freq, det, spacing_m)
            elev_pats[freq] = sim.simulate_pattern(
                model, freq, height_m=HEIGHT_M, ground=GROUND, el_step=5.0, az_step=360.0
            )['pattern']
            az_pats[freq] = sim.simulate_azimuth_pattern(
                model, freq, height_m=HEIGHT_M, ground=GROUND, el=30.0, az_step=5.0
            )
        out_file = os.path.join('output/2_el_yagi_15m', f'criticality_{int(frac*1000)}pl.png')
        plot_polar_patterns(
            elev_pats, az_pats, list(freqs), el_fixed=30.0, output_file=out_file, legend_labels=labels
        )
        report.add_plot(
            f'Criticality Polar Patterns ({frac:.3f}λ)',
            out_file,
            parameters=f'frequency offsets = ±25, ±50, ±100 kHz; reflector detune optimized for max F/B; spacing = {frac:.3f}λ'
        )
        # Add table of forward gain and F/B for frequency offsets
        table_rows = []
        for off_khz, freq in zip(offsets_khz, freqs):
            az_pattern = az_pats[freq]
            fwd = next(p['gain'] for p in az_pattern if abs(p['az']) < 1e-6)
            back = next(p['gain'] for p in az_pattern if abs(p['az'] - 180.0) < 1e-6)
            fb = fwd - back
            table_rows.append([f"{int(off_khz)}", f"{fwd:.2f}", f"{fb:.2f}"])
        report.add_table(
            f'Criticality Data ({frac:.3f}λ)',
            ['Offset (kHz)', 'Forward Gain (dBi)', 'F/B (dB)'],
            table_rows,
            parameters=f'spacing = {frac:.3f}λ; detune = {det*100:.2f}%'
        )

    # === VSWR vs Frequency for each spacing fraction ===
    # Determine best detune for max F/B across *all* spacing_fracs
    best_detune_spacing = {}
    for j, frac in enumerate(spacing_fracs):
        peak_fb = fb_peaks[j]
        i_row = next(i for i, row in enumerate(fb_matrix) if abs(row[j] - peak_fb) < 1e-6)
        best_detune_spacing[frac] = detune_steps[i_row]

    # Frequency sweep offsets (kHz) and list in MHz
    vswr_offsets_khz = np.arange(-300, 301, 25)  # -300 to +300 kHz in 25 kHz steps
    vswr_freqs_mhz = FREQ_MHZ + vswr_offsets_khz / 1e3

    vswr_plot_path = os.path.join('output/2_el_yagi_15m', 'vswr_vs_freq.png')
    plt.figure(figsize=(10, 6))

    # Store impedance data: {spacing: [(offset_khz, R, X), ...]}
    impedance_data = {}

    for frac in spacing_fracs:
        det = best_detune_spacing[frac]
        spacing_m = frac * wavelength_m
        vswr_values = []
        imp_list = []
        for off_khz, f_mhz in zip(vswr_offsets_khz, vswr_freqs_mhz):
            model = build_two_element_yagi_model(f_mhz, det, spacing_m)
            imp_res = sim.simulate_pattern(
                model, f_mhz, height_m=HEIGHT_M, ground=GROUND, el_step=90.0, az_step=360.0
            )['impedance']
            if imp_res is None:
                vswr_values.append(np.nan)
                imp_list.append((off_khz, np.nan, np.nan))
                continue
            R, X = imp_res
            Z = complex(R, X)
            Z0 = 50.0
            gamma = (Z - Z0) / (Z + Z0)
            vswr = (1 + abs(gamma)) / (1 - abs(gamma)) if abs(gamma) < 1 else (1 + abs(gamma)) / (abs(gamma) - 1)
            vswr_values.append(vswr)
            imp_list.append((off_khz, R, X))
        plt.plot(vswr_freqs_mhz, vswr_values, label=f"{frac:.3f}λ")
        impedance_data[frac] = imp_list

    plt.xlabel('Frequency (MHz)')
    plt.ylabel('VSWR (50 Ω)')
    plt.title('VSWR vs Frequency for Reflector-Tuned 2-el Yagi (15 m)')
    plt.ylim(1, 5)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(vswr_plot_path)
    report.add_plot('VSWR vs Frequency (All Spacings)', vswr_plot_path, parameters='Spacing fractions = 0.05-0.40 λ; reflector detune set for max F/B at 21 MHz; height = 0.5 λ; 50 Ω reference')
    plt.close()

    # --- Impedance tables ---
    for frac in spacing_fracs:
        rows = []
        for off_khz, R, X in impedance_data[frac]:
            rows.append([f"{int(off_khz)}", f"{R:.1f}", f"{X:.1f}"])
        report.add_table(
            f'Feedpoint Impedance vs Frequency ({frac:.3f}λ)',
            ['Offset (kHz)', 'R (Ω)', 'X (Ω)'],
            rows,
            parameters=f'spacing = {frac:.3f}λ; detune = {best_detune_spacing[frac]*100:.2f}%'
        )

    # === Rescaled element lengths to achieve X≈0 at 21 MHz ===
    rescale_spacings = [0.05, 0.075, 0.10]

    def reactance_for_scale(scale, detune, spacing_m):
        driven_len = resonant_dipole_length(FREQ_MHZ) * scale
        refl_len = resonant_dipole_length(FREQ_MHZ / (1 + detune)) * scale
        model_tmp = AntennaModel()
        half_d = driven_len / 2
        half_r = refl_len / 2
        model_tmp.add_element(AntennaElement(
            x1=0.0, y1=-half_d, z1=0.0, x2=0.0, y2=half_d, z2=0.0, segments=SEGMENTS, radius=RADIUS))
        model_tmp.add_feedpoint(element_index=0, segment=center_seg)
        model_tmp.add_element(AntennaElement(
            x1=-spacing_m, y1=-half_r, z1=0.0, x2=-spacing_m, y2=half_r, z2=0.0, segments=SEGMENTS, radius=RADIUS))
        R, X = sim.simulate_pattern(
            model_tmp, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el_step=90.0, az_step=360.0
        )['impedance']
        return X

    def find_scale_factor(detune, spacing_m):
        # Bracket search between 0.8 and 1.1
        low, high = 0.8, 1.1
        X_low = reactance_for_scale(low, detune, spacing_m)
        X_high = reactance_for_scale(high, detune, spacing_m)
        # Ensure sign change
        if X_low * X_high > 0:
            # expand range
            for s in np.linspace(0.6, 1.2, 13):
                Xs = reactance_for_scale(s, detune, spacing_m)
                if X_low * Xs <= 0:
                    high, X_high = s, Xs
                    break
                if Xs * X_high <= 0:
                    low, X_low = s, Xs
                    break
        # Bisection
        for _ in range(20):
            mid = 0.5 * (low + high)
            X_mid = reactance_for_scale(mid, detune, spacing_m)
            if abs(X_mid) < 0.1:
                return mid, X_mid
            if X_low * X_mid <= 0:
                high, X_high = mid, X_mid
            else:
                low, X_low = mid, X_mid
        return mid, X_mid

    rescale_rows = []
    orig_rows = []
    pattern_compare_plots = []
    for frac in rescale_spacings:
        det = best_detune_spacing[frac]
        spacing_m = frac * wavelength_m
        # --- Original geometry impedance ---
        orig_model_tmp = build_two_element_yagi_model(FREQ_MHZ, det, spacing_m)
        R0, X0 = sim.simulate_pattern(orig_model_tmp, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el_step=90.0, az_step=360.0)['impedance']
        driven_orig = resonant_dipole_length(FREQ_MHZ)
        refl_orig = resonant_dipole_length(FREQ_MHZ / (1 + det))
        orig_rows.append([f"{frac:.3f}", f"{driven_orig:.3f}", f"{refl_orig:.3f}", f"{R0:.1f}", f"{X0:.1f}"])
        scale, x_final = find_scale_factor(det, spacing_m)
        # original driven length and reflector length
        driven_len = resonant_dipole_length(FREQ_MHZ)
        refl_len = resonant_dipole_length(FREQ_MHZ / (1 + det))
        new_driven = driven_len * scale
        new_refl = refl_len * scale
        # Build scaled model manually
        model_scaled = AntennaModel()
        half_d = new_driven / 2
        half_r = new_refl / 2
        model_scaled.add_element(AntennaElement(
            x1=0.0, y1=-half_d, z1=0.0, x2=0.0, y2=half_d, z2=0.0, segments=SEGMENTS, radius=RADIUS))
        model_scaled.add_feedpoint(element_index=0, segment=center_seg)
        model_scaled.add_element(AntennaElement(
            x1=-spacing_m, y1=-half_r, z1=0.0, x2=-spacing_m, y2=half_r, z2=0.0, segments=SEGMENTS, radius=RADIUS))
        R,X = sim.simulate_pattern(
            model_scaled, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el_step=90.0, az_step=360.0
        )['impedance']
        rescale_rows.append([
            f"{frac:.3f}", f"{scale:.4f}", f"{new_driven:.3f}", f"{new_refl:.3f}", f"{R:.1f}", f"{X:.1f}"])

        # --- Pattern comparison plot ---
        orig_model = build_two_element_yagi_model(FREQ_MHZ, det, spacing_m)
        elev_orig = sim.simulate_pattern(orig_model, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el_step=5.0, az_step=360.0)['pattern']
        az_orig = sim.simulate_azimuth_pattern(orig_model, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el=30.0, az_step=5.0)
        elev_scaled = sim.simulate_pattern(model_scaled, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el_step=5.0, az_step=360.0)['pattern']
        az_scaled = sim.simulate_azimuth_pattern(model_scaled, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el=30.0, az_step=5.0)

        # Build plot
        from antenna_model import configure_polar_axes
        comp_path = os.path.join('output/2_el_yagi_15m', f'pattern_compare_{int(frac*1000)}pl.png')
        fig, (ax_el, ax_az) = plt.subplots(1, 2, subplot_kw={'polar': True}, figsize=(14,7))
        colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
        # Elevation
        raw_max = max(max(p['gain'] for p in elev_orig), max(p['gain'] for p in elev_scaled))
        configure_polar_axes(ax_el, 'Elevation Pattern (az=0)', raw_max)
        for idx, (data, lbl, style) in enumerate([(elev_orig,'Original','--'),(elev_scaled,'Scaled','-')]):
            sorted_data = sorted(data, key=lambda p:p['el'])
            theta=np.radians([p['el'] for p in sorted_data])
            r=[0.89**((raw_max - p['gain'])/2.0) for p in sorted_data]
            ax_el.plot(theta,r,label=lbl,color=colors[idx%len(colors)],linestyle=style)
        ax_el.legend(loc='upper right', bbox_to_anchor=(1.2,1.1))
        # Azimuth
        raw_max_az = max(max(p['gain'] for p in az_orig), max(p['gain'] for p in az_scaled))
        configure_polar_axes(ax_az, 'Az Pattern (el=30°)', raw_max_az, zero_loc='E', direction=-1)
        for idx,(data,lbl,style) in enumerate([(az_orig,'Original','--'),(az_scaled,'Scaled','-')]):
            sorted_data=sorted(data,key=lambda p:p['az'])
            phi=np.radians([p['az'] for p in sorted_data])
            r=[0.89**((raw_max_az - p['gain'])/2.0) for p in sorted_data]
            ax_az.plot(phi,r,label=lbl,color=colors[idx%len(colors)],linestyle=style)
        ax_az.legend(loc='upper right', bbox_to_anchor=(1.2,1.1))
        plt.tight_layout()
        plt.savefig(comp_path)
        plt.close(fig)
        report.add_plot(
            f'Pattern Comparison Original vs Scaled ({frac:.3f}λ)',
            comp_path,
            parameters=f'scale factor = {scale:.4f}; R={R:.1f} Ω, X={X:.1f} Ω'
        )

    report.add_table(
        'Rescaled Element Lengths for X≈0',
        ['Spacing λ', 'Scale Factor', 'Driven Len (m)', 'Reflector Len (m)', 'R (Ω)', 'X (Ω)'],
        rescale_rows,
        parameters='Lengths scaled uniformly so that feedpoint reactance ~0 at 21 MHz; detune held constant.'
    )

    report.add_table(
        'Original Element Lengths and Impedances for Spacings 0.05,0.075,0.10 λ',
        ['Spacing λ', 'Driven Len (m)', 'Reflector Len (m)', 'R (Ω)', 'X (Ω)'],
        orig_rows,
        parameters='Lengths and impedances for original unscaled element lengths'
    )

    # === Joint optimisation: scale & detune to maximise F/B with |X| small ===
    opt_rows = []
    for frac in rescale_spacings:
        det_base = best_detune_spacing[frac]
        spacing_m = frac * wavelength_m
        # baseline scale from previous search
        scale_base, _ = find_scale_factor(det_base, spacing_m)
        scale_list = np.linspace(scale_base-0.03, scale_base+0.03, 13)
        det_list = np.linspace(det_base-0.02, det_base+0.02, 17)
        best_cost = 1e9
        best_tuple = None
        for sc in scale_list:
            # Precompute scaled lengths independent of detune? Need driven only.
            driven_len_sc = resonant_dipole_length(FREQ_MHZ) * sc
            half_d_sc = driven_len_sc /2
            for det in det_list:
                refl_len_sc = resonant_dipole_length(FREQ_MHZ / (1+det)) * sc
                half_r_sc = refl_len_sc/2
                model_tmp = AntennaModel()
                model_tmp.add_element(AntennaElement(
                    x1=0,y1=-half_d_sc,z1=0,x2=0, y2=half_d_sc,z2=0,segments=SEGMENTS,radius=RADIUS))
                model_tmp.add_feedpoint(element_index=0, segment=center_seg)
                model_tmp.add_element(AntennaElement(
                    x1=-spacing_m,y1=-half_r_sc,z1=0,x2=-spacing_m,y2=half_r_sc,z2=0,segments=SEGMENTS,radius=RADIUS))
                imp = sim.simulate_pattern(model_tmp, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el_step=90.0, az_step=360.0)['impedance']
                R_imp,X_imp = imp
                az_pat = sim.simulate_azimuth_pattern(model_tmp, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el=30.0, az_step=5.0)
                fwd = next(p['gain'] for p in az_pat if abs(p['az'])<1e-6)
                back = next(p['gain'] for p in az_pat if abs(p['az']-180.0)<1e-6)
                fb_val = fwd - back
                cost = -fb_val + 0.1*abs(X_imp)  # weight reactance 0.1 dB per ohm
                if cost < best_cost:
                    best_cost = cost
                    best_tuple = (sc, det, R_imp, X_imp, fb_val, fwd)
        if best_tuple is None:
            continue
        sc_opt, det_opt, R_opt, X_opt, fb_opt, gain_opt = best_tuple
        opt_rows.append([
            f"{frac:.3f}", f"{sc_opt:.4f}", f"{det_opt*100:.2f}", f"{R_opt:.1f}", f"{X_opt:.1f}", f"{gain_opt:.2f}", f"{fb_opt:.2f}"])

    report.add_table(
        'Optimised Scale & Detune (High F/B, |X| small)',
        ['Spacing λ','Scale','Detune %','R (Ω)','X (Ω)','Gain (dBi)','F/B (dB)'],
        opt_rows,
        parameters='Search over scale ±3% and detune ±2% around baseline; cost = -F/B + 0.1|X|'
    )

    # --- Update pattern comparison plots to include optimised model ---
    opt_dict = {float(row[0]): (float(row[1]), float(row[2])/100.0) for row in opt_rows}

    for frac in rescale_spacings:
        if frac not in opt_dict:
            continue
        sc_opt, det_opt = opt_dict[frac]
        spacing_m = frac * wavelength_m
        # Build models
        # Original
        det_orig = best_detune_spacing[frac]
        model_orig = build_two_element_yagi_model(FREQ_MHZ, det_orig, spacing_m)
        elev_orig = sim.simulate_pattern(model_orig, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el_step=5.0, az_step=360.0)['pattern']
        az_orig = sim.simulate_azimuth_pattern(model_orig, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el=30.0, az_step=5.0)
        # Scaled (reactance zero)
        scale_zero, _ = find_scale_factor(det_orig, spacing_m)
        driven_zero = resonant_dipole_length(FREQ_MHZ) * scale_zero
        refl_zero = resonant_dipole_length(FREQ_MHZ / (1 + det_orig)) * scale_zero
        half_dz, half_rz = driven_zero/2, refl_zero/2
        model_zero = AntennaModel()
        model_zero.add_element(AntennaElement(x1=0,y1=-half_dz,z1=0,x2=0,y2=half_dz,z2=0,segments=SEGMENTS,radius=RADIUS))
        model_zero.add_feedpoint(element_index=0, segment=center_seg)
        model_zero.add_element(AntennaElement(x1=-spacing_m,y1=-half_rz,z1=0,x2=-spacing_m,y2=half_rz,z2=0,segments=SEGMENTS,radius=RADIUS))
        elev_zero = sim.simulate_pattern(model_zero, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el_step=5.0, az_step=360.0)['pattern']
        az_zero = sim.simulate_azimuth_pattern(model_zero, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el=30.0, az_step=5.0)
        # Optimized
        driven_opt = resonant_dipole_length(FREQ_MHZ) * sc_opt
        refl_opt = resonant_dipole_length(FREQ_MHZ / (1 + det_opt)) * sc_opt
        half_do, half_ro = driven_opt/2, refl_opt/2
        model_opt = AntennaModel()
        model_opt.add_element(AntennaElement(x1=0,y1=-half_do,z1=0,x2=0,y2=half_do,z2=0,segments=SEGMENTS,radius=RADIUS))
        model_opt.add_feedpoint(element_index=0, segment=center_seg)
        model_opt.add_element(AntennaElement(x1=-spacing_m,y1=-half_ro,z1=0,x2=-spacing_m,y2=half_ro,z2=0,segments=SEGMENTS,radius=RADIUS))
        elev_opt = sim.simulate_pattern(model_opt, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el_step=5.0, az_step=360.0)['pattern']
        az_opt = sim.simulate_azimuth_pattern(model_opt, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el=30.0, az_step=5.0)

        from antenna_model import configure_polar_axes
        comp_path = os.path.join('output/2_el_yagi_15m', f'pattern_compare_{int(frac*1000)}pl.png')
        fig, (ax_el, ax_az) = plt.subplots(1,2,subplot_kw={'polar':True}, figsize=(14,7))
        colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
        # Elevation
        raw_max = max(max(p['gain'] for p in elev_orig+elev_zero+elev_opt))
        configure_polar_axes(ax_el,'Elevation Pattern (az=0)', raw_max)
        for idx,(data,lbl,style) in enumerate([
            (elev_orig,'Original','--'),
            (elev_zero,'Scaled','-.'),
            (elev_opt,'Optimized','-')]):
            sorted_data=sorted(data,key=lambda p:p['el'])
            theta=np.radians([p['el'] for p in sorted_data])
            r=[0.89**((raw_max-p['gain'])/2.0) for p in sorted_data]
            ax_el.plot(theta,r,label=lbl,color=colors[idx%len(colors)],linestyle=style)
        ax_el.legend(loc='upper right', bbox_to_anchor=(1.25,1.1))
        # Azimuth
        raw_max_az = max(max(p['gain'] for p in az_orig+az_zero+az_opt))
        configure_polar_axes(ax_az,'Az Pattern (el=30°)', raw_max_az, zero_loc='E', direction=-1)
        for idx,(data,lbl,style) in enumerate([
            (az_orig,'Original','--'),
            (az_zero,'Scaled','-.'),
            (az_opt,'Optimized','-')]):
            sorted_data=sorted(data,key=lambda p:p['az'])
            phi=np.radians([p['az'] for p in sorted_data])
            r=[0.89**((raw_max_az-p['gain'])/2.0) for p in sorted_data]
            ax_az.plot(phi,r,label=lbl,color=colors[idx%len(colors)],linestyle=style)
        ax_az.legend(loc='upper right', bbox_to_anchor=(1.25,1.1))
        plt.tight_layout()
        plt.savefig(comp_path)
        plt.close(fig)
        # Update plot reference
        report.add_plot(
            f'Pattern Comparison Orig vs Scaled vs Opt ({frac:.3f}λ)',
            comp_path,
            parameters=f'Optimised scale={sc_opt:.4f}, detune={det_opt*100:.2f}%'
        )

    # Save report
    report.save()

if __name__ == '__main__':
    main() 