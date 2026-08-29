# Design QA

**Comparison target**

- Source visual truth: `/var/folders/wz/x29jb7_x5rdc_5dcjr4qnhg00000gn/T/codex-clipboard-5d0ece7b-8e7b-489f-8d94-28b6877699ba.png`
- Implementation screenshot: `/tmp/agentbridge-popover-neutral-20260829.png`
- Combined comparison: `/tmp/agentbridge-popover-comparison-20260829.png`
- State: connected, zero active requests, one worker, dark appearance.
- Viewport: native macOS status popover at its fixed 350-point content width.
- Source pixels: 818 × 404. Implementation pixels: 752 × 444. Both are native high-density captures; no density normalization was applied because this change is limited to the visible control colors rather than geometry.

**Full-view comparison evidence**

- The source shows the gear and Open Dashboard control inheriting the green brand tint.
- The implementation shows both controls in the same neutral secondary-label palette used by the refresh row and supporting text.
- The native screenshot API renders the vibrancy material with a pink capture artifact; this does not affect the visible verification that the two controls no longer use the green tint.

**Focused region comparison evidence**

- A separate crop was not needed: the settings icon and dashboard button are large and clearly readable in the combined full-view comparison.

**Required fidelity surfaces**

- Fonts and typography: unchanged.
- Spacing and layout rhythm: unchanged.
- Colors and visual tokens: the popover-wide control tint now uses the native secondary-label color. The logo, connected indicator, and activity fill retain their intentional brand/status colors.
- Image quality and asset fidelity: unchanged; the existing native brand mark and SF Symbols remain in use.
- Copy and content: unchanged.

**Findings**

- No actionable P0, P1, or P2 mismatches remain for the requested control-color change.

**Open Questions**

- None.

**Implementation Checklist**

- [x] Remove the green tint from popover controls.
- [x] Preserve brand and semantic status colors.
- [x] Build and run the native test suite.
- [x] Capture and compare the rendered popover.

**Comparison History**

- Initial source finding: the settings icon and dashboard button inherited the green popover-wide tint.
- Fix: changed the popover tint to the native secondary-label color.
- Post-fix evidence: the combined comparison shows both controls rendered in neutral gray, with the brand and status colors preserved.

**Follow-up Polish**

- None.

final result: passed
