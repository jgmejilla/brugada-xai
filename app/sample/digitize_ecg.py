"""
digitize_ecg.py — Standalone ECG digitizer

Usage:
    python digitize_ecg.py              # uses ecg.png in the current directory
    python digitize_ecg.py myecg.png    # uses a custom image path

Outputs (written to sample_results/):
    <stem>.npy          — (3,) object array of (time_s, voltage_mV) tuples for V1/V2/V3
    <stem>_plot.png     — ECG-paper-styled plot of the three leads
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from PIL import Image, ImageDraw, ImageEnhance
from scipy import stats
from scipy.interpolate import interp1d


# ── Parameters ────────────────────────────────────────────────────────────────
# These mirror the values used in digitize_ecg.ipynb.
# Edit here if you need to re-calibrate for a different scan.

BASELINES = [50, 167, 288]          # [y_V1, y_V2, y_V3] in original image pixels

CROP_REGIONS = {
    'V1': {'x1': 409, 'y1': 35, 'x2': 601, 'y2': 122},
    'V2': {'x1': 441, 'y1': 140, 'x2': 573, 'y2': 233},
    'V3': {'x1': 440, 'y1': 247, 'x2': 573, 'y2': 323},
}

PIXELS_PER_SQUARE = 3.85            # pixels per small ECG square
CONTRAST          = 1.8             # contrast enhancement multiplier
THRESHOLD         = 50              # darkness cutoff for trace detection


# ── Resampling function ───────────────────────────────────────────────────────

def resample_to_1000hz(raw_lead, sample_rate=1000):
    """
    Resample a list of (time, voltage) pairs to uniform 1000 Hz sampling.
    
    Parameters
    ----------
    raw_lead : list of (time, voltage) tuples
        Raw digitized ECG datapoints
    sample_rate : int
        Target sampling rate in Hz (default 1000)
    
    Returns
    -------
    np.ndarray
        Uniformly sampled voltage values at `sample_rate` Hz
    """
    if len(raw_lead) == 0:
        return np.array([])
    
    # Unzip pairs into two arrays
    times, voltages = zip(*raw_lead)
    times = np.array(times)
    voltages = np.array(voltages)
    
    # Handle duplicate times by keeping unique values
    unique_times, indices = np.unique(times, return_index=True)
    unique_voltages = voltages[indices]
    
    # Add tiny offsets if times are still not strictly increasing
    if not np.all(np.diff(unique_times) > 0):
        unique_times = unique_times + np.arange(len(unique_times)) * 1e-9
    
    # Interpolate to create uniform sampling
    f = interp1d(unique_times, unique_voltages, kind='linear', fill_value='extrapolate')
    start_time = unique_times[0]
    end_time = unique_times[-1]
    
    uniform_times = np.arange(start_time, end_time, 1/sample_rate)
    uniform_voltages = f(uniform_times)
    
    return uniform_voltages


# ── Core digitization function ─────────────────────────────────────────────────

def digitize_ecg(image, crop_regions, baselines, pixels_per_square,
                 contrast=1.5, threshold=50):
    """
    Convert an ECG image to uniformly sampled 1000 Hz voltage arrays for V1, V2, V3.

    Returns
    -------
    numpy.ndarray of shape (3,), dtype=object
        Each element is a 1D array of voltage values sampled at 1000 Hz.
    """
    # Embed baselines as blue lines onto a copy of the raw image (pre-contrast).
    ecg_with_baselines = image.copy()
    draw = ImageDraw.Draw(ecg_with_baselines)
    for baseline_y in baselines:
        draw.line((0, baseline_y, image.width, baseline_y), fill='blue', width=1)

    # Apply contrast enhancement to the working image only.
    enhancer = ImageEnhance.Contrast(image)
    ecg = enhancer.enhance(contrast)

    lead_names    = ['V1', 'V2', 'V3']
    all_datapoints = []

    for lead_name in lead_names:
        region = crop_regions[lead_name]
        x1, y1, x2, y2 = region['x1'], region['y1'], region['x2'], region['y2']

        lead_crop            = ecg.crop((x1, y1, x2, y2))
        lead_baselines_crop  = ecg_with_baselines.crop((x1, y1, x2, y2))

        cv_image     = np.array(lead_crop.convert('RGB'))
        cv_baselines = np.array(lead_baselines_crop.convert('RGB'))
        height, width, _ = cv_image.shape

        # Detect baseline row from the blue-line copy.
        blues = []
        for col in range(width):
            for row in range(height):
                r, g, b = cv_baselines[row][col]
                if int(b) > 100 and int(r) < 100 and int(g) < 100:
                    blues.append(row)
                    break

        if len(blues) == 0:
            print(f"[WARNING] No baseline detected for {lead_name} — using image midpoint")
            baseline_row = height // 2
        else:
            baseline_row = int(stats.mode(blues).mode)

        # Detect ECG trace: first dark (non-blue) pixel per column.
        raw_points = []
        for col in range(width):
            for row in range(height):
                r, g, b = cv_image[row][col]
                if (int(r) + int(g) + int(b)) / 3 < threshold and b < 180:
                    raw_points.append((col, row))
                    break

        # Convert pixel coordinates → (time_s, voltage_mV).
        #   1 small square = 0.04 s  (horizontal)
        #   1 small square = 0.1 mV  (vertical)
        datapoints = []
        for col, row in raw_points:
            time    = col * (1 / pixels_per_square) * 0.04
            voltage = (baseline_row - row) * (1 / pixels_per_square) * 0.1
            datapoints.append((time, voltage))

        # Resample to uniform 1000 Hz
        resampled_voltages = resample_to_1000hz(datapoints, sample_rate=1000)

        print(f"  {lead_name}: {len(datapoints)} raw points → {len(resampled_voltages)} samples @ 1000 Hz")
        all_datapoints.append(resampled_voltages)

    return np.array(all_datapoints, dtype=object)


# ── Plot helper ────────────────────────────────────────────────────────────────

def plot_ecg(datapoints, title, save_path):
    """Render ECG-paper-styled plot and save to save_path."""
    lead_names = ['V1', 'V2', 'V3']
    num_leads  = len(lead_names)

    fig, axs = plt.subplots(num_leads, 1, figsize=(20, 5), dpi=300)
    fig.suptitle(title, fontsize=16)
    fig.patch.set_facecolor('#F5E6D3')

    if num_leads == 1:
        axs = [axs]

    for ax, lead_name, voltages in zip(axs, lead_names, datapoints):
        ax.set_facecolor('#F5E6D3')
        ax.text(0.02, 1.08, lead_name, transform=ax.transAxes,
                fontsize=14, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        if len(voltages) == 0:
            ax.text(0.5, 0.5, f'{lead_name}: no data',
                    ha='center', va='center', transform=ax.transAxes)
            continue

        # Generate time axis for 1000 Hz sampling
        times = np.arange(len(voltages)) / 1000.0

        ax.set_ylim(-1.5, 1.5)
        ax.set_xlim(0, max(times) if len(times) > 0 else 5)

        ax.xaxis.set_major_locator(MultipleLocator(0.2))
        ax.xaxis.set_minor_locator(MultipleLocator(0.04))
        ax.yaxis.set_major_locator(MultipleLocator(0.5))
        ax.yaxis.set_minor_locator(MultipleLocator(0.1))

        ax.grid(which='major', axis='x', linewidth=0.4, color='#CC0000', alpha=0.8)
        ax.grid(which='minor', axis='x', linewidth=0.2, color='#FF6666', alpha=0.6)
        ax.grid(which='major', axis='y', linewidth=0.4, color='#CC0000', alpha=0.8)
        ax.grid(which='minor', axis='y', linewidth=0.2, color='#FF6666', alpha=0.6)

        ax.set_xlabel('')
        ax.set_ylabel('')
        ax.set_xticklabels([])
        ax.set_yticklabels([])
        ax.tick_params(left=False, bottom=False)

        ax.set_aspect(0.04 / 0.1, adjustable='box')
        ax.plot(times, voltages, linewidth=0.4, color='black')

    plt.subplots_adjust(hspace=0.4, wspace=0.2)
    plt.savefig(save_path, bbox_inches='tight')
    plt.close(fig)
    print(f"  Plot saved  → {save_path}")


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Digitize an ECG image to .npy datapoints.')
    parser.add_argument('image', nargs='?', default='ecg.png',
                        help='Path to the input ECG image (default: ecg.png)')
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"[ERROR] Image not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    stem = image_path.stem

    # Create output directory next to this script.
    out_dir = Path(__file__).parent / 'sample_results'
    out_dir.mkdir(exist_ok=True)

    npy_path  = out_dir / f'{stem}.npy'
    plot_path = out_dir / f'{stem}_plot.png'

    print(f"Input  : {image_path}")
    print(f"Output : {out_dir}/")

    image = Image.open(image_path)

    print("Digitizing…")
    datapoints = digitize_ecg(
        image=image,
        crop_regions=CROP_REGIONS,
        baselines=BASELINES,
        pixels_per_square=PIXELS_PER_SQUARE,
        contrast=CONTRAST,
        threshold=THRESHOLD,
    )

    # Save .npy
    np.save(npy_path, datapoints)
    print(f"  Data saved  → {npy_path}  (shape: {datapoints.shape})")

    # Save plot
    plot_ecg(datapoints, title=f'Digitized ECG', save_path=plot_path)

    print("Done.")


if __name__ == '__main__':
    main()
