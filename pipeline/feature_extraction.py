import numpy as np
from scipy.signal import savgol_filter, find_peaks, butter, filtfilt
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

def normalize_ecg_sample(sample):
    # Support both direct dict samples and 0-D object arrays loaded via np.load(..., allow_pickle=True)
    if isinstance(sample, np.ndarray) and sample.dtype == object and sample.shape == ():
        sample = sample.item()

    if isinstance(sample, dict):
        signal = np.asarray(sample['signal'])
        lead_names = list(sample.get('lead_names', []))
    else:
        signal = np.asarray(sample)
        lead_names = []

    if signal.ndim == 1:
        signal = np.expand_dims(signal, 0)

    if not lead_names:
        lead_names = [f'V{i+1}' for i in range(signal.shape[0])]

    return signal, lead_names

def apply_high_pass_filter(signal, sampling_rate=1000, cutoff_hz=0.5):
    """
    Remove baseline drift with high-pass filter.
    
    Parameters
    ----------
    signal : ndarray
        ECG waveform.
    sampling_rate : int
        Samples per second.
    cutoff_hz : float
        Cutoff frequency in Hz (default 0.5 Hz removes slow baseline drift).
    
    Returns
    -------
    filtered_signal : ndarray
        High-pass filtered signal.
    """
    nyquist = sampling_rate / 2
    normalized_cutoff = cutoff_hz / nyquist
    b, a = butter(2, normalized_cutoff, btype='high')
    filtered = filtfilt(b, a, signal)
    return filtered


def detect_s_nadirs(signal, sampling_rate=1000, distance=150, height=0.0005, min_interval_ms=500, window=50):
    """
    Locate S-wave nadirs by finding peaks in second derivative, then refining 
    with local minima in the original signal within a window around each peak.

    Parameters
    ----------
    signal : ndarray
        Single-lead ECG waveform.
    sampling_rate : int
        Samples per second.
    distance : int
        Minimum number of samples between detected nadirs.
    height : float
        Minimum prominence of peaks in second derivative.
    min_interval_ms : float
        Minimum time in milliseconds between successive nadirs.
    window : int
        Window size (samples) around each d2 peak to search for signal minimum.

    Returns
    -------
    s_nadirs : ndarray
        Indices where the S-wave nadirs were detected.
    """
    window_length = 31
    polyorder = 3
    d2 = savgol_filter(signal, window_length=window_length, polyorder=polyorder, deriv=2)

    # enforce minimum interval in samples
    if min_interval_ms is not None:
        min_samples = int(round((min_interval_ms / 1000.0) * sampling_rate))
        distance = max(distance, min_samples)

    # find coarse candidates from d2 peaks
    candidates, _ = find_peaks(d2, distance=distance, height=height)
    
    # refine each candidate by finding local minimum in signal within window
    s_nadirs = []
    for cand in candidates:
        start = max(0, cand - window)
        end = min(len(signal), cand + 3 * window + 1)
        signal_window = signal[start:end]
        
        if len(signal_window) > 0:
            local_min_idx = np.argmin(signal_window)
            refined = start + local_min_idx
            s_nadirs.append(refined)
    
    return np.array(s_nadirs, dtype=int)

