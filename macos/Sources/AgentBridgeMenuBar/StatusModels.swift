import Foundation
import SwiftUI

struct PoolStatus: Codable, Equatable, Sendable {
    let size: Int
    let available: Int
    let inUse: Int

    enum CodingKeys: String, CodingKey {
        case size
        case available
        case inUse = "in_use"
    }
}

struct HealthPayload: Codable, Equatable, Sendable {
    let status: String
    let version: String
    let startedAt: String?
    let uptimeSeconds: Double?
    let workers: Int?
    let activeRequests: Int?
    let pool: PoolStatus?

    enum CodingKeys: String, CodingKey {
        case status
        case version
        case startedAt = "started_at"
        case uptimeSeconds = "uptime_seconds"
        case workers
        case activeRequests = "active_requests"
        case pool
    }
}

struct CapabilitiesPayload: Codable, Equatable, Sendable {
    struct Codex: Codable, Equatable, Sendable {
        let available: Bool
        let authenticated: Bool
        let cliVersion: String?

        enum CodingKeys: String, CodingKey {
            case available
            case authenticated
            case cliVersion = "cli_version"
        }
    }

    let codex: Codex
}

enum HealthResult: Equatable, Sendable {
    case healthy(HealthPayload)
    case unavailable
    case unexpected(String)
}

enum ServerPhase: Equatable, Sendable {
    case stopped
    case starting
    case runningManaged
    case runningExternal
    case stopping
    case conflict
    case failed

    var label: String {
        switch self {
        case .stopped: "Stopped"
        case .starting: "Starting"
        case .runningManaged: "Running"
        case .runningExternal: "Running externally"
        case .stopping: "Stopping"
        case .conflict: "Port conflict"
        case .failed: "Needs attention"
        }
    }

    var color: Color {
        switch self {
        case .runningManaged, .runningExternal: .green
        case .starting, .stopping: .orange
        case .conflict, .failed: .red
        case .stopped: .secondary
        }
    }

    var menuBarSymbol: String {
        switch self {
        case .runningManaged, .runningExternal:
            "arrow.left.arrow.right.circle.fill"
        case .starting, .stopping:
            "arrow.triangle.2.circlepath.circle"
        case .conflict, .failed:
            "exclamationmark.circle.fill"
        case .stopped:
            "arrow.left.arrow.right.circle"
        }
    }
}

struct ServerConfiguration: Equatable, Sendable {
    let port: Int
    let workers: Int

    static func current(defaults: UserDefaults = .standard) -> ServerConfiguration {
        let environment = ProcessInfo.processInfo.environment
        let environmentPort = environment["PORT"]
            .flatMap(Int.init)
            .flatMap { (1...65_535).contains($0) ? $0 : nil }
        let environmentWorkers = environment["POOL_SIZE"]
            .flatMap(Int.init)
            .flatMap { $0 > 0 ? $0 : nil }
        let storedPort = defaults.integer(forKey: PreferenceKey.port)
        let storedWorkers = defaults.integer(forKey: PreferenceKey.workers)
        return ServerConfiguration(
            port: environmentPort ?? ((1...65_535).contains(storedPort) ? storedPort : 8082),
            workers: environmentWorkers ?? (storedWorkers > 0 ? storedWorkers : 1)
        )
    }

    var baseURL: URL {
        URL(string: "http://127.0.0.1:\(port)")!
    }
}

enum PreferenceKey {
    static let port = "serverPort"
    static let workers = "workerCount"
    static let startOnLaunch = "startServerOnLaunch"
}
