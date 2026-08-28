import AppKit
import Darwin
import Foundation

@MainActor
final class ServerController: ObservableObject {
    @Published private(set) var phase: ServerPhase = .stopped
    @Published private(set) var health: HealthPayload?
    @Published private(set) var codex: CapabilitiesPayload.Codex?
    @Published private(set) var detail: String?
    @Published private(set) var lastUpdated: Date?

    private let healthClient: any HealthChecking
    private var configuration: ServerConfiguration
    private var process: Process?
    private var logHandle: FileHandle?
    private var monitorTask: Task<Void, Never>?
    private var capabilityTask: Task<Void, Never>?
    private var lastCapabilityRefresh = Date.distantPast
    private var didApplyLaunchPolicy = false

    init(
        healthClient: any HealthChecking = HTTPHealthClient(),
        configuration: ServerConfiguration = .current()
    ) {
        self.healthClient = healthClient
        self.configuration = configuration
    }

    var baseURL: URL { configuration.baseURL }
    var dashboardURL: URL { baseURL.appendingPathComponent("dashboard") }
    var activeRequests: Int { health?.activeRequests ?? 0 }
    var workerCount: Int { health?.workers ?? configuration.workers }
    var versionLabel: String { health.map { "v\($0.version)" } ?? "" }
    var claudeAvailable: Bool {
        ServerLauncher.candidateExecutablePaths(named: "claude")
            .contains(where: FileManager.default.isExecutableFile(atPath:))
    }
    var canStart: Bool { phase == .stopped || phase == .failed }
    var canStop: Bool { phase == .runningManaged || phase == .starting }

    func begin() {
        guard monitorTask == nil else { return }
        monitorTask = Task { [weak self] in
            guard let self else { return }
            await self.refresh()
            if !self.didApplyLaunchPolicy {
                self.didApplyLaunchPolicy = true
                let startOnLaunch = UserDefaults.standard.object(
                    forKey: PreferenceKey.startOnLaunch
                ) as? Bool ?? true
                if startOnLaunch, self.phase == .stopped {
                    await self.start()
                }
            }

            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 2_000_000_000)
                await self.refresh()
            }
        }
    }

    func refresh() async {
        let result = await healthClient.health(baseURL: baseURL)
        switch result {
        case let .healthy(payload):
            health = payload
            detail = nil
            phase = process?.isRunning == true ? .runningManaged : .runningExternal
            refreshCapabilitiesIfNeeded()
        case .unavailable:
            health = nil
            codex = nil
            if let process {
                if process.isRunning {
                    if phase != .starting && phase != .stopping {
                        phase = .failed
                        detail = "The server process is running but is not responding."
                    }
                } else if phase != .stopping {
                    phase = .failed
                    detail = "The server exited with status \(process.terminationStatus)."
                    self.process = nil
                }
            } else if phase != .starting && phase != .stopping {
                phase = .stopped
                detail = nil
            }
        case let .unexpected(message):
            health = nil
            codex = nil
            phase = .conflict
            detail = message
        }
        lastUpdated = Date()
    }

    func start() async {
        guard canStart else { return }
        configuration = .current()
        await refresh()
        guard phase == .stopped || phase == .failed else { return }

        phase = .starting
        detail = nil
        do {
            let command = try ServerLauncher.command()
            let child = Process()
            child.executableURL = command.executable
            child.arguments = command.argumentsPrefix + [
                "--port", String(configuration.port),
                "--workers", String(configuration.workers),
            ]
            child.environment = ServerLauncher.processEnvironment(command: command)

            let handle = try makeLogHandle()
            child.standardOutput = handle
            child.standardError = handle
            child.terminationHandler = { [weak self] terminated in
                Task { @MainActor [weak self] in
                    self?.processDidTerminate(terminated)
                }
            }
            process = child
            logHandle = handle
            do {
                try child.run()
            } catch {
                process = nil
                logHandle = nil
                try? handle.close()
                throw error
            }

            for _ in 0..<40 {
                try? await Task.sleep(nanoseconds: 250_000_000)
                await refresh()
                if phase == .runningManaged { return }
                if child.isRunning == false { break }
            }
            if child.isRunning {
                phase = .failed
                detail = "AgentBridge did not become healthy within 10 seconds."
            }
        } catch {
            phase = .failed
            detail = error.localizedDescription
        }
    }

    func stop() async {
        guard let child = process, child.isRunning else {
            process = nil
            await refresh()
            return
        }
        phase = .stopping
        detail = nil
        child.terminate()

        for _ in 0..<50 where child.isRunning {
            try? await Task.sleep(nanoseconds: 100_000_000)
        }
        if child.isRunning {
            Darwin.kill(child.processIdentifier, SIGKILL)
        }
        process = nil
        try? logHandle?.close()
        logHandle = nil
        health = nil
        codex = nil
        phase = .stopped
        lastUpdated = Date()
    }

    func openDashboard() {
        NSWorkspace.shared.open(dashboardURL)
    }

    func openLogs() {
        let directory = Self.configDirectory()
            .appendingPathComponent("logs", isDirectory: true)
        try? FileManager.default.createDirectory(
            at: directory,
            withIntermediateDirectories: true
        )
        NSWorkspace.shared.open(directory)
    }

    func openConfig() {
        let directory = Self.configDirectory()
        try? FileManager.default.createDirectory(
            at: directory,
            withIntermediateDirectories: true
        )
        NSWorkspace.shared.open(directory)
    }

    func quit() async {
        if process?.isRunning == true {
            await stop()
        }
        NSApplication.shared.terminate(nil)
    }

    private func refreshCapabilitiesIfNeeded() {
        guard capabilityTask == nil,
              Date().timeIntervalSince(lastCapabilityRefresh) >= 30
        else { return }
        let baseURL = baseURL
        capabilityTask = Task { [weak self] in
            guard let self else { return }
            let result = await self.healthClient.capabilities(baseURL: baseURL)
            self.codex = result?.codex
            self.lastCapabilityRefresh = Date()
            self.capabilityTask = nil
        }
    }

    private func processDidTerminate(_ terminated: Process) {
        guard process === terminated else { return }
        try? logHandle?.close()
        logHandle = nil
        process = nil
        health = nil
        codex = nil
        if phase == .stopping {
            phase = .stopped
            detail = nil
        } else if terminated.terminationStatus == 0 {
            phase = .stopped
            detail = nil
        } else {
            phase = .failed
            detail = "The server exited with status \(terminated.terminationStatus)."
        }
        lastUpdated = Date()
    }

    private func makeLogHandle() throws -> FileHandle {
        let logDirectory = Self.configDirectory().appendingPathComponent("logs", isDirectory: true)
        try FileManager.default.createDirectory(
            at: logDirectory,
            withIntermediateDirectories: true
        )
        let logURL = logDirectory.appendingPathComponent("menu-bar.log")
        if !FileManager.default.fileExists(atPath: logURL.path) {
            FileManager.default.createFile(atPath: logURL.path, contents: nil)
        }
        let handle = try FileHandle(forWritingTo: logURL)
        try handle.seekToEnd()
        return handle
    }

    private static func configDirectory() -> URL {
        if let override = ProcessInfo.processInfo.environment["AGENTBRIDGE_CONFIG_DIR"],
           !override.isEmpty
        {
            return URL(fileURLWithPath: NSString(string: override).expandingTildeInPath)
        }
        return FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".config", isDirectory: true)
            .appendingPathComponent("agentbridge", isDirectory: true)
    }
}