def detect_j_points(signal, s_nadirs, sampling_rate=1000, search_window_ms=200, target_visual_angle_deg=45):
    """
    Detect J-points where visual angle on ECG grid drops to target threshold.
    
    Algorithm:
    1. From each S-nadir, find the maximum slope (steepest ascent)
    2. Convert target visual angle to slope threshold, accounting for ECG grid aspect ratio
    3. Find where slope drops below this threshold - that's the J-point ('elbow')
    
    Parameters
    ----------
    signal : ndarray
        Single-lead ECG waveform.
    s_nadirs : ndarray
        Indices of S-wave nadirs.
    sampling_rate : int
        Samples per second.
    search_window_ms : int
        Time window (ms) after S-nadir to search for J-point.
    target_visual_angle_deg : float
        Target visual angle in degrees on ECG grid (default 15°, representing near-horizontal).
    skip_samples : int
        Number of samples to skip from S-nadir before searching (to skip nadir trough).
    
    Returns
    -------
    j_points : ndarray
        Indices where J-points were detected.
    """
    if len(s_nadirs) == 0:
        return np.array([], dtype=int)
    
    # Convert visual angle to slope threshold
    # Visual angle accounts for ECG grid aspect ratio (0.04s / 0.1mV = 0.4)
    # visual_angle = arctan(slope_mV_per_s * 0.4), so slope_mV_per_s = tan(visual_angle) / 0.4
    import math
    angle_rad = math.radians(target_visual_angle_deg)
    slope_threshold_mv_per_s = math.tan(angle_rad) / 0.4
    slope_threshold = slope_threshold_mv_per_s / sampling_rate  # convert to mV/sample for comparison with d1
    
    window_length = 31
    polyorder = 3
    smoothed = savgol_filter(signal, window_length=window_length, polyorder=polyorder)
    d1 = savgol_filter(smoothed, window_length=window_length, polyorder=polyorder, deriv=1)
    search_samples = int(round((search_window_ms / 1000.0) * sampling_rate))
    
    j_points = []
    for s_nadir in s_nadirs:
        search_start = s_nadir
        search_end = min(s_nadir + search_samples, len(d1))
        
        if search_end <= search_start:
            continue
        
        region_d1 = d1[search_start:search_end]
        
        if len(region_d1) == 0:
            continue
        
        # Find the maximum slope (steepest part of ascent)
        max_slope = np.max(region_d1)
        # Convert to visual angle on ECG grid
        slope_mv_per_s = max_slope * 1000  # mV/sample → mV/s at 1000 Hz
        visual_slope = slope_mv_per_s / (0.1 / 0.04)  # ECG grid aspect ratio: 0.1 mV per 0.04 s
        visual_angle_deg = np.degrees(np.arctan(visual_slope))
        # print(f"max_slope (mV/sample): {max_slope:.6f}, max_slope (mV/s): {slope_mv_per_s:.2f}, visual angle: {visual_angle_deg:.1f}°, threshold: {slope_threshold:.6f}")
        
        # Find where slope peaks and then look for flattening after
        max_slope_idx = np.argmax(region_d1)
        post_steep_region = region_d1[max_slope_idx:]
        
        # Find where it drops below threshold AND stays below for persistence (min 10 samples)
        # This prevents brief noise spikes from being detected as J-points
        min_persistence_samples = 10
        below_threshold_indices = np.where(post_steep_region < slope_threshold)[0]
        
        if len(below_threshold_indices) > 0:
            # Check for persistence: find the first index where slope stays below threshold
            # for at least min_persistence_samples consecutive samples
            for i, idx in enumerate(below_threshold_indices):
                # Check if slope remains below threshold for the next min_persistence_samples
                end_check = min(idx + min_persistence_samples, len(post_steep_region))
                if end_check - idx >= min_persistence_samples:
                    # Verify all samples in this window are below threshold
                    if np.all(post_steep_region[idx:end_check] < slope_threshold):
                        j_point_local = max_slope_idx + idx
                        j_point_global = search_start + j_point_local
                        j_points.append(j_point_global)
                        break
    
    return np.array(j_points, dtype=int)


def get_st_measurements(signal, j_points, sampling_rate=1000):
    """
    Get ST segment measurements at +40ms and +80ms after each J-point.
    
    Parameters
    ----------
    signal : ndarray
        Single-lead ECG waveform.
    j_points : ndarray
        Indices of J-points.
    sampling_rate : int
        Samples per second.
    
    Returns
    -------
    dict with keys:
        'st_40_indices': indices at ST+40ms
        'st_80_indices': indices at ST+80ms
        'st_40_values': amplitudes at ST+40ms
        'st_80_values': amplitudes at ST+80ms
    """
    if len(j_points) == 0:
        return {
            'st_40_indices': np.array([], dtype=int),
            'st_80_indices': np.array([], dtype=int),
            'st_40_values': np.array([]),
            'st_80_values': np.array([])
        }
    
    offset_40_samples = int(round((40 / 1000.0) * sampling_rate))
    offset_80_samples = int(round((80 / 1000.0) * sampling_rate))
    
    st_40_indices = []
    st_80_indices = []
    st_40_values = []
    st_80_values = []
    
    for j_point in j_points:
        idx_40 = min(j_point + offset_40_samples, len(signal) - 1)
        st_40_indices.append(idx_40)
        st_40_values.append(signal[idx_40])
        
        idx_80 = min(j_point + offset_80_samples, len(signal) - 1)
        st_80_indices.append(idx_80)
        st_80_values.append(signal[idx_80])
    
    return {
        'st_40_indices': np.array(st_40_indices, dtype=int),
        'st_80_indices': np.array(st_80_indices, dtype=int),
        'st_40_values': np.array(st_40_values),
        'st_80_values': np.array(st_80_values)
    }


