import pytest
from antenna_model import build_dipole_model, run_pymininec, resonant_dipole_length
import re

def test_resonant_dipole_length():
    f = 14.1
    l = resonant_dipole_length(f)
    # ARRL formula: 468 / f (MHz) in feet, then meters
    arrl_length_ft = 468 / f
    arrl_length_m = arrl_length_ft * 0.3048
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
    out = run_pymininec(model, freq_mhz=14.1, height_m=9.144, excitation_pulse="5,1", pattern_opts={"theta": "10,10,2", "phi": "0,10,2"})
    assert "MININEC" in out['raw_output']
    assert "FREQUENCY" in out['raw_output']
    assert "PATTERN DATA" in out['raw_output']

def test_dipole_pattern_regression():
    # Reference: half-wave dipole at 14.1 MHz, 30ft (9.144m) elevation
    freq = 14.1
    height = 9.144
    length = resonant_dipole_length(freq)
    model = build_dipole_model(total_length=length, segments=21, radius=0.001)
    # Check gain at el=20, az=90 and el=45, az=90
    for el, ref_gain in [(20, 2.15), (45, 2.15)]:
        result = run_pymininec(
            model,
            freq_mhz=freq,
            height_m=height,
            excitation_pulse="10,1",
            pattern_opts={"theta": f"{el},0,1", "phi": "90,0,1"},
            option="far-field"
        )
        pattern = result['pattern']
        # Find the pattern point with el and az
        match = next((p for p in pattern if abs(p['el']-el)<1e-3 and abs(p['az']-90)<1e-3), None)
        assert match, f"Pattern point for el={el}, az=90 not found"
        gain = match['gain']
        assert gain == pytest.approx(ref_gain, abs=0.1), f"Gain at el={el}, az=90: got {gain}, expected {ref_gain}" 