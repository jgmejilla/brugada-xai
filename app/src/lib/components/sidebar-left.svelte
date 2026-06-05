<script lang="ts">
  import { page } from "$app/stores";
  import AudioWaveformIcon from "@lucide/svelte/icons/audio-waveform";
  import HouseIcon from "@lucide/svelte/icons/house";
  import HeartIcon from "@lucide/svelte/icons/heart";
  import SparklesIcon from "@lucide/svelte/icons/sparkles";
  import NavMain from "./nav-main.svelte";
  import TeamSwitcher from "./team-switcher.svelte";
  import * as Sidebar from "$lib/components/ui/sidebar/index.js";
  import type { ComponentProps } from "svelte";

  // minimal navigation for our ECG app
  const navItems = [
    { title: "Digitize ECG images", url: "/process", icon: AudioWaveformIcon },
    { title: "Analyze ECG data", url: "/analyze", icon: SparklesIcon },
  ];

  // Build data with dynamic isActive based on current page
  let data = $derived.by(() => ({
    profile: { name: "Guest", logo: HeartIcon, plan: "User" },
    navMain: navItems.map(item => ({
      ...item,
      isActive: $page.url.pathname === item.url
    }))
  }));

  let { ref = $bindable(null), ...restProps }: ComponentProps<typeof Sidebar.Root> = $props();
</script>

<Sidebar.Root {...restProps}>
  <Sidebar.Header class="pb-4">
    <div class="flex items-center gap-2 px-2 py-1">
      <h2 class="text-xl font-bold">Brugada Buddy</h2>
      <HeartIcon class="size-5 text-red-500" />
    </div>
  </Sidebar.Header>
  <Sidebar.Content class="px-3 pt-2">
    <NavMain items={data.navMain} />
  </Sidebar.Content>
  <Sidebar.Footer>
    <TeamSwitcher profiles={[data.profile]} />
  </Sidebar.Footer>
</Sidebar.Root>
