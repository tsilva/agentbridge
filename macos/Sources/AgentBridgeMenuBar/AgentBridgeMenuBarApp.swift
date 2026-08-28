import AppKit
import Combine
import SwiftUI

@main
struct AgentBridgeMenuBarApp: App {
    @NSApplicationDelegateAdaptor(AgentBridgeAppDelegate.self) private var appDelegate

    init() {
        UserDefaults.standard.register(defaults: [
            PreferenceKey.port: 8082,
            PreferenceKey.workers: 1,
            PreferenceKey.startOnLaunch: true,
        ])
    }

    var body: some Scene {
        Settings {
            SettingsView()
        }
        .windowResizability(.contentSize)
    }
}

@MainActor
final class AgentBridgeAppDelegate: NSObject, NSApplicationDelegate {
    private let controller = ServerController()
    private let popover = NSPopover()
    private let statusPresenter = MenuBarStatusPresenter()
    private var statusItem: NSStatusItem?
    private var statusObservation: AnyCancellable?
    #if DEBUG
    private var debugAnchorWindow: NSWindow?
    #endif

    func applicationDidFinishLaunching(_ notification: Notification) {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        statusItem = item

        if let button = item.button {
            button.target = self
            button.action = #selector(togglePopover(_:))
            statusPresenter.install(on: button)
            statusPresenter.update(
                button: button,
                phase: controller.phase,
                activeWorkers: controller.activeRequests
            )
        }

        let host = NSHostingController(rootView: StatusPopover(controller: controller))
        popover.contentViewController = host
        popover.behavior = .transient
        popover.animates = true

        statusObservation = Publishers.CombineLatest(controller.$phase, controller.$health)
            .receive(on: RunLoop.main)
            .sink { [weak self] phase, health in
                self?.updateStatusItem(
                    for: phase,
                    activeWorkers: health?.activeRequests ?? 0
                )
            }

        controller.begin()

        #if DEBUG
        if ProcessInfo.processInfo.environment["AGENTBRIDGE_SHOW_POPOVER_ON_LAUNCH"] == "1" {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) { [weak self] in
                self?.showDebugPreview()
            }
        }
        #endif
    }

    @objc private func togglePopover(_ sender: Any?) {
        if popover.isShown {
            popover.performClose(sender)
        } else {
            showPopover()
        }
    }

    private func showPopover() {
        guard let button = statusItem?.button else { return }
        popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
        if let window = popover.contentViewController?.view.window {
            window.setAccessibilityElement(true)
            window.setAccessibilityRole(.window)
            window.setAccessibilitySubrole(.floatingWindow)
            window.setAccessibilityTitle("AgentBridge status")
            window.makeKey()
        }
    }

    private func updateStatusItem(for phase: ServerPhase, activeWorkers: Int) {
        guard let button = statusItem?.button else { return }
        statusPresenter.update(
            button: button,
            phase: phase,
            activeWorkers: activeWorkers
        )
    }

    #if DEBUG
    private func showDebugPreview() {
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 54, height: 42),
            styleMask: [.titled],
            backing: .buffered,
            defer: false
        )
        window.title = "AgentBridge preview anchor"
        window.titleVisibility = .hidden
        window.isReleasedWhenClosed = false

        let button = NSButton(frame: NSRect(x: 11, y: 7, width: 32, height: 28))
        button.bezelStyle = .texturedRounded
        button.image = NSImage(
            systemSymbolName: controller.phase.menuBarSymbol,
            accessibilityDescription: "AgentBridge preview"
        )
        window.contentView = NSView(frame: window.contentLayoutRect)
        window.contentView?.addSubview(button)
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        debugAnchorWindow = window

        popover.behavior = .applicationDefined
        popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
        if let popoverWindow = popover.contentViewController?.view.window {
            popoverWindow.setAccessibilityElement(true)
            popoverWindow.setAccessibilityRole(.window)
            popoverWindow.setAccessibilitySubrole(.standardWindow)
            popoverWindow.setAccessibilityTitle("AgentBridge status")
            popoverWindow.makeKey()
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            window.orderOut(nil)
        }
        if let screenshotPath = ProcessInfo.processInfo.environment[
            "AGENTBRIDGE_POPOVER_SCREENSHOT_PATH"
        ] {
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) { [weak self] in
                self?.savePopoverScreenshot(to: screenshotPath)
            }
        }
    }

    private func savePopoverScreenshot(to path: String) {
        guard let window = popover.contentViewController?.view.window else { return }
        let representation: NSBitmapImageRep
        if let image = CGWindowListCreateImage(
            .null,
            .optionIncludingWindow,
            CGWindowID(window.windowNumber),
            .bestResolution
        ) {
            representation = NSBitmapImageRep(cgImage: image)
        } else {
            guard let contentView = window.contentView else { return }
            let renderedView = contentView.superview ?? contentView
            guard let cached = renderedView.bitmapImageRepForCachingDisplay(
                in: renderedView.bounds
            ) else { return }
            renderedView.cacheDisplay(in: renderedView.bounds, to: cached)
            representation = cached
        }
        guard let data = representation.representation(using: .png, properties: [:]) else {
            return
        }
        try? data.write(to: URL(fileURLWithPath: path), options: .atomic)
    }

    #endif
}
