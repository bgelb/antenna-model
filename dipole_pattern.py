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
from antenna_model import build_dipole_model, run_pymininec, resonant_dipole_length, get_ground_opts, feet_to_meters, meters_to_feet
import matplotlib.pyplot as plt
import numpy as np

def main():
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

    # Print gain at az=0 for el=10 to 80 deg in 5 deg steps, for multiple heights
    heights_m = [5, 10, 15, 20]
    el_table = list(range(10, 85, 5))
    print("\nGain at az=0 for el=10 to 80 deg (average ground), for various heights:")
    header = "Elevation (deg) |" + "".join([f" {h:>5} m" for h in heights_m])
    print(header)
    print("----------------|" + "-------" * len(heights_m))
    # For each height, get the full pattern sweep once (1 degree resolution)
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
        pattern = [p for p in result['pattern'] if abs(p['az']-0)<1e-3]
        patterns_by_height[h_m] = pattern
    # For each height, precompute the max gain and the closest table value for highlighting
    highlight_gain = {}
    for h_m in heights_m:
        pattern = patterns_by_height[h_m]
        if pattern:
            max_gain = max(p['gain'] for p in pattern)
            # Find the el in el_table whose gain is closest to max_gain
            closest_el = min(el_table, key=lambda el: abs(min(pattern, key=lambda p: abs(p['el']-el))['gain'] - max_gain))
            # Store the gain at that el for highlighting
            closest_gain = min(pattern, key=lambda p: abs(p['el']-closest_el))['gain']
            highlight_gain[h_m] = closest_gain
        else:
            highlight_gain[h_m] = None
    for el in el_table:
        row = f"     {el:2d}         |"
        for h_m in heights_m:
            pattern = patterns_by_height[h_m]
            if pattern:
                closest = min(pattern, key=lambda p: abs(p['el']-el))
                gain = closest['gain']
                # Highlight the table value closest to the true max gain for this height
                if abs(gain - highlight_gain[h_m]) < 1e-6:
                    # ANSI bold yellow
                    row += f" \033[1;33m{gain:7.3f}\033[0m"
                else:
                    row += f" {gain:7.3f}"
            else:
                row += f"    n/a "
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

    # --- POLAR PLOT: Power pattern vs Elevation for az=0, height=10m ---
    # Use the 1-degree pattern for height=10m, az=0
    pattern_10m = patterns_by_height[10]
    # Filter out invalid gain values (e.g., -999)
    pattern_10m = [p for p in pattern_10m if p['gain'] > -100]
    # Sort by elevation
    pattern_10m = sorted(pattern_10m, key=lambda p: p['el'])
    el_angles = [p['el'] for p in pattern_10m]
    gains = [p['gain'] for p in pattern_10m]
    # Convert elevation to radians for polar plot (0 deg = horizon at right/E, 90 deg = zenith at top/N)
    theta_rad = np.radians(el_angles)
    # Debug: print first 10 elevation angles and their theta_rad values
    print("Elevation (deg) -> theta (rad) for polar plot:")
    for el, th in list(zip(el_angles, theta_rad))[:10]:
        print(f"  el={el:.1f} deg -> theta={th:.3f} rad")
    # Convert dBi to linear power ratios
    r_linear = [10**(g/10.0) for g in gains]
    plt.figure(figsize=(7,7))
    ax = plt.subplot(111, polar=True)
    ax.plot(theta_rad, r_linear, label='Power ratio (az=0, h=10m)')
    ax.set_theta_zero_location('E')  # 0° elevation at right (horizon)
    ax.set_theta_direction(1)        # Increasing elevation moves counterclockwise
    ax.set_title('Elevation Pattern (az=0, h=10m)', va='bottom')
    # Set log scale for radial axis
    ax.set_rscale('log')
    # Define radial ticks at dB intervals
    min_db = -40
    max_db = int(max(gains))
    db_ticks = list(range(min_db, max_db+1, 10))
    r_ticks = [10**(d/10.0) for d in db_ticks]
    ax.set_rticks(r_ticks)
    ax.set_yticklabels([f"{d} dB" for d in db_ticks])
    ax.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main() 