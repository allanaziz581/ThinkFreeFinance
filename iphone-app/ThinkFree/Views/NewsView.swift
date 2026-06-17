import SwiftUI

struct NewsView: View {
    @EnvironmentObject var store: DataStore
    var d: TFData { store.data }
    @State private var selected: NewsItem?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: TF.gutter) {
                    Card(padding: 18) {
                        VStack(alignment: .leading, spacing: 8) {
                            CardTitle(text: "Market Overview")
                            Text(marketSummary).font(.system(size: 13)).foregroundStyle(TF.textSecondary).lineSpacing(3)
                        }
                    }
                    Card(padding: 18) {
                        VStack(alignment: .leading, spacing: 12) {
                            HStack { CardTitle(text: "Top News")
                                Spacer()
                                Text("\(d.news?.count ?? 0) · by credibility").font(.system(size: 11)).foregroundStyle(TF.textTertiary) }
                            ForEach(d.news ?? []) { n in
                                Button { selected = n } label: { newsRow(n) }
                                    .buttonStyle(.plain)
                                if n.id != d.news?.last?.id { Divider().overlay(TF.border) }
                            }
                        }
                    }
                }
                .padding(TF.gutter)
            }
            .background(TF.bgPrimary.ignoresSafeArea())
            .navigationTitle("News")
            .sheet(item: $selected) { StockDetailView(news: $0) }
        }
    }

    func newsRow(_ n: NewsItem) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(n.headline).font(.system(size: 14, weight: .bold)).foregroundStyle(TF.textPrimary)
                .multilineTextAlignment(.leading).fixedSize(horizontal: false, vertical: true)
            Text(n.summary).font(.system(size: 12)).foregroundStyle(TF.textSecondary).lineLimit(3)
            HStack(spacing: 6) {
                Pill(text: n.symbol, color: TF.info)
                Pill(text: n.sentiment?.capitalized ?? "Neutral",
                     color: n.sentiment == "positive" ? TF.success : n.sentiment == "negative" ? TF.danger : TF.info)
                Pill(text: n.credibility_tier ?? "", color: tierColor(n.credibility_tier))
                Spacer()
                Text("Source: \(n.source ?? "")").font(.system(size: 10.5, weight: .semibold)).foregroundStyle(TF.info)
            }
        }
    }

    func tierColor(_ t: String?) -> Color {
        switch t {
        case "Trusted": return TF.success
        case "Reliable": return TF.info
        case "Mixed": return TF.warning
        default: return TF.danger
        }
    }

    var marketSummary: String {
        let news = d.news ?? []
        if news.isEmpty { return "No market news to summarize right now." }
        let bySector = Dictionary(grouping: news) { $0.sector ?? "Markets" }
        let topSectors = bySector.sorted { $0.value.count > $1.value.count }.prefix(2).map { plain($0.key) }
        let cos = Array(Set(news.map { $0.symbol })).prefix(3)
        return "Most of today's news is about \(topSectors.joined(separator: " and ")). "
            + "The companies getting the most attention include \(cos.joined(separator: ", ")). "
            + "Stories are ranked by how reliable each source is, with trusted outlets shown first."
    }
    func plain(_ s: String) -> String {
        ["Information Technology": "tech companies", "Financials": "banks and insurers",
         "Health Care": "healthcare and drug companies", "Consumer Discretionary": "retail and consumer brands",
         "Energy": "energy companies", "Industrials": "manufacturers"][s] ?? "other companies"
    }
}

struct StockDetailView: View {
    let news: NewsItem
    @Environment(\.dismiss) var dismiss
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: TF.gutter) {
                    Card(padding: 18) {
                        VStack(alignment: .leading, spacing: 8) {
                            Text(news.symbol).font(.system(size: 22, weight: .heavy)).foregroundStyle(TF.textPrimary)
                            Text(news.sector ?? "").font(.system(size: 12)).foregroundStyle(TF.textTertiary)
                        }
                    }
                    Card(padding: 18) {
                        VStack(alignment: .leading, spacing: 8) {
                            CardTitle(text: news.headline)
                            Text(news.summary).font(.system(size: 14)).foregroundStyle(TF.textSecondary).lineSpacing(3)
                            if let url = news.url, let u = URL(string: url) {
                                Link("Open source: \(news.source ?? "source") ↗", destination: u)
                                    .font(.system(size: 13, weight: .semibold)).foregroundStyle(TF.info)
                            }
                        }
                    }
                }.padding(TF.gutter)
            }
            .background(TF.bgPrimary.ignoresSafeArea())
            .navigationTitle("Story").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Done") { dismiss() } } }
        }
    }
}
