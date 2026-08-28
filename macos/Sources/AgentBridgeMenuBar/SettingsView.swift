import ServiceManagement
import SwiftUI

struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss

    @State private var portText: String
    @State private var workers: Int
    @State private var startOnLaunch: Bool
    @State private var launchAtLogin: Bool
    @State private var errorMessage: String?
    @State private var savedPort: Int
    @State private var savedWorkers: Int
    @State private var savedStartOnLaunch: Bool
    @State private var savedLaunchAtLogin: Bool

    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        let storedPort = defaults.integer(forKey: PreferenceKey.port)
        let port = (1...65_535).contains(storedPort) ? storedPort : 8082
        let storedWorkers = defaults.integer(forKey: PreferenceKey.workers)
        let workers = (1...32).contains(storedWorkers) ? storedWorkers : 1
        let startOnLaunch = defaults.bool(forKey: PreferenceKey.startOnLaunch)
        let launchAtLogin = SMAppService.mainApp.status == .enabled

        self.defaults = defaults
        _portText = State(initialValue: String(port))
        _workers = State(initialValue: workers)
        _startOnLaunch = State(initialValue: startOnLaunch)
        _launchAtLogin = State(initialValue: launchAtLogin)
        _savedPort = State(initialValue: port)
        _savedWorkers = State(initialValue: workers)
        _savedStartOnLaunch = State(initialValue: startOnLaunch)
        _savedLaunchAtLogin = State(initialValue: launchAtLogin)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            brandHeader

            Divider()

            serverSection

            Divider()

            macOSSection

            Divider()

            footer
        }
        .padding(24)
        .frame(width: 440)
        .fixedSize(horizontal: false, vertical: true)
        .tint(AgentBridgeBrand.fir)
        .onAppear(perform: reload)
    }

    private var brandHeader: some View {
        HStack(spacing: 12) {
            AgentBridgeBrandMark(size: 34)
            VStack(alignment: .leading, spacing: 1) {
                Text("AgentBridge")
                    .font(.title3.weight(.semibold))
                Text("Settings")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }

    private var serverSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Server")
                .font(.headline)

            VStack(spacing: 12) {
                settingRow("Port") {
                    TextField("Port", text: $portText)
                        .labelsHidden()
                        .textFieldStyle(.roundedBorder)
                        .multilineTextAlignment(.trailing)
                        .frame(width: 92)
                        .accessibilityLabel("Server port")
                }

                settingRow("Workers") {
                    Stepper(value: $workers, in: 1...32) {
                        Text("\(workers)")
                            .monospacedDigit()
                            .frame(minWidth: 22, alignment: .trailing)
                    }
                    .fixedSize()
                    .accessibilityLabel("Workers")
                    .accessibilityValue("\(workers)")
                }

                settingRow("Start server when AgentBridge opens") {
                    Toggle("Start server when AgentBridge opens", isOn: $startOnLaunch)
                        .labelsHidden()
                }
            }

            Text("Port and worker changes apply the next time the server starts.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    private var macOSSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("macOS")
                .font(.headline)

            settingRow("Launch AgentBridge at login") {
                Toggle("Launch AgentBridge at login", isOn: $launchAtLogin)
                    .labelsHidden()
            }

            if let errorMessage {
                Text(errorMessage)
                    .font(.caption)
                    .foregroundStyle(.red)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    private var footer: some View {
        HStack(spacing: 10) {
            if port == nil {
                Text("Enter a port from 1 to 65535.")
                    .font(.caption)
                    .foregroundStyle(.red)
            }

            Spacer()

            Button("Cancel") {
                restoreSavedValues()
                dismiss()
            }
            .keyboardShortcut(.cancelAction)

            Button("Save") {
                save()
            }
            .keyboardShortcut(.defaultAction)
            .disabled(!hasChanges || port == nil)
        }
    }

    private func settingRow<Control: View>(
        _ title: String,
        @ViewBuilder control: () -> Control
    ) -> some View {
        HStack(spacing: 16) {
            Text(title)
            Spacer()
            control()
        }
    }

    private var port: Int? {
        guard let value = Int(portText.trimmingCharacters(in: .whitespacesAndNewlines)),
              (1...65_535).contains(value)
        else {
            return nil
        }
        return value
    }

    private var hasChanges: Bool {
        port != savedPort
            || workers != savedWorkers
            || startOnLaunch != savedStartOnLaunch
            || launchAtLogin != savedLaunchAtLogin
    }

    private func save() {
        guard let port else { return }

        do {
            if launchAtLogin != savedLaunchAtLogin {
                if launchAtLogin {
                    try SMAppService.mainApp.register()
                } else {
                    try SMAppService.mainApp.unregister()
                }
            }

            defaults.set(port, forKey: PreferenceKey.port)
            defaults.set(workers, forKey: PreferenceKey.workers)
            defaults.set(startOnLaunch, forKey: PreferenceKey.startOnLaunch)
            savedPort = port
            savedWorkers = workers
            savedStartOnLaunch = startOnLaunch
            savedLaunchAtLogin = launchAtLogin
            errorMessage = nil
            dismiss()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func reload() {
        let storedPort = defaults.integer(forKey: PreferenceKey.port)
        savedPort = (1...65_535).contains(storedPort) ? storedPort : 8082
        let storedWorkers = defaults.integer(forKey: PreferenceKey.workers)
        savedWorkers = (1...32).contains(storedWorkers) ? storedWorkers : 1
        savedStartOnLaunch = defaults.bool(forKey: PreferenceKey.startOnLaunch)
        savedLaunchAtLogin = SMAppService.mainApp.status == .enabled
        restoreSavedValues()
    }

    private func restoreSavedValues() {
        portText = String(savedPort)
        workers = savedWorkers
        startOnLaunch = savedStartOnLaunch
        launchAtLogin = savedLaunchAtLogin
        errorMessage = nil
    }
}
