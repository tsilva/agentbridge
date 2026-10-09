<script>
  import { onMount } from 'svelte';
  import RequestDetail from './RequestDetail.svelte';
  import { streamOffset, needsDetailRefresh, filteredRequests } from './lib/monitor.js';
  let requests = $state([]);
  let selectedId = $state(new URLSearchParams(location.search).get('request_id'));
  let detail = $state(null);
  let filter = $state('');
  let error = $state('');
  let loading = $state(false);
  let received = $state(false);
  let connected = $state(false);
  let pool = $state({ size: 0, in_use: 0 });
  let poolConnected = $state(false);
  let filterInput;
  let liveStream;
  let detailController;
  let retryTimer;
  let disposed = false;
  let generation = 0;
  const filtered = $derived(filteredRequests(requests, filter));
  const groups = $derived([
    ['Active', filtered.filter(request => request.is_active)],
    ['Completed', filtered.filter(request => !request.is_active && !request.error)],
    ['Failed', filtered.filter(request => !request.is_active && request.error)],
  ]);

  async function loadDetail() {
    liveStream?.close();
    clearTimeout(retryTimer);
    detailController?.abort();
    const current = ++generation;
    if (!selectedId || disposed) { detail = null; loading = false; return; }
    const id = selectedId;
    detailController = new AbortController();
    loading = true;
    error = '';
    try {
      const response = await fetch('/dashboard/request/' + encodeURIComponent(id), { signal: detailController.signal });
      if (!response.ok) throw new Error(response.status === 404 ? 'Request not found' : 'Could not load request details');
      const data = await response.json();
      if (current !== generation || disposed) return;
      detail = data;
      if (data.is_active) {
        const source = new EventSource('/dashboard/stream/' + encodeURIComponent(id) + '?offset=' + streamOffset(data.buffered_text));
        liveStream = source;
        source.addEventListener('chunk', event => {
          if (current === generation && detail?.request_id === id) detail.buffered_text += event.data;
        });
        source.addEventListener('done', () => { source.close(); loadDetail(); });
        source.addEventListener('error', () => {
          source.close();
          // Reload the snapshot before reconnecting so replay cannot duplicate tokens.
          if (current === generation && !disposed) retryTimer = setTimeout(loadDetail, 500);
        });
      }
    } catch (reason) {
      if (reason.name !== 'AbortError' && current === generation && !disposed) { detail = null; error = reason.message; }
    } finally { if (current === generation) loading = false; }
  }

  function select(id, push = true) {
    if (selectedId !== id) detail = null;
    selectedId = id;
    if (push) history.pushState(null, '', '/dashboard?request_id=' + encodeURIComponent(id));
    loadDetail();
  }

  onMount(() => {
    const list = new EventSource('/dashboard/requests');
    const capacity = new EventSource('/dashboard/pool/stream');
    list.onmessage = event => {
      try {
        requests = JSON.parse(event.data);
        connected = true;
        received = true;
        if (!selectedId && requests.length) select(requests[0].request_id, false);
        else if (!loading && needsDetailRefresh(detail, requests)) loadDetail();
      } catch { connected = false; }
    };
    list.onerror = () => { connected = false; };
    capacity.onmessage = event => {
      try { pool = JSON.parse(event.data); poolConnected = true; } catch { poolConnected = false; }
    };
    capacity.onerror = () => { poolConnected = false; };
    function back() {
      const id = new URLSearchParams(location.search).get('request_id') || requests[0]?.request_id || null;
      detail = null; selectedId = id; loadDetail();
    }
    function keyboard(event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); filterInput?.focus(); }
    }
    window.addEventListener('popstate', back);
    window.addEventListener('keydown', keyboard);
    if (selectedId) loadDetail();
    return () => {
      disposed = true; generation++; list.close(); capacity.close(); liveStream?.close(); detailController?.abort(); clearTimeout(retryTimer);
      window.removeEventListener('popstate', back); window.removeEventListener('keydown', keyboard);
    };
  });
</script>
<header class="topbar">
  <a class="brand" href="/dashboard"><img class="brand-mark" src="/favicon.svg" alt="" />AgentBridge</a>
  <nav class="main-nav" aria-label="Dashboard views"><a class="nav-item active" href="/dashboard" aria-current="page">Monitor</a><a class="nav-item" href="/dashboard/chat">Chat</a></nav>
  <div class="header-actions"><div class="pool-status"><span class="pool-dot" class:available={poolConnected && pool.in_use < pool.size} class:empty={!poolConnected || pool.in_use >= pool.size}></span><span>{!poolConnected ? 'Connecting' : pool.in_use >= pool.size ? 'Busy' : 'Healthy'}</span><span class="pool-count">{Math.max(0, pool.size - pool.in_use)}/{pool.size} capacity</span></div><button class="refresh-button" onclick={() => location.reload()}>Refresh</button></div>
</header>
<div class="dashboard">
  <aside class="sidebar">
    <div class="filter-wrap"><label class="filter-field"><input type="text" id="request-filter" aria-label="Filter requests" placeholder="Filter requests..." autocomplete="off" bind:value={filter} bind:this={filterInput} /><span class="kbd">⌘K</span></label></div>
    <div id="request-list"><h3 class="request-list-title">Requests</h3>
      {#each groups as [title, items]}
        {#if items.length}<section class="request-group"><h4 class="request-group-title">{title} ({items.length})</h4>
          {#each items as request (request.request_id)}
            <button class="request-row" class:request-row-active={request.is_active} class:active={selectedId === request.request_id} aria-pressed={selectedId === request.request_id} data-request-id={request.request_id} onclick={() => select(request.request_id)}>
              <span class="request-main"><span class="request-title"><span class="status-dot" class:streaming={request.is_active} class:error={!!request.error} class:idle={!request.is_active && !request.error}></span><span class="request-id">{request.request_id}</span><span class="badge" class:badge-active={request.is_active} class:badge-err={!!request.error} class:badge-ok={!request.is_active && !request.error}>{request.is_active ? 'streaming' : request.error ? 'error' : 'ok'}</span></span><span class="request-model">{request.model}</span></span>
              <span class="request-metrics"><span>{request.is_active ? request.elapsed_s + 's' : request.duration_ms + 'ms'}</span><span>{request.input_tokens != null || request.output_tokens != null ? (request.input_tokens || 0) + (request.output_tokens || 0) + 't' : '-'}</span></span>
            </button>
          {/each}
        </section>{/if}
      {/each}
      {#if !filtered.length}<p class="empty-state">{!received ? (connected ? 'Loading…' : 'Connecting…') : requests.length ? 'No matching requests' : 'No requests'}</p>{/if}
    </div>
  </aside>
  <main class="detail-panel" id="detail">
    {#if error}<div class="detail-empty"><div><h3>{error}</h3><button class="action-button" onclick={loadDetail}>Retry</button></div></div>
    {:else if detail}{#key detail.request_id}<RequestDetail {detail} refresh={loadDetail} />{/key}
    {:else}<div class="detail-empty"><div><h3>Request Detail</h3><p class="empty-state">{loading ? 'Loading…' : 'Click a request to view details'}</p></div></div>{/if}
  </main>
</div>
<footer class="footer-status"><span class="status-dot" class:error={!connected}></span>{connected ? 'Live updates via SSE' : 'Reconnecting to live updates…'}</footer>
