"""
ECG Processing Backend
Integrates with the Brugada Syndrome Classifier pipeline
"""
import os
import sys
import io
import base64
import json
import numpy as np

# Use non-interactive matplotlib backend for server environment
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from pathlib import Path
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from PIL import Image, ImageDraw, ImageEnhance
from scipy import stats
from scipy.interpolate import interp1d
from matplotlib.ticker import MultipleLocator

# LLM imports
try:
    from langchain_ollama import ChatOllama
    from langchain_core.messages import SystemMessage, HumanMessage
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("[WARNING] langchain_ollama not available - LLM features disabled")

# Add pipeline to path for imports
pipeline_path = Path(__file__).parent.parent / 'pipeline'
print(f"[DEBUG] Pipeline path: {pipeline_path}")
print(f"[DEBUG] Pipeline exists: {pipeline_path.exists()}")

if str(pipeline_path) not in sys.path:
    sys.path.insert(0, str(pipeline_path))

try:
    import extract_features as ef
    print(f"[INFO] Successfully imported extract_features")
except ImportError as e:
    print(f"[ERROR] Failed to import extract_features: {e}")
    import traceback
    traceback.print_exc()
    ef = None

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

# ── Debug flag ────────────────────────────────────────────────────────────────
# Set to True to ignore all frontend inputs and run digitize_ecg with the
# hardcoded values from digitize_ecg.py.  Useful for isolating whether the
# problem is in input-passing or in the function itself.
DEBUG_HARDCODE = False

_HARDCODE_IMAGE_PATH = Path(__file__).parent / 'sample' / 'ecg.png'
_HARDCODE_BASELINES  = [50, 169, 289]   # original-image pixels
_HARDCODE_CROPS = {
    'V1': {'x1': 445, 'y1':  29, 'x2': 574, 'y2': 128},
    'V2': {'x1': 445, 'y1': 137, 'x2': 578, 'y2': 224},
    'V3': {'x1': 441, 'y1': 241, 'x2': 568, 'y2': 328},
}
_HARDCODE_PPS       = 3.32   # pixels per small square
_HARDCODE_CONTRAST  = 1.5
_HARDCODE_THRESHOLD = 20
# ─────────────────────────────────────────────────────────────────────────────

def scale_coordinates(display_coords, display_dims, original_dims):
    """Scale crop coordinates from display to original image space"""
    scale_x = original_dims['width'] / display_dims['width']
    scale_y = original_dims['height'] / display_dims['height']
    
    return {
        'x1': max(0, int(display_coords['x1'] * scale_x)),
        'y1': max(0, int(display_coords['y1'] * scale_y)),
        'x2': min(original_dims['width'], int(display_coords['x2'] * scale_x)),
        'y2': min(original_dims['height'], int(display_coords['y2'] * scale_y))
    }

def resample_to_1000hz(raw_lead, sample_rate=1000):
    """
    Resample a list of (time, voltage) pairs to uniform 1000 Hz sampling.
    """
    if len(raw_lead) == 0:
        return np.array([])
    
    times, voltages = zip(*raw_lead)
    times = np.array(times)
    voltages = np.array(voltages)
    
    unique_times, indices = np.unique(times, return_index=True)
    unique_voltages = voltages[indices]
    
    if not np.all(np.diff(unique_times) > 0):
        unique_times = unique_times + np.arange(len(unique_times)) * 1e-9
    
    f = interp1d(unique_times, unique_voltages, kind='linear', fill_value='extrapolate')
    start_time = unique_times[0]
    end_time = unique_times[-1]
    
    uniform_times = np.arange(start_time, end_time, 1/sample_rate)
    uniform_voltages = f(uniform_times)
    
    return uniform_voltages

