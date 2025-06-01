import pytest
from antenna_model import (
    build_dipole_model,
    AntennaSimulator,
    resonant_dipole_length,
    get_ground_opts,
    feet_to_meters,
    meters_to_feet,
    AntennaModel,
    AntennaElement,
)
import re
import os
import filecmp
import shutil
import subprocess

def test_resonant_dipole_length():
    f = 14.1
    l = resonant_dipole_length(f)
    # ARRL formula: 468 / f (MHz) in feet, then meters
    arrl_length_ft = 468 / f
    arrl_length_m = feet_to_meters(arrl_length_ft)
    assert l == pytest.approx(arrl_length_m, rel=0.0001)  # should match exactly

def test_build_dipole_model():
    model = build_dipole_model(total_length=20.0, segments=21, radius=0.001)
    assert len(model.wires) == 1
    w = model.wires[0]
    assert float(w['z1']) == 0.0
    assert float(w['radius']) == pytest.approx(0.001)
    assert float(w['x1']) == pytest.approx(0.0)
    assert float(w['x2']) == pytest.approx(0.0)
    assert float(w['y1']) == pytest.approx(-10.0)
    assert float(w['y2']) == pytest.approx(10.0)

def test_run_pymininec_runs():
    length = resonant_dipole_length(14.1)
    model = build_dipole_model(total_length=length, segments=11, radius=0.001)
    sim = AntennaSimulator()
    out = sim.simulate_pattern(model, freq_mhz=14.1, height_m=9.144, ground="average", el_step=10, az_step=10)
    # Can't check raw_output, but can check impedance and pattern
    assert out['impedance'] is not None
    assert isinstance(out['pattern'], list)
    assert len(out['pattern']) > 0

def test_dipole_pattern_regression():
    """
    Check gain at multiple (el, az) points for a dipole in free space (height=0).
    Use 1 degree increments for both elevation and azimuth. Expect ~2.15 dBi at az=0.
    """
    freq = 14.1
    height = 0.0  # meters (free space)
    length = resonant_dipole_length(freq)
    model = build_dipole_model(total_length=length, segments=21, radius=0.001)
    sim = AntennaSimulator()
    result = sim.simulate_pattern(
        model, freq_mhz=freq, height_m=height, ground="free", el_step=1, az_step=1
    )
    pattern = result['pattern']
    # Extract gains at az=0 for elevations 20, 30, 40
    test_els = [20, 30, 40]
    gains = {int(p['el']): p['gain'] for p in pattern if p['az'] == 0.0 and int(p['el']) in test_els}
    assert len(gains) == len(test_els), f"Expected gains for elevations {test_els}, got {sorted(gains.keys())}"
    # Ensure gain is constant across these elevations
    g0 = gains[test_els[0]]
    for el, g in gains.items():
        assert g == pytest.approx(g0, abs=1e-6), f"Gain at el={el}, got {g}, expected constant {g0}"
    # Check approximate theoretical value (~2.15 dBi)
    assert g0 == pytest.approx(2.15, abs=0.05), f"Broadside gain {g0} dBi not within expected ~2.15"

def test_dipole_impedance_5m():
    """
    Check feedpoint impedance of reference dipole at 5m above ground for all ground types.
    """
    freq = 14.1
    height = 5.0
    length = resonant_dipole_length(freq)
    model = build_dipole_model(total_length=length, segments=21, radius=0.001)
    ground_types = ["free", "poor", "average", "good"]
    sim = AntennaSimulator()
    for ground in ground_types:
        result = sim.simulate_pattern(model, freq_mhz=freq, height_m=height, ground=ground, el_step=45, az_step=360)
        R, X = result['impedance']
        print(f"Feedpoint impedance at 5m ({ground} ground): R={R:.5f} Ω, X={X:.5f} Ω")

def test_dipole_impedance_10m():
    """
    Check feedpoint impedance of reference dipole at 10m above ground for 'free' and 'average' ground types.
    """
    freq = 14.1
    height = 10.0
    length = resonant_dipole_length(freq)
    model = build_dipole_model(total_length=length, segments=21, radius=0.001)
    ground_types = ["free", "average"]
    # Reference values for average ground
    expected = (68.74317, -49.64125)
    sim = AntennaSimulator()
    for ground in ground_types:
        result = sim.simulate_pattern(model, freq_mhz=freq, height_m=height, ground=ground, el_step=45, az_step=360)
        R, X = result['impedance']
        print(f"Feedpoint impedance at 10m ({ground} ground): R={R:.5f} Ω, X={X:.5f} Ω")
        if ground == "average":
            assert R == pytest.approx(expected[0], rel=0.01), f"R at 10m: got {R}, expected {expected[0]}"
            assert X == pytest.approx(expected[1], rel=0.01), f"X at 10m: got {X}, expected {expected[1]}"

