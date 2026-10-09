<script>
  import { onMount } from 'svelte';
  import Chat from './Chat.svelte';
  import Monitor from './Monitor.svelte';
  const chatView = window.location.pathname === '/dashboard/chat';
  let config = $state(null);
  let error = $state('');
  onMount(() => {
    if (!chatView) return;
    const controller = new AbortController();
    fetch('/dashboard/config', { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error('Could not load dashboard configuration.');
      config = await response.json();
    }).catch(reason => { if (reason.name !== 'AbortError') error = reason.message; });
    return () => controller.abort();
  });
</script>
<svelte:head><title>{chatView ? 'Chat' : 'Monitor'} · AgentBridge</title></svelte:head>
<div class="app" class:chat-view={chatView} class:monitor-view={!chatView}>
  {#if chatView}
    {#if config}<Chat models={config.available_models} defaultModel={config.default_model} />
    {:else}<main class="main"><p role="status">{error || 'Loading chat…'}</p>{#if error}<button onclick={() => location.reload()}>Retry</button>{/if}<a href="/dashboard">Monitor</a></main>{/if}
  {:else}<Monitor />{/if}
</div>
