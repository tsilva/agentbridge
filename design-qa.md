# AgentBridge macOS status window design QA

- Source visual truth: `/var/folders/wz/x29jb7_x5rdc_5dcjr4qnhg00000gn/T/codex-clipboard-6065429c-e8b8-40f4-a1be-c95c4734eb1c.png`
- Implementation screenshot: `/Users/tsilva/repos/tsilva/agentbridge/design-qa-implementation.png`
- Source dimensions: 722 × 478 pixels; density metadata unavailable
- Implementation viewport and capture: 400 × 430 native logical pixels, running state
- Density normalization: none. Both originals were opened in the same comparison input. Because the source was explicitly supplied as a style reference rather than a content/layout specification, spacing and control proportions were compared relative to each window width rather than forcing equal height or copy.
- State: server running, zero active requests, three configured workers, Claude Code available, Codex connected

## Full-view comparison evidence

The implementation preserves the reference's compact macOS status-window language: dark translucent material, continuous rounded frame, bold title, top-right SF Symbol settings control, semantic status dot and secondary status copy, strong section heading/value pairing, thick rounded activity track, aligned metadata, fine dividers, and a refresh footer. The implementation replaces quota-specific content with live AgentBridge server and backend status, as requested.

The source uses San Francisco system typography and native macOS iconography. The implementation uses the same system font stack, semantic weights, and SF Symbols. Its 24-point horizontal padding is proportional to the reference's approximately 48 pixels at the supplied larger capture width. The 11-point activity track matches the reference after width normalization.

The implementation screenshot is hosted in a debug NSWindow so Computer Use can capture and exercise it. Production uses the exact same `StatusPopover` view inside `MenuBarExtra(.window)`; the debug-only traffic-light controls are not present in the menu-bar popover.

## Focused-region comparison

A separate crop was not required. Both windows are compact, and the full-view evidence keeps typography, status indicators, activity track, dividers, buttons, icons, and footer legible at original resolution.

## Required fidelity surfaces

- Fonts and typography: passed. System font, bold title/section hierarchy, medium secondary text, line lengths, and optical weights match the reference language.
- Spacing and layout rhythm: passed. Header, status line, primary section, divider cadence, action area, and footer maintain the same compact vertical rhythm. Content height intentionally differs because AgentBridge has backend and lifecycle controls rather than quota copy.
- Colors and visual tokens: passed. Semantic green, amber, red, gray, blue activity, secondary foregrounds, and material background respond to system appearance. Exact material tint varies with the desktop behind the popover, as it does in the source.
- Image quality and assets: passed. No custom raster imagery is required in the status window. Standard controls use SF Symbols; the packaged application icon reuses the repository's source artwork.
- Copy and content: passed. All visible copy is AgentBridge-specific, concise, state-aware, and does not leak instructions or placeholder content.

## Comparison history

### Iteration 1

- Earlier finding [P2]: the default SwiftUI linear progress indicator was visibly thinner than the reference.
- Fix: replaced it with an accessible 11-point continuous activity track using native SwiftUI shapes and semantic blue fill.
- Earlier finding [P1]: the gear control rendered correctly but did not open the SwiftUI Settings scene.
- Fix: added a macOS 14+ `openSettings` adapter while retaining the macOS 13 selector fallback.
- Post-fix evidence: `design-qa-implementation.png`; Computer Use also confirmed the Settings window opens and exposes port, worker, start-on-launch, and launch-at-login controls.

### Final pass

No actionable P0, P1, or P2 visual or interaction findings remain. Start, healthy, stop, stopped, restart, external-instance, and Settings states were exercised in the native app.

## Follow-up polish

- [P3] Material tint and outer corner appearance will vary slightly by macOS version, wallpaper, and light/dark appearance because production deliberately uses the native menu-bar window material.

## Implementation checklist

- [x] Native status hierarchy and material
- [x] Live semantic server states
- [x] Accessible activity indicator
- [x] Functional Settings, Start, Stop, Restart, Refresh, Dashboard, and overflow actions
- [x] External-process ownership safeguard
- [x] Production view shared with the captured debug host

final result: passed
