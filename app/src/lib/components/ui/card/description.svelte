<script lang="ts">
	import { cn } from "$lib/utils.js";
	import type { HTMLAttributes } from "svelte/elements";

	interface $$Props extends HTMLAttributes<HTMLParagraphElement> {
		children?: any;
		class?: string;
	}

	let { children, class: className, ...props }: $$Props = $props();
</script>

<p
	class={cn("text-sm text-muted-foreground", className)}
	{...props}
>
	{@render children?.()}
</p>
