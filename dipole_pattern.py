#!/usr/bin/env python3
"""
Generate radiation pattern of a half-wave dipole antenna at 30ft elevation and 14.1 MHz.
Usage: python3 dipole_pattern.py [--show-gui]
"""
import sys
import argparse
import matplotlib.pyplot as plt
import numpy as np
from antenna_model import (
    build_dipole_model,
    AntennaSimulator,
    resonant_dipole_length,
    get_ground_opts,
    feet_to_meters,
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
    heights_m_imp = [5, 10, 15, 20]
    print("Feedpoint impedance vs height (average ground):")
    print("Height (m) |    R (ohm) |   X (ohm)")
    print("-----------------------------------")
    for h in heights_m_imp:
        result = sim.simulate_pattern(
            model, freq_mhz=freq_mhz, height_m=h, ground=ground,
            el_step=45.0, az_step=360.0
        )
        R, X = result['impedance']
        print(f"   {h:6.1f} | {R:9.2f} | {X:8.2f}")

    # 2) Gain vs elevation for 30 ft (free-space at 30ft)
    height_ft = 30
    height_m = feet_to_meters(height_ft)
    result = sim.simulate_pattern(
        model, freq_mhz=freq_mhz, height_m=height_m, ground=ground,
        el_step=10.0, az_step=360.0
    )
    pattern = result['pattern']
    if not pattern:
        print("No pattern data found.")
        sys.exit(1)
    max_gain = max(p['gain'] for p in pattern)
    print(f"\nRadiation pattern at {height_ft} ft (average ground):")
    print("Elevation (deg) | Relative Gain (dB)")
    print("-----------------------------------")
    for p in pattern:
        el = p['el']
        rel = p['gain'] - max_gain
        print(f"{el:8.1f} | {rel:7.2f}")

    # 3) Combined polar plots for elevation and azimuth patterns
    heights_m = [5, 10, 15, 20]
    # Elevation patterns (az=0)
    full_patterns = {}
    for h in heights_m:
        res = sim.simulate_pattern(
            model, freq_mhz=freq_mhz, height_m=h, ground=ground,
            el_step=1.0, az_step=360.0
        )
        full_patterns[h] = res['pattern']
    # Azimuth patterns at fixed elevation 30°
    el_fixed = 30.0
    az_patterns = {}
    for h in heights_m:
        az_patterns[h] = sim.simulate_azimuth_pattern(
            model, freq_mhz=freq_mhz, height_m=h, ground=ground,
            el=el_fixed, az_step=5.0
        )

    # Plotting
    fig, (ax1, ax2) = plt.subplots(1, 2, subplot_kw={'polar': True}, figsize=(14, 7))
    colors = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red']

    # Elevation pattern plot
    for idx, h in enumerate(heights_m):
        data = sorted(full_patterns[h], key=lambda p: p['el'])
        els = [p['el'] for p in data]
        gains = [p['gain'] for p in data]
        theta = np.radians(els)
        r = [10**(g/10.0) for g in gains]
        ax1.plot(theta, r, label=f'h={h}m', color=colors[idx % len(colors)])
    ax1.set_theta_zero_location('E')
    ax1.set_theta_direction(1)
    ax1.set_title('Elevation Pattern (az=0, all heights)', va='bottom')
    ax1.set_rscale('log')
    # Clamp radial axis between -40 dB and the maximum gain
    min_db = -40
    max_db = int(max(max(p['gain'] for p in full_patterns[h]) for h in heights_m))
    # Prepare dB ticks and corresponding linear ticks
    db_ticks = list(range(min_db, max_db + 1, 10))
    r_ticks = [10**(d/10.0) for d in db_ticks]
    ax1.set_rticks(r_ticks)
    ax1.set_yticklabels([f"{d} dB" for d in db_ticks])
    # Enforce radial axis limits so extremely low gains don't skew the plot
    ax1.set_ylim(r_ticks[0], r_ticks[-1])
    ax1.grid(True)
    ax1.legend(loc='upper right', bbox_to_anchor=(1.2, 1.1))

    # Azimuth pattern plot
    for idx, h in enumerate(heights_m):
        data = sorted(az_patterns[h], key=lambda p: p['az'])
        azs = [p['az'] for p in data]
        gains = [p['gain'] for p in data]
        phi = np.radians(azs)
        r = [10**(g/10.0) for g in gains]
        ax2.plot(phi, r, label=f'h={h}m', color=colors[idx % len(colors)])
    ax2.set_theta_zero_location('E')
    ax2.set_theta_direction(-1)
    ax2.set_title(f'Azimuth Pattern (el={int(el_fixed)}°, all heights)', va='bottom')
    ax2.set_rscale('log')
    max_db_az = int(max(max(p['gain'] for p in az_patterns[h]) for h in heights_m))
    db_ticks_az = list(range(min_db, max_db_az + 1, 10))
    r_ticks_az = [10**(d/10.0) for d in db_ticks_az]
    ax2.set_rticks(r_ticks_az)
    ax2.set_yticklabels([f"{d} dB" for d in db_ticks_az])
    ax2.grid(True)
    ax2.legend(loc='upper right', bbox_to_anchor=(1.2, 1.1))

    plt.tight_layout()
    if args.show_gui:
        plt.show()
    else:
        plt.savefig('pattern_comparison_all_heights.png')
        print('Saved combined pattern comparison plot to pattern_comparison_all_heights.png')

if __name__ == '__main__':
    main() 