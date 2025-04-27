import pytest
from antenna_model import build_dipole_model, run_pymininec, resonant_dipole_length
import re

def test_resonant_dipole_length():
    l = resonant_dipole_length(14.1)
    c = 299792458.0
    wl = c / (14.1e6)
    assert l == pytest.approx(wl / 2.0)

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
    assert "MININEC" in out
    assert "FREQUENCY" in out
    assert "PATTERN DATA" in out

def test_dipole_pattern_regression():
    # Reference: half-wave dipole at 14.1 MHz, 30ft (9.144m) elevation
    freq = 14.1
    height = 9.144
    length = resonant_dipole_length(freq)
    model = build_dipole_model(total_length=length, segments=21, radius=0.001)
    # Check gain at theta=20, phi=90 and theta=45, phi=90
    for theta, ref_gain in [(20, 2.15), (45, 2.15)]:
        out = run_pymininec(
            model,
            freq_mhz=freq,
            height_m=height,
            excitation_pulse="10,1",
            pattern_opts={"theta": f"{theta},0,1", "phi": "90,0,1"},
            option="far-field"
        )
        # Parse gain from output (match TOTAL column)
        m = re.search(rf"^\s*{theta}\s+90\s+[-.\deE]+\s+([-.\deE]+)\s+([-.\deE]+)", out, re.MULTILINE)
        assert m, f"Pattern line for theta={theta}, phi=90 not found"
        gain = float(m.group(2))  # TOTAL column
        assert gain == pytest.approx(ref_gain, abs=0.1), f"Gain at theta={theta}, phi=90: got {gain}, expected {ref_gain}" 