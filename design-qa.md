# AgentBridge external-management row design QA

## Evidence

- Source visual truth: `/var/folders/wz/x29jb7_x5rdc_5dcjr4qnhg00000gn/T/codex-clipboard-a99a20bd-c92f-4734-98a7-d3e03360d25a.png`, with the user-requested target being complete removal of the visible row
- Source pixels: 664 × 127 at Retina density
- Implementation: `/Applications/AgentBridge.app`
- Implementation screenshot: pending user-provided capture
- Viewport: native macOS status popover, 350-point content width, Retina display
- State to capture: external server running so no Start or Stop action is available

## Findings

- [Blocked] The revised app is built, installed, and running, but post-fix visual evidence is pending because the user requested that Computer Use not be used and will provide screenshots directly.
- Functional structure: the “Managed externally” label and its action row are removed. The first and second divider no longer render around an empty row. Start and Stop remain available in states where either action is valid.
- Fonts and typography: the unwanted label is absent by construction; remaining typography awaits the implementation screenshot.
- Spacing and layout rhythm: the external-server state now flows from server activity to one footer divider with no empty action band. Final visible gap verification is pending.
- Colors and visual tokens: no tokens were added or changed.
- Image quality and assets: this change contains no image assets or icons.
- Copy and content: the duplicate external-management message is removed; the status summary remains the single place that communicates the externally running state.

## Open Questions

- Does the user-provided post-fix screenshot show the activity-to-footer spacing as compact and balanced?

## Implementation Checklist

- [x] Remove the “Managed externally” label.
- [x] Remove the entire action row when neither Start nor Stop is available.
- [x] Collapse duplicate dividers and row padding in the external-server state.
- [x] Preserve actionable Start and Stop rows.
- [x] Run Swift tests and patch-format validation.
- [x] Build, sign, verify, install, and launch the updated app.
- [ ] Compare a user-provided post-fix screenshot against the source crop.

## Comparison History

1. Source evidence showed a non-actionable “Managed externally” row occupying a full band between two dividers.
2. The implementation conditionally renders the entire action section only when Start or Stop is available. Automated tests and bundle verification pass; visual comparison awaits the user capture.

## Follow-up Polish

- None classified until the post-fix screenshot is available.

final result: blocked
