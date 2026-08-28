import AppKit
import SwiftUI

struct StatusPopover: View {
    @ObservedObject var controller: ServerController

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            header
            statusLine
                .padding(.top, 10)

            activity
                .padding(.top, 30)

            Divider()
                .padding(.vertical, 22)

            backendStatus
            actions
                .padding(.top, 20)

            Divider()
                .padding(.top, 22)

            footer
                .padding(.top, 16)
        }
        .padding(.horizontal, 24)
        .padding(.top, 20)
        .padding(.bottom, 18)
        .frame(width: 400)
        .background(.ultraThinMaterial)
        .task { controller.begin() }
    }

    private var header: some View {
        HStack {
            Text("AgentBridge")
                .font(.system(size: 25, weight: .bold))
            Spacer()
            settingsButton
        }
    }

    private var statusLine: some View {
        HStack(spacing: 10) {
            Circle()
                .fill(controller.phase.color)
                .frame(width: 12, height: 12)
            Text(statusSummary)
                .font(.system(size: 16, weight: .medium))
                .foregroundStyle(.secondary)
                .lineLimit(1)
        }
    }

    private var statusSummary: String {
        let version = controller.versionLabel
        return version.isEmpty
            ? controller.phase.label
            : "\(controller.phase.label) · \(version)"
    }

    private var activity: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                Text("Server activity")
                    .font(.system(size: 19, weight: .bold))
                Spacer()
                Text(activityLabel)
                    .font(.system(size: 18, weight: .bold))
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
            .font(.system(size: 14, weight: .medium))
            .foregroundStyle(.secondary)

            if let detail = controller.detail {
                Text(detail)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(controller.phase == .conflict ? .red : .secondary)
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

    @ViewBuilder
    private var backendStatus: some View {
        if controller.phase == .runningManaged || controller.phase == .runningExternal {
            VStack(spacing: 12) {
                HStack {
                    Label("Claude Code", systemImage: "bubble.left.and.text.bubble.right")
                        .font(.system(size: 14, weight: .semibold))
                    Spacer()
                    Text(controller.claudeAvailable ? "Available" : "Not found")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundStyle(controller.claudeAvailable ? .green : .orange)
                }
                HStack {
                    Label("Codex", systemImage: "terminal")
                        .font(.system(size: 14, weight: .semibold))
                    Spacer()
                    Text(codexLabel)
                        .font(.system(size: 14, weight: .medium))
                        .foregroundStyle(codexColor)
                }
            }
        }
    }

    private var codexLabel: String {
        guard let codex = controller.codex else { return "Checking" }
        if !codex.available { return "Not found" }
        if !codex.authenticated { return "Sign-in required" }
        return codex.cliVersion.map { "Connected · \($0)" } ?? "Connected"
    }

    private var codexColor: Color {
        guard let codex = controller.codex else { return .secondary }
        return codex.available && codex.authenticated ? .green : .orange
    }

    private var actions: some View {
        HStack(spacing: 10) {
            Button("Open Dashboard") {
                controller.openDashboard()
            }
            .buttonStyle(.borderedProminent)
            .disabled(controller.phase != .runningManaged && controller.phase != .runningExternal)

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
            } else if controller.phase == .runningExternal {
                Text("Managed externally")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var footer: some View {
        HStack(spacing: 12) {
            Button {
                Task { await controller.refresh() }
            } label: {
                Image(systemName: "arrow.clockwise")
                    .font(.system(size: 17, weight: .medium))
            }
            .buttonStyle(.plain)
            .help("Refresh")

            Text(updatedLabel)
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(.secondary)

            Spacer()

            Menu {
                Button("View Logs", action: controller.openLogs)
                Button("Open Config Folder", action: controller.openConfig)
                Divider()
                Button("Quit AgentBridge") {
                    Task { await controller.quit() }
                }
            } label: {
                Image(systemName: "ellipsis.circle")
                    .font(.system(size: 17, weight: .medium))
            }
            .menuStyle(.borderlessButton)
            .fixedSize()
        }
    }

    private var updatedLabel: String {
        guard let updated = controller.lastUpdated else { return "Checking status" }
        let elapsed = Date().timeIntervalSince(updated)
        return elapsed < 5 ? "Updated now" : "Updated \(Int(elapsed))s ago"
    }

    @ViewBuilder
    private var settingsButton: some View {
        if #available(macOS 14.0, *) {
            ModernSettingsButton()
        } else {
            Button {
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
            } label: {
                settingsIcon
            }
            .buttonStyle(.plain)
            .help("Settings")
        }
    }

    private var settingsIcon: some View {
        Image(systemName: "gearshape")
            .font(.system(size: 20, weight: .semibold))
            .frame(width: 30, height: 30)
    }
}

@available(macOS 14.0, *)
private struct ModernSettingsButton: View {
    @Environment(\.openSettings) private var openSettings

    var body: some View {
        Button(action: openSettings.callAsFunction) {
            Image(systemName: "gearshape")
                .font(.system(size: 20, weight: .semibold))
                .frame(width: 30, height: 30)
        }
        .buttonStyle(.plain)
        .help("Settings")
    }
}

private struct ActivityProgressBar: View {
    let value: Double
    let total: Double

    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                Capsule()
                    .fill(.secondary.opacity(0.22))
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
        .frame(height: 11)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Server activity")
        .accessibilityValue("\(Int(value)) of \(Int(total)) workers active")
    }
}
