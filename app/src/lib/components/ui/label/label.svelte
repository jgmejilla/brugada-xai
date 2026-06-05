<script lang="ts">
	import { cn } from "$lib/utils.js";
	import type { HTMLAttributes } from "svelte/elements";

	interface $$Props extends HTMLAttributes<HTMLLabelElement> {
		children?: any;
		for?: string;
		class?: string;
	}

	let { children, for: htmlFor, class: className, ...props }: $$Props = $props();
</script>

<label
	{...props}
	for={htmlFor}
	class={cn(
		"text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70",
		className
	)}
>
	{@render children?.()}
</label>
