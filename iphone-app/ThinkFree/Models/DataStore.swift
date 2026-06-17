import Foundation

/// Loads the bundled JSON (exported from the web app) once at launch.
final class DataStore: ObservableObject {
    @Published var data = TFData()

    init() { load() }

    func load() {
        guard let url = Bundle.main.url(forResource: "data", withExtension: "json"),
              let raw = try? Data(contentsOf: url) else {
            print("data.json not found in bundle")
            return
        }
        do {
            data = try JSONDecoder().decode(TFData.self, from: raw)
        } catch {
            print("decode error:", error)
        }
    }

    // convenience accessors
    var userName: String { data.user?.name ?? "Allan" }
    var topPolitician: Politician? { data.politicians?.first }
    var recessionPct: Int {
        let s = data.recession?.score ?? 0, m = data.recession?.max ?? 10
        return Int((s / m * 100).rounded())
    }
}
