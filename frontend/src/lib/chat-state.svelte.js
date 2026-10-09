import { buildUserContent } from './attachments.js';
import { streamResponse } from './stream.js';

const stateKey = 'agentbridge.chat.state.v1';

export function createChat(initialModel, storage, transport = fetch, prepare = buildUserContent) {
  let model = $state(initialModel);
  let draft = $state('');
  let files = $state([]);
  let conversation = $state([]);
  let messages = $state([]);
  let sending = $state(false);
  let status = $state('Checking');
  let destroyed = false;
  let controller;

  function save() {
    try {
      storage.setItem(stateKey + '.draft', draft);
      storage.setItem(stateKey, JSON.stringify({ model, conversationMessages: conversation, renderedMessages: messages }));
    } catch {
      // Attachment data can exceed storage quota. Preserve visible history if possible.
      try { storage.setItem(stateKey, JSON.stringify({ model, conversationMessages: [], renderedMessages: messages })); } catch { /* Keep the live chat usable. */ }
    }
  }

  function restore(models) {
    try {
      draft = storage.getItem(stateKey + '.draft') || '';
      const saved = JSON.parse(storage.getItem(stateKey) || 'null');
      if (!saved || !Array.isArray(saved.renderedMessages)) return;
      if (models.some(item => item.slug === saved.model)) model = saved.model;
      conversation = Array.isArray(saved.conversationMessages) ? saved.conversationMessages : [];
      messages = saved.renderedMessages.map(message => message.pendingRequest ? {
        role: 'error', status: 0, statusText: 'Request interrupted', requestId: message.requestId,
        retryRequest: message.pendingRequest,
      } : message);
      if (messages.some(message => message.role === 'error')) status = 'Error';
      save();
    } catch { /* Ignore unavailable storage or malformed saved state. */ }
  }

  function appendError(statusCode, statusText, body, requestId, retryRequest) {
    messages.push({ role: 'error', status: statusCode, statusText, body, requestId, retryRequest });
    status = 'Error';
    save();
  }

  function addFiles(selected) {
    for (const file of selected) {
      if (file.type.startsWith('image/') || file.type === 'application/pdf' || isText(file)) files.push(file);
      else appendError(0, 'Unsupported attachment', { error: { message: `${file.name} is not an image, PDF, or TXT file.`, type: 'invalid_attachment', code: 'unsupported_file_type' } });
    }
  }

  function isText(file) { return file.type === 'text/plain' || /\.txt$/i.test(file.name); }

  async function submit(payload, userMessageId) {
    status = 'Sending';
    controller = new AbortController();
    const pendingRequest = { payload, userMessageId };
    const assistantId = crypto.randomUUID();
    messages.push({ role: 'assistant', messageId: assistantId, text: '', model: payload.model, pendingRequest, files: [] });
    save();
    let requestId;
    try {
      const response = await transport('/api/v1/chat/completions', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal: controller.signal,
      });
      requestId = response.headers.get('x-request-id');
      for (const message of messages) {
        if (message.messageId === userMessageId || message.messageId === assistantId) message.requestId = requestId;
      }
      save();
      if (!response.ok) {
        const text = await response.text();
        let body;
        try { body = JSON.parse(text); } catch { body = { raw: text }; }
        const error = new Error(response.statusText);
        Object.assign(error, { status: response.status, statusText: response.statusText, details: body });
        throw error;
      }
      const text = await streamResponse(response, delta => {
        const assistant = messages.find(message => message.messageId === assistantId);
        if (assistant) assistant.text += delta;
      });
      const assistant = messages.find(message => message.messageId === assistantId);
      if (assistant) { assistant.text = text; assistant.pendingRequest = null; }
      // Commit only successful turns, using the exact history that was submitted.
      conversation = [...payload.messages, { role: 'assistant', content: text }];
      status = 'Healthy';
      save();
    } catch (error) {
      if (destroyed) return; // Preserve the pending request for reload recovery.
      messages = messages.filter(message => message.messageId !== assistantId);
      appendError(error.status || 0, error.statusText || (error.type === 'stream_error' ? 'Stream failed' : 'Request failed'),
        error.details || { error: { message: error.message, type: 'network_error', code: 'request_failed' } }, requestId, pendingRequest);
    } finally { controller = null; }
  }

  async function send() {
    if (sending || (!draft.trim() && !files.length)) return;
    sending = true;
    status = 'Sending';
    const draftSnapshot = draft;
    const modelSnapshot = model;
    const fileSnapshot = [...files];
    try {
      const content = await prepare(draftSnapshot.trim(), fileSnapshot);
      if (destroyed) return;
      const userMessage = { role: 'user', content };
      const payload = { model: modelSnapshot, messages: [...conversation, userMessage], stream: true };
      const userMessageId = crypto.randomUUID();
      messages.push({ role: 'user', messageId: userMessageId,
        text: draftSnapshot.trim() || `Attached ${fileSnapshot.length} file${fileSnapshot.length === 1 ? '' : 's'}`,
        files: fileSnapshot.map(file => file.name) });
      if (draft === draftSnapshot) draft = '';
      files = files.filter(file => !fileSnapshot.includes(file));
      save();
      await submit(payload, userMessageId);
    } catch (error) {
      if (!destroyed) appendError(0, 'Request preparation failed', { error: { message: error.message, type: 'request_preparation_error' } });
    } finally { sending = false; }
  }

  async function retry(message) {
    if (sending || !message.retryRequest) return;
    sending = true;
    const request = $state.snapshot(message.retryRequest);
    messages = messages.filter(item => item !== message);
    try { await submit(request.payload, request.userMessageId); }
    finally { sending = false; }
  }

  return {
    get model() { return model; }, set model(value) { model = value; save(); },
    get draft() { return draft; }, set draft(value) { draft = value; save(); },
    get files() { return files; }, get messages() { return messages; },
    get sending() { return sending; }, get status() { return status; },
    set status(value) { status = value; },
    restore, send, retry, addFiles,
    removeFile(index) { files.splice(index, 1); },
    destroy() { destroyed = true; controller?.abort(); },
  };
}
