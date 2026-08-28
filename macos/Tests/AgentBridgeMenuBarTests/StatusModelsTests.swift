import Foundation
import XCTest
@testable import AgentBridgeMenuBar

final class StatusModelsTests: XCTestCase {
    func testDecodesCurrentHealthPayload() throws {
        let data = Data(
            """
            {
              "status": "ok",
              "version": "0.1.12",
              "started_at": "2026-08-28T12:00:00+00:00",
              "uptime_seconds": 42.5,
              "workers": 3,
              "active_requests": 1,
              "pool": {"size": 3, "available": 2, "in_use": 1}
            }
            """.utf8
        )

        let payload = try JSONDecoder().decode(HealthPayload.self, from: data)

        XCTAssertEqual(payload.version, "0.1.12")
        XCTAssertEqual(payload.workers, 3)
        XCTAssertEqual(payload.activeRequests, 1)
        XCTAssertEqual(payload.pool?.inUse, 1)
    }

    func testDecodesOlderHealthPayloadForCompatibility() throws {
        let data = Data(#"{"status":"ok","version":"0.1.11"}"#.utf8)
        let payload = try JSONDecoder().decode(HealthPayload.self, from: data)

        XCTAssertEqual(payload.version, "0.1.11")
        XCTAssertNil(payload.workers)
        XCTAssertNil(payload.activeRequests)
    }

    func testServerConfigurationUsesDefaults() {
        let suiteName = "StatusModelsTests-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suiteName)!
        defer { defaults.removePersistentDomain(forName: suiteName) }

        XCTAssertEqual(
            ServerConfiguration.current(defaults: defaults),
            ServerConfiguration(port: 8082, workers: 1)
        )

        defaults.set(9080, forKey: PreferenceKey.port)
        defaults.set(4, forKey: PreferenceKey.workers)
        XCTAssertEqual(
            ServerConfiguration.current(defaults: defaults),
            ServerConfiguration(port: 9080, workers: 4)
        )

        defaults.set(70_000, forKey: PreferenceKey.port)
        defaults.set(0, forKey: PreferenceKey.workers)
        XCTAssertEqual(
            ServerConfiguration.current(defaults: defaults),
            ServerConfiguration(port: 8082, workers: 1)
        )
    }

    func testExecutableSearchPathAddsDeveloperToolLocationsOnce() {
        let paths = ServerLauncher.executableSearchPath(environment: [
            "HOME": "/Users/example",
            "PATH": "/usr/bin:/opt/homebrew/bin",
        ])

        XCTAssertEqual(paths.first, "/usr/bin")
        XCTAssertEqual(paths.filter { $0 == "/opt/homebrew/bin" }.count, 1)
        XCTAssertTrue(paths.contains("/Users/example/.local/bin"))
        XCTAssertTrue(paths.contains("/Users/example/.npm-global/bin"))
    }
}
