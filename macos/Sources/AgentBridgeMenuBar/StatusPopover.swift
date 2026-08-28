import AppKit
import SwiftUI

struct StatusPopover: View {
    @ObservedObject var controller: ServerController

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            header
            statusLine
                .padding(.top, 2)

            activity
                .padding(.top, 18)

            if hasServerAction {
                Divider()
                    .padding(.top, 16)

                actions
                    .padding(.top, 12)
            }

            Divider()
                .padding(.top, hasServerAction ? 14 : 16)

            footer
                .padding(.top, 10)
        }
        .padding(.horizontal, 20)
        .padding(.top, 18)
        .padding(.bottom, 16)
        .frame(width: 350)
        .fixedSize(horizontal: false, vertical: true)
    }

    private var header: some View {
        HStack {
            Text("AgentBridge")
                .font(.system(size: 17, weight: .bold))
            Spacer()
            settingsButton
        }
    }

    private var statusLine: some View {
        HStack(spacing: 7) {
            Circle()
                .fill(controller.phase.color)
                .frame(width: 7, height: 7)
            Text(statusSummary)
                .font(.system(size: 11, weight: .regular))
                .foregroundStyle(secondaryTextColor)
                .lineLimit(1)
        }
    }

    private var statusSummary: String {
        if controller.phase == .runningManaged || controller.phase == .runningExternal {
            return "Connected"
        }

        let version = controller.versionLabel
        return version.isEmpty
            ? controller.phase.label
            : "\(controller.phase.label) · \(version)"
    }

    private var activity: some View {
        VStack(alignment: .leading, spacing: 9) {
            HStack(alignment: .firstTextBaseline) {
                Text("Server activity")
                    .font(.system(size: 14, weight: .semibold))
                Spacer()
                Text(activityLabel)
                    .font(.system(size: 14, weight: .semibold))
            }

            ActivityProgressBar(
                value: Double(min(controller.activeRequests, controller.workerCount)),
                total: Double(max(controller.workerCount, 1))
            )

            HStack {
                Text("127.0.0.1:\(controller.baseURL.port ?? 8082)")
                Spacer()
                Text("\(controller.workerCount) worker\(controller.workerCount == 1 ? "" : "s")")
            }
            .font(.system(size: 11, weight: .regular))
            .foregroundStyle(secondaryTextColor)

            if let detail = controller.detail {
                Text(detail)
                    .font(.system(size: 11, weight: .regular))
                    .foregroundStyle(
                        controller.phase == .conflict ? .red : secondaryTextColor
                    )
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    private var activityLabel: String {
        switch controller.phase {
        case .runningManaged, .runningExternal:
            "\(controller.activeRequests) active"
        default:
            controller.phase.label
        }
    }

    private var actions: some View {
        HStack(spacing: 10) {
            Spacer()

            if controller.canStop {
                Button("Stop") {
                    Task { await controller.stop() }
                }
                .buttonStyle(.bordered)
            } else if controller.canStart {
                Button("Start AgentBridge") {
                    Task { await controller.start() }
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .font(.system(size: 11, weight: .regular))
        .controlSize(.small)
    }

    private var hasServerAction: Bool {
        controller.canStop || controller.canStart
    }

    private var footer: some View {
        HStack(spacing: 12) {
            Button {
                Task { await controller.refresh() }
            } label: {
                HStack(spacing: 9) {
                    Image(systemName: "arrow.clockwise")
                        .font(.system(size: 15, weight: .regular))
                        .frame(width: 16)

                    Text(updatedLabel)
                        .font(.system(size: 13, weight: .medium))
                }
                .foregroundStyle(secondaryTextColor)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .help("Refresh")
            .accessibilityLabel("Refresh status, \(updatedLabel)")

            Spacer()

            Button("Open Dashboard") {
                controller.openDashboard()
            }
            .buttonStyle(.bordered)
            .font(.system(size: 11, weight: .regular))
            .controlSize(.small)
            .disabled(controller.phase != .runningManaged && controller.phase != .runningExternal)
        }
    }

    private var updatedLabel: String {
        guard let updated = controller.lastUpdated else { return "Checking status" }
        let elapsed = Date().timeIntervalSince(updated)
        return elapsed < 5 ? "Updated now" : "Updated \(Int(elapsed))s ago"
    }

    private var secondaryTextColor: Color {
        Color(nsColor: .secondaryLabelColor)
    }

    private var settingsButton: some View {
        Menu {
            Button {
                Task { await controller.refresh() }
            } label: {
                Label("Refresh", systemImage: "arrow.clockwise")
            }

            Divider()

            if #available(macOS 14.0, *) {
                SettingsLink {
                    Label("Settings…", systemImage: "gearshape")
                }
            } else {
                Button(action: openLegacySettings) {
                    Label("Settings…", systemImage: "gearshape")
                }
            }

            Divider()

            Button(action: showAboutPanel) {
                Label("About AgentBridge", systemImage: "info.circle")
            }

            Button(action: controller.openLogs) {
                Label("View Logs", systemImage: "doc.text")
            }

            Button(action: controller.openConfig) {
                Label("Open Config Folder", systemImage: "folder")
            }

            Divider()

            Button {
                Task { await controller.quit() }
            } label: {
                Label("Quit AgentBridge", systemImage: "power")
            }
            .keyboardShortcut("q", modifiers: .command)
        } label: {
            settingsIcon
        }
        .menuStyle(.borderlessButton)
        .menuIndicator(.hidden)
        .fixedSize()
        .help("AgentBridge menu")
    }

    private var settingsIcon: some View {
        Image(systemName: "gearshape")
            .font(.system(size: 15, weight: .semibold))
            .frame(width: 24, height: 24)
    }

    private func openLegacySettings() {
        let opened = NSApp.sendAction(
            Selector(("showSettingsWindow:")),
            to: nil,
            from: nil
        )
        if !opened {
            NSApp.sendAction(
                Selector(("showPreferencesWindow:")),
                to: nil,
                from: nil
            )
        }
    }

    private func showAboutPanel() {
        NSApp.activate(ignoringOtherApps: true)
        NSApp.orderFrontStandardAboutPanel(nil)
    }
}

private struct ActivityProgressBar: View {
    let value: Double
    let total: Double

    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                Capsule()
                    .fill(.secondary.opacity(0.18))
                if value > 0 {
                    Capsule()
                        .fill(.blue)
                        .frame(
                            width: max(
                                10,
                                geometry.size.width * min(max(value / total, 0), 1)
                            )
                        )
                }
            }
        }
        .frame(height: 8)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Server activity")
        .accessibilityValue("\(Int(value)) of \(Int(total)) workers active")
    }
}
