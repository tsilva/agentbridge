import Foundation

struct ServerCommand: Equatable {
    let executable: URL
    let argumentsPrefix: [String]
    let pythonPath: String?
}

enum ServerLauncherError: LocalizedError {
    case bundledServerMissing

    var errorDescription: String? {
        switch self {
        case .bundledServerMissing:
            "The bundled AgentBridge server is missing. Reinstall the application."
        }
    }
}

struct ServerLauncher {
    static func command(
        bundle: Bundle = .main,
        environment: [String: String] = ProcessInfo.processInfo.environment
    ) throws -> ServerCommand {
        if let override = environment["AGENTBRIDGE_SERVER_EXECUTABLE"], !override.isEmpty {
            return ServerCommand(
                executable: URL(fileURLWithPath: override),
                argumentsPrefix: [],
                pythonPath: environment["PYTHONPATH"]
            )
        }

        if let resources = bundle.resourceURL {
            let serverRoot = resources.appendingPathComponent("server", isDirectory: true)
            let python = serverRoot
                .appendingPathComponent("python", isDirectory: true)
                .appendingPathComponent("bin", isDirectory: true)
                .appendingPathComponent("python3")
            if FileManager.default.isExecutableFile(atPath: python.path) {
                return ServerCommand(
                    executable: python,
                    argumentsPrefix: ["-m", "agentbridge.server"],
                    pythonPath: serverRoot.appendingPathComponent("site-packages").path
                )
            }
        }

        for path in candidateExecutablePaths(named: "agentbridge", environment: environment) {
            if FileManager.default.isExecutableFile(atPath: path) {
                return ServerCommand(
                    executable: URL(fileURLWithPath: path),
                    argumentsPrefix: [],
                    pythonPath: nil
                )
            }
        }
        throw ServerLauncherError.bundledServerMissing
    }

    static func processEnvironment(
        command: ServerCommand,
        environment: [String: String] = ProcessInfo.processInfo.environment
    ) -> [String: String] {
        var result = environment
        let path = executableSearchPath(environment: environment)
        result["PATH"] = path.joined(separator: ":")
        result["AGENTBRIDGE_PARENT_PID"] = String(ProcessInfo.processInfo.processIdentifier)
        result["PYTHONDONTWRITEBYTECODE"] = "1"
        if let pythonPath = command.pythonPath {
            result["PYTHONPATH"] = pythonPath
        }
        if result["CODEX_BIN"] == nil,
           let codex = candidateExecutablePaths(named: "codex", environment: result)
            .first(where: FileManager.default.isExecutableFile(atPath:))
        {
            result["CODEX_BIN"] = codex
        }
        if result["CLAUDE_BIN"] == nil,
           let claude = candidateExecutablePaths(named: "claude", environment: result)
            .first(where: FileManager.default.isExecutableFile(atPath:))
        {
            result["CLAUDE_BIN"] = claude
        }
        return result
    }

    static func executableSearchPath(
        environment: [String: String] = ProcessInfo.processInfo.environment
    ) -> [String] {
        let home = environment["HOME"] ?? FileManager.default.homeDirectoryForCurrentUser.path
        let configured = (environment["PATH"] ?? "")
            .split(separator: ":")
            .map(String.init)
        let common = [
            "\(home)/.local/bin",
            "\(home)/.claude/local",
            "\(home)/.npm-global/bin",
            "\(home)/.bun/bin",
            "/opt/homebrew/bin",
            "/usr/local/bin",
            "/usr/bin",
            "/bin",
        ]
        var seen = Set<String>()
        return (configured + common).filter { seen.insert($0).inserted }
    }

    static func candidateExecutablePaths(
        named name: String,
        environment: [String: String] = ProcessInfo.processInfo.environment
    ) -> [String] {
        executableSearchPath(environment: environment).map { directory in
            URL(fileURLWithPath: directory).appendingPathComponent(name).path
        }
    }
}
