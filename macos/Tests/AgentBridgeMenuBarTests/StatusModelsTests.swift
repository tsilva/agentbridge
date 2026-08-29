import AppKit
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

    @MainActor
    func testMenuBarBadgeIsHiddenWithoutActiveWorkers() throws {
        let (canvas, button, presenter) = makeMenuBarFixture(activeWorkers: 0)

        XCTAssertTrue(presenter.badgeView.isHidden)
        XCTAssertNil(presenter.badgeView.displayedCount)
        XCTAssertEqual(button.toolTip, "AgentBridge: Running")

        try writeSnapshot(
            of: canvas,
            requestedBy: "AGENTBRIDGE_STATUS_ITEM_ZERO_SNAPSHOT_PATH"
        )
    }

    @MainActor
    func testMenuBarIconUsesAdaptiveTemplateRendering() {
        let (_, button, presenter) = makeMenuBarFixture(activeWorkers: 0)

        XCTAssertEqual(
            button.image?.isTemplate,
            true,
            "Menu-bar icons must be templates so macOS can maintain contrast"
        )

        presenter.update(
            button: button,
            phase: .runningManaged,
            activeWorkers: 48
        )
        XCTAssertEqual(button.image?.isTemplate, true)
        XCTAssertFalse(presenter.badgeView.isHidden)
    }

    @MainActor
    func testMenuBarBadgeShowsActiveWorkerCount() throws {
        let (canvas, button, presenter) = makeMenuBarFixture(activeWorkers: 48)

        XCTAssertFalse(presenter.badgeView.isHidden)
        XCTAssertEqual(presenter.badgeView.displayedCount, 48)
        XCTAssertEqual(button.toolTip, "AgentBridge: Running, 48 active workers")
        XCTAssertEqual(button.image?.isTemplate, true)

        try writeSnapshot(
            of: canvas,
            requestedBy: "AGENTBRIDGE_STATUS_ITEM_SNAPSHOT_PATH"
        )
    }

    @MainActor
    private func makeMenuBarFixture(
        activeWorkers: Int
    ) -> (NSView, NSStatusBarButton, MenuBarStatusPresenter) {
        let canvas = NSView(frame: NSRect(x: 0, y: 0, width: 48, height: 31))
        canvas.appearance = NSAppearance(named: .darkAqua)
        canvas.wantsLayer = true
        canvas.layer?.backgroundColor = NSColor(
            calibratedRed: 0.01,
            green: 0.22,
            blue: 0.19,
            alpha: 1
        ).cgColor

        let button = NSStatusBarButton(frame: NSRect(x: 8, y: 4, width: 32, height: 22))
        button.isBordered = false
        canvas.addSubview(button)
        let presenter = MenuBarStatusPresenter()
        presenter.install(on: button)
        presenter.update(
            button: button,
            phase: .runningManaged,
            activeWorkers: activeWorkers
        )
        return (canvas, button, presenter)
    }

    @MainActor
    private func writeSnapshot(of view: NSView, requestedBy environmentKey: String) throws {
        guard let snapshotPath = ProcessInfo.processInfo.environment[environmentKey] else {
            return
        }

        view.layoutSubtreeIfNeeded()
        let representation = try XCTUnwrap(
            view.bitmapImageRepForCachingDisplay(in: view.bounds)
        )
        view.cacheDisplay(in: view.bounds, to: representation)
        let data = try XCTUnwrap(
            representation.representation(using: .png, properties: [:])
        )
        try data.write(to: URL(fileURLWithPath: snapshotPath), options: .atomic)
    }
}
