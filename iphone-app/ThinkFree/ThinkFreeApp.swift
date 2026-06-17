import SwiftUI

@main
struct ThinkFreeApp: App {
    @StateObject private var store = DataStore()
    init() {
        // dark theme throughout
        UITabBar.appearance().backgroundColor = UIColor(TF.bgSecondary)
        UINavigationBar.appearance().largeTitleTextAttributes = [.foregroundColor: UIColor(TF.textPrimary)]
        UINavigationBar.appearance().titleTextAttributes = [.foregroundColor: UIColor(TF.textPrimary)]
    }
    var body: some Scene {
        WindowGroup {
            RootView().environmentObject(store).preferredColorScheme(.dark)
        }
    }
}

struct RootView: View {
    var body: some View {
        TabView {
            DashboardView()
                .tabItem { Label("Dashboard", systemImage: "square.grid.2x2.fill") }
            NewsView()
                .tabItem { Label("News", systemImage: "newspaper.fill") }
            PoliticalView()
                .tabItem { Label("Politics", systemImage: "building.columns.fill") }
            IntelligenceView()
                .tabItem { Label("Intelligence", systemImage: "chart.bar.fill") }
        }
        .tint(TF.success)
        .background(TF.bgPrimary)
    }
}
