#!/usr/bin/env python3
"""
Model a 2-element beam with 88' driven element and a resonant passive reflector
cut for resonance at 7.1 MHz, detuned slightly. Spacing is 20' behind the driven.
Plot azimuth and elevation patterns at 7.1 and 3.5 MHz with reflector detuned by 3%, 4%, 5%, and 6%.
Add a table of feedpoint impedance at both frequencies for each detune.
"""
import argparse
import os
from typing import Dict, List
import numpy as np
import math
import matplotlib.pyplot as plt
from antenna_model import (
    feet_to_meters,
    resonant_dipole_length,
    AntennaElement,
    AntennaModel,
    AntennaSimulator,
    plot_polar_patterns,
    Report,
    build_dipole_model
)

def build_two_element_beam_88ft(
    detune_frac: float,
    driven_length_ft: float = 88.0,
    spacing_ft: float = 20.0,
    reflector_resonant_freq_mhz: float = 7.1,
    segments: int = 21,
    radius: float = 0.001,
) -> AntennaModel:
    """
    Build a 2-element beam model: an 88' driven wire and a passive reflector cut
    for resonance at reflector_resonant_freq_mhz, then detuned by detune_frac.
    Spacing is spacing_ft behind the driven element.
    """
    # Convert lengths
    spacing_m = feet_to_meters(spacing_ft)
    driven_length_m = feet_to_meters(driven_length_ft)
    # Driven element
    half_driven = driven_length_m / 2.0
    # Reflector base resonant length
    base_reflector_length = resonant_dipole_length(reflector_resonant_freq_mhz)
    # Apply detune
    detuned_reflector_length = base_reflector_length * (1.0 + detune_frac)
    half_reflector = detuned_reflector_length / 2.0

    model = AntennaModel()
    # Add driven element
    el1 = AntennaElement(
        x1=0.0, y1=-half_driven, z1=0.0,
        x2=0.0, y2= half_driven, z2=0.0,
        segments=segments, radius=radius
    )
    model.add_element(el1)
    center_seg = (segments + 1) // 2
    model.add_feedpoint(element_index=0, segment=center_seg)
    # Add passive reflector behind along x-axis
    el2 = AntennaElement(
        x1=-spacing_m, y1=-half_reflector, z1=0.0,
        x2=-spacing_m, y2= half_reflector, z2=0.0,
        segments=segments, radius=radius
    )
    model.add_element(el2)
    return model


