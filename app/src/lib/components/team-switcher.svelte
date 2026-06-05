<script lang="ts">
	import * as DropdownMenu from "$lib/components/ui/dropdown-menu/index.js";
	import * as Sidebar from "$lib/components/ui/sidebar/index.js";
	import ChevronDownIcon from "@lucide/svelte/icons/chevron-down";
	import PlusIcon from "@lucide/svelte/icons/plus";
	import type { Component } from "svelte";

	let {
		profiles,
	}: {
		profiles: {
			name: string;
			logo: Component;
			plan: string;
		}[];
	} = $props();

	let activeProfile = $state(profiles[0]);
</script>

<Sidebar.Menu>
	<Sidebar.MenuItem>
		<DropdownMenu.Root>
			<DropdownMenu.Trigger>
				{#snippet child({ props })}
					<Sidebar.MenuButton {...props} class="w-full px-1.5 py-5">
						<div
							class="bg-sidebar-primary text-sidebar-primary-foreground flex aspect-square size-5 items-center justify-center rounded-md"
						>
								<activeProfile.logo class="size-3" />
							</div>
							<span class="truncate font-medium">{activeProfile.name}</span>
							<ChevronDownIcon class="opacity-50 ml-auto" />
						</Sidebar.MenuButton>
					{/snippet}
				</DropdownMenu.Trigger>
				<DropdownMenu.Content
					class="w-64 rounded-lg"
					align="start"
					side="bottom"
					sideOffset={4}
				>
					<DropdownMenu.Label class="text-muted-foreground text-xs">Profiles</DropdownMenu.Label>
					{#each profiles as profile, index (profile.name)}
						<DropdownMenu.Item onSelect={() => (activeProfile = profile)} class="gap-2 p-2">
							<div class="flex size-6 items-center justify-center rounded-xs border">
								<profile.logo class="size-4 shrink-0" />
							</div>
							{profile.name}
							<DropdownMenu.Shortcut>⌘{index + 1}</DropdownMenu.Shortcut>
						</DropdownMenu.Item>
					{/each}
					<DropdownMenu.Separator />
					<DropdownMenu.Item class="gap-2 p-2">
						<div
							class="bg-background flex size-6 items-center justify-center rounded-md border"
						>
							<PlusIcon class="size-4" />
						</div>
						<div class="text-muted-foreground font-medium">Sign in as another user</div>
					</DropdownMenu.Item>
				</DropdownMenu.Content>
			</DropdownMenu.Root>
		</Sidebar.MenuItem>
	</Sidebar.Menu>