<script lang="ts">
  import Upload from "@lucide/svelte/icons/upload";
  import AlertCircle from "@lucide/svelte/icons/alert-circle";
  import { Input } from "$lib/components/ui/input/index.js";
  import { Root as Label } from "$lib/components/ui/label/index.js";
  import * as Card from "$lib/components/ui/card/index.js";

  console.log("[ANALYZE] Page script loaded");

  let npyFile: File | null = null;
  let age: string = "";
  let medicalHistory: string = "";
  let analyzing = false;
  let analysisError: string | null = null;
  let analysisResult: any = null;
  let analysisProgress = 0;
  let llmAnalyzing = false;
  let llmError: string | null = null;
  let llmResult: any = null;

  function handleNpyFile(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files?.[0]) {
      const file = input.files[0];
      if (!file.name.endsWith('.npy')) {
        analysisError = "Please select a .npy file";
        return;
      }
      npyFile = file;
      analysisError = null;
    }
  }

  async function analyzeECG() {
    console.log("[ANALYZE] Button clicked, analyzeECG() called");
    if (!npyFile) {
      analysisError = "Please select an NPY file";
      return;
    }

    analyzing = true;
    console.log("[ANALYZE] analyzing set to true, starting file read");
    analysisError = null;
    analysisResult = null;
    analysisProgress = 0;

    try {
      analysisProgress = 20;

      // Read file as base64
      console.log("[ANALYZE] Reading file as arrayBuffer...");
      const arrayBuffer = await npyFile.arrayBuffer();
      console.log("[ANALYZE] arrayBuffer read, size:", arrayBuffer.byteLength);
      const bytes = new Uint8Array(arrayBuffer);
      console.log("[ANALYZE] Converting to base64 (chunked to avoid stack overflow)...");
      
      // Convert in chunks to avoid stack overflow with large files
      let binary = '';
      const chunkSize = 8192;
      for (let i = 0; i < bytes.length; i += chunkSize) {
        const chunk = bytes.subarray(i, i + chunkSize);
        binary += String.fromCharCode.apply(null, Array.from(chunk));
      }
      
      console.log("[ANALYZE] Binary string created, encoding with btoa...");
      const base64 = btoa(binary);
      console.log("[ANALYZE] Base64 encoding complete, length:", base64.length);

      analysisProgress = 40;

      const payload = {
        npyData: base64,
        filename: npyFile.name,
        age: age ? parseInt(age) : null,
        medicalHistory: medicalHistory || null
      };

      analysisProgress = 60;

      console.log("[ANALYZE] Sending fetch request to backend...");
      const response = await fetch('http://localhost:5000/api/analyze-ecg', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      console.log("[ANALYZE] Fetch response received, status:", response.status);

      analysisProgress = 80;

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Analysis failed');
      }

      const result = await response.json();
      console.log("[ANALYZE] Result received:", result);
      analysisResult = result;
      analysisProgress = 100;
      console.log("[ANALYZE] Analysis complete!");
    } catch (err) {
      console.error("[ANALYZE] Error occurred:", err);
      analysisError = err instanceof Error ? err.message : 'Unknown error occurred';
      analysisProgress = 0;
    } finally {
      analyzing = false;
    }
  }

  async function analyzeLLM() {
    console.log("[LLM] Analyze with LLM button clicked");
    if (!analysisResult?.features) {
      llmError = "Please analyze ECG features first";
      return;
    }

    llmAnalyzing = true;
    llmError = null;
    llmResult = null;

    try {
      console.log("[LLM] Sending features to LLM...");
      const response = await fetch('http://localhost:5000/api/analyze-features', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          features: analysisResult.features,
          age: age ? parseInt(age) : null,
          medicalHistory: medicalHistory || null
        })
      });

      console.log("[LLM] LLM response received, status:", response.status);

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'LLM analysis failed');
      }

      const result = await response.json();
      console.log("[LLM] LLM result:", result);
      
      // Ensure analysis is parsed as an object
      let analysis = result.analysis;
      if (typeof analysis === 'string') {
        analysis = JSON.parse(analysis);
      }
      
      // Check if this is a fallback response (parsing failed)
      const isParsingFallback = 
        analysis.risk_category === 'uncertain' &&
        analysis.findings === 'Unable to parse LLM response properly.' &&
        analysis.reasoning === 'The LLM response format was invalid and could not be recovered.';
      
      if (isParsingFallback && result.raw_response) {
        // Display raw JSON in fallback mode
        llmResult = {
          isFallback: true,
          raw_json: result.raw_response,
          risk_category: 'uncertain'
        };
      } else {
        // Normal structured display
        llmResult = analysis;
        analysisResult.textual_response = analysis.findings;
        analysisResult.status = analysis.risk_category;
        analysisResult.score = analysis.confidence;
      }
    } catch (err) {
      console.error("[LLM] Error occurred:", err);
      llmError = err instanceof Error ? err.message : 'Unknown error occurred';
    } finally {
      llmAnalyzing = false;
    }
  }
