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

    # Save report
    report.save()

if __name__ == '__main__':
    main() 