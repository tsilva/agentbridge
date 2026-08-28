import AppKit

@MainActor
final class MenuBarStatusPresenter {
    let badgeView = MenuBarActivityBadgeView()

    func install(on button: NSStatusBarButton) {
        guard badgeView.superview !== button else { return }

        badgeView.translatesAutoresizingMaskIntoConstraints = false
        button.addSubview(badgeView)
        NSLayoutConstraint.activate([
            badgeView.trailingAnchor.constraint(equalTo: button.trailingAnchor),
            badgeView.bottomAnchor.constraint(equalTo: button.bottomAnchor, constant: 2),
            badgeView.heightAnchor.constraint(equalToConstant: 11),
        ])
    }

    func update(
        button: NSStatusBarButton,
        phase: ServerPhase,
        activeWorkers: Int
    ) {
        let count = max(activeWorkers, 0)
        let label = Self.accessibilityLabel(for: phase, activeWorkers: count)
        let baseImage = NSImage(
            systemSymbolName: phase.menuBarSymbol,
            accessibilityDescription: label
        )
        let appearance = button.effectiveAppearance.bestMatch(from: [.darkAqua, .aqua])
        let symbolDetailColor = appearance == .darkAqua
            ? NSColor.black.withAlphaComponent(0.68)
            : NSColor.white.withAlphaComponent(0.88)
        let paletteColors: [NSColor]
        switch phase {
        case .runningManaged, .runningExternal, .conflict, .failed:
            paletteColors = [symbolDetailColor, .labelColor]
        case .starting, .stopping, .stopped:
            paletteColors = [.labelColor]
        }
        let colorConfiguration = NSImage.SymbolConfiguration(
            paletteColors: paletteColors
        )
        let image = baseImage?.withSymbolConfiguration(colorConfiguration) ?? baseImage
        image?.isTemplate = false
        button.image = image
        button.toolTip = label
        button.setAccessibilityLabel(label)
        badgeView.update(count: count)
    }

    static func accessibilityLabel(for phase: ServerPhase, activeWorkers: Int) -> String {
        guard activeWorkers > 0 else { return "AgentBridge: \(phase.label)" }
        let noun = activeWorkers == 1 ? "worker" : "workers"
        return "AgentBridge: \(phase.label), \(activeWorkers) active \(noun)"
    }
}

@MainActor
final class MenuBarActivityBadgeView: NSView {
    private let countLabel = NSTextField(labelWithString: "")

    private(set) var displayedCount: Int?

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        configureView()
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
        configureView()
    }

    override var intrinsicContentSize: NSSize {
        let labelWidth = ceil(countLabel.intrinsicContentSize.width)
        return NSSize(width: max(11, labelWidth + 1.5), height: 11)
    }

    override func hitTest(_ point: NSPoint) -> NSView? {
        nil
    }

    override func viewDidChangeEffectiveAppearance() {
        super.viewDidChangeEffectiveAppearance()
        updateColors()
    }

    func update(count: Int) {
        guard count > 0 else {
            displayedCount = nil
            countLabel.stringValue = ""
            isHidden = true
            invalidateIntrinsicContentSize()
            return
        }

        displayedCount = count
        countLabel.stringValue = String(count)
        isHidden = false
        invalidateIntrinsicContentSize()
    }

    private func configureView() {
        wantsLayer = true
        layer?.cornerRadius = 5.5
        layer?.cornerCurve = .continuous

        countLabel.translatesAutoresizingMaskIntoConstraints = false
        countLabel.font = .systemFont(ofSize: 7.5, weight: .semibold)
        countLabel.alignment = .center
        countLabel.lineBreakMode = .byClipping
        countLabel.maximumNumberOfLines = 1
        addSubview(countLabel)

        NSLayoutConstraint.activate([
            countLabel.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 0.75),
            countLabel.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -0.75),
            countLabel.centerYAnchor.constraint(equalTo: centerYAnchor),
        ])

        setAccessibilityElement(false)
        isHidden = true
        updateColors()
    }

    private func updateColors() {
        let match = effectiveAppearance.bestMatch(from: [.darkAqua, .aqua])
        let usesDarkMenuBar = match == .darkAqua
        layer?.backgroundColor = NSColor.labelColor.withAlphaComponent(0.48).cgColor
        countLabel.textColor = usesDarkMenuBar
            ? NSColor.black.withAlphaComponent(0.78)
            : NSColor.white.withAlphaComponent(0.94)
    }
}
