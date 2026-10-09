<script>
  import { onMount, tick, untrack } from 'svelte';
  import { createChat } from './lib/chat-state.svelte.js';
  import { markdownToHtml } from './lib/markdown.js';
  let { models, defaultModel } = $props();
  const chat = untrack(() => createChat(defaultModel, sessionStorage));
  let prompt;
  let fileInput;
  let messageList;
  let dragging = $state(false);
  let copyError = $state('');

  onMount(() => {
    chat.restore(models);
    fetch('/health').then(response => {
      if (chat.status === 'Checking') chat.status = response.ok ? 'Healthy' : 'Error';
    }).catch(() => { if (chat.status === 'Checking') chat.status = 'Offline'; });
    return () => chat.destroy();
  });

  $effect(() => {
    chat.draft;
    if (prompt) {
      prompt.style.height = 'auto';
      prompt.style.height = Math.min(prompt.scrollHeight, 180) + 'px';
      prompt.style.overflowY = prompt.scrollHeight > 180 ? 'auto' : 'hidden';
    }
  });
  $effect(() => {
    chat.messages.map(message => message.text);
    tick().then(() => { if (messageList) messageList.scrollTop = messageList.scrollHeight; });
  });
  async function copy(value) {
    try { await navigator.clipboard.writeText(value); copyError = ''; }
    catch { copyError = 'Could not copy to the clipboard.'; }
  }
  function details(message) {
    return JSON.stringify({ status: message.status, statusText: message.statusText, request_id: message.requestId || null, error: message.body?.error || message.body || null }, null, 2);
  }
</script>

<header class="topbar">
  <a class="brand" href="/dashboard"><img class="brand-mark" src="/favicon.svg" alt="" />AgentBridge</a>
  <nav class="main-nav" aria-label="Dashboard views">
    <a class="nav-item" href="/dashboard">Monitor</a>
    <a class="nav-item active" aria-current="page" href="/dashboard/chat">Chat</a>
  </nav>
  <div class="header-actions">
    <label class="field field-model"><span>Model</span><select id="model" bind:value={chat.model} disabled={chat.sending}>
      {#each models as model}<option value={model.slug}>{model.slug}</option>{/each}
    </select></label>
    <div id="status" class="status" class:ok={chat.status === 'Healthy'} class:error={['Error', 'Offline'].includes(chat.status)} role="status">{chat.status}</div>
  </div>
</header>
<main class="main">
  <section id="messages" class="messages" aria-label="Conversation" aria-live="polite" bind:this={messageList}>
    {#if !chat.messages.length}<div class="empty"><strong>Send a test message</strong>Use a model namespace, attach files if needed, and inspect any server error inline.</div>{/if}
    {#each chat.messages as message}
      {#if message.role === 'error'}
        <article class="message error">
          <div class="error-title">Server error</div>
          <div class="error-summary">{[message.status || '', message.statusText || 'Request failed'].filter(Boolean).join(' ')}{message.body?.error?.message ? ': ' + message.body.error.message : ''}</div>
          <details class="error-details" open><summary>Details</summary><pre>{details(message)}</pre></details>
          <div class="error-actions">
            {#if message.retryRequest}<button class="secondary" disabled={chat.sending} onclick={() => chat.retry(message)}>Retry</button>{/if}
            <button class="secondary" onclick={() => copy(details(message))}>Copy details</button>
          </div>
        </article>
      {:else}
        <article class="message {message.role}" data-message-id={message.messageId}>
          <div class="message-header">
            <div class="message-heading"><span class="message-role">{message.role === 'user' ? 'You' : 'Assistant'}</span>{#if message.model}<span class="model-badge">{message.model}</span>{/if}</div>
            {#if message.requestId}<a class="message-info available" aria-label="Inspect request" title="Inspect request" href={'/dashboard?request_id=' + encodeURIComponent(message.requestId)}>ⓘ</a>{/if}
          </div>
          {#if message.role === 'assistant'}
            {#if message.pendingRequest && !message.text}<div class="message-body typing" role="status" aria-label="Assistant is typing"><span class="typing-indicator" aria-hidden="true"><span></span><span></span><span></span></span></div>
            {:else}<div class="message-body markdown">{@html markdownToHtml(message.text)}</div>{/if}
          {:else}<div class="message-body">{message.text}</div>{/if}
          {#if message.files?.length}<div class="attached-files">{#each message.files as name}<span class="file-pill">{name}</span>{/each}</div>{/if}
        </article>
      {/if}
    {/each}
  </section>
  {#if copyError}<p role="alert">{copyError}</p>{/if}
  <form id="composer" class="composer" class:dragging aria-label="Message composer"
    onsubmit={event => { event.preventDefault(); chat.send(); }}
    ondragover={event => { event.preventDefault(); dragging = true; }}
    ondragleave={() => { dragging = false; }}
    ondrop={event => { event.preventDefault(); dragging = false; chat.addFiles(event.dataTransfer.files); }}>
    <div class="drop-hint">Drop files to attach</div>
    <div id="attached-files" class="attached-files">{#each chat.files as file, index}<span class="file-pill">{file.name}<button class="remove-file" type="button" aria-label={'Remove ' + file.name} onclick={() => chat.removeFile(index)}>×</button></span>{/each}</div>
    <div class="input-row">
      <button id="attach-button" class="icon-button" title="Attach files" type="button" aria-label="Attach files" onclick={() => fileInput.click()}>＋</button>
      <textarea id="prompt" aria-label="Message" placeholder="Send a test message..." rows="1" bind:this={prompt} bind:value={chat.draft}
        onkeydown={event => { if (event.key === 'Enter' && !event.isComposing && !event.shiftKey && !event.altKey) { event.preventDefault(); chat.send(); } }}></textarea>
      <button id="send" class="primary" type="submit" aria-label="Send message" title="Send message" disabled={chat.sending || (!chat.draft.trim() && !chat.files.length)}>↑</button>
    </div>
    <input id="file-input" class="hidden-input" type="file" tabindex="-1" aria-hidden="true" multiple accept="image/*,application/pdf,text/plain,.txt" bind:this={fileInput}
      onchange={event => { chat.addFiles(event.currentTarget.files); event.currentTarget.value = ''; }} />
  </form>
</main>
