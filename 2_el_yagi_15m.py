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
HEIGHT_M = resonant_dipole_length(FREQ_MHZ) / 2  # ~half-wavelength height

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

    c = 299792458.0
    wavelength_m = c / (FREQ_MHZ * 1e6)
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

    # Add detailed tables for each boom length
    for r in results:
        detune_steps = np.arange(0.00, 0.11, 0.01)
        # Find peaks for bolding
        gain_arr = np.array(r['gain_vs_detune'])
        fb_arr = np.array(r['fb_vs_detune'])
        max_gain = np.max(gain_arr)
        max_fb = np.max(fb_arr)
        detail_rows = []
        for i, detune in enumerate(detune_steps):
            gain = gain_arr[i]
            fb = fb_arr[i]
            gain_str = f"**{gain:.2f}**" if abs(gain - max_gain) < 1e-6 else f"{gain:.2f}"
            fb_str = f"**{fb:.2f}**" if abs(fb - max_fb) < 1e-6 else f"{fb:.2f}"
            detail_rows.append([
                f"{detune*100:.0f}",
                gain_str,
                fb_str,
            ])
        report.add_table(
            f"Detail: Gain and F/B vs Detune for Boom {r['boom_ft']:.1f} ft ({r['boom_lambda']:.3f}λ)",
            ['Detune (%)', 'Fwd Gain (dBi)', 'F/B (dB)'],
            detail_rows,
            parameters=f"Boom = {r['boom_ft']:.1f} ft ({r['boom_lambda']:.3f}λ); frequency = {FREQ_MHZ} MHz; height = {HEIGHT_M:.2f} m; ground = {GROUND}; segments = {SEGMENTS}; radius = {RADIUS} m; elevation = 30° (azimuth pattern)"
        )

    # Plot: Gain and F/B vs Detune for each boom length
    plt.figure(figsize=(10,6))
    for r in results:
        plt.plot(detune_fracs*100, r['gain_vs_detune'], label=f"{int(r['boom_ft'])} ft Gain")
    plt.xlabel('Reflector Detune (%)')
    plt.ylabel('Forward Gain (dBi)')
    plt.title('Forward Gain vs Detune for Each Boom Length (15m Yagi)')
    plt.legend()
    plt.grid(True)
    gain_detune_plot = os.path.join('output/2_el_yagi_15m', 'gain_vs_detune.png')
    os.makedirs('output/2_el_yagi_15m', exist_ok=True)
    plt.savefig(gain_detune_plot)
    report.add_plot('Forward Gain vs Detune for Each Boom Length', gain_detune_plot, parameters=f"frequency = {FREQ_MHZ} MHz; height = {HEIGHT_M:.2f} m; ground = {GROUND}; segments = {SEGMENTS}; radius = {RADIUS} m; elevation = 30° (azimuth pattern)")
    plt.close()

    plt.figure(figsize=(10,6))
    for r in results:
        plt.plot(detune_fracs*100, r['fb_vs_detune'], label=f"{int(r['boom_ft'])} ft F/B")
    plt.xlabel('Reflector Detune (%)')
    plt.ylabel('Front-to-Back Ratio (dB)')
    plt.title('F/B Ratio vs Detune for Each Boom Length (15m Yagi)')
    plt.legend()
    plt.grid(True)
    fb_detune_plot = os.path.join('output/2_el_yagi_15m', 'fb_vs_detune.png')
    plt.savefig(fb_detune_plot)
    report.add_plot('Front-to-Back Ratio vs Detune for Each Boom Length', fb_detune_plot, parameters=f"frequency = {FREQ_MHZ} MHz; height = {HEIGHT_M:.2f} m; ground = {GROUND}; segments = {SEGMENTS}; radius = {RADIUS} m; elevation = 30° (azimuth pattern)")
    plt.close()

    # Plot: Max Gain and F/B vs Boom Length
    plt.figure(figsize=(10,6))
    plt.plot(boom_lengths_ft, [r['best_gain'] for r in results], 'o-', label='Max Gain (dBi)')
    plt.plot(boom_lengths_ft, [r['best_fb'] for r in results], 's-', label='Max F/B (dB)')
    plt.xlabel('Boom Length (ft)')
    plt.ylabel('dB')
    plt.title('Max Gain and F/B vs Boom Length (15m Yagi)')
    plt.legend()
    plt.grid(True)
    boom_plot = os.path.join('output/2_el_yagi_15m', 'max_gain_fb_vs_boom.png')
    plt.savefig(boom_plot)
    report.add_plot('Max Gain and F/B vs Boom Length', boom_plot, parameters=f"frequency = {FREQ_MHZ} MHz; height = {HEIGHT_M:.2f} m; ground = {GROUND}; segments = {SEGMENTS}; radius = {RADIUS} m; elevation = 30° (azimuth pattern)")
    plt.close()

    # Main pattern plot for best gain config
    best = max(results, key=lambda r: r['best_gain'])
    best_model = build_two_element_yagi_model(FREQ_MHZ, best['best_gain_detune'], best['boom_m'])
    heights = [HEIGHT_M]
    el_pats = compute_elevation_patterns(sim, best_model, FREQ_MHZ, heights, GROUND)
    az_pats = compute_azimuth_patterns(sim, best_model, FREQ_MHZ, heights, GROUND, el=30.0)
    pattern_plot = os.path.join('output/2_el_yagi_15m', 'pattern_best_gain.png')
    plot_polar_patterns(el_pats, az_pats, heights, 30.0, pattern_plot, args.show_gui)
    report.add_plot('Azimuth and Elevation Pattern (Best Gain Config)', pattern_plot, parameters=f"frequency = {FREQ_MHZ} MHz; height = {HEIGHT_M:.2f} m; ground = {GROUND}; segments = {SEGMENTS}; radius = {RADIUS} m; elevation = 30° (azimuth pattern)")

    # Save report
    report.save()

if __name__ == '__main__':
    main() 