def refine_extremum_from_curvature_peak(signal, peak_idx, search_radius_ms=50, sampling_rate=1000, is_maximum=True):
    """
    Refine a curvature peak to the actual extremum in the original signal.
    
    Given an index from a peak in the second derivative, find the actual extremum
    (maximum or minimum) in the original signal within a window around the peak.
    
    Parameters
    ----------
    signal : ndarray
        The original ECG signal.
    peak_idx : int
        Index of the peak in the second derivative.
    search_radius_ms : float
        Search radius in milliseconds around the peak index.
    sampling_rate : int
        Samples per second.
    is_maximum : bool
        If True, search for local maximum. If False, search for local minimum.
    
    Returns
    -------
    int
        Index of the refined extremum in the original signal.
    """
    search_radius_samples = max(1, int(round((search_radius_ms / 1000.0) * sampling_rate)))
    
    left_idx = max(0, peak_idx - search_radius_samples)
    right_idx = min(len(signal) - 1, peak_idx + search_radius_samples)
    
    search_window = signal[left_idx:right_idx+1]
    
    if is_maximum:
        refined_local_idx = np.argmax(search_window)
    else:
        refined_local_idx = np.argmin(search_window)
    
    refined_global_idx = left_idx + refined_local_idx
    return refined_global_idx


def is_true_local_extremum(signal, idx, window_ms=10, sampling_rate=1000, is_maximum=True):
    """
    Check if a point is a true local extremum by verifying that both left and right
    neighbors within a window are less than (for maximum) or greater than (for minimum) the point.
    
    Parameters
    ----------
    signal : ndarray
        The signal to analyze.
    idx : int
        Index of the candidate extremum.
    window_ms : float
        Window size in milliseconds to check on both sides.
    sampling_rate : int
        Samples per second.
    is_maximum : bool
        If True, check for local maximum. If False, check for local minimum.
    
    Returns
    -------
    bool
        True if the point is a true local extremum.
    """
    window_samples = max(1, int(round((window_ms / 1000.0) * sampling_rate)))
    
    left_idx = max(0, idx - window_samples)
    right_idx = min(len(signal) - 1, idx + window_samples)
    
    center_val = signal[idx]
    
    if is_maximum:
        # For maximum: all left and right neighbors should be less than center
        left_check = np.all(signal[left_idx:idx] <= center_val)
        right_check = np.all(signal[idx+1:right_idx+1] <= center_val)
    else:
        # For minimum: all left and right neighbors should be greater than center
        left_check = np.all(signal[left_idx:idx] >= center_val)
        right_check = np.all(signal[idx+1:right_idx+1] >= center_val)
    
    return left_check and right_check