def digitize_ecg(image, crop_regions, baselines, pixels_per_square, contrast=1.5, threshold=50):
    """
    Convert an ECG image to uniformly sampled 1000 Hz voltage arrays for V1, V2, V3.

    Parameters
    ----------
    image : PIL.Image
        Raw ECG image (pre-contrast).
    crop_regions : dict
        {'V1': {'x1': int, 'y1': int, 'x2': int, 'y2': int}, 'V2': ..., 'V3': ...}
    baselines : list of int
        [y_v1, y_v2, y_v3] — y-coordinates of the isoelectric baseline in original image pixels.
    pixels_per_square : float
        Pixels per small ECG square (1 square = 0.04 s = 0.1 mV).
    contrast : float
        Contrast enhancement multiplier. Default 1.5.
    threshold : int
        Mean-RGB cutoff for trace detection. Default 50.

    Returns
    -------
    numpy.ndarray of shape (3,), dtype=object
        Each element is a 1D array of voltage values sampled at 1000 Hz for V1, V2, V3.
    """
    # Embed baselines as blue lines onto a copy of the raw image (pre-contrast).
    ecg_with_baselines = image.copy()
    draw = ImageDraw.Draw(ecg_with_baselines)
    for baseline_y in baselines:
        draw.line((0, baseline_y, image.width, baseline_y), fill='blue', width=1)

    # Apply contrast enhancement to the working image only.
    enhancer = ImageEnhance.Contrast(image)
    ecg = enhancer.enhance(contrast)

    lead_names     = ['V1', 'V2', 'V3']
    all_datapoints = []

    for lead_name in lead_names:
        region = crop_regions.get(lead_name)
        if region is None:
            print(f"[WARNING] No crop region for {lead_name}")
            all_datapoints.append([])
            continue

        x1, y1, x2, y2 = region['x1'], region['y1'], region['x2'], region['y2']

        lead_crop           = ecg.crop((x1, y1, x2, y2))
        lead_baselines_crop = ecg_with_baselines.crop((x1, y1, x2, y2))

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
        lead_datapoints = []
        for col, row in raw_points:
            time    = col * (1 / pixels_per_square) * 0.04
            voltage = (baseline_row - row) * (1 / pixels_per_square) * 0.1
            lead_datapoints.append((time, voltage))

        # Resample to uniform 1000 Hz
        resampled_voltages = resample_to_1000hz(lead_datapoints, sample_rate=1000)

        print(f"[INFO] {lead_name}: {len(lead_datapoints)} raw points → {len(resampled_voltages)} samples @ 1000 Hz")
        all_datapoints.append(resampled_voltages)

    return np.array(all_datapoints, dtype=object)

def create_visualization(datapoints):
    """
    Render an ECG-paper-styled plot from 1000 Hz voltage arrays.
    Returns PNG bytes.
    """
    lead_names = ['V1', 'V2', 'V3']
    num_leads  = len(lead_names)

    fig, axs = plt.subplots(num_leads, 1, figsize=(20, 5), dpi=150)
    fig.suptitle('Digitized ECG — V1, V2, V3 (1000 Hz)', fontsize=16)
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

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)

    return buf.getvalue()

