<script lang="ts">
  import AudioWaveformIcon from "@lucide/svelte/icons/audio-waveform";
  import Input from "$lib/components/ui/input/index.ts";
  // basic file upload state
  let file: File | null = null;
  let previewUrl: string | null = null;

  function handleFile(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files[0]) {
      file = input.files[0];
      previewUrl = URL.createObjectURL(file);
    }
  }
</script>

<div class="p-8">
<h1 class="text-2xl font-bold flex items-center">
  <AudioWaveformIcon class="size-6 mr-2" />Process
</h1>
<p class="py-2 text-sm font- italic text-muted-foreground">Get time-series data from an ECG image</p>
<div class="p-4">
  <!-- card container -->
  <div class="max-w-xl mx-auto bg-card text-card-foreground rounded-lg shadow-md p-6 space-y-6">
    <label class="block">
      <span class="text-sm font-medium">ECG image</span>
      <Input
        type="file"
        accept="image/*"
        bind:files={null}
        on:change={handleFile}
        class="mt-1 w-full"
      />
    </label>

    {#if previewUrl}
      <div class="border rounded overflow-hidden">
        <img src={previewUrl} alt="ECG preview" class="w-full" />
      </div>
    {/if}

    <p class="text-sm text-muted-foreground">Upload and process ECG images here.</p>

    <button
      class="w-full bg-primary text-primary-foreground py-2 rounded disabled:opacity-50"
      disabled={!file}
      on:click={() => { /* placeholder for next step */ }}
    >
      Continue &rarr;
    </button>
  </div>
</div>
</div>