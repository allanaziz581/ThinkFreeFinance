import SwiftUI

/// ThinkFree dark fintech palette, matching the web dashboard.
enum TF {
    static let bgPrimary   = Color(hex: 0x050816)
    static let bgSecondary = Color(hex: 0x070E1D)
    static let bgCard      = Color(hex: 0x0C1628)
    static let bgCard2     = Color(hex: 0x0A1322)
    static let bgInner     = Color(hex: 0x0A1018)

    static let textPrimary   = Color(hex: 0xF1F5F9)
    static let textSecondary = Color(hex: 0x94A3B8)
    static let textTertiary  = Color(hex: 0x64748B)

    static let success = Color(hex: 0x00C46A)
    static let warning = Color(hex: 0xF59E0B)
    static let danger  = Color(hex: 0xEF4444)
    static let info    = Color(hex: 0x38BDF8)
    static let purple  = Color(hex: 0xA855F7)
    static let gold    = Color(hex: 0xE9C46A)

    static let border = Color.white.opacity(0.10)
    static let radius: CGFloat = 18
    static let gutter: CGFloat = 14
}

extension Color {
    init(hex: UInt, alpha: Double = 1) {
        self.init(.sRGB,
                  red: Double((hex >> 16) & 0xff) / 255,
                  green: Double((hex >> 8) & 0xff) / 255,
                  blue: Double(hex & 0xff) / 255,
                  opacity: alpha)
    }
}

/// Reusable card container matching the web's rounded, thin-bordered dark cards.
struct Card<Content: View>: View {
    var padding: CGFloat = 16
    @ViewBuilder var content: Content
    var body: some View {
        content
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: TF.radius)
                    .fill(LinearGradient(colors: [TF.bgCard, TF.bgCard2],
                                         startPoint: .top, endPoint: .bottom))
            )
            .overlay(RoundedRectangle(cornerRadius: TF.radius).stroke(TF.border, lineWidth: 1))
    }
}

struct CardTitle: View {
    let text: String
    var body: some View {
        HStack(spacing: 8) {
            Circle().fill(TF.success).frame(width: 6, height: 6)
            Text(text.uppercased())
                .font(.system(size: 11, weight: .bold))
                .tracking(1.2)
                .foregroundStyle(TF.textSecondary)
        }
    }
}

struct Pill: View {
    let text: String
    var color: Color = TF.success
    var body: some View {
        Text(text)
            .font(.system(size: 10.5, weight: .bold))
            .foregroundStyle(color)
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(Capsule().fill(color.opacity(0.15)))
    }
}
