# AgentBridge macOS status window design QA

- Source visual truth: `/var/folders/wz/x29jb7_x5rdc_5dcjr4qnhg00000gn/T/codex-clipboard-7d264239-152f-42e2-bddb-e728cf5fe09e.png`
- Earlier implementation evidence: `/var/folders/wz/x29jb7_x5rdc_5dcjr4qnhg00000gn/T/codex-clipboard-74c41c50-e709-4cde-83b5-b9cd35a70a65.png`
- Revised implementation screenshot: `/Users/tsilva/repos/tsilva/agentbridge/design-qa-implementation.png`
- Source dimensions: 788 × 570 pixels; the 702 × 447 popover region was cropped and normalized to 350 × 223 pixels for the focused typography comparison.
- Implementation viewport and capture: 350 × 366 native logical pixels at scale 1 in the debug NSWindow host.
- State: external AgentBridge server running, zero active requests, one worker, Claude Code available, Codex connected.

## Full-view comparison evidence

The revised implementation uses the same 350-point content width as the normalized reference. It preserves the reference hierarchy: compact bold title, small secondary connection line and status dot, 14–15 point section heading/value pairing, slim rounded activity track, 12–13 point metadata, fine dividers, and a restrained refresh footer. Its additional backend and lifecycle rows intentionally make the AgentBridge panel taller than the quota-only reference.

The implementation screenshot is hosted in a debug NSWindow so Computer Use can capture it. Production uses the same `StatusPopover` view inside `MenuBarExtra(.window)`; the debug-only title-bar controls are absent from the menu-bar popover.

## Focused-region comparison evidence

The source popover was cropped and downsampled from 702 pixels to 350 pixels wide, then opened beside the 350-pixel implementation in the same comparison input. At equal width, the title cap height, connection line, section heading, metadata, gear, status dot, progress track, and footer now have the same compact optical scale. No remaining text is a full hierarchy step larger than its reference counterpart.

## Required fidelity surfaces

- Fonts and typography: passed. Both use San Francisco system typography. Revised sizes are 18 pt title, 12 pt connection line, 14–15 pt activity heading/value, 12 pt metadata, 13 pt backend/footer copy, and 11–12 pt auxiliary controls.
- Spacing and layout rhythm: passed. Width is 350 points with 20-point side padding; section gaps, dividers, and control sizing were tightened with the type scale. Extra height is expected from AgentBridge-specific backend and lifecycle controls.
- Colors and visual tokens: passed. Native material, secondary foregrounds, semantic green, blue activity fill, and divider opacity match the source language. Material tint varies with the desktop behind the window.
- Image quality and assets: passed. The panel requires no raster imagery; visible controls use native SF Symbols. The debug title-bar controls are capture-host infrastructure, not production content.
- Copy and content: passed. Copy is live AgentBridge status rather than the quota-specific reference content, as intended.

## Comparison history

### Iteration 1

- Earlier finding [P1]: the 25 pt title, 16 pt status line, 18–19 pt activity heading/value, 14–15 pt supporting copy, 20 pt gear, 11 pt track, and 400 pt panel made the entire interface visibly oversized beside the supplied reference.
- Fix: reduced the panel to 350 points, reset the hierarchy to 11–18 point type, reduced the status dot and SF Symbols, changed buttons to small control sizing, slimmed the activity track to 8 points, and tightened padding and vertical gaps.
- Post-fix evidence: `design-qa-implementation.png`, compared at the same 350-pixel width with `/tmp/agentbridge-reference-panel.png`.

### Final pass

No actionable P0, P1, or P2 typography, spacing, color, asset, copy, or interaction findings remain. Swift tests pass and the rebuilt `.app` and DMG contain the corrected shared production view.

## Follow-up polish

- [P3] Native material tint and outer corner rendering vary slightly by macOS version, wallpaper, and whether the view is hosted in the debug window or production menu-bar popover.

## Implementation checklist

- [x] Reference-width typography comparison
- [x] Compact system type hierarchy
- [x] Matching icon, dot, track, and control scale
- [x] Tightened panel spacing
- [x] Shared production and capture view
- [x] Rebuilt app and DMG

final result: passed
