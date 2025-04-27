#!/usr/bin/env python3
"""
Generate radiation pattern of a half-wave dipole antenna at 30ft elevation and 14.1 MHz.
Usage: python3 dipole_pattern.py
"""
import subprocess
import sys
import shlex
import math
import re
import argparse
import matplotlib.pyplot as plt
import numpy as np
from antenna_model import build_dipole_model, run_pymininec, resonant_dipole_length, get_ground_opts, feet_to_meters, meters_to_feet

def main():
    parser = argparse.ArgumentParser(description="Dipole pattern analysis and plotting.")
    parser.add_argument('--show-gui', action='store_true', help='Show plot in GUI window instead of saving PNG')
    args = parser.parse_args()
    # Frequency in MHz
    freq_mhz = 14.1
    # Heights in feet to test
    heights_ft = [5, 10, 20, 30, 45, 60, 100, 150]
    # Use ARRL resonant dipole length
    dipole_length = resonant_dipole_length(freq_mhz)
    segments = 21
    radius = 0.001
    model = build_dipole_model(total_length=dipole_length, segments=segments, radius=radius)
    ground_opts = get_ground_opts("average")

    # Feedpoint impedance vs height (average ground): use 5, 10, 15, 20 meters
    heights_m_imp = [5, 10, 15, 20]
    print("Feedpoint impedance vs height (average ground):")
    print("Height (m) |    R (ohm) |   X (ohm)")
    print("-----------------------------------")
    for height_m in heights_m_imp:
        result = run_pymininec(
            model,
            freq_mhz=freq_mhz,
            height_m=height_m,
            ground_opts=ground_opts,
            excitation_pulse="10,1",
            pattern_opts={"theta": "45,0,1", "phi": "0,0,1"},
            option="far-field"
        )
        R, X = result['impedance']
        print(f"   {height_m:6.1f} | {R:9.2f} | {X:8.2f}")

    # Also print the pattern for the default height (30 ft)
    height_ft = 30
    height_m = feet_to_meters(height_ft)
    print(f"\nRadiation pattern at {height_ft} ft (average ground):")
    result = run_pymininec(
        model,
        freq_mhz=freq_mhz,
        height_m=height_m,
        ground_opts=ground_opts,
        excitation_pulse="10,1",
        pattern_opts={"theta": "10,10,8", "phi": "0,0,1"},
        option="far-field-absolute",
        ff_distance=1000
    )
    pattern = result['pattern']
    if not pattern:
        print("No pattern data found.")
        sys.exit(1)
    max_gain = max(p['gain'] for p in pattern)
    print("\nElevation (deg) | Relative Gain (dB)")
    print("-----------------------------------")
    for p in pattern:
        theta = p['el']
        db = p['gain'] - max_gain
        print(f"{theta:8.1f} | {db:7.2f}")

    # Print gain at az=0 for el=0 to 180 deg in 5 deg steps, for multiple heights
    heights_m = [5, 10, 15, 20]
    # Build hemisphere patterns by height
    patterns_by_height = {}
    for h_m in heights_m:
        result = run_pymininec(
            model,
            freq_mhz=freq_mhz,
            height_m=h_m,
            ground_opts=ground_opts,
            excitation_pulse="10,1",
            pattern_opts={"theta": "0,1,91", "phi": "0,0,1"},
            option="far-field",
        )
        # Only keep points at az=0
        patterns_by_height[h_m] = [p for p in result['pattern'] if abs(p['az'] - 0) < 1e-3]
    # Mirror hemisphere data for full horizon-to-horizon cut
    full_patterns = {}
    for h_m, hemi in patterns_by_height.items():
        hemi_sorted = sorted(hemi, key=lambda p: p['el'])
        mirror = [{"el": 180 - p['el'], "gain": p['gain']} for p in hemi_sorted if p['el'] != 0.0]
        full_patterns[h_m] = hemi_sorted + sorted(mirror, key=lambda p: p['el'])
    # Create elevation table 0° to 180° in steps of 5°
    el_table = list(range(0, 181, 5))
    print("\nGain at az=0 for el=0 to 180 deg (average ground), for various heights:")
    header = "Elevation (deg) |" + "".join([f" {h:>5} m" for h in heights_m])
    print(header)
    print("----------------|" + "-------" * len(heights_m))
    # Compute the integer elevation of the peak gain per height for highlighting
    highlight_el = {}
    for h_m in heights_m:
        # find the point with max gain
        p_max = max(full_patterns[h_m], key=lambda p: p['gain'])
        # round elevation to nearest multiple of 5° for table highlight
        highlight_el[h_m] = int(round(p_max['el']/5.0) * 5)
    for el in el_table:
        row = f"   {el:3d}         |"
        for h_m in heights_m:
            pattern = full_patterns[h_m]
            closest = min(pattern, key=lambda p: abs(p['el'] - el))
            gain_val = closest['gain']
            # Highlight the cell at the peak elevation
            if el == highlight_el[h_m]:
                row += f" \033[1;33m{gain_val:7.3f}\033[0m"
            else:
                row += f" {gain_val:7.3f}"
        print(row)

    # Print azimuth pattern at el=30 deg for each height (5 deg steps)
    az_table = list(range(0, 360, 5))
    el_fixed = 30
    print(f"\nAzimuth pattern at el={el_fixed} deg (average ground), for various heights:")
    header = "Azimuth (deg)   |" + "".join([f" {h:>5} m" for h in heights_m])
    print(header)
    print("----------------|" + "-------" * len(heights_m))
    # For each height, get the full azimuth sweep at el=30
    az_patterns_by_height = {}
    for h_m in heights_m:
        result = run_pymininec(
            model,
            freq_mhz=freq_mhz,
            height_m=h_m,
            ground_opts=ground_opts,
            excitation_pulse="10,1",
            pattern_opts={"theta": f"{90-el_fixed},0,1", "phi": "0,5,72"},
            option="far-field",
        )
        # Only keep points at el=30 (zenith=60)
        pattern = [p for p in result['pattern'] if abs(p['el']-el_fixed)<1e-3]
        # Map azimuth to gain
        az_gain = {int(round(p['az'])): p['gain'] for p in pattern}
        az_patterns_by_height[h_m] = az_gain
    # For each height, find the max gain for highlighting
    az_max_gain = {h_m: max(az_patterns_by_height[h_m].values()) if az_patterns_by_height[h_m] else None for h_m in heights_m}
    for az in az_table:
        row = f"    {az:3d}         |"
        for h_m in heights_m:
            az_gain = az_patterns_by_height[h_m]
            gain = az_gain.get(az, None)
            if gain is not None:
                if abs(gain - az_max_gain[h_m]) < 1e-6:
                    row += f" \033[1;33m{gain:7.3f}\033[0m"
                else:
                    row += f" {gain:7.3f}"
            else:
                row += f"    n/a "
        print(row)

    # --- POLAR PLOT: Power pattern vs Elevation for az=0, all heights ---
    plt.figure(figsize=(7,7))
    ax = plt.subplot(111, polar=True)
    colors = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red']
    for idx, h_m in enumerate(heights_m):
        pattern_full = full_patterns[h_m]
        pattern_full = [p for p in pattern_full if p['gain'] > -100]
        pattern_full = sorted(pattern_full, key=lambda p: p['el'])
        el_angles = [p['el'] for p in pattern_full]
        gains = [p['gain'] for p in pattern_full]
        theta_rad = np.radians(el_angles)
        r_linear = [10**(g/10.0) for g in gains]
        ax.plot(theta_rad, r_linear, label=f'h={h_m}m', color=colors[idx % len(colors)])
    ax.set_theta_zero_location('E')
    ax.set_theta_direction(1)
    ax.set_title('Elevation Pattern (az=0, all heights)', va='bottom')
    ax.set_rscale('log')
    min_db = -40
    max_db = int(max(max([p['gain'] for p in full_patterns[h]]) for h in heights_m))
    db_ticks = list(range(min_db, max_db+1, 10))
    r_ticks = [10**(d/10.0) for d in db_ticks]
    ax.set_rticks(r_ticks)
    ax.set_yticklabels([f"{d} dB" for d in db_ticks])
    ax.grid(True)
    plt.legend()
    plt.tight_layout()
    if args.show_gui:
        plt.show()
    else:
        plt.savefig('elevation_pattern_az0_all_heights.png')
        print("Saved elevation pattern plot for all heights to elevation_pattern_az0_all_heights.png")

    return

if __name__ == "__main__":
    main() 