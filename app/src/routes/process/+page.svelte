<script lang="ts">
  import { onMount } from 'svelte';
  import AudioWaveformIcon from "@lucide/svelte/icons/audio-waveform";
  import Upload from "@lucide/svelte/icons/upload";
  import AlertCircle from "@lucide/svelte/icons/alert-circle";
  import ChevronRight from "@lucide/svelte/icons/chevron-right";
  import Check from "@lucide/svelte/icons/check";
  import { Button } from "$lib/components/ui/button/index.js";
  import { Input } from "$lib/components/ui/input/index.js";
  import { Root as Label } from "$lib/components/ui/label/index.js";
  import * as Card from "$lib/components/ui/card/index.js";

  // State management
  let currentStep = 1;
  let file: File | null = null;
  let previewUrl: string | null = null;
  let originalImageDimensions: { width: number; height: number } | null = null;
  let displayImageDimensions: { width: number; height: number } = { width: 0, height: 0 };

  // Step 2: Baseline
  let baselineMode: "auto" | "manual" = "manual";
  let baselines: number[] = [];

  // Step 3: Contrast
  let contrastValue = 1.5;

  // Step 4: Cropping
  let cropAuto = false;
  let leads = ["V1", "V2", "V3"];
  let cropRegions: { [key: string]: { x1: number; y1: number; x2: number; y2: number } | null } = {
    V1: null,
    V2: null,
    V3: null
  };
  let currentCropLead: string | null = null;
  let isDrawing = false;
  let startX = 0;
  let startY = 0;
  let imageElement: HTMLImageElement | null = null;
  let previewContainerElement: HTMLDivElement | null = null;

  // Step 5: Calibration
  let pixelsPerSmallSquare = 0;
  let calibrationPoints: { x: number; y: number }[] = [];
  let calibrationMode = false;
  let measuredPixels = 0;

  // Step 6: Detection & Processing
  let detectionProgress = 0;
  let detectionComplete = false;
  let processingError: string | null = null;
  let processedData: any = null;

  // Step 7: Export
  let exportFormat: 'npy' | 'csv' = 'npy';
  let exportProgress = 0;
  let exportComplete = false;

  // ── Session persistence ──────────────────────────────────────────────────────
  // Keeps all state alive across SvelteKit navigations and Vite HMR reloads.
  // Uses sessionStorage so it clears when the browser tab is closed.
  let imageDataUrl: string | null = null;  // base64 data URL (blob URLs die on reload)
  const SESSION_KEY = 'ecg_process_state';

  function saveState() {
    try {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify({
        currentStep,
        imageDataUrl,
        originalImageDimensions,
        baselines,
        contrastValue,
        cropRegions,
        pixelsPerSmallSquare,
        processedData,
        detectionComplete,
        detectionProgress,
        exportFormat,
      }));
    } catch (e) {
      console.warn('[ECG] Failed to save state:', e);
    }
  }

  function loadState() {
    try {
      const saved = sessionStorage.getItem(SESSION_KEY);
      if (!saved) return;
      const s = JSON.parse(saved);
      currentStep             = s.currentStep             ?? 1;
      originalImageDimensions = s.originalImageDimensions ?? null;
      baselines               = s.baselines               ?? [];
      contrastValue           = s.contrastValue           ?? 1.5;
      cropRegions             = s.cropRegions             ?? { V1: null, V2: null, V3: null };
      pixelsPerSmallSquare    = s.pixelsPerSmallSquare    ?? 0;
      processedData           = s.processedData           ?? null;
      detectionComplete       = s.detectionComplete       ?? false;
      detectionProgress       = s.detectionProgress       ?? 0;
      exportFormat            = s.exportFormat            ?? 'npy';
      if (s.imageDataUrl) {
        imageDataUrl = s.imageDataUrl;
        previewUrl   = s.imageDataUrl;  // data URLs are self-contained, no blob needed
      }
    } catch (e) {
      console.warn('[ECG] Failed to load state:', e);
    }
  }

  onMount(() => loadState());
  // ────────────────────────────────────────────────────────────────────────────

  function handleFile(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files?.[0]) {
      const selectedFile = input.files[0];
      if (!selectedFile.type.startsWith("image/")) {
        alert("Please select a valid image file");
        return;
      }
      file = selectedFile;

      // Reset all downstream state so stale data from the previous image is cleared
      imageDataUrl            = null;
      previewUrl              = null;
      originalImageDimensions = null;
      baselines               = [];
      contrastValue           = 1.5;
      cropRegions             = { V1: null, V2: null, V3: null };
      pixelsPerSmallSquare    = 0;
      calibrationPoints       = [];
      measuredPixels          = 0;
      calibrationMode         = false;
      detectionProgress       = 0;
      detectionComplete       = false;
      processingError         = null;
      processedData           = null;
      exportProgress          = 0;
      exportComplete          = false;
      currentStep             = 1;

      // Read as base64 data URL so it survives page reloads / navigation
      const reader = new FileReader();
      reader.onload = (e) => {
        imageDataUrl = e.target?.result as string;
        previewUrl   = imageDataUrl;

        const img = new Image();
        img.onload = () => {
          originalImageDimensions = { width: img.width, height: img.height };
          saveState();
        };
        img.src = previewUrl;
      };
      reader.readAsDataURL(selectedFile);
    }
  }

  function onImageLoad() {
    if (imageElement) {
      displayImageDimensions = {
        width: imageElement.offsetWidth,
        height: imageElement.offsetHeight
      };
    }
  }

  // Scale coordinate from display space to original image space
  function scaleCoordinate(displayCoord: number, dimension: 'x' | 'y'): number {
    if (!originalImageDimensions) return displayCoord;

    const displaySize = dimension === 'x' ? displayImageDimensions.width : displayImageDimensions.height;
    const originalSize = dimension === 'x' ? originalImageDimensions.width : originalImageDimensions.height;

    if (displaySize === 0) return displayCoord;
    return Math.round((displayCoord / displaySize) * originalSize);
  }

  function nextStep() {
    if (currentStep < 7) {
      currentStep++;
      saveState();
    }
  }

  function prevStep() {
    if (currentStep > 1) {
      currentStep--;
      saveState();
    }
  }

  function handleClear() {
    file = null;
    previewUrl = null;
    imageDataUrl = null;
    currentStep = 1;
    sessionStorage.removeItem(SESSION_KEY);
  }

  function handleDownload() {
    // TODO: Download the processed data
    console.log("Downloading processed ECG data...");
  }

  // Cropping functions with proper coordinate scaling
  function startCrop(lead: string, event: MouseEvent) {
    if (cropAuto || !imageElement || !previewContainerElement) return;
    currentCropLead = lead;
    isDrawing = true;

    const rect = previewContainerElement.getBoundingClientRect();
    startX = event.clientX - rect.left;
    startY = event.clientY - rect.top;
  }

  function updateCrop(event: MouseEvent) {
    if (!isDrawing || !imageElement || !currentCropLead) return;
  }

  function endCrop(event: MouseEvent) {
    if (!isDrawing || !imageElement || !currentCropLead || !previewContainerElement) return;

    const rect = previewContainerElement.getBoundingClientRect();
    const endX = event.clientX - rect.left;
    const endY = event.clientY - rect.top;

    // Coordinates are already relative to display image (within container)
    const x1 = Math.min(startX, endX);
    const x2 = Math.max(startX, endX);
    const y1 = Math.min(startY, endY);
    const y2 = Math.max(startY, endY);

    // Convert to original-image space NOW while displayImageDimensions is accurate.
    cropRegions[currentCropLead] = {
      x1: Math.round(scaleCoordinate(x1, 'x')),
      y1: Math.round(scaleCoordinate(y1, 'y')),
      x2: Math.round(scaleCoordinate(x2, 'x')),
      y2: Math.round(scaleCoordinate(y2, 'y')),
    };

    isDrawing = false;
    currentCropLead = null;
    saveState();
  }

  function clearCropRegion(lead: string) {
    cropRegions[lead] = null;
    saveState();
  }

  // Calibration functions
  function startCalibration() {
    calibrationMode = true;
    calibrationPoints = [];
    measuredPixels = 0;
  }

  function handleCalibrationClick(event: MouseEvent) {
    if (!calibrationMode || !previewContainerElement) return;

    const rect = previewContainerElement.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    calibrationPoints = [...calibrationPoints, { x, y }];

    if (calibrationPoints.length === 2) {
      const dx = calibrationPoints[1].x - calibrationPoints[0].x;
      const dy = calibrationPoints[1].y - calibrationPoints[0].y;

      // Scale from display space to original image space before measuring
      const scaleX = originalImageDimensions ? originalImageDimensions.width / displayImageDimensions.width : 1;
      const scaleY = originalImageDimensions ? originalImageDimensions.height / displayImageDimensions.height : 1;
      const dxOriginal = dx * scaleX;
      const dyOriginal = dy * scaleY;

      measuredPixels = Math.round(Math.sqrt(dxOriginal * dxOriginal + dyOriginal * dyOriginal));
      calibrationMode = false;
      saveState();
    }
  }

  function resetCalibration() {
    calibrationPoints = [];
    measuredPixels = 0;
    calibrationMode = false;
    pixelsPerSmallSquare = 0;
    saveState();
  }

  // Detection & Processing
  async function startDetection() {
    if (detectionProgress > 0 || !previewUrl) return;

    detectionProgress = 0;
    detectionComplete = false;
    processingError = null;
    processedData = null;

    try {
      detectionProgress = 10;

      // Use stored base64 data URL if the File object is gone (e.g. after navigation)
      const imageData: string = file
        ? await new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target?.result as string);
            reader.onerror = () => reject(new Error('Failed to read image file'));
            reader.readAsDataURL(file!);
          })
        : imageDataUrl!;

      if (!imageData) throw new Error('No image data available');

      detectionProgress = 30;

      // Prepare payload - send to Python backend
      const payload = {
        imageData,
        baselines,
        contrast: contrastValue,
        cropRegions,
        pixelsPerSmallSquare,
        imageDimensions: displayImageDimensions,
        originalImageDimensions
      };

      detectionProgress = 50;

      // Send to Python Flask backend
      const response = await fetch('http://localhost:5000/api/process-ecg', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      detectionProgress = 75;

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Processing failed');
      }

      const result = await response.json();
      processedData = result;
      detectionProgress = 100;
      detectionComplete = true;
      saveState();

      // Auto-export after detection completes
      await new Promise(resolve => setTimeout(resolve, 500));
      await exportData();
    } catch (err) {
      processingError = err instanceof Error ? err.message : 'Unknown error occurred';
      detectionProgress = 0;
    }
  }

  async function exportData() {
    if (!processedData) return;

    exportProgress = 0;
    exportComplete = false;

    try {
      exportProgress = 25;

      if (exportFormat === 'npy') {
        // Send to backend to create proper NPY file
        const response = await fetch('http://localhost:5000/api/export-npy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ npy_data: processedData.npy_data })
        });

        exportProgress = 75;

        if (!response.ok) {
          throw new Error('NPY export failed');
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `ecg_${Date.now()}.npy`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } else {
        // CSV format
        const rows: string[] = ['Time,V1,V2,V3'];
        const maxLength = Math.max(
          processedData.results.V1?.time?.length || 0,
          processedData.results.V2?.time?.length || 0,
          processedData.results.V3?.time?.length || 0
        );

        for (let i = 0; i < maxLength; i++) {
          const time = processedData.results.V1?.time?.[i] || '';
          const v1 = processedData.results.V1?.voltage?.[i] || '';
          const v2 = processedData.results.V2?.voltage?.[i] || '';
          const v3 = processedData.results.V3?.voltage?.[i] || '';
          rows.push(`${time},${v1},${v2},${v3}`);
        }

        const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
        exportProgress = 75;

        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `ecg_${Date.now()}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }

      exportProgress = 100;
      exportComplete = true;
    } catch (err) {
      processingError = err instanceof Error ? err.message : 'Export failed';
      exportProgress = 0;
    }
  }

  const steps = [
    { number: 1, title: "Upload", description: "Select ECG image" },
    { number: 2, title: "Baselines", description: "Mark baseline positions" },
    { number: 3, title: "Contrast", description: "Enhance image clarity" },
    { number: 4, title: "Crop Leads", description: "Extract V1, V2, V3" },
    { number: 5, title: "Calibrate", description: "Set scale factor" },
    { number: 6, title: "Detect", description: "Find ECG trace" },
    { number: 7, title: "Export", description: "Download results" },
  ];
</script>

<div class="flex flex-col gap-6 p-8">
  <!-- Header -->
  <div>
    <h1 class="text-3xl font-bold flex items-center gap-2">
      <AudioWaveformIcon class="size-7" />
      Process ECG
    </h1>
    <p class="text-sm text-muted-foreground mt-2">
      Extract time-series data from ECG images through an interactive preprocessing pipeline
    </p>
  </div>

  <!-- Progress Indicator -->
  <div class="max-w-4xl">
    <div class="flex items-center justify-between gap-2 mb-4">
      {#each steps as step, idx}
        <div class="flex flex-col items-center flex-1">
          <div
            class={`flex items-center justify-center size-10 rounded-full font-semibold text-sm transition-colors ${
              step.number < currentStep
                ? "bg-green-600 text-white"
                : step.number === currentStep
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground"
            }`}
          >
            {#if step.number < currentStep}
              <Check class="size-5" />
            {:else}
              {step.number}
            {/if}
          </div>
          <p class="text-xs font-medium mt-2 text-center">{step.title}</p>
        </div>
      {/each}
    </div>
  </div>

  <!-- Step Content -->
  <div class="max-w-3xl">
    {#if currentStep === 1}
      <!-- Step 1: Upload -->
      <div class="space-y-4">
        <h2 class="text-lg font-semibold">Step 1: Upload Image</h2>
        
        <Card.Root>
          <Card.Header>
            <Card.Title>Select an ECG Image</Card.Title>
            <Card.Description>
              Upload a PNG or JPG file
            </Card.Description>
          </Card.Header>

          <Card.Content class="space-y-6">
            {#if !file}
              <input
                type="file"
                accept="image/*"
                on:change={handleFile}
                class="hidden"
                id="file-input"
              />
              <label 
                for="file-input"
                class="border-2 border-dashed border-muted-foreground/25 rounded-lg p-8 text-center hover:border-muted-foreground/50 transition-colors cursor-pointer block"
                on:drop|preventDefault={(e) => {
                  const droppedFile = e.dataTransfer?.files?.[0];
                  if (droppedFile?.type.startsWith("image/")) {
                    file = droppedFile;
                    previewUrl = URL.createObjectURL(droppedFile);
                  }
                }}
                on:dragover|preventDefault
              >
                <Upload class="size-8 mx-auto mb-2 text-muted-foreground" />
                <p class="font-medium">Click to upload or drag and drop</p>
                <p class="text-sm text-muted-foreground">PNG or JPG</p>
              </label>
            {:else}
              <div class="space-y-4">
                <div class="bg-muted p-3 rounded-lg">
                  <p class="text-sm font-medium">{file.name}</p>
                  <p class="text-xs text-muted-foreground mt-1">
                    {(file.size / 1024).toFixed(2)} KB
                  </p>
                </div>

                {#if previewUrl}
                  <div class="border rounded-lg overflow-hidden bg-muted">
                    <img 
                      src={previewUrl} 
                      alt="ECG preview" 
                      class="w-full max-h-96 object-cover"
                    />
                  </div>
                {/if}

                <button 
                  class="h-8 gap-1.5 rounded-md px-3 py-2 text-sm font-medium bg-background hover:bg-accent hover:text-accent-foreground dark:bg-input/30 dark:border-input dark:hover:bg-input/50 border shadow-xs"
                  on:click={handleClear}
                >
                  Change Image
                </button>
              </div>
            {/if}
          </Card.Content>

          <Card.Footer class="flex gap-3 justify-between">
            {#if file}
              <div class="flex items-center gap-2 text-sm text-green-600">
                <Check class="size-4" /> Image ready
              </div>
            {/if}
            <button 
              disabled={!file}
              class="h-9 px-4 py-2 rounded-md text-sm font-medium inline-flex shrink-0 items-center justify-center gap-2 bg-primary text-primary-foreground hover:bg-primary/90 shadow-xs disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              on:click={nextStep}
            >
              Continue <ChevronRight class="size-4" />
            </button>
          </Card.Footer>
        </Card.Root>
      </div>

    {:else if currentStep === 2}
      <!-- Step 2: Baselines -->
      <div class="space-y-4">
        <h2 class="text-lg font-semibold">Step 2: Mark Baselines</h2>
        
        <Card.Root>
          <Card.Header>
            <Card.Title>Define Baseline Positions</Card.Title>
            <Card.Description>
              Identify three horizontal baseline positions in the ECG image
            </Card.Description>
          </Card.Header>

          <Card.Content class="space-y-6">
            <div class="space-y-4">
              {#if previewUrl}
                <div class="space-y-2">
                  <p class="text-xs text-muted-foreground">
                    Click on the image to mark baselines ({baselines.length}/3)
                  </p>
                  <div 
                    class="border rounded-lg overflow-hidden bg-muted relative inline-block w-full cursor-crosshair"
                    role="button"
                    tabindex="0"
                    on:click={(e) => {
                      if (baselineMode === "manual") {
                        const containerRect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
                        const displayY = e.clientY - containerRect.top;
                        // Convert to original-image space NOW, while displayImageDimensions is accurate.
                        // Sending original-space values directly avoids stale-dimension bugs.
                        if (baselines.length < 3) {
                          baselines = [...baselines, Math.round(scaleCoordinate(displayY, 'y'))];
                          saveState();
                        }
                      }
                    }}
                    on:keydown={(e) => {
                      if (baselineMode === "manual" && (e.key === 'Enter' || e.key === ' ')) {
                        e.preventDefault();
                        // For keyboard, we can't get a precise click position, so skip
                      }
                    }}
                  >
                    <img 
                      bind:this={imageElement}
                      src={previewUrl} 
                      alt="ECG for baseline marking" 
                      class="w-full rounded pointer-events-none"
                      on:load={onImageLoad}
                      draggable={false}
                    />
                    {#each baselines as baseline, idx}
                      <div 
                        class="absolute left-0 right-0 border-t-2 border-red-500 pointer-events-none"
                        style="top: {(baseline / (originalImageDimensions?.height || 1)) * displayImageDimensions.height}px"
                      >
                        <span class="absolute -top-5 left-2 text-xs font-medium text-red-500 bg-white dark:bg-slate-900 px-2 rounded">
                          Baseline {idx + 1}
                        </span>
                      </div>
                    {/each}
                  </div>
                  {#if baselines.length > 0}
                    <div class="space-y-1">
                      {#each baselines as baseline, idx}
                        <div class="flex items-center justify-between text-xs">
                          <span>Baseline {idx + 1}: {baseline}px</span>
                          <button 
                            class="text-red-500 hover:text-red-700 font-medium"
                            on:click={() => {
                              baselines = baselines.filter((_, i) => i !== idx);
                            }}
                          >
                            Remove
                          </button>
                        </div>
                      {/each}
                    </div>
                  {/if}
                </div>
              {/if}

              {#if baselines.length > 0}
                <div class="bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded-lg p-3">
                  <p class="text-sm font-medium text-green-900 dark:text-green-100">
                    ✓ {baselines.length} baseline(s) marked
                  </p>
                </div>
              {/if}
            </div>
          </Card.Content>

          <Card.Footer class="flex gap-3 justify-between">
            <button 
              class="h-9 px-4 py-2 rounded-md text-sm font-medium bg-background hover:bg-accent hover:text-accent-foreground dark:bg-input/30 dark:border-input dark:hover:bg-input/50 border shadow-xs transition-all"
              on:click={prevStep}
            >
              Back
            </button>
            <button 
              class="h-9 px-4 py-2 rounded-md text-sm font-medium inline-flex shrink-0 items-center justify-center gap-2 bg-primary text-primary-foreground hover:bg-primary/90 shadow-xs transition-all"
              on:click={nextStep}
            >
              Continue <ChevronRight class="size-4" />
            </button>
          </Card.Footer>
        </Card.Root>
      </div>

    {:else if currentStep === 3}
      <!-- Step 3: Contrast -->
      <div class="space-y-4">
        <h2 class="text-lg font-semibold">Step 3: Enhance Contrast</h2>
        
        <Card.Root>
          <Card.Header>
            <Card.Title>Adjust Image Contrast</Card.Title>
            <Card.Description>
              Enhance the clarity of the ECG trace for better detection
            </Card.Description>
          </Card.Header>

          <Card.Content class="space-y-6">
            <div class="space-y-4">
              <div>
                <div class="flex items-center justify-between mb-2">
                  <Label>Contrast Multiplier</Label>
                  <span class="text-sm font-medium">{contrastValue.toFixed(2)}x</span>
                </div>
                <input 
                  type="range" 
                  min="0.5" 
                  max="3" 
                  step="0.1" 
                  bind:value={contrastValue}
                  class="w-full"
                />
                <p class="text-xs text-muted-foreground mt-2">Increase for clearer traces, decrease to preserve details</p>
              </div>

              {#if previewUrl}
                <div class="border rounded-lg overflow-hidden bg-muted">
                  <img 
                    src={previewUrl} 
                    alt="Contrast preview" 
                    class="w-full max-h-96 object-cover"
                    style="filter: contrast({contrastValue})"
                  />
                </div>
              {/if}
            </div>
          </Card.Content>

          <Card.Footer class="flex gap-3 justify-between">
            <button 
              class="h-9 px-4 py-2 rounded-md text-sm font-medium bg-background hover:bg-accent hover:text-accent-foreground dark:bg-input/30 dark:border-input dark:hover:bg-input/50 border shadow-xs transition-all"
              on:click={prevStep}
            >
              Back
            </button>
            <button 
              class="h-9 px-4 py-2 rounded-md text-sm font-medium inline-flex shrink-0 items-center justify-center gap-2 bg-primary text-primary-foreground hover:bg-primary/90 shadow-xs transition-all"
              on:click={nextStep}
            >
              Continue <ChevronRight class="size-4" />
            </button>
          </Card.Footer>
        </Card.Root>
      </div>

    {:else if currentStep === 4}
      <!-- Step 4: Crop Leads -->
      <div class="space-y-4">
        <h2 class="text-lg font-semibold">Step 4: Extract ECG Leads</h2>
        
        <Card.Root>
          <Card.Header>
            <Card.Title>Define Lead Regions</Card.Title>
            <Card.Description>
              Click and drag on the image to select regions for each lead
            </Card.Description>
          </Card.Header>

          <Card.Content class="space-y-6">
            <div class="space-y-4">
              {#if previewUrl}
                <div class="space-y-2">
                  <p class="text-sm font-medium text-muted-foreground">
                    {#if !cropAuto}
                      Select lead region: {currentCropLead ? currentCropLead : "Click a lead button below"}
                    {:else}
                      Preview
                    {/if}
                  </p>
                  <div 
                    bind:this={previewContainerElement}
                    class="border rounded-lg overflow-hidden bg-muted relative cursor-crosshair"
                    on:mousedown={(e) => {
                      if (!cropAuto && currentCropLead) startCrop(currentCropLead, e);
                    }}
                    on:mousemove={updateCrop}
                    on:mouseup={endCrop}
                    on:mouseleave={() => {
                      isDrawing = false;
                    }}
                    role="button"
                    tabindex="0"
                  >
                    <img 
                      bind:this={imageElement}
                      src={previewUrl} 
                      alt="Lead cropping" 
                      class="w-full select-none"
                      draggable={false}
                      on:dragstart|preventDefault
                      on:load={onImageLoad}
                    />
                    <!-- Draw rectangles for already-cropped regions -->
                    {#each leads as lead}
                      {#if cropRegions[lead]}
                        <div
                          class="absolute border-2 border-blue-500 bg-blue-500/10"
                          style="
                            left: {(cropRegions[lead].x1 / (originalImageDimensions?.width || 1)) * displayImageDimensions.width}px;
                            top: {(cropRegions[lead].y1 / (originalImageDimensions?.height || 1)) * displayImageDimensions.height}px;
                            width: {((cropRegions[lead].x2 - cropRegions[lead].x1) / (originalImageDimensions?.width || 1)) * displayImageDimensions.width}px;
                            height: {((cropRegions[lead].y2 - cropRegions[lead].y1) / (originalImageDimensions?.height || 1)) * displayImageDimensions.height}px;
                          "
                        >
                          <span class="text-xs font-bold text-blue-600 bg-white px-1">{lead}</span>
                        </div>
                      {/if}
                    {/each}
                  </div>
                </div>
              {/if}

              <!-- Lead selection buttons and status -->
              {#if !cropAuto}
                <div class="space-y-3">
                  <p class="text-sm font-medium">Select each lead to crop:</p>
                  <div class="grid grid-cols-3 gap-2">
                    {#each leads as lead}
                      <button
                        class="h-12 px-4 py-2 rounded-md text-sm font-medium transition-all {
                          currentCropLead === lead
                            ? 'bg-blue-600 text-white ring-2 ring-blue-400'
                            : cropRegions[lead]
                              ? 'bg-green-600 text-white hover:bg-green-700'
                              : 'bg-muted hover:bg-muted/80 border'
                        }"
                        on:click={() => {
                          currentCropLead = currentCropLead === lead ? null : lead;
                        }}
                      >
                        <div class="flex flex-col items-center gap-1">
                          {lead}
                          {#if cropRegions[lead]}
                            <span class="text-xs opacity-90">✓ Cropped</span>
                          {/if}
                        </div>
                      </button>
                    {/each}
                  </div>
                </div>

                <!-- Show crop details -->
                <div class="space-y-2">
                  {#each leads as lead}
                    {#if cropRegions[lead]}
                      <div class="bg-muted p-3 rounded-lg text-sm space-y-1">
                        <p class="font-medium">{lead}: ({cropRegions[lead].x1}, {cropRegions[lead].y1}) to ({cropRegions[lead].x2}, {cropRegions[lead].y2})</p>
                        <button
                          class="text-xs text-red-600 hover:text-red-700 font-medium"
                          on:click={() => clearCropRegion(lead)}
                        >
                          Clear region
                        </button>
                      </div>
                    {/if}
                  {/each}
                </div>
              {/if}

              <!-- Auto-detect mode status -->
              {#if cropAuto}
                <div class="grid grid-cols-3 gap-2">
                  {#each leads as lead}
                    <div class="bg-muted p-3 rounded-lg text-center">
                      <p class="text-sm font-medium">{lead}</p>
                      <p class="text-xs text-muted-foreground mt-1">Will auto-detect</p>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          </Card.Content>

          <Card.Footer class="flex gap-3 justify-between">
            <button 
              class="h-9 px-4 py-2 rounded-md text-sm font-medium bg-background hover:bg-accent hover:text-accent-foreground dark:bg-input/30 dark:border-input dark:hover:bg-input/50 border shadow-xs transition-all"
              on:click={prevStep}
            >
              Back
            </button>
            <button 
              class="h-9 px-4 py-2 rounded-md text-sm font-medium inline-flex shrink-0 items-center justify-center gap-2 bg-primary text-primary-foreground hover:bg-primary/90 shadow-xs transition-all"
              on:click={nextStep}
              disabled={!cropAuto && Object.values(cropRegions).filter(Boolean).length === 0}
            >
              Continue <ChevronRight class="size-4" />
            </button>
          </Card.Footer>
        </Card.Root>
      </div>

    {:else if currentStep === 5}
      <!-- Step 5: Calibration -->
      <div class="space-y-4">
        <h2 class="text-lg font-semibold">Step 5: Calibrate Scale</h2>
        
        <Card.Root>
          <Card.Header>
            <Card.Title>Set Pixels per Small Square</Card.Title>
            <Card.Description>
              {#if calibrationMode}
                Click two points on the image to measure a known distance
              {:else if measuredPixels > 0}
                Enter how many small squares the measured distance represents
              {:else}
                Measure distance or enter calibration value manually
              {/if}
            </Card.Description>
          </Card.Header>

          <Card.Content class="space-y-6">
            <div class="space-y-4">
              <!-- Manual Input -->
              <div>
                <Label>Pixels per Small Square</Label>
                <Input 
                  type="number" 
                  placeholder="Enter calibration value"
                  bind:value={pixelsPerSmallSquare}
                  class="mt-2"
                  min="0"
                  step="0.1"
                />
                <p class="text-xs text-muted-foreground mt-2">
                  Standard ECG: 1 small square = 0.04s (horizontal) or 0.1mV (vertical)
                </p>
              </div>

              <!-- Interactive Measurement -->
              {#if previewUrl}
                <div class="space-y-3">
                  <p class="text-sm font-medium">Or measure on the image:</p>
                  <div 
                    bind:this={previewContainerElement}
                    class="relative border rounded-lg overflow-hidden bg-muted w-full cursor-crosshair"
                    on:click={calibrationMode ? handleCalibrationClick : undefined}
                    role="button"
                    tabindex="0"
                    on:keydown={(e) => {
                      if (calibrationMode && (e.key === 'Enter' || e.key === ' ')) {
                        e.preventDefault();
                        // Keyboard interaction for accessibility
                      }
                    }}
                  >
                    <img 
                      bind:this={imageElement}
                      src={previewUrl} 
                      alt="Calibration" 
                      class="w-full max-h-80 object-cover cursor-crosshair select-none"
                      draggable={false}
                      on:load={onImageLoad}
                    />
                    <!-- Draw measurement line if two points selected -->
                    {#if calibrationPoints.length >= 1}
                      {#each calibrationPoints as point}
                        <div
                          class="absolute size-3 bg-red-500 rounded-full border-2 border-white shadow-lg"
                          style="
                            left: {point.x}px;
                            top: {point.y}px;
                            transform: translate(-50%, -50%);
                            pointer-events: none;
                          "
                        ></div>
                      {/each}
                      {#if calibrationPoints.length === 2}
                        <svg
                          class="absolute inset-0 w-full h-full pointer-events-none"
                          style="width: 100%; height: 100%;"
                        >
                          <line
                            x1={calibrationPoints[0].x}
                            y1={calibrationPoints[0].y}
                            x2={calibrationPoints[1].x}
                            y2={calibrationPoints[1].y}
                            stroke="red"
                            stroke-width="2"
                            stroke-dasharray="5,5"
                          />
                        </svg>
                      {/if}
                    {/if}
                  </div>

                  {#if calibrationPoints.length > 0}
                    <div class="bg-muted p-3 rounded-lg text-sm space-y-2">
                      <p>
                        <span class="font-medium">Points selected:</span> {calibrationPoints.length}/2
                      </p>
                      <p class="text-xs text-muted-foreground">
                        Display size: {displayImageDimensions.width} × {displayImageDimensions.height}px | Original: {originalImageDimensions?.width} × {originalImageDimensions?.height}px
                      </p>
                      {#if measuredPixels > 0}
                        <p>
                          <span class="font-medium">Measured distance:</span> {measuredPixels} pixels
                        </p>
                        <div class="space-y-1">
                          <label for="squares-input" class="text-xs text-muted-foreground">
                            How many small squares is this distance?
                          </label>
                          <input 
                            id="squares-input"
                            type="number" 
                            placeholder="e.g., 10"
                            on:change={(e) => {
                              const squares = parseFloat((e.target as HTMLInputElement).value);
                              if (squares > 0) {
                                pixelsPerSmallSquare = Math.round((measuredPixels / squares) * 100) / 100;
                              }
                            }}
                            class="w-full h-9 px-3 py-2 rounded-md border border-input bg-background text-sm transition-colors hover:bg-accent focus:outline-none focus:ring-1 focus:ring-ring dark:border-input/50 dark:bg-input/10"
                            min="0.1"
                            step="0.1"
                          />
                          <p class="text-xs mt-2">
                            {#if pixelsPerSmallSquare > 0}
                              Calculated: <span class="font-semibold">{pixelsPerSmallSquare}</span> pixels per small square
                            {/if}
                          </p>
                        </div>
                      {/if}
                    </div>
                  {/if}

                  <div class="flex gap-2">
                    {#if !calibrationMode}
                      <button
                        class="flex-1 h-9 px-4 py-2 rounded-md text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition-all"
                        on:click={startCalibration}
                      >
                        Measure Distance
                      </button>
                    {:else}
                      <button
                        class="flex-1 h-9 px-4 py-2 rounded-md text-sm font-medium bg-orange-600 text-white hover:bg-orange-700 transition-all"
                        on:click={() => {
                          calibrationMode = false;
                          calibrationPoints = [];
                        }}
                      >
                        Cancel
                      </button>
                    {/if}
                    {#if calibrationPoints.length > 0 || measuredPixels > 0}
                      <button
                        class="flex-1 h-9 px-4 py-2 rounded-md text-sm font-medium bg-muted hover:bg-muted/80 border transition-all"
                        on:click={resetCalibration}
                      >
                        Reset
                      </button>
                    {/if}
                  </div>
                </div>
              {/if}
            </div>
          </Card.Content>

          <Card.Footer class="flex gap-3 justify-between">
            <button 
              class="h-9 px-4 py-2 rounded-md text-sm font-medium bg-background hover:bg-accent hover:text-accent-foreground dark:bg-input/30 dark:border-input dark:hover:bg-input/50 border shadow-xs transition-all"
              on:click={prevStep}
            >
              Back
            </button>
            <button 
              class="h-9 px-4 py-2 rounded-md text-sm font-medium inline-flex shrink-0 items-center justify-center gap-2 bg-primary text-primary-foreground hover:bg-primary/90 shadow-xs transition-all" 
              on:click={nextStep}
              disabled={pixelsPerSmallSquare === 0}
            >
              Continue <ChevronRight class="size-4" />
            </button>
          </Card.Footer>
        </Card.Root>
      </div>

    {:else if currentStep === 6}
      <!-- Step 6: Detection -->
      <div class="space-y-4">
        <h2 class="text-lg font-semibold">Step 6: Detect ECG Trace</h2>
        
        <Card.Root>
          <Card.Header>
            <Card.Title>Extract ECG Waveform</Card.Title>
            <Card.Description>
              Find and trace the ECG signal path from the cropped images
            </Card.Description>
          </Card.Header>

          <Card.Content class="space-y-6">
            {#if processingError}
              <div class="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4">
                <p class="text-sm font-medium text-red-900 dark:text-red-100">⚠ Error during processing</p>
                <p class="text-xs text-red-700 dark:text-red-200 mt-1">{processingError}</p>
              </div>
            {/if}

            <div class="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-4 space-y-2">
              <p class="text-sm font-medium text-blue-900 dark:text-blue-100">
                {#if !detectionComplete}
                  Processing ECG trace detection...
                {:else}
                  ✓ Detection complete!
                {/if}
              </p>
              <div class="w-full bg-blue-200 dark:bg-blue-900 rounded-full h-2">
                <div class="bg-blue-600 h-2 rounded-full transition-all duration-200" style="width: {detectionProgress}%"></div>
              </div>
              <p class="text-xs text-blue-700 dark:text-blue-200">{Math.round(detectionProgress)}% complete</p>
            </div>

            {#if detectionComplete && processedData}
              <div class="space-y-4">
                {#if processedData.visualization}
                  <div class="border rounded-lg overflow-hidden bg-white p-4">
                    <img 
                      src={processedData.visualization} 
                      alt="ECG Visualization"
                      class="w-full"
                    />
                  </div>
                {/if}

                <div class="grid grid-cols-1 gap-2">
                  <div class="bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded-lg p-3">
                    <p class="text-sm font-medium text-green-900 dark:text-green-100">
                      ✓ ECG traces detected in all 3 leads
                    </p>
                  </div>
                  {#if processedData.results.V1 && 'voltage' in processedData.results.V1}
                    <div class="bg-muted p-3 rounded-lg text-sm">
                      <p><span class="font-medium">V1:</span> {processedData.results.V1.voltage.length} points extracted</p>
                    </div>
                  {/if}
                  {#if processedData.results.V2 && 'voltage' in processedData.results.V2}
                    <div class="bg-muted p-3 rounded-lg text-sm">
                      <p><span class="font-medium">V2:</span> {processedData.results.V2.voltage.length} points extracted</p>
                    </div>
                  {/if}
                  {#if processedData.results.V3 && 'voltage' in processedData.results.V3}
                    <div class="bg-muted p-3 rounded-lg text-sm">
                      <p><span class="font-medium">V3:</span> {processedData.results.V3.voltage.length} points extracted</p>
                    </div>
                  {/if}
                </div>
              </div>
            {/if}
          </Card.Content>

          <Card.Footer class="flex gap-3 justify-between">
            <button 
              class="h-9 px-4 py-2 rounded-md text-sm font-medium bg-background hover:bg-accent hover:text-accent-foreground dark:bg-input/30 dark:border-input dark:hover:bg-input/50 border shadow-xs transition-all"
              on:click={prevStep}
              disabled={detectionProgress > 0 && !detectionComplete}
            >
              Back
            </button>
            {#if !detectionComplete}
              <button 
                class="h-9 px-4 py-2 rounded-md text-sm font-medium inline-flex shrink-0 items-center justify-center gap-2 bg-blue-600 text-white hover:bg-blue-700 shadow-xs transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                on:click={startDetection}
                disabled={detectionProgress > 0 || !file || pixelsPerSmallSquare === 0 || Object.values(cropRegions).every(v => v === null)}
              >
                {detectionProgress > 0 ? 'Processing...' : 'Start Detection'}
              </button>
            {:else}
              <button 
                class="h-9 px-4 py-2 rounded-md text-sm font-medium inline-flex shrink-0 items-center justify-center gap-2 bg-primary text-primary-foreground hover:bg-primary/90 shadow-xs transition-all"
                on:click={nextStep}
              >
                Continue <ChevronRight class="size-4" />
              </button>
            {/if}
          </Card.Footer>
        </Card.Root>
      </div>

    {:else if currentStep === 7}
      <!-- Step 7: Export -->
      <div class="space-y-4">
        <h2 class="text-lg font-semibold">Step 7: Export Results</h2>
        
        <Card.Root>
          <Card.Header>
            <Card.Title>Download Processed ECG Data</Card.Title>
            <Card.Description>
              Save the extracted ECG time-series data in your preferred format
            </Card.Description>
          </Card.Header>

          <Card.Content class="space-y-6">
            {#if processedData}
              <div class="bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded-lg p-4">
                <p class="text-sm font-medium text-green-900 dark:text-green-100 mb-2">✓ Preprocessing Complete!</p>
                <p class="text-xs text-green-700 dark:text-green-200">
                  Your ECG data has been successfully extracted and is ready for export.
                </p>
              </div>

              <div class="grid grid-cols-1 gap-2">
                {#if processedData.results.V1 && 'voltage' in processedData.results.V1}
                  <div class="bg-muted p-3 rounded-lg">
                    <p class="text-sm font-medium">V1 Lead</p>
                    <p class="text-xs text-muted-foreground mt-1">{processedData.results.V1.voltage.length} data points extracted</p>
                  </div>
                {/if}
                {#if processedData.results.V2 && 'voltage' in processedData.results.V2}
                  <div class="bg-muted p-3 rounded-lg">
                    <p class="text-sm font-medium">V2 Lead</p>
                    <p class="text-xs text-muted-foreground mt-1">{processedData.results.V2.voltage.length} data points extracted</p>
                  </div>
                {/if}
                {#if processedData.results.V3 && 'voltage' in processedData.results.V3}
                  <div class="bg-muted p-3 rounded-lg">
                    <p class="text-sm font-medium">V3 Lead</p>
                    <p class="text-xs text-muted-foreground mt-1">{processedData.results.V3.voltage.length} data points extracted</p>
                  </div>
                {/if}
              </div>

              <div class="border rounded-lg p-4 space-y-3">
                <p class="text-sm font-medium">Select Export Format</p>
                <div class="space-y-2">
                  <label class="flex items-center gap-3 cursor-pointer p-3 border rounded-lg hover:bg-muted/50">
                    <input 
                      type="radio" 
                      bind:group={exportFormat}
                      value="npy"
                      class="size-4"
                    />
                    <div>
                      <p class="text-sm font-medium">NumPy Format (.npy)</p>
                      <p class="text-xs text-muted-foreground">Compatible with Python/NumPy workflows</p>
                    </div>
                  </label>
                  <label class="flex items-center gap-3 cursor-pointer p-3 border rounded-lg hover:bg-muted/50">
                    <input 
                      type="radio" 
                      bind:group={exportFormat}
                      value="csv"
                      class="size-4"
                    />
                    <div>
                      <p class="text-sm font-medium">CSV Format (.csv)</p>
                      <p class="text-xs text-muted-foreground">Compatible with spreadsheet applications</p>
                    </div>
                  </label>
                </div>
              </div>

              {#if exportProgress > 0 && !exportComplete}
                <div class="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-4 space-y-2">
                  <p class="text-sm font-medium text-blue-900 dark:text-blue-100">Exporting...</p>
                  <div class="w-full bg-blue-200 dark:bg-blue-900 rounded-full h-2">
                    <div class="bg-blue-600 h-2 rounded-full transition-all duration-200" style="width: {exportProgress}%"></div>
                  </div>
                  <p class="text-xs text-blue-700 dark:text-blue-200">{Math.round(exportProgress)}% complete</p>
                </div>
              {/if}

              {#if exportComplete}
                <div class="bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded-lg p-3">
                  <p class="text-sm font-medium text-green-900 dark:text-green-100">
                    ✓ File downloaded successfully!
                  </p>
                </div>
              {/if}
            {:else}
              <div class="bg-yellow-50 dark:bg-yellow-950 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
                <p class="text-sm font-medium text-yellow-900 dark:text-yellow-100">
                  ⚠ No processed data available. Please complete step 6 first.
                </p>
              </div>
            {/if}
          </Card.Content>

          <Card.Footer class="flex gap-3 justify-between">
            <button 
              class="h-9 px-4 py-2 rounded-md text-sm font-medium bg-background hover:bg-accent hover:text-accent-foreground dark:bg-input/30 dark:border-input dark:hover:bg-input/50 border shadow-xs transition-all"
              on:click={prevStep}
            >
              Back
            </button>
            <button 
              class="h-9 px-4 py-2 rounded-md text-sm font-medium inline-flex shrink-0 items-center justify-center gap-2 bg-primary text-primary-foreground hover:bg-primary/90 shadow-xs transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              on:click={exportData}
              disabled={!processedData || exportProgress > 0}
            >
              Download {exportFormat.toUpperCase()}
            </button>
          </Card.Footer>
        </Card.Root>
      </div>
    {/if}
  </div>

  <!-- Info Box -->
  <div class="max-w-3xl bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-4 flex gap-3">
    <AlertCircle class="size-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
    <div>
      <p class="font-medium text-sm text-blue-900 dark:text-blue-100">
        Step {currentStep} of {steps.length}
      </p>
      <p class="text-xs text-blue-700 dark:text-blue-200 mt-1">
        {steps[currentStep - 1].description}
      </p>
    </div>
  </div>
</div>
