// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "AgentBridgeMenuBar",
    platforms: [
        .macOS(.v13),
    ],
    products: [
        .executable(name: "AgentBridgeMenuBar", targets: ["AgentBridgeMenuBar"]),
    ],
    targets: [
        .executableTarget(name: "AgentBridgeMenuBar"),
        .testTarget(
            name: "AgentBridgeMenuBarTests",
            dependencies: ["AgentBridgeMenuBar"]
        ),
    ],
    swiftLanguageModes: [.v5]
)
