# Broker Integrations

## Binance Integration
- REST and WebSocket support
- API key authentication
- Handles rate limits and order lifecycle
- WebSocket for order updates
- Key hardening gaps: production credential management, error handling, monitoring

## IBKR Integration
- REST and session-based support
- API key/session authentication
- Handles rate limits and order lifecycle
- Session management for order updates
- Key hardening gaps: session reliability, error handling, monitoring

## Authentication
- API key (Binance)
- API key/session (IBKR)

## Rate Limits
- Handled per broker adapter

## Order Lifecycle
- New, filled, cancelled, rejected, expired

## WebSocket/Session Concerns
- Binance: WebSocket for real-time updates
- IBKR: Session management for updates

## Key Production-Hardening Gaps
- Credential rotation
- Monitoring and alerting
- Robust error handling
