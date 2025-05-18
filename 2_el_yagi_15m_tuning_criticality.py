#!/usr/bin/env python3
"""
Analyze tuning criticality for 2-element Yagi (15m) by generating polar plots for specified spacings
with reflector optimized for peak front-to-back ratio. Patterns at nominal frequency and ±25, ±50, ±100 kHz.
"""
import os
import numpy as np
import matplotlib.pyplot as plt

from antenna_model import (
    AntennaModel,
    AntennaElement,
    AntennaSimulator,
    resonant_dipole_length,
    plot_polar_patterns,
)

# Constants
FREQ_MHZ = 21.0
C = 299792458.0
WAVELENGTH_M = C / (FREQ_MHZ * 1e6)
HEIGHT_M = 0.5 * WAVELENGTH_M  # ~0.5λ height
GROUND = 'average'
SEGMENTS = 21
RADIUS = 0.001

# Frequency offsets in kHz
OFFSETS_KHZ = np.array([-100, -50, -25, 0, 25, 50, 100])
# Reflector detune fractions to explore (0–10% in 0.5% steps)
DETUNE_FRACS = np.linspace(0.00, 0.10, 21)
# Spacing fractions (boom lengths in wavelengths) to analyze
SPACING_FRACS = [0.05, 0.075, 0.10, 0.15]

def build_two_element_model(detune_frac, spacing_frac):
    """Build a 2-element Yagi model for given detune and spacing fractions."""
    driven_len = resonant_dipole_length(FREQ_MHZ)
    half_driven = driven_len / 2.0
    passive_len = resonant_dipole_length(FREQ_MHZ / (1.0 + detune_frac))
    half_passive = passive_len / 2.0
    spacing_m = spacing_frac * WAVELENGTH_M

    model = AntennaModel()
    # Driven element
    el1 = AntennaElement(
        x1=0.0, y1=-half_driven, z1=0.0,
        x2=0.0, y2=half_driven, z2=0.0,
        segments=SEGMENTS, radius=RADIUS,
    )
    model.add_element(el1)
    center_seg = (SEGMENTS + 1) // 2
    model.add_feedpoint(element_index=0, segment=center_seg)
    # Reflector
    el2 = AntennaElement(
        x1=-spacing_m, y1=-half_passive, z1=0.0,
        x2=-spacing_m, y2=half_passive, z2=0.0,
        segments=SEGMENTS, radius=RADIUS,
    )
    model.add_element(el2)
    return model

def find_best_fb_detune(spacing_frac):
    """Find detune fraction that maximizes F/B at nominal frequency for given spacing."""
    sim = AntennaSimulator()
    best_det = 0.0
    best_fb = -1e9
    for det in DETUNE_FRACS:
        model = build_two_element_model(det, spacing_frac)
        az_pat = sim.simulate_azimuth_pattern(
            model, FREQ_MHZ, height_m=HEIGHT_M, ground=GROUND, el=30.0, az_step=5.0
        )
        fwd = next(p['gain'] for p in az_pat if abs(p['az']) < 1e-6)
        back = next(p['gain'] for p in az_pat if abs(p['az'] - 180.0) < 1e-6)
        fb = fwd - back
        if fb > best_fb:
            best_fb = fb
            best_det = det
    return best_det

def main():
    sim = AntennaSimulator()
    # Create output directory
    out_dir = os.path.join('output', 'criticality_15m')
    os.makedirs(out_dir, exist_ok=True)

    # Compute best detune for each spacing
    best_detunes = {
        frac: find_best_fb_detune(frac) for frac in SPACING_FRACS
    }

    # Frequency list for analysis
    freqs = FREQ_MHZ + OFFSETS_KHZ / 1e3
    # Legend labels for offsets
    labels = [f"{int(off)} kHz" if off != 0 else "0 kHz" for off in OFFSETS_KHZ]

    for frac in SPACING_FRACS:
        det = best_detunes[frac]
        model = build_two_element_model(det, frac)

        # Collect patterns
        elev_pats = {}
        az_pats = {}
        for freq in freqs:
            res_elev = sim.simulate_pattern(
                model, freq, height_m=HEIGHT_M, ground=GROUND, el_step=5.0, az_step=360.0
            )
            elev_pats[freq] = res_elev['pattern']
            az_pats[freq] = sim.simulate_azimuth_pattern(
                model, freq, height_m=HEIGHT_M, ground=GROUND, el=30.0, az_step=5.0
            )

        # Output file
        frac_label = int(frac * 1000)
        out_file = os.path.join(out_dir, f'criticality_{frac_label}pl.png')
        # Generate polar plots
        plot_polar_patterns(
            elev_pats, az_pats, list(freqs), el_fixed=30.0, output_file=out_file,
            legend_labels=labels
        )
        print(f"Saved criticality plot for spacing {frac:.3f}λ to {out_file}")

if __name__ == '__main__':
    main() 