<script lang="ts">
	import { cn } from "$lib/utils.js";
	import type { HTMLAttributes } from "svelte/elements";

	interface $$Props extends HTMLAttributes<HTMLDivElement> {
		children?: any;
		class?: string;
	}

	let { children, class: className, ...props }: $$Props = $props();
</script>

<div
	class={cn("flex items-center p-6 pt-0", className)}
	{...props}
>
	{@render children?.()}
</div>
