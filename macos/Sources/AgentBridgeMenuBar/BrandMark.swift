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
        ZStack {
            RoundedRectangle(cornerRadius: size * 0.24, style: .continuous)
                .fill(AgentBridgeBrand.fir)

            Image(systemName: "arrow.left.arrow.right.circle.fill")
                .font(.system(size: size * 0.62, weight: .semibold))
                .foregroundStyle(AgentBridgeBrand.warmWhite)

            VStack {
                Spacer()
                Capsule()
                    .fill(AgentBridgeBrand.signal)
                    .frame(width: size * 0.56, height: max(1, size * 0.06))
                    .padding(.bottom, size * 0.08)
            }
        }
        .frame(width: size, height: size)
        .accessibilityHidden(true)
    }
}
