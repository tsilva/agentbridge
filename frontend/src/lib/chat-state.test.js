import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import { compileModule } from 'svelte/compiler';

const source = await readFile(new URL('./chat-state.svelte.js', import.meta.url), 'utf8');
const compiled = compileModule(source, { filename: 'chat-state.svelte.js', generate: 'server' }).js.code
  .replaceAll("'svelte/internal/server'", JSON.stringify(import.meta.resolve('svelte/internal/server')))
  .replaceAll("'./attachments.js'", JSON.stringify(new URL('./attachments.js', import.meta.url).href))
  .replaceAll("'./stream.js'", JSON.stringify(new URL('./stream.js', import.meta.url).href));
const { createChat } = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
function storage() {
  const values = new Map();
  return { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value) };
}
function completion(text = 'answer') {
  return new Response('data: ' + JSON.stringify({ choices: [{ delta: { content: text } }] }) + '\n\ndata: [DONE]\n\n', { headers: { 'x-request-id': 'chatcmpl-00000001' } });
}

test('preparation snapshots files, model, and draft; repeated sends stay single', async () => {
  const first = { name: 'first.txt', type: 'text/plain' };
  const next = { name: 'next.txt', type: 'text/plain' };
  let finish;
  const payloads = [];
  const chat = createChat('codex/test', storage(), async (_url, options) => {
    payloads.push(JSON.parse(options.body)); return completion();
  }, async (text, files) => {
    assert.deepEqual(files, [first]);
    await new Promise(resolve => { finish = resolve; });
    return text + '\n' + files[0].name;
  });
  chat.draft = 'first prompt'; chat.addFiles([first]);
  const pending = chat.send();
  await chat.send();
  chat.draft = 'next draft'; chat.model = 'codex/next'; chat.removeFile(0); chat.addFiles([next]);
  finish(); await pending;
  assert.equal(payloads.length, 1);
  assert.equal(payloads[0].model, 'codex/test');
  assert.equal(payloads[0].messages[0].content, 'first prompt\nfirst.txt');
  assert.equal(chat.draft, 'next draft');
  assert.deepEqual(chat.files, [next]);
  assert.equal(chat.sending, false);
  assert.equal(chat.messages[1].text, 'answer');
});

test('retry after reload reuses exact failed payload and discards partial assistant history', async () => {
  const saved = storage();
  const payloads = [];
  let failing = true;
  const transport = async (_url, options) => {
    payloads.push(JSON.parse(options.body));
    return failing ? new Response('data: {"choices":[{"delta":{"content":"partial"}}]}\n\n') : completion();
  };
  let chat = createChat('codex/test', saved, transport);
  chat.draft = 'original'; await chat.send();
  assert.deepEqual(chat.messages.map(message => message.role), ['user', 'error']);
  chat = createChat('codex/test', saved, transport);
  chat.restore([{ slug: 'codex/test' }]);
  chat.draft = 'next draft';
  failing = false;
  await chat.retry(chat.messages[1]);
  assert.deepEqual(payloads[1], payloads[0]);
  assert.equal(chat.draft, 'next draft');
  assert.deepEqual(chat.messages.map(message => message.role), ['user', 'assistant']);
  await chat.send();
  assert.deepEqual(payloads[2].messages, [
    { role: 'user', content: 'original' }, { role: 'assistant', content: 'answer' }, { role: 'user', content: 'next draft' },
  ]);
});

test('interrupted pending request restores as a retryable error', () => {
  const saved = storage();
  const request = { payload: { model: 'codex/test', messages: [{ role: 'user', content: 'hello' }], stream: true }, userMessageId: 'user-1' };
  saved.setItem('agentbridge.chat.state.v1', JSON.stringify({ model: 'codex/test', conversationMessages: [], renderedMessages: [{ role: 'assistant', text: 'partial', pendingRequest: request }] }));
  const chat = createChat('codex/test', saved);
  chat.restore([{ slug: 'codex/test' }]);
  assert.equal(chat.messages[0].role, 'error');
  assert.equal(chat.messages[0].statusText, 'Request interrupted');
  assert.deepEqual(chat.messages[0].retryRequest, request);
});
