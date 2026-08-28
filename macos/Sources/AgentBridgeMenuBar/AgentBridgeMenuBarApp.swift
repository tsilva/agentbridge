import SwiftUI

@main
struct AgentBridgeMenuBarApp: App {
    @StateObject private var controller: ServerController

    init() {
        UserDefaults.standard.register(defaults: [
            PreferenceKey.port: 8082,
            PreferenceKey.workers: 1,
            PreferenceKey.startOnLaunch: true,
        ])
        let controller = ServerController()
        _controller = StateObject(wrappedValue: controller)
        Task { @MainActor in
            controller.begin()
#if DEBUG
            if ProcessInfo.processInfo.environment["AGENTBRIDGE_SHOW_STATUS_WINDOW"] == "1" {
                DebugStatusWindow.shared.show(controller: controller)
            }
#endif
        }
    }

    var body: some Scene {
        MenuBarExtra {
            StatusPopover(controller: controller)
        } label: {
            Image(systemName: controller.phase.menuBarSymbol)
                .accessibilityLabel("AgentBridge: \(controller.phase.label)")
        }
        .menuBarExtraStyle(.window)

        Settings {
            SettingsView()
        }
    }
}

#if DEBUG
import AppKit

@MainActor
private final class DebugStatusWindow {
    static let shared = DebugStatusWindow()
    private var window: NSWindow?

    func show(controller: ServerController) {
        guard window == nil else { return }
        let hostingController = NSHostingController(
            rootView: StatusPopover(controller: controller)
        )
        let window = NSWindow(contentViewController: hostingController)
        window.title = "AgentBridge Status"
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.styleMask = [.titled, .closable, .fullSizeContentView]
        window.isReleasedWhenClosed = false
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        self.window = window
    }
}
#endif
