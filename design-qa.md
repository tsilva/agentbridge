# Active-worker menu-bar badge and inactive brightness design QA

## Evidence

- Source visual truths:
  - Badge proportions: `/var/folders/wz/x29jb7_x5rdc_5dcjr4qnhg00000gn/T/codex-clipboard-a88e73a8-8b49-415b-b2ef-9f289e13c5ea.png`
  - Unfocused menu-bar brightness: `/var/folders/wz/x29jb7_x5rdc_5dcjr4qnhg00000gn/T/codex-clipboard-6c362e7b-d087-493b-8d8f-683607e7a420.png`
  - Inner-arrow contrast: `/var/folders/wz/x29jb7_x5rdc_5dcjr4qnhg00000gn/T/codex-clipboard-7fb76339-7c5e-4568-98cf-3c91d8ad0f48.png`
- Source pixels: 208 × 62 for the badge reference, 3232 × 76 for the unfocused menu-bar reference, and 260 × 58 for the inner-arrow reference, all at Retina density. Focused item crops retain their original 2× scale.
- Implementation screenshots:
  - Active state: `/Users/tsilva/repos/tsilva/agentbridge/design-qa/status-item-active-workers.png`
  - Zero state: `/Users/tsilva/repos/tsilva/agentbridge/design-qa/status-item-no-workers.png`
- Implementation pixels: 96 × 62 for a 48 × 31-point native AppKit fixture at 2× density.
- Viewport: native macOS status-item button, 32 × 22 points inside a 48 × 31-point menu-bar crop.
- Density normalization: the 64 × 62 source crop was centered on a 96 × 62 canvas without scaling so both sides retain 2× density.
- State: dark, unfocused-style menu bar with 48 active workers for visual fidelity; running server with zero active workers for empty-state verification.
- Combined comparisons:
  - Badge proportions: `/Users/tsilva/repos/tsilva/agentbridge/design-qa/status-item-badge-comparison.png`
  - Unfocused brightness: `/Users/tsilva/repos/tsilva/agentbridge/design-qa/status-item-inactive-comparison.png`
  - Inner-arrow contrast before/after: `/Users/tsilva/repos/tsilva/agentbridge/design-qa/status-item-arrow-contrast-comparison.png`

## Findings

- No actionable P0/P1/P2 differences remain.
- Fonts and typography: the badge uses a 7.5-point semibold native system font; the two-digit weight and density match the compact Telegram reference without crowding.
- Spacing and layout rhythm: the 11-point capsule sits at the lower trailing edge of the existing icon, with the source-like overlap and enough of AgentBridge's mark remaining visible.
- Colors and visual tokens: the badge uses the current semantic label color at 48% opacity and automatically reverses its number color for light and dark appearances. The main mark uses an appearance-aware label-color palette without template dimming, keeping it bright on an unfocused display like Telegram. Filled status symbols now use a contrasting secondary palette layer: translucent black arrows in dark appearance and translucent white detail in light appearance.
- Image quality and asset fidelity: the existing SF Symbol remains native but is rendered as a non-template, appearance-aware image so AppKit does not mute it with inactive template tinting. The badge is rendered natively at Retina density with no raster replacement or custom icon asset.
- Copy and content: the visible badge is the exact live active-worker number. The button tooltip and accessibility label include the same count with correct singular/plural wording.
- Empty state: the zero-state rendering shows only the AgentBridge icon; no empty capsule or numeric badge remains.

The full menu-bar reference establishes the inactive-display context and Telegram's brighter mark. The component capture is the complete implementation viewport for this isolated status item. Focused comparisons confirm capsule size, opacity, number weight, overlap, the brighter main-icon treatment, and clear separation between the outer circle and inner arrows.

## Comparison History

1. The first active-state rendering used a 14-point badge with wider padding. It obscured most of the circular AgentBridge symbol and was visibly larger and lighter than the Telegram badge.
2. The badge was reduced to 11 points, its type and horizontal padding were tightened, and label opacity was lowered from 68% to 48%. The revised combined comparison shows matching compact proportions and tone, while the zero-state capture confirms complete badge removal.
3. The inactive-display reference showed AppKit's template tint making AgentBridge materially dimmer than Telegram. The symbol now uses an appearance-aware palette and is explicitly non-template; the revised dark-appearance capture shows the bright main mark while retaining the subdued badge.
4. The first bright non-template render gave the circle and arrows nearly identical light values, making the arrows hard to perceive. Filled symbols now use a two-color palette with 68%-opaque black inner detail in dark appearance; the before/after comparison shows clear arrow contrast. Outline-only stopped and transitional symbols retain a single semantic label color so they remain visible.

## Implementation Checklist

- [x] Observe live health-count changes in addition to server-phase changes.
- [x] Show the exact active-worker count in a compact native badge.
- [x] Hide the badge at zero.
- [x] Keep the main icon bright instead of accepting inactive template dimming.
- [x] Preserve appearance-aware light/dark coloring.
- [x] Give filled symbols contrasting inner detail without darkening outline-only states.
- [x] Preserve status-item click behavior.
- [x] Include the count in tooltip and accessibility text.
- [x] Verify active and zero states with Retina component captures.
- [x] Pass Swift unit tests and a release build.

## Follow-up Polish

- None.

final result: passed