def detect_t_waves(signal, j_points, sampling_rate=1000, search_start_ms=100, search_end_ms=300):
    if len(j_points) == 0:
        return {
            'indices': np.array([], dtype=int),
            'values': np.array([]),
            'st_baselines': np.array([]),
            'polarities': np.array([], dtype=object)
        }
    
    window_length = 31
    polyorder = 3
    smoothed = savgol_filter(signal, window_length=window_length, polyorder=polyorder)
    d2 = savgol_filter(smoothed, window_length=window_length, polyorder=polyorder, deriv=2)
    
    offset_40 = int(round((40 / 1000.0) * sampling_rate))
    offset_80 = int(round((80 / 1000.0) * sampling_rate))
    search_start_samples = int(round((search_start_ms / 1000.0) * sampling_rate))
    search_end_samples = int(round((search_end_ms / 1000.0) * sampling_rate))
    
    t_indices = []
    t_values = []
    baselines = []
    polarities = []
    
    for j_point in j_points:
        st_40_idx = min(j_point + offset_40, len(signal) - 1)
        st_80_idx = min(j_point + offset_80, len(signal) - 1)
        st_baseline = np.mean(signal[st_40_idx:st_80_idx+1])
        
        search_start_idx = j_point + search_start_samples
        search_end_idx = min(j_point + search_end_samples, len(signal))
        
        if search_start_idx >= search_end_idx or search_start_idx >= len(signal):
            continue
        
        d2_window = d2[search_start_idx:search_end_idx]
        
        maxima, _ = find_peaks(d2_window, distance=10)
        minima, _ = find_peaks(-d2_window, distance=10)
        
        if len(maxima) == 0 and len(minima) == 0:
            continue
        
        best_idx = None
        best_polarity = None
        best_amplitude = 0
        
        # Filter maxima to ensure they are true local maxima in the original signal
        for max_idx in maxima:
            global_idx = search_start_idx + max_idx
            # Refine the d2 peak to the actual maximum in the signal
            refined_idx = refine_extremum_from_curvature_peak(signal, global_idx, search_radius_ms=50, sampling_rate=sampling_rate, is_maximum=True)
            # Verify it's a true local maximum
            if is_true_local_extremum(signal, refined_idx, window_ms=50, sampling_rate=sampling_rate, is_maximum=True):
                amp = signal[refined_idx]
                if abs(amp) > best_amplitude:
                    best_amplitude = abs(amp)
                    best_idx = refined_idx
        
        # Filter minima to ensure they are true local minima in the original signal
        for min_idx in minima:
            global_idx = search_start_idx + min_idx
            # Refine the d2 peak to the actual minimum in the signal
            refined_idx = refine_extremum_from_curvature_peak(signal, global_idx, search_radius_ms=50, sampling_rate=sampling_rate, is_maximum=False)
            # Verify it's a true local minimum
            if is_true_local_extremum(signal, refined_idx, window_ms=50, sampling_rate=sampling_rate, is_maximum=False):
                amp = signal[refined_idx]
                if abs(amp) > best_amplitude:
                    best_amplitude = abs(amp)
                    best_idx = refined_idx
        
        # Determine polarity based on sign and magnitude of amplitude
        if best_idx is not None:
            t_indices.append(best_idx)
            t_values.append(signal[best_idx])
            baselines.append(st_baseline)
            
            # Polarity: positive if >= 0.1mV, negative if <= -0.1mV, else neutral
            amp_value = signal[best_idx]
            if amp_value >= 0.1:
                best_polarity = 'positive'
            elif amp_value <= -0.1:
                best_polarity = 'negative'
            else:
                best_polarity = 'neutral'
            
            polarities.append(best_polarity)
    
    return {
        'indices': np.array(t_indices, dtype=int),
        'values': np.array(t_values),
        'st_baselines': np.array(baselines),
        'polarities': np.array(polarities, dtype=object)
    }

