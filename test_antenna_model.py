import pytest
from antenna_model import build_dipole_model, AntennaSimulator, resonant_dipole_length, get_ground_opts, feet_to_meters, meters_to_feet
import re

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