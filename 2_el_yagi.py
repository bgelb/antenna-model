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
)

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
    model = AntennaModel()

    # Driven element (half-wave dipole) at origin
    half_len = driven_length / 2.0
    driven = AntennaElement(
        x1=0.0, y1=-half_len, z1=0.0,
        x2=0.0, y2= half_len, z2=0.0,
        segments=segments, radius=radius,
    )
    model.add_element(driven)
    # Feedpoint at center segment of driven element
    center_seg = (segments + 1) // 2
    model.add_feedpoint(element_index=0, segment=center_seg)

    # Passive reflector: 5% longer, spaced 0.2 λ along x-axis
    c = 299792458.0
    lambda_m = c / (freq_mhz * 1e6)
    spacing = 0.2 * lambda_m
    # Compute passive element length using resonant_dipole_length at 5% reduced frequency to get 5% longer length
    passive_length = resonant_dipole_length(freq_mhz / 1.05)
    half_pass = passive_length / 2.0
    passive = AntennaElement(
        x1=-spacing, y1=-half_pass, z1=0.0,
        x2=-spacing, y2= half_pass, z2=0.0,
        segments=segments, radius=radius,
    )
    model.add_element(passive)

    sim = AntennaSimulator()

    # 1) Feedpoint impedance vs height
    heights_imp = [5.0, 10.0, 15.0, 20.0]
    print("Feedpoint impedance vs height (average ground):")
    print("Height (m) |    R (Ω)   |   X (Ω)")
    print("-----------------------------------")
    for h in heights_imp:
        result = sim.simulate_pattern(
            model, freq_mhz=freq_mhz, height_m=h, ground=ground, el_step=45.0, az_step=360.0
        )
        R, X = result['impedance']
        print(f"   {h:6.1f} | {R:9.2f} | {X:8.2f}")

    # 2) Combined polar plots for elevation and azimuth patterns
    heights = [5.0, 10.0, 15.0, 20.0]
    full_patterns = {h: sim.simulate_pattern(model, freq_mhz=freq_mhz, height_m=h, ground=ground, el_step=1.0, az_step=360.0)['pattern'] for h in heights}

    el_angles = list(range(0, 181, 5))
    print("\nGain at az=0 for el=0 to 180° (average ground), for various heights:")
    header = "Elevation (deg) |" + "".join([f" {h:>7} m" for h in heights])
    print(header)
    print("----------------|" + "-------" * len(heights))
    highlight = {h: int(round(max(full_patterns[h], key=lambda p: p['gain'])['el'] / 5.0) * 5) for h in heights}
    for el in el_angles:
        row = f"{el:8d}         |"
        for h in heights:
            closest = min(full_patterns[h], key=lambda p: abs(p['el'] - el))
            g = closest['gain']
            if el == highlight[h]:
                row += f" \033[1;33m{g:7.3f}\033[0m"
            else:
                row += f" {g:7.3f}"
        print(row)

    # 3) Azimuth patterns at fixed elevation (30°)
    el_fixed = 30.0
    az_patterns = {h: sim.simulate_azimuth_pattern(model, freq_mhz=freq_mhz, height_m=h, ground=ground, el=el_fixed, az_step=5.0) for h in heights}

    # Plotting
    fig, (ax1, ax2) = plt.subplots(1, 2, subplot_kw={'polar': True}, figsize=(14, 7))
    colors = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red']

    # Elevation pattern (az=0)
    raw_max = max(max(p['gain'] for p in full_patterns[h]) for h in heights)
    tick_int = 10
    min_db = -40
    max_db = int(tick_int * math.ceil(raw_max / tick_int))
    db_ticks = list(range(min_db, max_db + tick_int, tick_int))
    r_ticks = [10**(d/10.0) for d in db_ticks]
    ax1.set_theta_zero_location('E')
    ax1.set_theta_direction(1)
    ax1.set_title('Elevation Pattern (az=0, all heights)', va='bottom')
    ax1.set_rscale('log')
    ax1.set_rticks(r_ticks)
    ax1.set_yticklabels([f"{d} dB" for d in db_ticks])
    ax1.set_ylim(r_ticks[0], r_ticks[-1])
    ax1.grid(True)
    for idx, h in enumerate(heights):
        data = sorted(full_patterns[h], key=lambda p: p['el'])
        theta = np.radians([p['el'] for p in data])
        r = [10**(p['gain']/10.0) for p in data]
        ax1.plot(theta, r, label=f'h={h}m', color=colors[idx])
    ax1.legend(loc='upper right', bbox_to_anchor=(1.2, 1.1))

    # Azimuth pattern (el=30°)
    raw_max_az = max(max(p['gain'] for p in az_patterns[h]) for h in heights)
    db_ticks_az = list(range(min_db, int(math.ceil(raw_max_az))+1, 10))
    r_ticks_az = [10**(d/10.0) for d in db_ticks_az]
    ax2.set_theta_zero_location('E')
    ax2.set_theta_direction(-1)
    ax2.set_title(f'Azimuth Pattern (el={int(el_fixed)}°, all heights)', va='bottom')
    ax2.set_rscale('log')
    ax2.set_rticks(r_ticks_az)
    ax2.set_yticklabels([f"{d} dB" for d in db_ticks_az])
    ax2.grid(True)
    for idx, h in enumerate(heights):
        data = sorted(az_patterns[h], key=lambda p: p['az'])
        phi = np.radians([p['az'] for p in data])
        r = [10**(p['gain']/10.0) for p in data]
        ax2.plot(phi, r, label=f'h={h}m', color=colors[idx])
    ax2.legend(loc='upper right', bbox_to_anchor=(1.2, 1.1))

    plt.tight_layout()
    if args.show_gui:
        plt.show()
    else:
        plt.savefig('output/2_el_yagi_pattern.png')
        print('Saved 2-element Yagi pattern plot to output/2_el_yagi_pattern.png')

if __name__ == '__main__':
    main() 