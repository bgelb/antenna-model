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

def main():
    # Frequency in MHz and height in feet
    freq_mhz = 14.1
    height_ft = 30
    height_m = height_ft * 0.3048

    # Speed of light (m/s)
    c = 299792458.0
    # Wavelength and half-wave length
    wavelength = c / (freq_mhz * 1e6)
    dipole_length = wavelength / 2.0
    half_length = dipole_length / 2.0

    # Dipole segmentation (odd number to center feed on a segment edge)
    segments = 21
    # Wire radius in meters (thin-wire approximation)
    radius = 0.001

    # Build the pymininec command for absolute far-field in E-plane (φ=0)
    cmd = [
        "pymininec",
        "-f", str(freq_mhz),
        "-w", f"{segments},{-half_length:.6f},0,{height_m:.6f},{half_length:.6f},0,{height_m:.6f},{radius:.6f}",
        "--excitation-pulse", f"{segments//2},1",
        "--option", "far-field-absolute",
        "--ff-distance", "1000",
        # Elevation cut in E-plane (phi=0)
        "--theta", "10,10,8",
        "--phi", "0,0,1",
    ]

    print("Running:", " ".join(shlex.quote(x) for x in cmd))

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print("Error calling pymininec:", e, file=sys.stderr)
        print("Stdout:", e.stdout, file=sys.stderr)
        print("Stderr:", e.stderr, file=sys.stderr)
        sys.exit(1)

    # Extract E(theta) magnitude for phi=0 from far-field absolute pattern
    et_pattern = []
    capture = False
    header = False
    for line in proc.stdout.splitlines():
        if not capture:
            if 'PATTERN DATA' in line:
                capture = True
            continue
        if not header:
            # wait for the table header line containing E(THETA)
            if 'E(THETA)' in line:
                header = True
            continue
        parts = line.strip().split()
        # expect rows: theta, phi, E(theta) mag, phase, E(phi) mag, phase
        if len(parts) < 6:
            continue
        try:
            theta = float(parts[0])
            phi = float(parts[1])
            etheta = float(parts[2])
        except ValueError:
            continue
        # include only phi=0 rows
        if abs(phi) < 1e-6:
            et_pattern.append((theta, etheta))
    if not et_pattern:
        print("No E-plane pattern data found (phi=0).")
        sys.exit(1)
    # normalize and compute relative gain in dB
    max_etheta = max(val for _, val in et_pattern)
    pattern_db = [(theta, 20 * math.log10(val / max_etheta)) for theta, val in et_pattern]
    # Print the normalized pattern
    print("\nElevation (deg) | Relative Gain (dB)")
    print("-----------------------------------")
    for theta, db in pattern_db:
        print(f"{theta:8.1f} | {db:7.2f}")

if __name__ == "__main__":
    main() 