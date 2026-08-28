import ServiceManagement
import SwiftUI

@MainActor
final class LaunchAtLoginSettings: ObservableObject {
    @Published var enabled = SMAppService.mainApp.status == .enabled
    @Published var errorMessage: String?

    func setEnabled(_ value: Bool) {
        do {
            if value {
                try SMAppService.mainApp.register()
            } else {
                try SMAppService.mainApp.unregister()
            }
            enabled = SMAppService.mainApp.status == .enabled
            errorMessage = nil
        } catch {
            enabled = SMAppService.mainApp.status == .enabled
            errorMessage = error.localizedDescription
        }
    }
}

struct SettingsView: View {
    @AppStorage(PreferenceKey.port) private var port = 8082
    @AppStorage(PreferenceKey.workers) private var workers = 1
    @AppStorage(PreferenceKey.startOnLaunch) private var startOnLaunch = true
    @StateObject private var launchAtLogin = LaunchAtLoginSettings()

    var body: some View {
        Form {
            Section("Server") {
                TextField("Port", value: $port, format: .number)
                    .frame(width: 110)
                Stepper("Workers: \(workers)", value: $workers, in: 1...32)
                Toggle("Start server when AgentBridge opens", isOn: $startOnLaunch)
            }

            Section("macOS") {
                Toggle(
                    "Launch AgentBridge at login",
                    isOn: Binding(
                        get: { launchAtLogin.enabled },
                        set: launchAtLogin.setEnabled
                    )
                )
                if let error = launchAtLogin.errorMessage {
                    Text(error)
                        .foregroundStyle(.red)
                        .font(.caption)
                }
            }

            Text("Port and worker changes apply the next time the server starts.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .formStyle(.grouped)
        .padding()
        .frame(width: 430, height: 310)
    }
}
