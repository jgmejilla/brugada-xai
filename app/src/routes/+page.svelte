<script lang="ts">
  import SidebarLeft from "$lib/components/sidebar-left.svelte";
  import * as Sidebar from "$lib/components/ui/sidebar/index.js";
</script>

<Sidebar.Provider>
  <SidebarLeft />
</Sidebar.Provider>
