import Foundation

protocol HealthChecking: Sendable {
    func health(baseURL: URL) async -> HealthResult
    func capabilities(baseURL: URL) async -> CapabilitiesPayload?
}

struct HTTPHealthClient: HealthChecking {
    private let session: URLSession

    init(session: URLSession = .shared) {
        self.session = session
    }

    func health(baseURL: URL) async -> HealthResult {
        var request = URLRequest(url: baseURL.appendingPathComponent("health"))
        request.timeoutInterval = 1.5

        do {
            let (data, response) = try await session.data(for: request)
            guard let response = response as? HTTPURLResponse else {
                return .unexpected("The configured port returned an invalid response.")
            }
            guard response.statusCode == 200 else {
                return .unexpected("Port \(baseURL.port ?? 8082) returned HTTP \(response.statusCode).")
            }
            guard let payload = try? JSONDecoder().decode(HealthPayload.self, from: data),
                  payload.status == "ok"
            else {
                return .unexpected("Another application is using port \(baseURL.port ?? 8082).")
            }
            return .healthy(payload)
        } catch let error as URLError where Self.isUnavailable(error) {
            return .unavailable
        } catch {
            return .unexpected(error.localizedDescription)
        }
    }

    func capabilities(baseURL: URL) async -> CapabilitiesPayload? {
        var request = URLRequest(
            url: baseURL
                .appendingPathComponent("api")
                .appendingPathComponent("v1")
                .appendingPathComponent("capabilities")
        )
        request.timeoutInterval = 22

        guard let (data, response) = try? await session.data(for: request),
              let response = response as? HTTPURLResponse,
              response.statusCode == 200
        else {
            return nil
        }
        return try? JSONDecoder().decode(CapabilitiesPayload.self, from: data)
    }

    private static func isUnavailable(_ error: URLError) -> Bool {
        switch error.code {
        case .cannotConnectToHost, .cannotFindHost, .networkConnectionLost,
             .notConnectedToInternet, .timedOut:
            true
        default:
            false
        }
    }
}