def main():
    parser = argparse.ArgumentParser(
        description="2-element beam: 88' driven, resonant reflector at 7.1 MHz detuned by 3-6%."
    )
    parser.add_argument('--show-gui', action='store_true',
                        help='Display plots interactively instead of saving PNG.')
    args = parser.parse_args()

    # Simulation parameters
    height_m = 20.0
    freqs_mhz = [7.1, 3.5]
    detune_fracs = [0.03, 0.04, 0.05, 0.06]
    # Define cases: (label, detune_frac), None detune_frac means no reflector
    cases = [
        ("No reflector", None),
        ("3%", 0.03),
        ("4%", 0.04),
        ("5%", 0.05),
        ("6%", 0.06),
    ]
    segments = 21
    radius = 0.001
    ground = 'average'
    el_fixed = 30.0  # elevation for azimuth cut

    sim = AntennaSimulator()
    report = Report('2_el_beam_88ft')

    # Split feedpoint impedance into separate tables per frequency
    imp7_rows: List[List[str]] = []
    imp3_rows: List[List[str]] = []
    for label, detune in cases:
        # Build model: dipole only or two-element beam
        if detune is None:
            driven_length_m = feet_to_meters(88.0)
            model = build_dipole_model(total_length=driven_length_m, segments=segments, radius=radius)
        else:
            model = build_two_element_beam_88ft(detune, segments=segments, radius=radius)
        # Impedance at 7.1 MHz
        R7, X7 = sim.simulate_pattern(
            model, freq_mhz=7.1, height_m=height_m, ground=ground,
            el_step=45.0, az_step=360.0
        )['impedance']
        # Impedance at 3.5 MHz
        R3, X3 = sim.simulate_pattern(
            model, freq_mhz=3.5, height_m=height_m, ground=ground,
            el_step=45.0, az_step=360.0
        )['impedance']
        # Series compensation for 7.1
        if X7 > 0:
            C7 = 1/(2*math.pi*7.1e6*X7)
            match7 = f"C={C7*1e12:.1f} pF"
        else:
            L7 = abs(X7)/(2*math.pi*7.1e6)
            match7 = f"L={L7*1e9:.1f} nH"
        # Series compensation for 3.5 MHz
        if X3 > 0:
            C3 = 1/(2*math.pi*3.5e6*X3)
            match3 = f"C={C3*1e12:.1f} pF"
        else:
            L3 = abs(X3)/(2*math.pi*3.5e6)
            match3 = f"L={L3*1e9:.1f} nH"
        imp7_rows.append([label, f"{R7:.2f}", f"{X7:.2f}", match7])
        imp3_rows.append([label, f"{R3:.2f}", f"{X3:.2f}", match3])
    report.add_table(
        "Feedpoint Impedance at 7.1 MHz vs Case",
        ["Case", "R (Ω)", "X (Ω)", "Match"],
        imp7_rows,
        parameters=f"driven=88'; spacing=20'; height={height_m} m; segments={segments}; radius={radius} m; ground={ground}"
    )
    report.add_table(
        "Feedpoint Impedance at 3.5 MHz vs Case",
        ["Case", "R (Ω)", "X (Ω)", "Match"],
        imp3_rows,
        parameters=f"driven=88'; spacing=20'; height={height_m} m; segments={segments}; radius={radius} m; ground={ground}"
    )
    # Forward Gain and Front-to-Back tables at each frequency (beam cases + half-wave dipole reference)
    for freq in freqs_mhz:
        fgfb_rows: List[List[str]] = []
        # Beam / reflector cases
        for label, detune in cases:
            if detune is None:
                # 88' driven element without reflector
                driven_length_m = feet_to_meters(88.0)
                model = build_dipole_model(total_length=driven_length_m, segments=segments, radius=radius)
            else:
                model = build_two_element_beam_88ft(detune, segments=segments, radius=radius)
            az_res = sim.simulate_azimuth_pattern(
                model, freq_mhz=freq, height_m=height_m, ground=ground, el=el_fixed, az_step=5.0
            )
            fwd_gain = next(p['gain'] for p in az_res if abs(p['az'] - 0.0) < 1e-6)
            back_gain = next(p['gain'] for p in az_res if abs(p['az'] - 180.0) < 1e-6)
            fgfb_rows.append([label, f"{fwd_gain:.2f}", f"{(fwd_gain - back_gain):.2f}"])
        # Half-wave dipole reference at this frequency
        ref_length = resonant_dipole_length(freq)
        ref_model = build_dipole_model(total_length=ref_length, segments=segments, radius=radius)
        az_res_ref = sim.simulate_azimuth_pattern(
            ref_model, freq_mhz=freq, height_m=height_m, ground=ground, el=el_fixed, az_step=5.0
        )
        fwd_ref = next(p['gain'] for p in az_res_ref if abs(p['az'] - 0.0) < 1e-6)
        back_ref = next(p['gain'] for p in az_res_ref if abs(p['az'] - 180.0) < 1e-6)
        fgfb_rows.append(["Half-wave dipole", f"{fwd_ref:.2f}", f"{(fwd_ref - back_ref):.2f}"])
        report.add_table(
            f"Forward Gain and F/B at {freq:.1f} MHz",
            ["Case", "Fwd Gain (dB)", "F/B (dB)"],
            fgfb_rows,
            parameters=f"height={height_m} m; el={el_fixed}°; ground={ground}; segments={segments}; radius={radius} m; freq={freq} MHz"
        )

    # Pattern plots for each frequency (including beam cases and half-wave dipole reference)
    for freq in freqs_mhz:
        elev_pats: Dict[str, List[Dict[str, float]]] = {}
        az_pats: Dict[str, List[Dict[str, float]]] = {}
        # Beam/reflector cases
        for label, detune in cases:
            if detune is None:
                driven_length_m = feet_to_meters(88.0)
                model = build_dipole_model(total_length=driven_length_m, segments=segments, radius=radius)
            else:
                model = build_two_element_beam_88ft(detune, segments=segments, radius=radius)
            # Elevation (az=0)
            res = sim.simulate_pattern(
                model, freq_mhz=freq, height_m=height_m, ground=ground,
                el_step=1.0, az_step=360.0
            )
            elev_pats[label] = res['pattern']
            # Azimuth (el fixed)
            az_pats[label] = sim.simulate_azimuth_pattern(
                model, freq_mhz=freq, height_m=height_m, ground=ground,
                el=el_fixed, az_step=5.0
            )
        # Half-wave dipole reference
        ref_label = "Half-wave dipole"
        ref_length = resonant_dipole_length(freq)
        ref_model = build_dipole_model(total_length=ref_length, segments=segments, radius=radius)
        res_ref = sim.simulate_pattern(
            ref_model, freq_mhz=freq, height_m=height_m, ground=ground,
            el_step=1.0, az_step=360.0
        )
        elev_pats[ref_label] = res_ref['pattern']
        az_pats[ref_label] = sim.simulate_azimuth_pattern(
            ref_model, freq_mhz=freq, height_m=height_m, ground=ground,
            el=el_fixed, az_step=5.0
        )
        # Compile labels including dipole ref
        plot_labels = [label for label, _ in cases] + [ref_label]
        output_file = os.path.join(report.report_dir, f'polar_patterns_{freq:.1f}MHz.png')
        plot_polar_patterns(
            elev_pats, az_pats, plot_labels, el_fixed,
            output_file, args.show_gui, legend_labels=plot_labels
        )
        report.add_plot(
            f'Polar Patterns at {freq:.1f} MHz',
            output_file,
            parameters=f"height={height_m} m; ground={ground}; segments={segments}; radius={radius} m; el={el_fixed}°"
        )

    # === Elevation study: best detune vs height at 7.1 MHz ===
    heights_study = [10.0, 15.0, 20.0]
    best_detunes: Dict[float, float] = {}
    for h in heights_study:
        best_fb = float('-inf')
        best_df = None
        for df in detune_fracs:
            m = build_two_element_beam_88ft(df, segments=segments, radius=radius)
            azres = sim.simulate_azimuth_pattern(
                m, freq_mhz=7.1, height_m=h, ground=ground, el=el_fixed, az_step=5.0
            )
            fwd = next(p['gain'] for p in azres if abs(p['az']) < 1e-6)
            back = next(p['gain'] for p in azres if abs(p['az'] - 180.0) < 1e-6)
            fb = fwd - back
            if fb > best_fb:
                best_fb = fb
                best_df = df
        best_detunes[h] = best_df
    # Multi-height beam-only patterns at 7.1 MHz for heights 10m, 15m, 20m
    elev_multi: Dict[float, List[Dict[str, float]]] = {}
    az_multi: Dict[float, List[Dict[str, float]]] = {}
    for h in heights_study:
        df = best_detunes[h]
        m = build_two_element_beam_88ft(df, segments=segments, radius=radius)
        res = sim.simulate_pattern(
            m, freq_mhz=7.1, height_m=h, ground=ground,
            el_step=1.0, az_step=360.0
        )
        elev_multi[h] = res['pattern']
        az_multi[h] = sim.simulate_azimuth_pattern(
            m, freq_mhz=7.1, height_m=h, ground=ground,
            el=el_fixed, az_step=5.0
        )
    multi_labels = [f"{h:.0f} m" for h in heights_study]
    multi_file = os.path.join(report.report_dir, 'beam_patterns_heights_7.1MHz.png')
    plot_polar_patterns(
        elev_multi, az_multi, heights_study, el_fixed,
        multi_file, args.show_gui, legend_labels=multi_labels
    )
    report.add_plot(
        'Beam Patterns vs Height at 7.1 MHz',
        multi_file,
        parameters=f"heights={heights_study}; detunes={[best_detunes[h] for h in heights_study]}; spacing=20'; ground={ground}; segments={segments}; radius={radius} m; el={el_fixed}°"
    )
    # Beam vs Dipole comparison at each height for elevation study
    for h in heights_study:
        df = best_detunes[h]
        # Beam pattern
        beam_model = build_two_element_beam_88ft(df, segments=segments, radius=radius)
        beam_el_pat = sim.simulate_pattern(
            beam_model, freq_mhz=7.1, height_m=h, ground=ground,
            el_step=1.0, az_step=360.0
        )['pattern']
        beam_az_pat = sim.simulate_azimuth_pattern(
            beam_model, freq_mhz=7.1, height_m=h, ground=ground,
            el=el_fixed, az_step=5.0
        )
        # Dipole reference pattern
        dip_length = resonant_dipole_length(7.1)
        dip_model = build_dipole_model(total_length=dip_length, segments=segments, radius=radius)
        dip_el_pat = sim.simulate_pattern(
            dip_model, freq_mhz=7.1, height_m=h, ground=ground,
            el_step=1.0, az_step=360.0
        )['pattern']
        dip_az_pat = sim.simulate_azimuth_pattern(
            dip_model, freq_mhz=7.1, height_m=h, ground=ground,
            el=el_fixed, az_step=5.0
        )
        # Compile patterns for comparison
        cmp_el_pats = {'Beam': beam_el_pat, 'Dipole': dip_el_pat}
        cmp_az_pats = {'Beam': beam_az_pat, 'Dipole': dip_az_pat}
        cmp_keys = ['Beam', 'Dipole']
        cmp_labels = [f"Beam (detune={df*100:.1f}%)", 'Dipole']
        cmp_output = os.path.join(report.report_dir, f'beam_vs_dipole_{int(h)}m.png')
        plot_polar_patterns(
            cmp_el_pats, cmp_az_pats, cmp_keys, el_fixed,
            cmp_output, args.show_gui, legend_labels=cmp_labels
        )
        report.add_plot(
            f'Beam vs Dipole at {h:.0f} m (7.1 MHz)', cmp_output,
            parameters=f"frequency=7.1 MHz; height={h} m; detune={df*100:.1f}%; spacing=20'; ground={ground}; segments={segments}; radius={radius} m; el={el_fixed}°"
        )

    # Feedpoint impedance vs height for beam (best detune) and half-wave dipole at 7.1 MHz
    imp_study: List[List[str]] = []
    for h in heights_study:
        df = best_detunes[h]
        # Beam impedance
        beam_model = build_two_element_beam_88ft(df, segments=segments, radius=radius)
        Rb, Xb = sim.simulate_pattern(
            beam_model, freq_mhz=7.1, height_m=h, ground=ground,
            el_step=45.0, az_step=360.0
        )['impedance']
        if Xb > 0:
            Cb = 1/(2*math.pi*7.1e6*Xb)
            matchb = f"C={Cb*1e12:.1f} pF"
        else:
            Lb = abs(Xb)/(2*math.pi*7.1e6)
            matchb = f"L={Lb*1e9:.1f} nH"
        imp_study.append([f"{h:.0f}", f"Beam", f"{df*100:.1f}%", f"{Rb:.2f}", f"{Xb:.2f}", matchb])
        # Dipole impedance
        dip_length = resonant_dipole_length(7.1)
        dip_model = build_dipole_model(total_length=dip_length, segments=segments, radius=radius)
        Rd, Xd = sim.simulate_pattern(
            dip_model, freq_mhz=7.1, height_m=h, ground=ground,
            el_step=45.0, az_step=360.0
        )['impedance']
        if Xd > 0:
            Cd = 1/(2*math.pi*7.1e6*Xd)
            matchd = f"C={Cd*1e12:.1f} pF"
        else:
            Ld = abs(Xd)/(2*math.pi*7.1e6)
            matchd = f"L={Ld*1e9:.1f} nH"
        imp_study.append([f"{h:.0f}", f"Dipole", "", f"{Rd:.2f}", f"{Xd:.2f}", matchd])
    report.add_table(
        'Feedpoint Impedance vs Height Comparison',
        ['Height (m)', 'Type', 'Detune (%)', 'R (Ω)', 'X (Ω)', 'Match'],
        imp_study,
        parameters=f"frequency=7.1 MHz; spacing=20'; ground={ground}; segments={segments}; radius={radius} m"
    )
    # Forward Gain and F/B vs Height at 7.1 MHz (Optimum beam vs No Reflector)
    fgfb_height_rows: List[List[str]] = []
    for h in heights_study:
        df = best_detunes[h]
        # Beam at optimum detune
        beam_model = build_two_element_beam_88ft(df, segments=segments, radius=radius)
        az_beam = sim.simulate_azimuth_pattern(
            beam_model, freq_mhz=7.1, height_m=h, ground=ground, el=el_fixed, az_step=5.0
        )
        fwd_beam = next(p['gain'] for p in az_beam if abs(p['az']) < 1e-6)
        back_beam = next(p['gain'] for p in az_beam if abs(p['az'] - 180.0) < 1e-6)
        fb_beam = fwd_beam - back_beam
        # No reflector (dipole)
        driven_len_m = feet_to_meters(88.0)
        no_ref_model = build_dipole_model(total_length=driven_len_m, segments=segments, radius=radius)
        az_no = sim.simulate_azimuth_pattern(
            no_ref_model, freq_mhz=7.1, height_m=h, ground=ground, el=el_fixed, az_step=5.0
        )
        fwd_no = next(p['gain'] for p in az_no if abs(p['az']) < 1e-6)
        back_no = next(p['gain'] for p in az_no if abs(p['az'] - 180.0) < 1e-6)
        fb_no = fwd_no - back_no
        fgfb_height_rows.append([
            f"{h:.0f}", f"{df*100:.1f}%", f"{fwd_beam:.2f}", f"{fb_beam:.2f}", f"{fwd_no:.2f}", f"{fb_no:.2f}"
        ])
    report.add_table(
        'Forward Gain & F/B vs Height (7.1 MHz)',
        ['Height (m)', 'Detune (%)', 'Beam Fwd (dB)', 'Beam F/B (dB)', 'No reflector Fwd (dB)', 'No reflector F/B (dB)'],
        fgfb_height_rows,
        parameters=f"spacing=20'; ground={ground}; segments={segments}; radius={radius} m; el={el_fixed}°"
    )
    # === Spacing study at 20 m height for 18ft and 16ft ===
    for spacing_ft in [18.0, 16.0]:
        # Impedance vs detune
        imp_spacing: List[List[str]] = []
        for df in detune_fracs:
            model = build_two_element_beam_88ft(df, driven_length_ft=88.0, spacing_ft=spacing_ft, segments=segments, radius=radius)
            R, X = sim.simulate_pattern(
                model, freq_mhz=7.1, height_m=height_m, ground=ground,
                el_step=45.0, az_step=360.0
            )['impedance']
            imp_spacing.append([f"{int(df*100)}%", f"{R:.2f}", f"{X:.2f}"])
        report.add_table(
            f'Feedpoint Impedance vs Detune (spacing={int(spacing_ft)} ft)',
            ['Detune (%)', 'R (Ω)', 'X (Ω)'],
            imp_spacing,
            parameters=f"frequency=7.1 MHz; height={height_m} m; spacing={int(spacing_ft)} ft; ground={ground}; segments={segments}; radius={radius} m"
        )
        # Pattern plots vs detune
        elev_sweep: Dict[float, List[Dict[str, float]]] = {}
        az_sweep: Dict[float, List[Dict[str, float]]] = {}
        for df in detune_fracs:
            model = build_two_element_beam_88ft(df, driven_length_ft=88.0, spacing_ft=spacing_ft, segments=segments, radius=radius)
            elev_sweep[df] = sim.simulate_pattern(
                model, freq_mhz=7.1, height_m=height_m, ground=ground,
                el_step=1.0, az_step=360.0
            )['pattern']
            az_sweep[df] = sim.simulate_azimuth_pattern(
                model, freq_mhz=7.1, height_m=height_m, ground=ground,
                el=el_fixed, az_step=5.0
            )
        labels = [f"{int(df*100)}%" for df in detune_fracs]
        out_png = os.path.join(report.report_dir, f'detune_sweep_spacing_{int(spacing_ft)}ft.png')
        plot_polar_patterns(
            elev_sweep, az_sweep, detune_fracs, el_fixed,
            out_png, args.show_gui, legend_labels=labels
        )
        report.add_plot(
            f'Detune Sweep Polar Patterns (spacing={int(spacing_ft)} ft)',
            out_png,
            parameters=f"frequency=7.1 MHz; height={height_m} m; spacing={int(spacing_ft)} ft; ground={ground}; segments={segments}; radius={radius} m; el={el_fixed}°"
        )
        # Forward gain & F/B vs detune
        fgfb_rows_sp: List[List[str]] = []
        for df in detune_fracs:
            model = build_two_element_beam_88ft(df, driven_length_ft=88.0, spacing_ft=spacing_ft, segments=segments, radius=radius)
            az = sim.simulate_azimuth_pattern(model, freq_mhz=7.1, height_m=height_m, ground=ground, el=el_fixed, az_step=5.0)
            fwd = next(p['gain'] for p in az if abs(p['az']) < 1e-6)
            back = next(p['gain'] for p in az if abs(p['az'] - 180.0) < 1e-6)
            fgfb_rows_sp.append([f"{int(df*100)}%", f"{fwd:.2f}", f"{(fwd-back):.2f}"])
        report.add_table(
            f'Forward Gain & F/B vs Detune (spacing={int(spacing_ft)} ft)',
            ['Detune (%)', 'Fwd Gain (dB)', 'F/B (dB)'],
            fgfb_rows_sp,
            parameters=f"frequency=7.1 MHz; height={height_m} m; spacing={int(spacing_ft)} ft; ground={ground}; segments={segments}; radius={radius} m; el={el_fixed}°"
        )

    report.save()

if __name__ == "__main__":
    main() 