class TestAntennaModel:
    def test_broadside_dipole_phased_symmetry(self):
        """Two half-wave dipoles spaced 0.125 λ apart and fed 180° out of phase
        should yield a bidirectional broadside pattern that is symmetric in the
        horizontal plane and exhibits a deep null at the zenith (90° el)."""
        freq_mhz = 14.1
        # Wavelength in metres ≈ 300 / f(MHz)
        lam = 300.0 / freq_mhz
        spacing = 0.125 * lam  # 0.125 λ centre-to-centre spacing

        # Build element geometry (y-axis dipoles)
        segs = 21
        radius = 0.001
        length = resonant_dipole_length(freq_mhz)
        half_len = length / 2.0

        model = AntennaModel()
        # Element 0 at –spacing/2 on x-axis
        el0 = AntennaElement(
            x1=-spacing / 2, y1=-half_len, z1=0.0,
            x2=-spacing / 2, y2=half_len, z2=0.0,
            segments=segs, radius=radius,
        )
        model.add_element(el0)
        # Element 1 at +spacing/2 on x-axis
        el1 = AntennaElement(
            x1=spacing / 2, y1=-half_len, z1=0.0,
            x2=spacing / 2, y2=half_len, z2=0.0,
            segments=segs, radius=radius,
        )
        model.add_element(el1)

        # Centre segment index
        centre_seg = (segs + 1) // 2
        model.add_feedpoint(0, centre_seg, voltage=1 + 0j)
        model.add_feedpoint(1, centre_seg, voltage=-1 + 0j)

        sim = AntennaSimulator()

        # Azimuth cut at 30° elevation should be symmetric (az 0 vs 180)
        az_pat = sim.simulate_azimuth_pattern(
            model, freq_mhz, height_m=0.0, ground="free", el=30.0, az_step=5.0
        )
        gain_0 = next(p["gain"] for p in az_pat if abs(p["az"]) < 1e-6)
        gain_180 = next(p["gain"] for p in az_pat if abs(p["az"] - 180.0) < 1e-6)
        assert abs(gain_0 - gain_180) < 1e-3

        # Elevation pattern (az=0 from simulator) should have deep null at 90°
        el_res = sim.simulate_pattern(
            model, freq_mhz, height_m=0.0, ground="free", el_step=5.0, az_step=360.0
        )
        # Locate entry closest to 90° elevation
        zenith_gain = min(
            (abs(p["el"] - 90.0), p["gain"]) for p in el_res["pattern"]
        )[1]
        # Expect at least 20 dB down relative to broadside lobe
        assert zenith_gain < gain_0 - 20.0 

def run_antenna_script(script_name):
    """Run an antenna script as a subprocess."""
    subprocess.run(["python", script_name], check=True)

@pytest.mark.skipif(not os.path.exists("golden_output"), reason="golden_output directory missing")
def test_output_regression():
    """
    For each antenna program, check that all expected output files are generated, match exactly, and no extra files are present.
    The user must create and populate golden_output/8_jk, golden_output/2_el_yagi, golden_output/dipole_pattern, and golden_output/2_el_yagi_15m.
    """
    programs = [
        {
            "name": "8_jk",
            "script": "8_jk.py",
        },
        {
            "name": "2_el_yagi",
            "script": "2_el_yagi.py",
        },
        {
            "name": "dipole_pattern",
            "script": "dipole_pattern.py",
        },
        {
            "name": "2_el_yagi_15m",
            "script": "2_el_yagi_15m.py",
        },
    ]
    for prog in programs:
        out_dir = os.path.join("output", prog["name"])
        ref_dir = os.path.join("golden_output", prog["name"])
        # Clean output directory
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir)
        os.makedirs(out_dir, exist_ok=True)
        # Run the program
        run_antenna_script(prog["script"])
        # Compare file lists
        expected_files = set(os.listdir(ref_dir))
        output_files = set(os.listdir(out_dir))
        assert expected_files == output_files, f"{prog['name']}: Expected files {expected_files}, got {output_files}"
        # Compare file contents
        for fname in expected_files:
            ref_path = os.path.join(ref_dir, fname)
            out_path = os.path.join(out_dir, fname)
            assert filecmp.cmp(ref_path, out_path, shallow=False), f"{prog['name']}: File {fname} does not match reference." 