@app.route('/api/process-ecg', methods=['POST'])
def process_ecg():
    """
    Main ECG processing endpoint
    
    Expected JSON payload:
    {
        "imageData": "base64_encoded_image",
        "cropRegions": {
            "V1": {"x1": int, "y1": int, "x2": int, "y2": int},
            "V2": {...},
            "V3": {...}
        },
        "pixelsPerSmallSquare": float,
        "imageDimensions": {"width": int, "height": int},
        "originalImageDimensions": {"width": int, "height": int},
        "baselines": [int, int, int],
        "contrast": float
    }
    """
    try:
        payload = request.json

        if DEBUG_HARDCODE:
            print('[DEBUG_HARDCODE] Using frontend image, hardcoded everything else')
            # Decode image from frontend
            image_data = payload.get('imageData', '')
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            image_bytes = base64.b64decode(image_data)
            image             = Image.open(io.BytesIO(image_bytes))
            crop_regions      = _HARDCODE_CROPS
            baselines         = _HARDCODE_BASELINES
            pixels_per_square = payload['pixelsPerSmallSquare']
            contrast          = payload.get('contrast', 1.5)
            threshold         = payload.get('threshold', 20)
            datapoints = digitize_ecg(
                image=image,
                crop_regions=crop_regions,
                baselines=baselines,
                pixels_per_square=pixels_per_square,
                contrast=contrast,
                threshold=threshold,
            )
            viz_bytes  = create_visualization(datapoints)
            viz_base64 = base64.b64encode(viz_bytes).decode('utf-8')
            npy_data   = [[list(pt) for pt in lead_pts] for lead_pts in datapoints]
            results    = {}
            for i, lead_name in enumerate(['V1', 'V2', 'V3']):
                pts = datapoints[i]
                results[lead_name] = {
                    'time':            [p[0] for p in pts],
                    'voltage':         [p[1] for p in pts],
                    'points_detected': len(pts),
                }
            return jsonify({
                'success': True,
                'debug_hardcode': True,
                'results': results,
                'npy_data': npy_data,
                'visualization': f'data:image/png;base64,{viz_base64}',
                'metadata': {'pixelsPerSmallSquare': pixels_per_square, 'timeResolution': 0.04, 'voltageResolution': 0.1}
            }), 200

        # Validate
        if not payload.get('imageData'):
            return jsonify({'error': 'Missing imageData'}), 400

        if not payload.get('cropRegions'):
            return jsonify({'error': 'Missing cropRegions'}), 400

        if payload.get('pixelsPerSmallSquare', 0) <= 0:
            return jsonify({'error': 'Invalid pixelsPerSmallSquare'}), 400

        # Decode image
        image_data = payload['imageData']
        if ',' in image_data:
            image_data = image_data.split(',')[1]

        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))

        original_dims = {'width': image.width, 'height': image.height}
        display_dims  = payload.get('imageDimensions', original_dims)

        # Crop regions and baselines already arrive in original-image space
        # (converted by the frontend at interaction time while dimensions were accurate).
        crop_regions = {}
        for lead_name in ['V1', 'V2', 'V3']:
            original_crop = payload['cropRegions'].get(lead_name)
            if original_crop:
                crop_regions[lead_name] = original_crop
                print(f"[DEBUG] {lead_name} crop (original, from frontend): {original_crop}")

        baselines = payload.get('baselines', [image.height // 2] * 3)
        print(f"[DEBUG] baselines (original, from frontend): {baselines}")
        print(f"[DEBUG] HARDCODED  baselines={_HARDCODE_BASELINES}  crops={_HARDCODE_CROPS}\n")

        pixels_per_square = payload['pixelsPerSmallSquare']
        contrast          = payload.get('contrast', 1.5)
        threshold         = payload.get('threshold', 20)

        # Run digitization (notebook approach)
        datapoints = digitize_ecg(
            image=image,
            crop_regions=crop_regions,
            baselines=baselines,
            pixels_per_square=pixels_per_square,
            contrast=contrast,
            threshold=threshold,
        )

        # Build per-lead results dict (voltage arrays already at 1000 Hz)
        results = {}
        for i, lead_name in enumerate(['V1', 'V2', 'V3']):
            voltages = datapoints[i]
            if len(voltages) > 0:
                # Generate time array for display (sample index / 1000 Hz)
                times = (np.arange(len(voltages)) / 1000.0).tolist()
                results[lead_name] = {
                    'time':            times,
                    'voltage':         voltages.tolist(),
                    'region':          crop_regions.get(lead_name, {}),
                    'points_detected': len(voltages),
                }
            else:
                results[lead_name] = {'error': 'No points detected'}

        # Generate ECG-paper visualization
        viz_bytes  = create_visualization(datapoints)
        viz_base64 = base64.b64encode(viz_bytes).decode('utf-8')

        # npy_data: voltage arrays as lists (pipeline .npy format)
        npy_data = [voltages.tolist() for voltages in datapoints]

        return jsonify({
            'success': True,
            'results': results,
            'npy_data': npy_data,
            'visualization': f'data:image/png;base64,{viz_base64}',
            'metadata': {
                'pixelsPerSmallSquare': pixels_per_square,
                'originalDimensions':  original_dims,
                'timeResolution':      0.04,
                'voltageResolution':   0.1,
            }
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e), 'type': type(e).__name__}), 500

@app.route('/api/export-npy', methods=['POST'])
def export_npy():
    """
    Export processed data as proper .npy file (voltage arrays at 1000 Hz)
    Format: np.array([v1_array, v2_array, v3_array], dtype=object)
    where each v*_array is a 1D numpy array of voltage values
    """
    try:
        payload  = request.json
        npy_data = payload.get('npy_data', [[], [], []])

        # npy_data is a list of 3 voltage arrays [V1, V2, V3] at 1000 Hz
        # Convert each to a proper numpy array, ensuring they're 1D
        all_leads = []
        for i, lead_voltages in enumerate(npy_data):
            voltage_array = np.array(lead_voltages, dtype=np.float64).flatten()
            all_leads.append(voltage_array)
            print(f"[NPY Export] V{i+1}: {len(voltage_array)} samples, dtype={voltage_array.dtype}, shape={voltage_array.shape}")

        # Save as object array (allows different lengths if needed)
        output = io.BytesIO()
        np.save(output, np.array(all_leads, dtype=object), allow_pickle=True)
        output.seek(0)

        return send_file(
            output,
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name=f'ecg_{int(os.times().elapsed)}.npy'
        )
    except Exception as e:
        print(f"[NPY Export Error] {type(e).__name__}: {e}")
        return jsonify({'error': str(e), 'type': type(e).__name__}), 500

@app.route('/api/analyze-ecg', methods=['POST'])
def analyze_ecg():
    """
    Upload NPY file and get landmark visualization
    Matches evaluation_2.ipynb workflow
    """
    try:
        if ef is None:
            return jsonify({'error': 'extract_features module not available'}), 500
        
        payload = request.json
        npy_data_b64 = payload.get('npyData')
        
        if not npy_data_b64:
            return jsonify({'error': 'No NPY data provided'}), 400
        
        # Decode base64 NPY
        npy_bytes = base64.b64decode(npy_data_b64)
        sample = np.load(io.BytesIO(npy_bytes), allow_pickle=True)
        
        print(f"[Analyze] Loaded NPY: type={type(sample)}, shape={sample.shape}, dtype={sample.dtype}")
        for i in range(min(3, len(sample))):
            lead = sample[i]
            print(f"[Analyze] V{i+1}: type={type(lead)}, shape={getattr(lead, 'shape', 'N/A')}, dtype={getattr(lead, 'dtype', 'N/A')}, len={len(lead) if hasattr(lead, '__len__') else 'N/A'}")
        
        # Analyze all three leads (V1, V2, V3)
        visualizations = []
        features_text = None
        
        for lead_idx in range(min(3, len(sample))):
            # Ensure lead is a clean 1D numpy array
            lead_signal = np.array(sample[lead_idx], dtype=np.float64).flatten()
            print(f"[Analyze] Processing V{lead_idx+1}: {len(lead_signal)} samples")
            
            # Detect landmarks
            landmarks = ef.detect_ecg_landmarks(lead_signal)
            
            # Create visualization using exact notebook approach
            ef.visualize_ecg_landmarks(
                landmarks['lead_signal'], 
                landmarks['r_peaks'], 
                landmarks['s_nadirs'],
                landmarks['j_points'], 
                landmarks['r_prime_peaks'], 
                landmarks['t_waves'],
                landmarks['smoothed'], 
                landmarks['d2'], 
                title=f'Lead V{lead_idx+1}',
                show_d2=False
            )
            
            # Convert current figure to base64
            img_bytes = io.BytesIO()
            plt.savefig(img_bytes, format='png', dpi=100, bbox_inches='tight')
            plt.close()
            img_bytes.seek(0)
            img_b64 = base64.b64encode(img_bytes.read()).decode('utf-8')
            visualizations.append({
                'lead': f'V{lead_idx+1}',
                'image': f'data:image/png;base64,{img_b64}'
            })
        
        # Extract features - convert object array to 2D array for the function
        # Stack all leads into a 2D array: shape (3, n_samples)
        # Find minimum length to ensure all leads have same length
        min_length = min(len(sample[i]) for i in range(len(sample)))
        stacked_signal = np.vstack([
            np.array(sample[i][:min_length], dtype=np.float64) 
            for i in range(min(3, len(sample)))
        ])
        print(f"[Analyze] Stacked signal for features: shape={stacked_signal.shape}, dtype={stacked_signal.dtype}")
        
        features_text = ef.extract_brugada_features(stacked_signal)
        
        return jsonify({
            'success': True,
            'visualizations': visualizations,
            'features': features_text
        }), 200
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'type': type(e).__name__}), 500


