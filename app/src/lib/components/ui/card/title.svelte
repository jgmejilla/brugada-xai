<script lang="ts">
	import { cn } from "$lib/utils.js";
	import type { HTMLAttributes } from "svelte/elements";

	interface $$Props extends HTMLAttributes<HTMLHeadingElement> {
		children?: any;
		class?: string;
	}

	let { children, class: className, ...props }: $$Props = $props();
</script>

<h2
	class={cn("text-xl font-semibold leading-none tracking-tight", className)}
	{...props}
>
	{@render children?.()}
</h2>