</script>

<div class="min-h-screen bg-background p-8">
  <div class="max-w-4xl space-y-8">
    <div class="space-y-2">
      <h1 class="text-4xl font-bold">ECG Analysis</h1>
      <p class="text-muted-foreground">Upload an ECG (.npy) file to analyze it</p>
    </div>

    <!-- Input Card -->
    <Card.Root>
      <Card.Header>
        <Card.Title>Upload ECG Data</Card.Title>
        <Card.Description>
          File must contain 3-lead ECG data (V1, V2, V3)
        </Card.Description>
      </Card.Header>

      <Card.Content class="space-y-6">
        <!-- File Upload -->
        <div class="space-y-2">
          <Label>ECG File (NPY) <span class="text-xs text-muted-foreground font-normal">required</span></Label>
          <label class="flex flex-col items-center justify-center w-full h-24 border-2 border-dashed border-input rounded-lg cursor-pointer hover:bg-muted/50 transition-colors">
            <div class="flex flex-col items-center justify-center pt-5 pb-6">
              {#if npyFile}
                <div class="text-green-600 text-center">
                  <p class="font-semibold text-sm">✓ {npyFile.name}</p>
                </div>
              {:else}
                <Upload class="w-6 h-6 text-muted-foreground mb-2" />
                <p class="text-sm text-muted-foreground">Click to select .npy file</p>
              {/if}
            </div>
            <input
              type="file"
              accept=".npy"
              on:change={handleNpyFile}
              class="hidden"
              disabled={analyzing}
            />
          </label>
        </div>

        <!-- Patient Data (Optional) -->
        <div class="space-y-3 p-4 bg-muted/30 rounded-lg">
          <p class="text-xs text-muted-foreground font-medium">Optional patient information (helps with analysis)</p>
          <div class="grid grid-cols-2 gap-4">
            <div class="space-y-2">
              <Label for="age">Age</Label>
              <Input
                id="age"
                type="number"
                placeholder="e.g., 45"
                bind:value={age}
                disabled={analyzing}
              />
            </div>
            <div class="space-y-2">
              <Label for="history">Medical History</Label>
              <Input
                id="history"
                type="text"
                placeholder="e.g., Family history of sudden cardiac death"
                bind:value={medicalHistory}
                disabled={analyzing}
              />
            </div>
          </div>
        </div>

        <!-- Error Display -->
        {#if analysisError}
          <div class="flex gap-3 p-4 bg-red-50 border border-red-200 rounded-lg">
            <AlertCircle class="text-red-600 shrink-0" />
            <div class="text-sm text-red-700">{analysisError}</div>
          </div>
        {/if}

        <!-- Status message -->
        <!-- {#if analyzing}
          <div class="text-sm text-blue-600 font-medium">Extracting features...</div>
        {/if} -->
      </Card.Content>

      <Card.Footer>
        <button
          on:click={analyzeECG}
          disabled={!npyFile || analyzing}
          class="w-full h-10 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {#if analyzing}
            Extracting features...
          {:else}
            <Upload class="mr-2 size-4 inline" />
            Analyze ECG
          {/if}
        </button>
      </Card.Footer>
    </Card.Root>

    <!-- Results Card -->
    {#if analysisResult}
      <Card.Root class="border-green-200">
        <Card.Header>
          <Card.Title class="text-green-700">Feature Extraction Complete</Card.Title>
          <Card.Description>
            ECG landmarks detected. Proceed with LLM analysis for diagnosis.
          </Card.Description>
        </Card.Header>

        <Card.Content class="space-y-6">
          <!-- ECG Visualizations (all 3 leads) -->
          {#if analysisResult.visualizations && analysisResult.visualizations.length > 0}
            <div class="space-y-4">
              <h3 class="font-semibold">ECG with Landmarks</h3>
              {#each analysisResult.visualizations as viz}
                <div class="space-y-2">
                  <h4 class="text-sm text-muted-foreground">{viz.lead}</h4>
                  <img
                    src={viz.image}
                    alt="ECG {viz.lead} with landmarks"
                    class="w-full border rounded-lg"
                  />
                </div>
              {/each}
            </div>
          {/if}

          <!-- Features Extracted -->
          {#if analysisResult.features}
            <div class="space-y-2">
              <h3 class="font-semibold">Detected Features</h3>
              <div class="bg-muted p-4 rounded-lg text-sm whitespace-pre-wrap font-mono">
                {analysisResult.features}
              </div>
              
              <!-- LLM Analysis Button -->
              <button
                on:click={analyzeLLM}
                disabled={llmAnalyzing}
                class="w-full h-10 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {#if llmAnalyzing}
                  Analyzing with LLM...
                {:else}
                  Analyze with LLM
                {/if}
              </button>

              <!-- LLM Error -->
              {#if llmError}
                <div class="flex gap-3 p-4 bg-red-50 border border-red-200 rounded-lg">
                  <AlertCircle class="text-red-600 shrink-0" />
                  <div class="text-sm text-red-700">{llmError}</div>
                </div>
              {/if}
            </div>
          {/if}

          <!-- LLM Analysis (when available) -->
          {#if llmResult}
            <div class="space-y-4">
              <h3 class="font-semibold text-lg">Clinical Analysis</h3>
              
              {#if llmResult.isFallback}
                <!-- Fallback: Show raw JSON -->
                <div class="bg-yellow-50 p-4 rounded-lg border border-yellow-300">
                  <div class="mb-3">
                    <p class="text-sm text-muted-foreground mb-1">Risk Category</p>
                    <p class="text-lg font-bold text-yellow-600">UNCERTAIN (Parsing Error)</p>
                  </div>
                  <div>
                    <h4 class="font-semibold text-sm mb-2">Raw LLM Response</h4>
                    <pre class="text-xs bg-white p-3 rounded border border-yellow-200 overflow-auto max-h-96">{llmResult.raw_json}</pre>
                  </div>
                </div>
              {:else}
                <!-- Normal: Show structured output -->
                <!-- Risk Badge -->
                <div class={`p-4 rounded-lg border-2 ${
                  llmResult.risk_category === 'positive' 
                    ? 'bg-red-50 border-red-300' 
                    : llmResult.risk_category === 'negative'
                    ? 'bg-green-50 border-green-300'
                    : 'bg-yellow-50 border-yellow-300'
                }`}>
                  <div>
                    <p class="text-sm text-muted-foreground mb-1">Risk Category</p>
                    <p class={`text-2xl font-bold ${
                      llmResult.risk_category === 'positive' 
                        ? 'text-red-600' 
                        : llmResult.risk_category === 'negative'
                        ? 'text-green-600'
                        : 'text-yellow-600'
                    }`}>
                      {llmResult.risk_category?.toUpperCase() || 'UNKNOWN'}
                    </p>
                  </div>
                </div>

                <!-- Findings -->
                <div class="bg-muted p-4 rounded-lg">
                  <h4 class="font-semibold text-sm mb-2">Key Findings</h4>
                  <p class="text-sm text-gray-700">{llmResult.findings}</p>
                </div>

                <!-- Recommendation -->
                <div class="bg-blue-50 p-4 rounded-lg border border-blue-200">
                  <h4 class="font-semibold text-sm mb-2">Clinical Recommendation</h4>
                  <p class="text-sm text-gray-700">{llmResult.recommendation}</p>
                </div>

                <!-- Detailed Reasoning -->
                {#if llmResult.reasoning}
                  <details class="text-sm">
                    <summary class="cursor-pointer font-medium text-blue-600 hover:underline">
                      Show Detailed Reasoning
                    </summary>
                    <div class="mt-3 p-4 bg-muted rounded whitespace-pre-wrap text-xs">
                      {llmResult.reasoning}
                    </div>
                  </details>
                {/if}
              {/if}
            </div>
          {:else if analysisResult.textual_response && !llmAnalyzing}
            <div class="space-y-2">
              <h3 class="font-semibold">Clinical Analysis</h3>
              <div class="bg-muted p-4 rounded-lg text-sm">
                {analysisResult.textual_response}
              </div>
            </div>
          {/if}

          <!-- Status Badge (when available) -->
          {#if analysisResult.status && !llmResult}
            <div class="flex items-center gap-3 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <div class="text-sm font-medium">
                <span class="text-muted-foreground">Diagnosis: </span>
                <span
                  class={analysisResult.status === 'positive'
                    ? 'text-red-600 font-semibold'
                    : 'text-green-600 font-semibold'}
                >
                  {analysisResult.status?.toUpperCase() || "UNKNOWN"}
                </span>
              </div>
              {#if analysisResult.score}
                <div class="ml-auto text-sm">
                  <span class="text-muted-foreground">Confidence: </span>
                  <span class="font-semibold">{(analysisResult.score * 100).toFixed(1)}%</span>
                </div>
              {/if}
            </div>
          {/if}

          <!-- Full Conversation (if available) -->
          {#if analysisResult.raw_conversation}
            <details class="text-sm">
              <summary class="cursor-pointer font-medium text-blue-600 hover:underline">
                View Full Analysis Conversation
              </summary>
              <div class="mt-3 p-3 bg-muted rounded text-xs whitespace-pre-wrap">
                {analysisResult.raw_conversation}
              </div>
            </details>
          {/if}
        </Card.Content>
      </Card.Root>
    {/if}
  </div>
</div>
