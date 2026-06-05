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
	class={cn("rounded-lg border bg-card text-card-foreground", className)}
	{...props}
>
	{@render children?.()}
</div>