@app.route('/api/analyze-features', methods=['POST'])
def analyze_features():
    """
    Send extracted features to LLM for analysis
    """
    if not OLLAMA_AVAILABLE:
        return jsonify({'error': 'LLM not available'}), 500
    
    try:
        payload = request.json
        features_text = payload.get('features')
        age = payload.get('age')
        medical_history = payload.get('medicalHistory')
        
        if not features_text:
            return jsonify({'error': 'No features provided'}), 400
        
        # Initialize LLM
        llm = ChatOllama(
            model="llama3.2",
            base_url="http://localhost:11434",
            temperature=0.0
        )
        
        # Build context about patient if provided
        patient_context = ""
        if age:
            patient_context += f"Patient age: {age}\n"
        if medical_history:
            patient_context += f"Medical history: {medical_history}\n"
        
        # Create prompt
        system_prompt = """You are an expert cardiologist specializing in Brugada syndrome ECG analysis.

PATIENT CONTEXT:
Consider the patient's age and medical history when making your assessment, as these factors can influence risk stratification and clinical significance of ECG findings.

Brugada Syndrome Characteristics:
- J-point elevation and ST-segment elevation is present
- Inverted T waves is present
- high takeoff pattern is present

Normal ECG Characteristics:
- No ST-segment elevation
- No inverted T-waves
- No high takeoff pattern

ANALYSIS INSTRUCTIONS:
Please analyze the provided ECG features using a step-by-step chain of thought approach, incorporating patient age and medical history where relevant:

1. FEATURE INVENTORY: List each detected feature and its properties
2. BRUGADA INDICATORS: Identify which features match Brugada syndrome characteristics
3. NORMAL INDICATORS: Identify which features match normal ECG characteristics
4. WEIGHTING: Evaluate the significance and reliability of each indicator
5. DIFFERENTIAL DIAGNOSIS: Consider other potential diagnoses
6. CONCLUSION: Synthesize your analysis into a final risk assessment

Your final response MUST be valid JSON with this exact structure, nothing more or less:
{
    "risk_category": "positive" | "negative" | "uncertain",
    "confidence": 0.0-1.0, where values closer to 0.0 are more likely to be negative, and values closer to 1.0 are more likely to be positive
    "findings": "Summary of key findings and their clinical significance, and final conclusion",
    "reasoning": "Step-by-step analysis showing how you reached your conclusion",
    "recommendation": "Clinical next steps or recommendations"
}

Make sure to close your JSON response with a closing curly bracket (}).
"""
        
        user_message = f"{patient_context}Please analyze these ECG features using the chain of thought approach:\n\n{features_text}"
        
        # Call LLM
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ])
        
        response_text = response.content
        print(f"[DEBUG] LLM raw response:\n{response_text[:500]}")  # Debug log first 500 chars
        
        # Try to parse as JSON
        analysis = None
        import json as json_lib
        
        # Attempt 1: Direct JSON parse
        try:
            analysis = json_lib.loads(response_text)
            print("[DEBUG] Successfully parsed JSON directly")
        except json_lib.JSONDecodeError as e:
            print(f"[DEBUG] Direct JSON parse failed: {e}")
            
            # Attempt 2: Extract JSON block and use json.loads with special handling
            start_idx = response_text.find('{')
            if start_idx != -1:
                end_idx = response_text.rfind('}')
                if end_idx != -1 and end_idx > start_idx:
                    json_str = response_text[start_idx:end_idx+1]
                    
                    try:
                        # Try to decode with Python's json module which is more forgiving
                        # Use a custom decoder that handles control characters
                        analysis = json_lib.loads(
                            json_str,
                            strict=False
                        )
                        print("[DEBUG] Successfully extracted JSON with strict=False")
                    except:
                        # Last resort: manually fix common JSON issues
                        try:
                            # Replace actual newlines with spaces in the JSON
                            json_cleaned = ""
                            in_string = False
                            escape_next = False
                            
                            for char in json_str:
                                if escape_next:
                                    json_cleaned += char
                                    escape_next = False
                                elif char == '\\':
                                    json_cleaned += char
                                    escape_next = True
                                elif char == '"':
                                    json_cleaned += char
                                    in_string = not in_string
                                elif char in '\n\r\t' and in_string:
                                    # Replace control chars inside strings with space
                                    json_cleaned += ' '
                                else:
                                    json_cleaned += char
                            
                            analysis = json_lib.loads(json_cleaned)
                            print("[DEBUG] Successfully parsed after manual cleanup")
                        except Exception as e3:
                            print(f"[DEBUG] Manual cleanup failed: {e3}")
        
        # If still no analysis, create a fallback
        if analysis is None:
            print("[DEBUG] Using fallback JSON structure")
            analysis = {
                "risk_category": "uncertain",
                "confidence": 0.5,
                "findings": "Unable to parse LLM response properly.",
                "reasoning": "The LLM response format was invalid and could not be recovered.",
                "recommendation": "Please review with a cardiologist"
            }
        
        # Debug: Log the parsed confidence value
        if analysis and 'confidence' in analysis:
            print(f"[DEBUG] Parsed confidence value: {analysis['confidence']} (type: {type(analysis['confidence']).__name__})")
        
        return jsonify({
            'success': True,
            'analysis': analysis,
            'raw_response': response_text
        }), 200
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'type': type(e).__name__}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