def narrate_ecg(signal, lead_names=None, sampling_rate=1000):
    signal, inferred_lead_names = normalize_ecg_sample(signal)
    if lead_names is None or len(lead_names) != signal.shape[0]:
        lead_names = inferred_lead_names
        
    narratives = []
    
    for lead_idx in range(signal.shape[0]):
        lead_signal = signal[lead_idx]
        lead_name = lead_names[lead_idx]
        
        lead_filtered = apply_high_pass_filter(lead_signal, sampling_rate=sampling_rate)
        from scipy.signal import savgol_filter
        lead_filtered = savgol_filter(lead_filtered, window_length=31, polyorder=3)
        
        s_nadirs = detect_s_nadirs(lead_filtered, sampling_rate=sampling_rate)
        j_points = detect_j_points(lead_filtered, s_nadirs, sampling_rate=sampling_rate)
        st_meas = get_st_measurements(lead_filtered, j_points, sampling_rate=sampling_rate)
        
        if len(j_points) == 0:
            # If we cannot detect J-points, provide a quick view of the early ECG segment.
            # Show the first 2 seconds at ~100Hz (one value per 10ms) so downstream review can inspect the trace.
            sample_step = max(1, int(round(sampling_rate / 100)))  # 100 Hz per datapoint
            num_points = int(round(2.0 * 100))  # 2 seconds at 100 Hz -> 200 points
            values = lead_filtered[: sample_step * num_points : sample_step]

            text = f"Lead {lead_name}: Unable to detect J-point in this lead.\n"
            text += "First 2 seconds (100 Hz sampling) of filtered signal (mm):\n"

            for i, v in enumerate(values):
                if i > 0 and i % 10 == 0:
                    text += "\n"
                text += f"{v * 10:6.2f} "

            text += "\n"
            narratives.append(text)
            continue
        
        j_idx = j_points[0]
        j_height = lead_filtered[j_idx]
        
        st_80 = st_meas['st_80_values'][0] if len(st_meas['st_80_values']) > 0 else 0
        st_ratio = j_height / st_80 if st_80 != 0 else 0 
        
        text = f"Lead {lead_name}:\n"
        
        j_height_mm = j_height * 10
        
        # Check if there's J-point elevation
        if j_height_mm >= 2.0 - 0.1:
            text += f"The J-point has significant elevation at {j_height_mm:.1f}mm.\n"
        elif j_height_mm >= 1.0 - 0.1:
            text += f"The J-point has elevation at {j_height_mm:.1f}mm.\n"
        else:
            elevation_or_depression = "elevation" if j_height_mm >= 0 else "depression"
            text += f"The J-point shows minimal {elevation_or_depression} at {j_height_mm:.1f}mm.\n"

        # Compute average slope from the S-nadir to the J-point (left arm)
        # and from the J-point to the same distance past it (right arm).
        # Slopes are reported in ECG paper units: mV per 0.04s (one small box).
        # That means 1 mV over 0.04s yields a value of 1.
        # if len(s_nadirs) > 0:
        # Compute average slope in ECG 'box' units (vertical boxes per horizontal box).
        #  - 1 vertical box = 0.1 mV
        #  - 1 horizontal box = 0.04 s
        # Scaling factor: (1 / 0.1) * (0.04 s * sampling_rate) = 400 at 1000 Hz.
        left_slope = 0.0
        right_slope = 0.0
        right_end = j_idx

        if j_height_mm > 2 - 0.1:
            text += f"The Corrado index is {st_ratio:.2f}.\n"
            prior_s = s_nadirs[s_nadirs < j_idx]
            if len(prior_s) > 0:
                s_idx = int(prior_s[-1])
            else:
                s_idx = int(s_nadirs[0])

            dist = abs(j_idx - s_idx) // 2
            right_end = min(len(lead_filtered) - 1, j_idx + dist)

            def mean_slope_boxes(y, start_idx, end_idx):
                if end_idx <= start_idx:
                    return 0.0
                dy = np.diff(y[start_idx : end_idx + 1])
                # dy is in mV per sample; multiply by 400 to report in boxes/box
                # note to self: change to median?
                return float(np.mean(dy) * 400)

            left_slope = mean_slope_boxes(lead_filtered, s_idx, j_idx)
            right_slope = mean_slope_boxes(lead_filtered, j_idx, right_end)

            if left_slope > 0 and right_slope < 0:
                base_triangle_length = (5 / abs(left_slope) + 5 / abs(right_slope))
                text += f"The triangle base length is {base_triangle_length:.2f} mm"
            else: 
                print('debug')
                
        # Display ST segment signal datapoints (50 samples = 0.5s at 1000 Hz)
        text += "\nFollowing the J-point is the ST segment and T wave, whose signal (mm) is displayed below (each point is 10 ms, totalling 0.5s):\n\n"
        
        samples_per_10ms = int(round((10 / 1000.0) * sampling_rate))  # 10 samples at 1000 Hz
        total_samples = 50
        
        for i in range(total_samples):
            sample_idx = min(j_idx + i * samples_per_10ms, len(lead_filtered) - 1)
            sample_value_mv = lead_filtered[sample_idx]
            sample_value_mm = sample_value_mv * 10
            time_ms = i * 10
            text += f"{sample_value_mm:6.2f} "

            if i % 10 == 9:
                text += "\n"
        
        narratives.append(text)
    
    full_text = "DETAILED ECG NARRATION\n" + "="*50 + "\n\n"
    for narr in narratives:
        full_text += narr + "\n\n"
    
    return full_text

