import SwiftUI

enum AgentBridgeBrand {
    static let fir = Color(red: 0.0, green: 72.0 / 255.0, blue: 61.0 / 255.0)
    static let warmWhite = Color(
        red: 244.0 / 255.0,
        green: 241.0 / 255.0,
        blue: 232.0 / 255.0
    )
    static let signal = Color(
        red: 255.0 / 255.0,
        green: 122.0 / 255.0,
        blue: 115.0 / 255.0
    )
}

struct AgentBridgeBrandMark: View {
    let size: CGFloat

    var body: some View {
        Image("BrandIcon", bundle: .module)
            .resizable()
            .interpolation(.high)
            .scaledToFit()
            .frame(width: size, height: size)
            .accessibilityHidden(true)
    }
}
