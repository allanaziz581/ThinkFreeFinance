import SwiftUI

struct DashboardView: View {
    @EnvironmentObject var store: DataStore
    var d: TFData { store.data }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: TF.gutter) {
                    tickerStrip
                    kpiRow
                    politicalFeature
                    insightRow
                    portfolioCard
                }
                .padding(TF.gutter)
            }
            .background(TF.bgPrimary.ignoresSafeArea())
            .navigationTitle("Good evening, \(store.userName)")
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    // top market ticker strip
    var tickerStrip: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 18) {
                ForEach(d.market_ticker ?? []) { t in
                    HStack(spacing: 6) {
                        Text(t.label).foregroundStyle(TF.textSecondary).font(.system(size: 12, weight: .semibold))
                        Text(t.value).foregroundStyle(TF.textPrimary).font(.system(size: 12, weight: .bold))
                        Text(t.change).foregroundStyle(t.dir == "up" ? TF.success : TF.danger).font(.system(size: 11, weight: .bold))
                    }
                }
            }
        }
    }

    // KPI tiles (2 across) matching the web's top row
    var kpiRow: some View {
        let cols = [GridItem(.flexible()), GridItem(.flexible())]
        return LazyVGrid(columns: cols, spacing: TF.gutter) {
            kpi("Market Mood", "72%", "Risk-on across sectors", TF.success, "Bullish", TF.success)
            kpi("Recession Risk", "\(store.recessionPct)%", d.recession?.summary ?? "", TF.warning,
                d.recession?.label ?? "Low", store.recessionPct < 40 ? TF.success : TF.warning)
            kpi("Market Direction", "Slightly Up", "Indices trending higher", TF.info, "▲", TF.success)
            kpi("Top Story", "Fed holds rates", "Guidance stays neutral", TF.info, "Fed", TF.info)
        }
    }

    func kpi(_ label: String, _ value: String, _ foot: String, _ accent: Color, _ pill: String, _ pillColor: Color) -> some View {
        Card {
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text(label.uppercased()).font(.system(size: 10, weight: .semibold))
                        .tracking(0.8).foregroundStyle(TF.textSecondary)
                    Spacer()
                    Pill(text: pill, color: pillColor)
                }
                Text(value).font(.system(size: 22, weight: .heavy)).foregroundStyle(TF.textPrimary)
                    .minimumScaleFactor(0.6).lineLimit(2)
                Text(foot).font(.system(size: 11)).foregroundStyle(TF.textTertiary).lineLimit(2)
            }
        }
    }

    // Political Watch feature card (top trader)
    @ViewBuilder var politicalFeature: some View {
        if let p = store.topPolitician {
            Card(padding: 18) {
                VStack(alignment: .leading, spacing: 14) {
                    HStack { CardTitle(text: "Political Watch"); Spacer()
                        Text("Full report →").font(.system(size: 11, weight: .semibold)).foregroundStyle(TF.info) }
                    HStack(spacing: 14) {
                        PoliticianPhoto(bioguide: p.bioguide, name: p.name, size: 88)
                        VStack(alignment: .leading, spacing: 4) {
                            Text("TOP TRADING PROFIT").font(.system(size: 10, weight: .bold))
                                .tracking(1).foregroundStyle(TF.success)
                            Text(p.name).font(.system(size: 20, weight: .heavy)).foregroundStyle(TF.textPrimary)
                            Text("\(p.party ?? "") · \(p.state ?? "")").font(.system(size: 12)).foregroundStyle(TF.textTertiary)
                            HStack(spacing: 18) {
                                stat("Est. P&L", p.pnl_fmt ?? "$0", TF.success)
                                stat("Return", String(format: "%+.1f%%", p.ret ?? 0), TF.success)
                            }.padding(.top, 4)
                        }
                        Spacer()
                    }
                    Divider().overlay(TF.border)
                    Text("Top Politicians by Estimated Trading Gains")
                        .font(.system(size: 11, weight: .bold)).tracking(1).foregroundStyle(TF.textSecondary)
                    ForEach(Array((d.politicians ?? []).prefix(5).enumerated()), id: \.element.id) { i, pol in
                        HStack {
                            Text("\(i + 1)").foregroundStyle(TF.textTertiary).font(.system(size: 12, weight: .bold)).frame(width: 18)
                            Text(pol.name).foregroundStyle(TF.textPrimary).font(.system(size: 13, weight: .semibold))
                            Spacer()
                            Text(pol.pnl_fmt ?? "$0").foregroundStyle((pol.pnl ?? 0) >= 0 ? TF.success : TF.danger)
                                .font(.system(size: 13, weight: .bold))
                        }
                        if i < 4 { Divider().overlay(TF.border) }
                    }
                }
            }
        }
    }

    func stat(_ l: String, _ v: String, _ c: Color) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(l.uppercased()).font(.system(size: 9, weight: .semibold)).foregroundStyle(TF.textTertiary)
            Text(v).font(.system(size: 16, weight: .heavy)).foregroundStyle(c)
        }
    }

    // "How This Affects You" everyday impact
    var insightRow: some View {
        Card(padding: 18) {
            VStack(alignment: .leading, spacing: 10) {
                CardTitle(text: "How This Affects You")
                ForEach((d.everyday ?? []).prefix(5)) { m in
                    HStack(alignment: .top) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(m.category).font(.system(size: 13, weight: .bold)).foregroundStyle(TF.textPrimary)
                            Text(m.impact).font(.system(size: 12)).foregroundStyle(TF.textSecondary)
                        }
                        Spacer()
                        Pill(text: m.dir == "up" ? "Costs ↑" : m.dir == "down" ? "Costs ↓" : "Steady",
                             color: m.dir == "up" ? TF.danger : m.dir == "down" ? TF.success : TF.info)
                    }
                    if m.id != d.everyday?.prefix(5).last?.id { Divider().overlay(TF.border) }
                }
            }
        }
    }

    @ViewBuilder var portfolioCard: some View {
        if let p = d.portfolio {
            Card(padding: 18) {
                VStack(alignment: .leading, spacing: 8) {
                    HStack { CardTitle(text: "My Portfolio"); Spacer()
                        Pill(text: String(format: "%+.2f%%", p.return_pct ?? 0),
                             color: (p.return_pct ?? 0) >= 0 ? TF.success : TF.danger) }
                    Text(p.value_fmt ?? "$0").font(.system(size: 28, weight: .heavy)).foregroundStyle(TF.textPrimary)
                    Text("\(p.open_count ?? 0) open positions · \(String(format: "%.0f", p.exposure ?? 0))% exposure")
                        .font(.system(size: 12)).foregroundStyle(TF.textTertiary)
                }
            }
        }
    }
}

