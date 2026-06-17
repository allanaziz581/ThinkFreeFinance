import Foundation

// MARK: - Top-level data (data.json)

struct TFData: Decodable {
    var user: TFUser?
    var market_ticker: [Ticker]?
    var recession: Recession?
    var portfolio: Portfolio?
    var politicians: [Politician]?
    var recent_trades: [Trade]?
    var sectors: [SectorOpportunity]?
    var tickers_opp: [TickerOpportunity]?
    var parallels: [Parallel]?
    var events: [HistoricalEvent]?
    var news: [NewsItem]?
    var everyday: [Everyday]?
    var correlation: Correlation?
    var disclaimer: String?
}

struct TFUser: Decodable { var name: String?; var plan: String? }

struct Ticker: Decodable, Identifiable {
    var label: String; var value: String; var change: String; var dir: String
    var id: String { label }
}

struct Recession: Decodable {
    var score: Double?; var max: Double?; var label: String?
    var summary: String?; var factors: [String]?
}

struct Portfolio: Decodable {
    var value_fmt: String?; var exposure: Double?; var return_pct: Double?
    var open_count: Int?; var win_rate: Double?; var cash: Double?
    var positions: [Position]?
}
struct Position: Decodable, Identifiable {
    var ticker: String; var shares: Double?; var entry: Double?; var last: Double?
    var cost_basis_fmt: String?; var score: Double?; var reasoning: String?
    var id: String { ticker }
}

struct Politician: Decodable, Identifiable {
    var name: String; var party: String?; var party_abbr: String?; var state: String?
    var chamber: String?; var trades: Int?; var buys: Int?; var sells: Int?
    var total_traded_fmt: String?; var pnl: Double?; var pnl_fmt: String?; var ret: Double?
    var bioguide: String?; var summary: String?; var networth_range_fmt: String?
    var est_portfolio_value_fmt: String?
    var top_tickers: [TopTicker]?
    var id: String { name }
}
struct TopTicker: Decodable, Identifiable { var ticker: String; var trades: Int; var id: String { ticker } }

struct Trade: Decodable, Identifiable {
    var politician: String; var party_abbr: String?; var ticker: String
    var transaction: String?; var date: String?; var range: String?
    var pct_return: Double?; var pnl_fmt: String?
    var id: String { politician + ticker + (date ?? "") }
}

struct SectorOpportunity: Decodable, Identifiable {
    var sector: String; var score: Double?; var direction: String?; var rationale: String?
    var id: String { sector }
}
struct TickerOpportunity: Decodable, Identifiable {
    var ticker: String; var score: Double?; var direction: String?
    var id: String { ticker }
}

struct Parallel: Decodable, Identifiable {
    var label: String; var context: String?
    var id: String { label }
}
struct HistoricalEvent: Decodable, Identifiable {
    var id: String; var name: String; var date_range: String?; var category: String?
    var summary: String?; var why_similar: String?; var what_happened_after: String?
    var history_warning: String?; var personal_impact: String?
}

struct NewsItem: Decodable, Identifiable {
    var symbol: String; var headline: String; var summary: String
    var sector: String?; var url: String?; var source: String?
    var credibility: Double?; var credibility_tier: String?; var sentiment: String?
    var id: String { symbol + headline }
}

struct Everyday: Decodable, Identifiable {
    var category: String; var dir: String; var impact: String; var detail: String?
    var id: String { category }
}

struct Correlation: Decodable {
    var index: Double?; var headline: String?
    var correlated_trades: Int?; var bills_with_trades: Int?; var pct_before: Int?
}
