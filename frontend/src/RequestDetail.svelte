<script>
  let { detail, refresh } = $props();
  let copyStatus = $state('');
  let responseFormat = $state('text');
  const total = $derived(detail.input_tokens == null && detail.output_tokens == null ? '-' : (detail.input_tokens || 0) + (detail.output_tokens || 0));
  const failure = $derived(JSON.stringify({ error: { message: detail.error, type: detail.exception_type || 'server_error' }, request_id: detail.request_id, status: 'error' }, null, 2));
  function format(content) {
    if (typeof content !== 'string') return JSON.stringify(content, null, 2);
    return content;
  }
  function pretty(content) {
    try { return JSON.stringify(JSON.parse(content), null, 2); } catch { return format(content); }
  }
  async function copy(value) {
    try { await navigator.clipboard.writeText(value); copyStatus = 'Copied'; }
    catch { copyStatus = 'Could not copy to the clipboard.'; }
  }
</script>
<div class="detail-shell">
  <header class="detail-header">
    <div class="detail-heading">
      <h3>{detail.request_id}<span class="badge" class:badge-active={detail.is_active} class:badge-err={!!detail.error} class:badge-ok={!detail.is_active && !detail.error}>{detail.is_active ? 'streaming' : detail.error ? 'error' : 'ok'}</span><span class="badge badge-model">{detail.model}</span></h3>
      <div class="detail-subline"><span>{detail.duration_ms}ms</span>{#if total !== '-'}<span>{total} tokens</span>{/if}{#if detail.is_active}<span>Live Stream</span>{/if}</div>
    </div>
    <div class="detail-actions"><button class="action-button" onclick={() => copy(detail.request_id)}>Copy ID</button>{#if !detail.is_active}<a class="action-button" href={'/dashboard/log/' + detail.request_id} target="_blank" rel="noopener">Open Log</a>{/if}</div>
  </header>
  {#if copyStatus}<p role="status">{copyStatus}</p>{/if}
  <section class="meta-grid" aria-label="Request metadata">
    {#each [['Started', detail.timestamp || 'Active'], ['Duration', detail.duration_ms + 'ms'], ['Prompt Tokens', detail.input_tokens ?? '-'], ['Completion Tokens', detail.output_tokens ?? '-'], ['Total Tokens', total]] as [label, value]}
      <div class="meta-item"><div class="meta-label">{label}</div><div class="meta-value">{value}</div></div>
    {/each}
  </section>
  <section class="detail-grid">
    <div class="panel"><div class="panel-header"><div class="panel-title">Messages</div><span class="count-pill">{detail.messages?.length || 0}</span></div>
      <div class="panel-body">
        {#each detail.messages || [] as message}<details class="message message--{message.role}" open><summary><span>{message.role}</span><span>{detail.timestamp?.slice(11, 19)}</span></summary><pre>{format(message.content)}</pre></details>{:else}<p class="empty-state">No messages captured for this request.</p>{/each}
        {#if detail.attachments?.length}<h4>Attachments</h4>{#each detail.attachments as attachment}<a class="attachment-link" href={'/dashboard/attachment/' + detail.request_id + '/' + encodeURIComponent(attachment.filename)} target="_blank" rel="noopener">{attachment.filename}</a>{/each}{/if}
        {#if detail.is_active}<div class="live-stream"><div class="live-stream-title"><span class="status-dot streaming"></span>Live Stream</div><pre id="stream-output">{detail.buffered_text}</pre></div>{/if}
      </div>
    </div>
    <div class="panel"><div class="panel-header"><div class="panel-title">Response</div>
      {#if detail.response}<button class="action-button" onclick={() => { responseFormat = responseFormat === 'text' ? 'json' : 'text'; }}>{responseFormat === 'text' ? 'Format JSON' : 'Show text'}</button>{/if}</div>
      <div class="panel-body">
        {#if detail.error}<div class="error-card"><div class="error-title">Server error<small>{detail.error}</small></div><div class="error-actions"><button class="action-button" onclick={() => copy(failure)}>Copy details</button><button class="action-button" onclick={refresh}>Refresh</button></div><pre class="error-pre">{failure}</pre></div>
        {:else if detail.response}<pre class="response-pre">{responseFormat === 'json' ? pretty(detail.response) : format(detail.response)}</pre>
        {:else}<p class="empty-state">{detail.is_active ? 'Streaming response will appear in the live stream panel.' : 'No response body captured for this request.'}</p>{/if}
      </div>
    </div>
  </section>
</div>
