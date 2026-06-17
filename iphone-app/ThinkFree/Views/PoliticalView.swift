import SwiftUI

struct PoliticalView: View {
    @EnvironmentObject var store: DataStore
    var d: TFData { store.data }
    @State private var selected: Politician?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: TF.gutter) {
                    Card(padding: 14) {
                        Text(d.disclaimer ?? "This analysis identifies timing relationships between public disclosures and market events. It does not imply or allege wrongdoing.")
                            .font(.system(size: 11)).foregroundStyle(TF.gold).lineSpacing(2)
                    }
                    Card(padding: 18) {
                        VStack(alignment: .leading, spacing: 12) {
                            CardTitle(text: "Top Politicians by Trading Gains")
                            ForEach(Array((d.politicians ?? []).prefix(15).enumerated()), id: \.element.id) { i, p in
                                Button { selected = p } label: {
                                    HStack {
                                        Text("\(i + 1)").foregroundStyle(TF.textTertiary).font(.system(size: 12, weight: .bold)).frame(width: 20)
                                        PoliticianPhoto(bioguide: p.bioguide, name: p.name, size: 34)
                                        VStack(alignment: .leading, spacing: 1) {
                                            Text(p.name).foregroundStyle(TF.textPrimary).font(.system(size: 13, weight: .semibold))
                                            Text("\(p.party_abbr ?? "") · \(p.state ?? "")").foregroundStyle(TF.textTertiary).font(.system(size: 11))
                                        }
                                        Spacer()
                                        VStack(alignment: .trailing, spacing: 1) {
                                            Text(p.pnl_fmt ?? "$0").foregroundStyle((p.pnl ?? 0) >= 0 ? TF.success : TF.danger).font(.system(size: 13, weight: .bold))
                                            Text(String(format: "%+.1f%%", p.ret ?? 0)).foregroundStyle(TF.textTertiary).font(.system(size: 11))
                                        }
                                    }
                                }.buttonStyle(.plain)
                                if i < 14 { Divider().overlay(TF.border) }
                            }
                        }
                    }
                }.padding(TF.gutter)
            }
            .background(TF.bgPrimary.ignoresSafeArea())
            .navigationTitle("Political Watch")
            .sheet(item: $selected) { PoliticianDetailView(p: $0) }
        }
    }
}

struct PoliticianDetailView: View {
    let p: Politician
    @Environment(\.dismiss) var dismiss
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: TF.gutter) {
                    Card(padding: 18) {
                        HStack(spacing: 14) {
                            PoliticianPhoto(bioguide: p.bioguide, name: p.name, size: 76)
                            VStack(alignment: .leading, spacing: 3) {
                                Text(p.name).font(.system(size: 20, weight: .heavy)).foregroundStyle(TF.textPrimary)
                                Text("\(p.party ?? "") · \(p.state ?? "") · \(p.chamber ?? "")")
                                    .font(.system(size: 12)).foregroundStyle(TF.textTertiary)
                            }
                        }
                    }
                    Card(padding: 18) {
                        let cols = [GridItem(.flexible()), GridItem(.flexible())]
                        LazyVGrid(columns: cols, spacing: 12) {
                            metric("Est. Net Worth", (p.est_portfolio_value_fmt ?? "$0") == "$0" ? "Not disclosed" : (p.networth_range_fmt ?? "—"))
                            metric("Portfolio Value", (p.est_portfolio_value_fmt ?? "$0") == "$0" ? "Not disclosed" : (p.est_portfolio_value_fmt ?? "—"))
                            metric("Est. Return", String(format: "%+.1f%%", p.ret ?? 0))
                            metric("Est. P&L", p.pnl_fmt ?? "$0")
                        }
                    }
                    if let s = p.summary {
                        Card(padding: 18) {
                            VStack(alignment: .leading, spacing: 6) {
                                CardTitle(text: "Summary")
                                Text(s).font(.system(size: 13)).foregroundStyle(TF.textSecondary).lineSpacing(3)
                            }
                        }
                    }
                    if let tks = p.top_tickers, !tks.isEmpty {
                        Card(padding: 18) {
                            VStack(alignment: .leading, spacing: 8) {
                                CardTitle(text: "Most Traded")
                                FlowChips(items: tks.map { "\($0.ticker) ·\($0.trades)x" })
                            }
                        }
                    }
                }.padding(TF.gutter)
            }
            .background(TF.bgPrimary.ignoresSafeArea())
            .navigationTitle(p.name).navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Done") { dismiss() } } }
        }
    }
    func metric(_ l: String, _ v: String) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(l.uppercased()).font(.system(size: 9, weight: .semibold)).foregroundStyle(TF.textTertiary)
            Text(v).font(.system(size: 15, weight: .heavy)).foregroundStyle(TF.textPrimary).minimumScaleFactor(0.6).lineLimit(1)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(RoundedRectangle(cornerRadius: 10).fill(TF.bgCard2))
    }
}

/// simple wrapping chip row
struct FlowChips: View {
    let items: [String]
    var body: some View {
        let cols = [GridItem(.adaptive(minimum: 90), spacing: 8)]
        LazyVGrid(columns: cols, alignment: .leading, spacing: 8) {
            ForEach(items, id: \.self) { Pill(text: $0, color: TF.info) }
        }
    }
}
