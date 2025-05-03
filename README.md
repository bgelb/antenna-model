# antenna_model

**antenna_model.py** is a Python library for building wire-based antenna models and simulating their radiation patterns and feedpoint impedances via **pymininec**.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/bgelb/antenna-model.git
   cd antenna-model
   ```
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Library Usage

Import the core functions and classes from the library in your own scripts:

```python
from antenna_model import (
    build_dipole_model,
    AntennaSimulator,
    resonant_dipole_length,
    get_ground_opts,
    feet_to_meters,
    meters_to_feet,
)

# Example: center-fed dipole at 14.1 MHz
freq = 14.1  # MHz
length = resonant_dipole_length(freq)
model = build_dipole_model(total_length=length, segments=21, radius=0.001)
sim = AntennaSimulator()

# Simulate pattern and impedance
result = sim.simulate_pattern(
    model,
    freq_mhz=freq,
    height_m=10.0,
    ground="average",
    el_step=5.0,
    az_step=10.0,
)
impedance = result['impedance']  # (R, X)
pattern = result['pattern']      # list of {{'el', 'az', 'gain'}}
``` 

### Key API

- `build_dipole_model(total_length, segments, radius) -> AntennaModel`
- `AntennaSimulator().simulate_pattern(...) -> {{'impedance', 'pattern'}}`
- `AntennaSimulator().simulate_azimuth_pattern(...) -> list of cuts`
- Utility functions: `resonant_dipole_length()`, `feet_to_meters()`, `meters_to_feet()`, `get_ground_opts()`

## Example Script: dipole_pattern.py

The `dipole_pattern.py` script demonstrates how to use the library to:

1. Compute feedpoint impedance vs. height
2. Generate elevation and azimuth gain patterns at multiple heights
3. Plot combined polar diagrams and save them

Run the example:

```bash
python dipole_pattern.py [--show-gui]
```

- By default, plots are saved into the `output/` directory (e.g., `output/pattern_comparison_all_heights.png`).
- Use `--show-gui` to display interactive windows instead of saving files.

## Testing

This project uses pytest for automated tests. To run the test suite:

```bash
pytest -v
```

Tests include:
- Resonant dipole length calculation
- Model construction
- Basic simulation invocation
- Regression of gain patterns in free space
- Feedpoint impedance checks at various heights

---
*Author: Your Name* 