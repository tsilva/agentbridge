# Dashboard audit checklist

Use this as a coverage map, selecting cases supported by the current product.
Start with ordinary interactions on the active instance; use isolated fixtures
for failures and timing races. Check current source and README rather than
assuming that historical implementation details remain unchanged.

## Chat and composer

- Send a short message, follow up, and verify that the completed assistant reply
  is included in the next conversation payload. Check the requested default
  model in both the selector and outgoing request. Provider IDs require the
  appropriate namespace; for example, `codex/gpt-6.1-sol`.
- Exercise Enter, newline shortcuts, Send, and Retry. Repeated clicks and Enter
  during request preparation or streaming must not create duplicate requests.
- Type a new draft while a reply streams or attachments are being prepared.
  Completion must not erase the next draft. Navigate away/back and reload;
  check model selection, draft text, history, and interrupted-request recovery.
- Generate harmless TXT, PNG, and PDF attachments plus an unsupported file.
  Check preview/removal, errors, and saved downloads. Remove or add attachments
  while preparation is pending; the current request must use a stable snapshot,
  while the next composer retains its own files and text.
- Fail a response after partial output, then retry. Failed assistant text must
  not enter successful history. Compare the retry's exact prepared payload,
  attachments, and user-message identity to the original. Repeat after reload.
- Use the browser runtime's documented file chooser API. In runtimes with
  `waitForEvent('filechooser')`, arm the wait before clicking Attach files and
  set files on the returned chooser; do not assume `setInputFiles` exists.

## Streaming and rendering

Use controlled synthetic SSE responses to cover:

- LF and CRLF framing, separators split across chunks, split Unicode bytes,
  comments, and multiline `data` events.
- Normal text, valid empty completion, OpenAI-shaped HTTP errors, error chunks,
  malformed event JSON, and EOF before `[DONE]`.
- `[DONE]` followed by a connection that remains open. The UI must finish
  promptly and release the reader rather than waiting for transport EOF.
- Slow streaming, navigation, cancellation, and retry. Check terminal UI state,
  recorded error/finish reason, and restored worker capacity.
- Markdown headings, emphasis, inline/fenced code, and links with query
  ampersands or emphasis characters in the path. Literal HTML, `<script>`, and
  replacement-string characters such as `$&` must remain safe literal text;
  unsafe link schemes must not execute.

Capture fixture request bodies and compare them without printing private chat
data. Drive the visible page for assertions about controls and rendering.

## Monitor, request details, and logs

- Filter requests, reach an empty result, clear the filter, select a request,
  navigate Back, and reload. Check selected detail and filter consistency.
- Inspect active, completed, failed, and cancelled requests. Check duration,
  zero-valued usage, error information, and final response against saved logs.
- Stream newline-only chunks, trailing newlines, Unicode, and literal `<tag> &`
  text. The live response must preserve whitespace and escape HTML once.
- Reproduce the gap between rendering initial buffered text and subscribing to
  events. Newly buffered text must replay without duplicate initial content.
  If offsets are used, include Unicode to catch mismatched counting units.
- Complete a request after its live detail renders but before EventSource
  connects. Subsequent list updates must replace stale streaming details with
  the completed saved response.
- Saturate a subscriber queue before completion. Terminal notification must
  still reach the UI; saved response content must remain complete.
- Open an unknown valid request ID. Show clear missing-request feedback rather
  than a blank detail view. Test Copy ID, Open Log, and attachment links against
  the actual selected request.
- Save the clipboard before Copy ID tests, inspect only the expected match, and
  restore it afterward, including an originally empty clipboard.

## Provider lifecycle

Use deterministic fake providers/processes for exhaustive cancellation tests;
keep real provider probes small and synthetic.

- Verify streaming and non-streaming completion shapes, saved logs, and errors
  for the provider paths affected by changes.
- Close a stream before the first provider token and after partial output.
  Provider generators must close, cancellation must be logged, and capacity
  must recover. A completed request must not be relabeled as cancelled.
- With Codex wrappers, check that cancellation reaps the actual child process
  group, not just a launcher PID. Exercise cleanup under AnyIO cancellation;
  the slot must not release while the provider process remains alive.
- Preserve lazy Claude pooling and pure-chat settings, and Codex ephemeral,
  read-only execution. Do not use audit fixtures to weaken provider isolation.

## Branding, layout, and health

- Compare the visible logo and browser favicon with current repository assets,
  packaged `agentbridge/static/brand` files, and served asset bytes. Check
  `image-assets/web-seo` when tracing branding provenance. Reinstalling the same
  version can still leave stale files; rebuilding artwork is not a packaging fix.
- Check readable response text, long content, controls, loading states, and
  ordinary/narrow layouts using supported browser APIs. Inspect console errors
  when symptoms warrant it; deliberate restart/disconnect errors need context.
- Verify `/health` returns to idle after tests, and the original dashboard tab
  remains usable. After installation changes, validate the restarted instance
  rather than only the checkout or a fixture server.
