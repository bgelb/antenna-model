import pytest
from antenna_model import build_dipole_model, run_pymininec, resonant_dipole_length, get_ground_opts, feet_to_meters, meters_to_feet
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
    assert float(w['x1']) == pytest.approx(-10.0)
    assert float(w['x2']) == pytest.approx(10.0)

def test_run_pymininec_runs():
    length = resonant_dipole_length(14.1)
    model = build_dipole_model(total_length=length, segments=11, radius=0.001)
    out = run_pymininec(model, freq_mhz=14.1, height_m=9.144, excitation_pulse="5,1", pattern_opts={"theta": "10,10,2", "phi": "0,10,2"}, ground_opts=get_ground_opts("average"))
    assert "MININEC" in out['raw_output']
    assert "FREQUENCY" in out['raw_output']
    assert "PATTERN DATA" in out['raw_output']

def test_dipole_pattern_regression():
    """
    Check gain at multiple (el, az) points for a dipole at 10m above average ground.
    Use 1 degree increments for both elevation and azimuth.
    """
    freq = 14.1
    height = 10.0  # meters
    length = resonant_dipole_length(freq)
    model = build_dipole_model(total_length=length, segments=21, radius=0.001)
    # Now el means elevation above horizon, so we want el=20,30,40 at az=90
    test_points = [
        (20, 90),
        (30, 90),
        (40, 90),
    ]
    # Reference values to be filled after running
    reference = {
        (20, 90): 5.917107,
        (30, 90): 6.890709,
        (40, 90): 6.039798,
    }
    for el, az in test_points:
        # Convert elevation above horizon to zenith angle for pymininec
        theta = 90 - el
        result = run_pymininec(
            model,
            freq_mhz=freq,
            height_m=height,
            ground_opts=get_ground_opts("average"),
            excitation_pulse="10,1",
            pattern_opts={"theta": f"{theta},0,1", "phi": f"{az},0,1"},
            option="far-field",
        )
        pattern = result['pattern']
        match = next((p for p in pattern if abs(p['el']-el)<1e-3 and abs(p['az']-az)<1e-3), None)
        print(f"Gain at el={el}, az={az}: {match['gain'] if match else 'not found'} dBi")
        if (el, az) in reference and reference[(el, az)] != 0.0:
            assert match, f"Pattern point for el={el}, az={az} not found"
            gain = match['gain']
            assert gain == pytest.approx(reference[(el, az)], abs=0.01), f"Gain at el={el}, az={az}: got {gain}, expected {reference[(el, az)]}"

def test_dipole_impedance_5m():
    """
    Check feedpoint impedance of reference dipole at 5m above ground for all ground types.
    """
    freq = 14.1
    height = 5.0
    length = resonant_dipole_length(freq)
    model = build_dipole_model(total_length=length, segments=21, radius=0.001)
    ground_types = ["free", "poor", "average", "good"]
    for ground in ground_types:
        result = run_pymininec(
            model,
            freq_mhz=freq,
            height_m=height,
            ground_opts=get_ground_opts(ground),
            excitation_pulse="10,1",
            pattern_opts={"theta": "45,0,1", "phi": "90,0,1"},
            option="far-field",
        )
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
    for ground in ground_types:
        result = run_pymininec(
            model,
            freq_mhz=freq,
            height_m=height,
            ground_opts=get_ground_opts(ground),
            excitation_pulse="10,1",
            pattern_opts={"theta": "45,0,1", "phi": "90,0,1"},
            option="far-field",
        )
        R, X = result['impedance']
        print(f"Feedpoint impedance at 10m ({ground} ground): R={R:.5f} Ω, X={X:.5f} Ω")
        if ground == "average":
            assert R == pytest.approx(expected[0], rel=0.01), f"R at 10m: got {R}, expected {expected[0]}"
            assert X == pytest.approx(expected[1], rel=0.01), f"X at 10m: got {X}, expected {expected[1]}" 