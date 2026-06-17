import SwiftUI

struct IntelligenceView: View {
    @EnvironmentObject var store: DataStore
    var d: TFData { store.data }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: TF.gutter) {
                    // recession / economy
                    if let r = d.recession {
                        Card(padding: 18) {
                            VStack(alignment: .leading, spacing: 10) {
                                CardTitle(text: "Recession Risk")
                                HStack(alignment: .bottom, spacing: 8) {
                                    Text("\(store.recessionPct)%").font(.system(size: 34, weight: .heavy)).foregroundStyle(TF.textPrimary)
                                    Pill(text: r.label ?? "Low", color: store.recessionPct < 40 ? TF.success : TF.warning).padding(.bottom, 6)
                                }
                                Text(r.summary ?? "").font(.system(size: 13)).foregroundStyle(TF.textSecondary)
                                ForEach(r.factors ?? [], id: \.self) { f in
                                    HStack(alignment: .top, spacing: 8) {
                                        Text("▸").foregroundStyle(TF.success)
                                        Text(f).font(.system(size: 12)).foregroundStyle(TF.textSecondary)
                                    }
                                }
                            }
                        }
                    }
                    // sector opportunity scores
                    Card(padding: 18) {
                        VStack(alignment: .leading, spacing: 12) {
                            CardTitle(text: "Sector Opportunity Scores")
                            ForEach(d.sectors ?? []) { s in
                                VStack(alignment: .leading, spacing: 4) {
                                    HStack {
                                        Text(s.sector).font(.system(size: 13, weight: .semibold)).foregroundStyle(TF.textPrimary)
                                        Spacer()
                                        Pill(text: s.direction ?? "", color: s.direction == "Bullish" ? TF.success : TF.info)
                                        Text(String(format: "%.1f", s.score ?? 0)).font(.system(size: 13, weight: .bold)).foregroundStyle(TF.textPrimary)
                                    }
                                    ProgressView(value: (s.score ?? 0) / 10).tint(TF.success)
                                }
                            }
                        }
                    }
                    // bill-trade correlation
                    if let c = d.correlation {
                        Card(padding: 18) {
                            VStack(alignment: .leading, spacing: 8) {
                                CardTitle(text: "Bill–Trade Correlation Index")
                                Text("\(Int(c.index ?? 0))/100").font(.system(size: 30, weight: .heavy)).foregroundStyle(TF.gold)
                                Text(c.headline ?? "").font(.system(size: 12)).foregroundStyle(TF.textSecondary)
                            }
                        }
                    }
                }.padding(TF.gutter)
            }
            .background(TF.bgPrimary.ignoresSafeArea())
            .navigationTitle("Intelligence")
        }
    }
}
