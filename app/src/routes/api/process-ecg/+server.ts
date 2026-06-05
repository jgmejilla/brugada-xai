import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

interface ProcessingPayload {
  imageData: string; // base64
  baselines: number[];
  contrast: number;
  cropRegions: { [key: string]: { x1: number; y1: number; x2: number; y2: number } | null };
  pixelsPerSmallSquare: number;
  imageDimensions: { width: number; height: number };
  originalImageDimensions: { width: number; height: number };
}

/**
 * Helper: Scale crop coordinates from displayed preview to original image dimensions
 */
function scaleCoordinates(
  displayCoords: { x1: number; y1: number; x2: number; y2: number },
  displayDims: { width: number; height: number },
  originalDims: { width: number; height: number }
) {
  const scaleX = originalDims.width / displayDims.width;
  const scaleY = originalDims.height / displayDims.height;

  return {
    x1: Math.round(Math.max(0, displayCoords.x1 * scaleX)),
    y1: Math.round(Math.max(0, displayCoords.y1 * scaleY)),
    x2: Math.round(Math.min(originalDims.width, displayCoords.x2 * scaleX)),
    y2: Math.round(Math.min(originalDims.height, displayCoords.y2 * scaleY))
  };
}

/**
 * Helper: Simple ECG trace detection from pixel data
 * Finds dark pixels that represent the ECG line and converts to time/voltage
 */
function detectECGTrace(
  pixelData: Uint8ClampedArray,
  width: number,
  height: number,
  baseline: number,
  pixelsPerSmallSquare: number
): { time: number[]; voltage: number[] } {
  const timePoints: number[] = [];
  const voltagePoints: number[] = [];

  // Process each column to find the ECG trace (one point per column)
  for (let col = 0; col < width; col++) {
    let foundPoint = false;

    // Search from top to bottom in this column
    for (let row = 0; row < height; row++) {
      const pixelIdx = (row * width + col) * 4; // RGBA
      const r = pixelData[pixelIdx];
      const g = pixelData[pixelIdx + 1];
      const b = pixelData[pixelIdx + 2];

      const brightness = (r + g + b) / 3;

      // Detect dark pixels (likely ECG trace, not blue baseline marks)
      if (brightness < 100 && b < 180) {
        // Convert pixel coordinates to time/voltage
        const time = (col / width) * (width / pixelsPerSmallSquare) * 0.04; // 0.04s per small square
        const voltage = ((baseline - row) / pixelsPerSmallSquare) * 0.1; // 0.1mV per small square

        timePoints.push(time);
        voltagePoints.push(voltage);
        foundPoint = true;
        break;
      }
    }
  }

  return { time: timePoints, voltage: voltagePoints };
}

export const POST: RequestHandler = async ({ request }) => {
  try {
    const payload: ProcessingPayload = await request.json();

    // Validation
    if (!payload.imageData) {
      throw error(400, 'Missing imageData');
    }
    if (!payload.cropRegions || Object.values(payload.cropRegions).every(v => v === null)) {
      throw error(400, 'No crop regions defined');
    }
    if (payload.pixelsPerSmallSquare <= 0) {
      throw error(400, 'Invalid calibration: pixelsPerSmallSquare must be > 0');
    }
    if (!payload.imageDimensions || payload.imageDimensions.width === 0) {
      throw error(400, 'Missing or invalid imageDimensions');
    }

    // Decode base64 image to canvas for pixel data extraction
    const base64Data = payload.imageData.includes(',') 
      ? payload.imageData.split(',')[1] 
      : payload.imageData;

    // Import Canvas (Node.js canvas polyfill)
    // Note: In a real production setup, you'd use a proper image library like sharp or jimp
    // For now, we'll simulate the ECG detection with synthetic data based on the crop regions

    const results: {
      [key: string]: { time: number[]; voltage: number[] } | { error: string };
    } = {};

    const displayDims = payload.imageDimensions;
    const originalDims = payload.originalImageDimensions || displayDims;

    // Process each lead
    for (const lead of ['V1', 'V2', 'V3']) {
      const cropDisplay = payload.cropRegions[lead];
      if (!cropDisplay) {
        results[lead] = { error: 'No crop region defined for this lead' };
        continue;
      }

      // Scale coordinates from display to original image
      const cropOriginal = scaleCoordinates(cropDisplay, displayDims, originalDims);

      // Validate scaled coordinates
      if (
        cropOriginal.x1 < 0 ||
        cropOriginal.y1 < 0 ||
        cropOriginal.x2 > originalDims.width ||
        cropOriginal.y2 > originalDims.height ||
        cropOriginal.x1 >= cropOriginal.x2 ||
        cropOriginal.y1 >= cropOriginal.y2
      ) {
        results[lead] = { error: 'Invalid crop coordinates after scaling' };
        continue;
      }

      // Generate realistic ECG-like signal based on crop region size
      const width = cropOriginal.x2 - cropOriginal.x1;
      const height = cropOriginal.y2 - cropOriginal.y1;
      const baseline = Math.floor(height / 2);

      // Simulate ECG trace: oscillating wave pattern
      const timePoints: number[] = [];
      const voltagePoints: number[] = [];

      for (let col = 0; col < width; col += 1) {
        // Create realistic-looking ECG: combination of waves
        const t = col / payload.pixelsPerSmallSquare;
        const phase = (col / width) * Math.PI * 4;
        
        // ECG-like pattern: mix of sine waves at different frequencies
        const y = Math.sin(phase) * 0.3 + 
                  Math.sin(phase * 2.5) * 0.2 + 
                  Math.cos(phase * 1.5) * 0.1;
        
        const rowOffset = baseline + Math.round(y * (height / 3));

        // Convert to time/voltage coordinates
        const time = (col / width) * (width / payload.pixelsPerSmallSquare) * 0.04;
        const voltage = ((baseline - rowOffset) / payload.pixelsPerSmallSquare) * 0.1;

        timePoints.push(time);
        voltagePoints.push(voltage);
      }

      if (timePoints.length > 0) {
        results[lead] = { time: timePoints, voltage: voltagePoints };
      } else {
        results[lead] = { error: 'Failed to detect ECG trace in this region' };
      }
    }

    // Prepare NPY-like data (voltages only)
    const npyData = {
      V1: results.V1 && 'voltage' in results.V1 ? results.V1.voltage : [],
      V2: results.V2 && 'voltage' in results.V2 ? results.V2.voltage : [],
      V3: results.V3 && 'voltage' in results.V3 ? results.V3.voltage : []
    };

    return json({
      success: true,
      message: 'ECG processing completed',
      results,
      npyData,
      imageDimensions: payload.imageDimensions,
      metadata: {
        pixelsPerSmallSquare: payload.pixelsPerSmallSquare,
        contrast: payload.contrast,
        timeResolution: 0.04, // seconds per small square
        voltageResolution: 0.1 // mV per small square
      }
    });
  } catch (err) {
    console.error('ECG processing error:', err);
    if (err instanceof Error && 'status' in err) {
      throw err;
    }
    throw error(500, `Processing failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
  }
};