LEAD_NAMES = [f'V{i}' for i in range(1, 7)]
def display_ecg(signal, title="ECG", sampling_rate=1000, limit=10000, dpi=150, save_path=None, landmarks=True):
    signal, lead_names = normalize_ecg_sample(signal)
    # n_leads = signal.shape[0]
    n_leads = 3
    fig, axes = plt.subplots(n_leads, 1, figsize=(16, 4 * n_leads), dpi=dpi)
    fig.suptitle(title, fontsize=14, fontweight='bold')
    fig.patch.set_facecolor('#F5E6D3')
    
    if n_leads == 1:
        axes = [axes]
    
    for index in range(n_leads):    
        name = lead_names[index]
        ax = axes[index]
        ax.set_facecolor('#F5E6D3')
        
        lead = signal[index]
        lead = apply_high_pass_filter(lead)
        lead = savgol_filter(lead, window_length=31, polyorder=4)
        
        # optionally compute landmark features (S-nadirs, J-points, ST measurements, T-waves)
        if landmarks:
            s_nadirs = detect_s_nadirs(lead)
            j_points = detect_j_points(lead, s_nadirs)
            st_measurements = get_st_measurements(lead, j_points)
            t_waves = detect_t_waves(lead, j_points)
        else:
            # empty placeholders so downstream plotting logic can remain unchanged
            s_nadirs = np.array([], dtype=int)
            j_points = np.array([], dtype=int)
            st_measurements = {
                'st_40_indices': np.array([], dtype=int),
                'st_80_indices': np.array([], dtype=int)
            }
            t_waves = {
                'indices': np.array([], dtype=int)
            }
        
        # plot lead
        x_ticks = np.arange(0, min(len(lead), limit)) / sampling_rate
        ax.plot(x_ticks, lead[:limit], linewidth=0.8, color='black')
        
        # transform image to look more like a clinical ECG
        # horizontally, a small box is 0.04s while a big box is 0.2s
        ax.xaxis.set_major_locator(MultipleLocator(0.2))
        ax.xaxis.set_minor_locator(MultipleLocator(0.04))
        ax.grid(which='major', axis='x', linewidth=0.4, color='#CC0000', alpha=0.8)
        ax.grid(which='minor', axis='x', linewidth=0.2, color='#FF6666', alpha=0.6)
        
        # vertically, a small box is 0.1mV while a big box is 0.5 mV 
        ax.grid(which='major', axis='y', linewidth=0.4, color='#CC0000', alpha=0.8)
        ax.grid(which='minor', axis='y', linewidth=0.2, color='#FF6666', alpha=0.6)
        ax.yaxis.set_major_locator(MultipleLocator(0.5))
        ax.yaxis.set_minor_locator(MultipleLocator(0.1))

        # plot features        
        if len(s_nadirs) > 0:
            ax.scatter(x_ticks[s_nadirs], lead[s_nadirs], c='green', s=80, zorder=5, alpha=0.5,
                      label=f'S-nadirs ({len(s_nadirs)})', marker='^', edgecolors='darkgreen', linewidths=0.5)
        
        if len(j_points) > 0:
            ax.scatter(x_ticks[j_points], lead[j_points], c='red', s=80, zorder=5, alpha=0.5,
                      label=f'J-points ({len(j_points)})', marker='o', edgecolors='darkred', linewidths=0.5)
        
        st_40_indices = st_measurements['st_40_indices']
        st_80_indices = st_measurements['st_80_indices']
        if len(st_40_indices) > 0:
            ax.scatter(x_ticks[st_40_indices], lead[st_40_indices], c='blue', s=60, zorder=5, alpha=0.7,
                      label=f'ST+40ms ({len(st_40_indices)})', marker='s', edgecolors='darkblue', linewidths=0.5)
            
        if len(st_80_indices) > 0:
            ax.scatter(x_ticks[st_80_indices], lead[st_80_indices], c='orange', s=60, zorder=5, alpha=0.7,
                      label=f'ST+80ms ({len(st_80_indices)})', marker='D', edgecolors='darkorange', linewidths=0.5)
        
        if len(t_waves['indices']) > 0:
            ax.scatter(x_ticks[t_waves['indices']], lead[t_waves['indices']], c='purple', s=90, zorder=5, alpha=0.7,
                      label=f"T-waves ({len(t_waves['indices'])})", marker='*', edgecolors='indigo', linewidths=0.5)
        
        # adjust aspect ratio to be square
        ax.set_ylabel(f'{name} (mV)', fontsize=10)
        ax.set_ylim(-2, 2)
        ax.set_xlim(0, min(len(lead), limit) / sampling_rate)
        ax.set_aspect(0.04 / 0.1, adjustable='box')
        
        if len(s_nadirs) > 0 or len(j_points) > 0 or len(t_waves['indices']) > 0:
            ax.legend(loc='upper right', fontsize=9)
            
    axes[-1].set_xlabel('Time (s)', fontsize=10)
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=dpi, bbox_inches='tight')
    else:
        plt.show()
    
    plt.close()