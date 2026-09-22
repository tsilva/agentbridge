import AppKit

@MainActor
final class MenuBarStatusPresenter {
    private weak var presentedButton: NSStatusBarButton?
    private var displayedPhase: ServerPhase?
    private(set) var displayedCount: Int?

    func update(
        button: NSStatusBarButton,
        phase: ServerPhase,
        activeWorkers: Int
    ) {
        let count = max(activeWorkers, 0)
        let badgeCount = count > 0 ? count : nil
        guard presentedButton !== button || displayedPhase != phase || displayedCount != badgeCount
        else { return }

        let label = Self.accessibilityLabel(for: phase, activeWorkers: count)
        let symbol = NSImage(
            systemSymbolName: phase.menuBarSymbol,
            accessibilityDescription: label
        )
        let image = badgeCount.map { Self.badgedImage(symbol: symbol, count: $0) } ?? symbol
        image?.isTemplate = true
        button.image = image
        button.toolTip = label
        button.setAccessibilityLabel(label)
        presentedButton = button
        displayedPhase = phase
        displayedCount = badgeCount
    }

    static func accessibilityLabel(for phase: ServerPhase, activeWorkers: Int) -> String {
        guard activeWorkers > 0 else { return "AgentBridge: \(phase.label)" }
        let noun = activeWorkers == 1 ? "worker" : "workers"
        return "AgentBridge: \(phase.label), \(activeWorkers) active \(noun)"
    }
    private static func badgedImage(symbol: NSImage?, count: Int) -> NSImage {
        let text = NSAttributedString(
            string: String(count),
            attributes: [
                .font: NSFont.systemFont(ofSize: 7.5, weight: .semibold),
                .foregroundColor: NSColor.black,
            ]
        )
        let textSize = text.size()
        let badgeWidth = max(11, ceil(textSize.width) + 1.5)
        let size = NSSize(width: max(22, badgeWidth), height: 22)

        // AppKit snapshots status items under different appearances. A layer-backed
        // badge/text-field subview mutates during those callbacks and can schedule
        // another snapshot indefinitely, even while hidden. Keep the entire icon
        // in one template image so snapshots never update a custom view hierarchy.
        return NSImage(size: size, flipped: false) { rect in
            symbol?.draw(in: NSRect(x: (rect.width - 18) / 2, y: 3, width: 18, height: 18))
            let badge = NSBezierPath(roundedRect: NSRect(
                x: rect.width - badgeWidth, y: 0, width: badgeWidth, height: 11
            ), xRadius: 5.5, yRadius: 5.5)
            guard let context = NSGraphicsContext.current?.cgContext else { return false }
            context.saveGState()
            context.setBlendMode(.clear)
            badge.fill()
            context.setBlendMode(.normal)
            NSColor.black.withAlphaComponent(0.48).setFill()
            badge.fill()
            // Cut the number out of the alpha mask; macOS supplies the contrasting
            // foreground color for both light and dark menu bars.
            context.setBlendMode(.destinationOut)
            text.draw(at: NSPoint(
                x: rect.width - badgeWidth + (badgeWidth - textSize.width) / 2,
                y: (11 - textSize.height) / 2
            ))
            context.restoreGState()
            return true
        }
    }
}
