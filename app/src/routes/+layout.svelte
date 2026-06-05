<script lang="ts">
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import SidebarLeft from '$lib/components/sidebar-left.svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';

	let { children } = $props();
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>

<Sidebar.Provider>
	<SidebarLeft />
	<Sidebar.Inset>
		{@render children()}
	</Sidebar.Inset>
</Sidebar.Provider>
