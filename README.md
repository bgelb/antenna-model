# dipole_pattern.py

This Python script generates and analyzes the far-field radiation pattern of a center-fed half-wave dipole antenna mounted at 30 ft elevation on 14.1 MHz.

## Requirements

- Python 3.7 or newer
- [pymininec](https://pypi.org/project/pymininec/) antenna modeling package (install with `pip install pymininec`)

## Usage

1. Clone or download this repository.
2. Install dependencies:
   ```bash
   pip install pymininec
   ```
3. Run the script:
   ```bash
   python3 dipole_pattern.py
   ```

By default, the script:

- Computes the dipole geometry (half-wave length, divided into 21 segments)
- Calls `pymininec` with `--option far-field-absolute` at a reference distance of 1000 m
- Extracts the E(θ) magnitude in the E-plane (φ=0°)
- Normalizes E(θ) to its maximum value
- Prints the relative gain in dB for elevation angles 10°–80° in 10° steps

## Examples

### Elevation cut (E-plane)
```text
Elevation (deg) | Relative Gain (dB)
-----------------------------------
    10.0 |    0.00
    20.0 |   -0.58
    30.0 |   -1.57
    ...
```

### Horizontal (azimuth) cut at a fixed elevation (e.g. 20°)
You can extract the azimuth pattern manually using:
```bash
pymininec -f 14.1 \
  -w 21,-5.315469,0,9.144,5.315469,0,9.144,0.001 \
  --excitation-pulse 10,1 \
  --option far-field \
  --theta 20,0,1 \
  --phi 0,10,36 \
| awk '/^ *20/ { printf "%3s°   %6.2f dBi\n", $2, $5 }'
```

## Customization
- Modify frequency, height, segmentation, or wire radius in the script variables.
- Change the `--theta`/`--phi` parameters for different cuts or resolution.
- Extend parsing logic for other polarization planes or to integrate plotting.

---

*Author: Your Name* 