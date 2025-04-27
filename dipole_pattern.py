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

    print("Feedpoint impedance vs height (average ground):")
    print("Height (ft) |    R (ohm) |   X (ohm)")
    print("-----------------------------------")
    for feet in heights_ft:
        height_m = feet_to_meters(feet)
        result = run_pymininec(
            model,
            freq_mhz=freq_mhz,
            height_m=height_m,
            ground_opts=ground_opts,
            excitation_pulse="10,1",
            pattern_opts={"theta": "45,0,1", "phi": "90,0,1"},
            option="far-field"
        )
        R, X = result['impedance']
        print(f"   {feet:6.1f} | {R:9.2f} | {X:8.2f}")

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

    # Print gain at az=90 for el=10 to 80 deg in 10 deg steps, for multiple heights
    heights_m = [5, 10, 15, 20]
    print("\nGain at az=90 for el=10 to 80 deg (average ground), for various heights:")
    header = "Elevation (deg) |" + "".join([f" {h:>5} m" for h in heights_m])
    print(header)
    print("----------------|" + "-------" * len(heights_m))
    for el in range(10, 90, 10):
        row = f"     {el:2d}         |"
        for h_m in heights_m:
            result = run_pymininec(
                model,
                freq_mhz=freq_mhz,
                height_m=h_m,
                ground_opts=ground_opts,
                excitation_pulse="10,1",
                pattern_opts={"theta": f"{el},0,1", "phi": "90,0,1"},
                option="far-field",
            )
            pattern = result['pattern']
            gain = None
            for p in pattern:
                if abs(p['el']-el)<1e-3 and abs(p['az']-90)<1e-3:
                    gain = p['gain']
                    break
            if gain is not None:
                row += f" {gain:7.3f}"
            else:
                row += f"    n/a "
        print(row)

    # Plot full elevation pattern at 5, 10, 15m (az=90)
    heights_m = [5, 10, 15]
    el_angles = list(range(0, 91, 5))
    plt.figure(figsize=(8, 5))
    for h_m in heights_m:
        gains = []
        for el in el_angles:
            result = run_pymininec(
                model,
                freq_mhz=freq_mhz,
                height_m=h_m,
                ground_opts=ground_opts,
                excitation_pulse="10,1",
                pattern_opts={"theta": f"{el},0,1", "phi": "90,0,1"},
                option="far-field",
            )
            pattern = result['pattern']
            gain = None
            for p in pattern:
                if abs(p['el']-el)<1e-3 and abs(p['az']-90)<1e-3:
                    gain = p['gain']
                    break
            gains.append(gain if gain is not None else float('nan'))
        plt.plot(el_angles, gains, label=f"{h_m} m")
    plt.xlabel("Elevation angle (deg)")
    plt.ylabel("Gain (dBi) at az=90")
    plt.title("Dipole Elevation Pattern at Various Heights (average ground)")
    plt.legend(title="Height")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main() 