/// Politician photo from the bundled assets (firstname bioguide), falls back to initials.
struct PoliticianPhoto: View {
    let bioguide: String?; let name: String; var size: CGFloat = 88
    var body: some View {
        Group {
            if let bg = bioguide, let img = Self.loadPhoto(bg) {
                Image(uiImage: img).resizable().scaledToFill()
            } else {
                ZStack {
                    LinearGradient(colors: [TF.purple, TF.info], startPoint: .top, endPoint: .bottom)
                    Text(initials).font(.system(size: size * 0.32, weight: .heavy)).foregroundStyle(.white)
                }
            }
        }
        .frame(width: size, height: size * 1.18)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(TF.border, lineWidth: 1))
    }
    var initials: String {
        name.split(separator: " ").prefix(2).compactMap { $0.first }.map(String.init).joined().uppercased()
    }
    /// Robust photo lookup: works whether Resources is flattened or kept as a folder reference.
    static func loadPhoto(_ bg: String) -> UIImage? {
        if let i = UIImage(named: bg) { return i }
        for sub in [nil, "politicians", "Resources/politicians"] {
            if let url = Bundle.main.url(forResource: bg, withExtension: "jpg", subdirectory: sub),
               let img = UIImage(contentsOfFile: url.path) { return img }
        }
        return nil
    }
}
