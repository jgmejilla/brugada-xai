<script lang="ts">
  import Send from "@lucide/svelte/icons/send";
  import Loader from "@lucide/svelte/icons/loader";
  import * as Card from "$lib/components/ui/card/index.js";

  interface Message {
    id: string;
    content: string;
    role: "user" | "assistant";
    timestamp: Date;
  }

  let messages: Message[] = [];
  let inputValue = "";
  let isLoading = false;
  let messagesContainer: HTMLDivElement | null = null;

  async function sendMessage() {
    if (!inputValue.trim() || isLoading) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      content: inputValue,
      role: "user",
      timestamp: new Date()
    };

    messages = [...messages, userMessage];
    inputValue = "";
    isLoading = true;

    // Scroll to bottom
    setTimeout(() => {
      if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
      }
    }, 0);

    try {
      const response = await fetch("http://localhost:11434/api/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: "llama2:latest",
          prompt: userMessage.content,
          stream: false,
        }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const data = await response.json();
      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        content: data.response,
        role: "assistant",
        timestamp: new Date()
      };

      messages = [...messages, assistantMessage];
    } catch (error) {
      const errorMessage: Message = {
        id: crypto.randomUUID(),
        content: `Error: ${error instanceof Error ? error.message : "Failed to connect to Ollama"}. Make sure Ollama is running on localhost:11434`,
        role: "assistant",
        timestamp: new Date()
      };
      messages = [...messages, errorMessage];
    } finally {
      isLoading = false;
      setTimeout(() => {
        if (messagesContainer) {
          messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
      }, 0);
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }
</script>

<div class="flex flex-col h-screen bg-background">
  <!-- Header -->
  <div class="border-b border-border bg-card shadow-sm">
    <div class="max-w-4xl mx-auto px-8 py-6">
      <h1 class="text-3xl font-bold">Chat with Ollama</h1>
      <p class="text-sm text-muted-foreground mt-2">
        Talk to your local LLM. Using <span class="font-mono text-xs bg-muted px-2 py-1 rounded">llama2:latest</span> model
      </p>
    </div>
  </div>

  <!-- Messages Area -->
  <div
    bind:this={messagesContainer}
    class="flex-1 overflow-y-auto max-w-4xl mx-auto w-full px-8 py-6 space-y-4"
  >
    {#if messages.length === 0}
      <div class="flex flex-col items-center justify-center h-full text-center">
        <div class="size-16 rounded-full bg-muted flex items-center justify-center mb-4">
          <svg
            class="size-8 text-muted-foreground"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
            />
          </svg>
        </div>
        <h2 class="text-xl font-semibold mb-2">Start a conversation</h2>
        <p class="text-muted-foreground max-w-sm">
          Ask me anything! I'm here to help with ECG analysis, Brugada Syndrome information, or general questions.
        </p>
      </div>
    {:else}
      {#each messages as message (message.id)}
        <div class={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
          <div
            class={`max-w-xl rounded-lg px-4 py-3 ${
              message.role === "user"
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-foreground border border-border"
            }`}
          >
            <p class="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
            <p class={`text-xs mt-1 ${message.role === "user" ? "opacity-70" : "text-muted-foreground"}`}>
              {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </p>
          </div>
        </div>
      {/each}

      {#if isLoading}
        <div class="flex justify-start">
          <div class="bg-muted text-foreground border border-border rounded-lg px-4 py-3">
            <div class="flex items-center gap-2">
              <Loader class="size-4 animate-spin" />
              <span class="text-sm">Thinking...</span>
            </div>
          </div>
        </div>
      {/if}
    {/if}
  </div>

  <!-- Input Area -->
  <div class="border-t border-border bg-card max-w-4xl mx-auto w-full px-8 py-4">
    <div class="flex gap-3">
      <textarea
        value={inputValue}
        on:input={(e) => (inputValue = e.currentTarget.value)}
        on:keydown={handleKeydown}
        placeholder="Type your message... (Shift+Enter for new line)"
        class="flex-1 rounded-lg border border-input bg-background px-4 py-3 text-sm transition-colors placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring dark:border-input/50 dark:bg-input/10 resize-none"
        rows="3"
        disabled={isLoading}
      />
      <button
        on:click={sendMessage}
        disabled={isLoading || !inputValue.trim()}
        class="h-12 px-4 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all inline-flex items-center justify-center gap-2 font-medium text-sm"
      >
        {#if isLoading}
          <Loader class="size-4 animate-spin" />
        {:else}
          <Send class="size-4" />
        {/if}
      </button>
    </div>
    <p class="text-xs text-muted-foreground mt-2">
      💡 Press Enter to send, Shift+Enter for new line
    </p>
  </div>
</div>
