---
name: etoro-api
description: Interact with the user's real eToro account via the eToro Public API — search instruments, get prices/candles, read portfolio/PnL/trade history, manage watchlists, read/post social feeds, discover popular investors, manage agent sub-portfolios (copy-trading), and execute market/limit orders (demo or real). Use whenever the user mentions eToro trading, eToro positions/portfolio, placing or closing an eToro order, eToro watchlists, eToro feeds, copy-trading, instrument/candle lookup on eToro, or PnL on eToro. Keys live in etoro/back/.env (ETORO_PUBLIC_KEY, ETORO_PRIVATE_KEY).
---

# eToro Public API

Base URL: `https://public-api.etoro.com/api/v1`

## About

This skill interacts with the user's eToro account programmatically, including executing trades. The companion HTTP MCP server `etoro-api-docs` (`https://api-portal.etoro.com/mcp`) exposes the full request/response schemas — consult it when you need exact field shapes.

## Authentication & Required Headers

**Keys are already configured** in `etoro/back/.env` (the repo's single source of truth — never duplicate them):
- `ETORO_PUBLIC_KEY` → `x-api-key` (the application/Public API Key)
- `ETORO_PRIVATE_KEY` → `x-user-key` (the User Key; tied to a specific Real or Virtual/Demo environment)

Every request also needs `x-request-id`: a unique UUID generated per call.

**Use the helper script** `scripts/etoro_request.py` — it loads the keys from `back/.env`, generates a fresh `x-request-id`, sends the request, and pretty-prints the JSON response. Stdlib only.

```bash
# GET with a query string
python scripts/etoro_request.py GET /market-data/search \
  "internalSymbolFull=BTC&fields=instrumentId,internalSymbolFull,displayname"

# GET with no query
python scripts/etoro_request.py GET /watchlists

# POST with a JSON body
python scripts/etoro_request.py POST /trading/execution/demo/market-open-orders/by-amount \
  --json '{"InstrumentID":100000,"IsBuy":true,"Leverage":1,"Amount":100}'
```

> **Windows:** run the helper via **PowerShell** (or `cmd`), not Git Bash — MSYS rewrites a leading-`/` argument like `/watchlists` into a Windows path. (Under Git Bash, prefix with `MSYS_NO_PATHCONV=1`.) The script already sends a browser `User-Agent`, required because eToro is behind Cloudflare (default `Python-urllib` gets a `403 error code: 1010`).

Raw equivalent (if you build the call by hand):
```bash
curl -X GET "https://public-api.etoro.com/api/v1/watchlists" \
  -H "x-request-id: <UUID>" \
  -H "x-api-key: <ETORO_PUBLIC_KEY>" \
  -H "x-user-key: <ETORO_PRIVATE_KEY>"
```

**Key generation (only if the user needs new keys):** eToro → Settings → Trading → Create New Key → choose Environment (Real or Virtual/Demo) and Permissions (Read or Write) → verify identity → copy the User Key.

## Request Conventions
- **All paths below are relative to the Base URL** (which already includes `/api/v1`).
  Example: `GET /watchlists` means `GET https://public-api.etoro.com/api/v1/watchlists`.
- Query params go in the URL, path params go in the URL path.
- For query params documented as `array`, send **comma-separated values** (e.g., `instrumentIds=1001,1002`).
- Pagination patterns vary by endpoint:
  - Search: `pageNumber`, `pageSize`
  - People search & trade history: `page`, `pageSize`
  - Feeds: `take`, `offset`
  - Watchlist items listing: `pageNumber`, `itemsPerPage`
- **Casing matters** for request bodies:
  - Trading execution uses **PascalCase** fields (e.g., `InstrumentID`, `IsBuy`, `Leverage`).
  - Market close body uses `InstrumentId` (capital I, lowercase d).
  - Watchlist items use `ItemId`, `ItemType`, `ItemRank`.
  - Feeds post body uses lower camel (`owner`, `message`, `tags`, `mentions`, `attachments`).
- Some responses may use different casing for similar concepts (e.g., `instrumentId` vs `InstrumentID`). When extracting IDs, handle both if present.

## Demo vs Real Trading

- Use **demo execution endpoints** (contain `/demo/`) for testing and paper trading.
- Use **non-demo execution endpoints** for real trading.
- For portfolio/PnL:
  - Demo: `/trading/info/demo/*`
  - Real: `/trading/info/portfolio` and `/trading/info/real/pnl`
- Ensure your key environment matches the endpoint (Virtual vs Real). Each User Key is associated with a specific environment.

## Use Defaults

- Important: You don't need to specify all parameters. If the user doesn't specify leverage for example, don't send it on the API request.

> Safety: real-money execution endpoints move actual funds. Before sending any non-demo order (`/trading/execution/...` without `/demo/`), confirm the intent, instrument, side, size, and environment with the user.

## Quick Start (Demo Trade)

1) **Resolve `instrumentId`** using search. `fields` is required on search requests.

```bash
python scripts/etoro_request.py GET /market-data/search \
  "internalSymbolFull=BTC&fields=instrumentId,internalSymbolFull,displayname"
```

2) **Place a demo market order by amount** (PascalCase body):
```bash
python scripts/etoro_request.py POST /trading/execution/demo/market-open-orders/by-amount \
  --json '{"InstrumentID":100000,"IsBuy":true,"Leverage":1,"Amount":100}'
```

## Common IDs

- `instrumentId`: from Search or Instruments metadata
- `positionId`: from Portfolio endpoints
- `orderId`: from execution responses or Portfolio endpoints
- `marketId`: used by instrument feed endpoints (typically available in instrument metadata/search fields)
- `userId`: numeric eToro user ID (often referred to as **CID** in responses; discover via People endpoints/search)
- `watchlistId`: from watchlists list/create endpoints
- `subPortfolioId`: from Agent Portfolio endpoints (UUID)

## Market Data (Requests)

**Search instruments**
- `GET /market-data/search`
- Required query: `fields` (comma-separated list of instrument fields to return)
- Optional: `searchText`, `pageSize`, `pageNumber`, `sort`
- The Search endpoint supports filtering by fields returned in results; for exact symbol lookup, use `internalSymbolFull` as a query param and verify the exact match.
- Recommended minimal `fields` when you need IDs: include the instrument identifier (may appear as `instrumentId` or `InstrumentID`), plus `internalSymbolFull` and `displayname` (and `marketId` if you plan to use Feeds).

**Metadata**
- `GET /market-data/instruments`
  Filters: `instrumentIds`, `exchangeIds`, `stocksIndustryIds`, `instrumentTypeIds`.

**Prices & history**
- `GET /market-data/instruments/rates`
  Required: `instrumentIds` (comma-separated).
- `GET /market-data/instruments/history/closing-price`
  Returns historical closing prices for all instruments (bulk).
- `GET /market-data/instruments/{instrumentId}/history/candles/{direction}/{interval}/{candlesCount}`
  `direction`: `asc` or `desc`. `candlesCount` max 1000.
  Use only supported `interval` values (confirm via docs if unsure).

**Reference data**
- `GET /market-data/exchanges` (optional `exchangeIds`)
- `GET /market-data/instrument-types`
- `GET /market-data/stocks-industries` (optional `stocksIndustryIds`)

## Trading Execution (Requests)

> Requires a key with appropriate permissions (typically **Write**) and the correct environment (Demo vs Real).

### Market Open Orders (by amount)

Endpoints:
- `POST /trading/execution/demo/market-open-orders/by-amount`
- `POST /trading/execution/market-open-orders/by-amount`

Body (PascalCase, JSON):
- **Required:** `InstrumentID`, `IsBuy`, `Leverage`, `Amount`
- **Optional:** `StopLossRate`, `TakeProfitRate`, `IsTslEnabled`, `IsNoStopLoss`, `IsNoTakeProfit`

### Market Open Orders (by units)

Endpoints:
- `POST /trading/execution/demo/market-open-orders/by-units`
- `POST /trading/execution/market-open-orders/by-units`

Body (PascalCase, JSON):
- **Required:** `InstrumentID`, `IsBuy`, `Leverage`, `AmountInUnits`
- **Optional:** `StopLossRate`, `TakeProfitRate`, `IsTslEnabled`, `IsNoStopLoss`, `IsNoTakeProfit`

### Cancel Market Open Orders

Endpoints:
- `DELETE /trading/execution/demo/market-open-orders/{orderId}`
- `DELETE /trading/execution/market-open-orders/{orderId}`

### Market Close Orders

Endpoints:
- `POST /trading/execution/demo/market-close-orders/positions/{positionId}`
- `POST /trading/execution/market-close-orders/positions/{positionId}`
- `DELETE /trading/execution/demo/market-close-orders/{orderId}`
- `DELETE /trading/execution/market-close-orders/{orderId}`

Body (JSON):
- **Required:** `InstrumentId`
- **Optional:** `UnitsToDeduct` (number or `null`)

Partial close: set `UnitsToDeduct`.
Full close: set `UnitsToDeduct` to `null`.
You must close by `positionId`, not by symbol.

### Market-if-touched (Limit) Orders

Endpoints:
- `POST /trading/execution/demo/limit-orders`
- `DELETE /trading/execution/demo/limit-orders/{orderId}`
- `POST /trading/execution/limit-orders`
- `DELETE /trading/execution/limit-orders/{orderId}`

Body (PascalCase, JSON):
- **Required:** `InstrumentID`, `IsBuy`, `Leverage`, **`Rate`**, and **one of** `Amount` **or** `AmountInUnits`
- **Optional:** `StopLossRate`, `TakeProfitRate`, `IsTslEnabled`, `IsNoStopLoss`, `IsNoTakeProfit`
- **Do not send:** `IsDiscounted`, `CID`

## Trading Info & Portfolio (Requests)

- `GET /trading/info/demo/pnl`
- `GET /trading/info/real/pnl`
- `GET /trading/info/demo/portfolio`
- `GET /trading/info/portfolio`
  Use these to discover `positionId` and `orderId` for close/cancel flows.
- `GET /trading/info/trade/history`
  Required: `minDate` (YYYY-MM-DD). Optional: `page`, `pageSize`.

## Watchlists (Requests)

**User watchlists**
- `GET /watchlists`
  Optional: `itemsPerPageForSingle`, `ensureBuiltinWatchlists`, `addRelatedAssets`.
- `GET /watchlists/{watchlistId}`
  Optional: `pageNumber`, `itemsPerPage`.
- `POST /watchlists`
  Query: `name` (required), `type`, `dynamicQuery` (optional). (Uses query params, not a JSON body.)
- `PUT /watchlists/{watchlistId}`
  Query: `newName` (required). (Uses query params, not a JSON body.)
- `DELETE /watchlists/{watchlistId}`

**Watchlist items (body schema)**

`WatchlistItemDto` fields:
- `ItemId` (required, int)
- `ItemType` (required, string: `Instrument` or `Person`)
- `ItemRank` (optional, int)

Endpoints:
- `POST /watchlists/{watchlistId}/items`
- `PUT /watchlists/{watchlistId}/items`
- `DELETE /watchlists/{watchlistId}/items`

Example body:
```json
[
  { "ItemId": 12345, "ItemType": "Instrument", "ItemRank": 1 },
  { "ItemId": 67890, "ItemType": "Instrument", "ItemRank": 2 }
]
```

**Default watchlists**
- `POST /watchlists/default-watchlist/selected-items`
- `GET /watchlists/default-watchlists/items`
  Optional: `itemsLimit`, `itemsPerPage`.
- `POST /watchlists/newasdefault-watchlist`
  Query: `name` (required), `type`, `dynamicQuery` (optional).
- `PUT /watchlists/setUserSelectedUserDefault/{watchlistId}`
- `PUT /watchlists/rank/{watchlistId}`
  Query: `newRank` (required).

**Public watchlists**
- `GET /watchlists/public/{userId}`
- `GET /watchlists/public/{userId}/{watchlistId}`

## Feeds (Requests)

**Read feeds**
- `GET /feeds/instrument/{marketId}`
  Optional: `requesterUserId`, `take`, `offset`, `badgesExperimentIsEnabled`, `reactionsPageSize`.
- `GET /feeds/user/{userId}`
  Optional: `requesterUserId`, `take`, `offset`, `badgesExperimentIsEnabled`, `reactionsPageSize`.

Notes:
- `marketId` is associated with an instrument (typically available via instrument metadata/search if you include it in `fields`).
- `userId` is a numeric user identifier (CID). If you only have a username, discover the numeric ID via People endpoints (see User Info & Analytics).

**Create post**
- `POST /feeds/post`
- Body fields (lower camel, JSON):
  - `owner` (int)
  - `message` (string)
  - `tags`: `{ "tags": [{ "name": "...", "id": "..." }] }`
  - `mentions`: `{ "mentions": [{ "userName": "...", "id": "...", "isDirect": true }] }`
  - `attachments`: array of objects with `url`, `title`, `host`, `description`, `mediaType`, and optional `media`.

Minimal example:
```json
{ "message": "Hello eToro feed!" }
```

## Curated Lists & Recommendations (Requests)

- `GET /curated-lists`
- `GET /market-recommendations/{itemsCount}`

## Popular Investors (Copiers)

- `GET /pi-data/copiers`

## User Info & Analytics (Requests)

- `GET /user-info/people`
  Optional: `usernames`, `cidList`.
  Use this to map **username ↔ CID (userId)** when you need numeric `userId` for feeds/public watchlists.
- `GET /user-info/people/search`
  Required: `period`. Optional: `page`, `pageSize`, `sort`, `popularInvestor`, `gainMax`, `maxDailyRiskScoreMin`, `maxDailyRiskScoreMax`, `maxMonthlyRiskScoreMin`, `maxMonthlyRiskScoreMax`, `weeksSinceRegistrationMin`, `countryId`, `instrumentId`, `instrumentPctMin`, `instrumentPctMax`, `isTestAccount`, and other filters.
- `GET /user-info/people/{username}/gain`
- `GET /user-info/people/{username}/daily-gain`
  Required: `minDate`, `maxDate`, `type` (`Daily` or `Period`).
- `GET /user-info/people/{username}/portfolio/live`
- `GET /user-info/people/{username}/tradeinfo`
  Required: `period` (e.g., `LastTwoYears`).

## Agent Portfolios (Sub-Portfolios)

Agent portfolios are dedicated sub-accounts with their own virtual balance, enabling agents to trade independently via copy-trading. `investmentAmountInUsd` is deducted from **your** balance to copy the sub-portfolio — positions mirror proportionally (e.g. $2k investment / $10k virtual balance = 20% sizing). The `userToken` secret is **only returned at creation time**.

- `GET /sub-portfolios` — list all your agent portfolios.
- `POST /sub-portfolios` — create agent portfolio.
  Required body: `investmentAmountInUsd`, `subPortfolioName` (6–10 chars), `userTokenName`, `scopeIds`.
  Optional: `subPortfolioDescription`, `ipsWhitelist`, `expiresAt`.
- `DELETE /sub-portfolios/{subPortfolioId}` — permanently delete (revokes tokens, stops mirror).
- `POST /sub-portfolios/{subPortfolioId}/user-tokens` — create token.
  Required body: `userTokenName`, `scopeIds`. Optional: `ipsWhitelist`, `expiresAt`.
- `PATCH /sub-portfolios/{subPortfolioId}/user-tokens/{userTokenId}` — update token (at least one of: `scopeIds`, `ipsWhitelist`, `expiresAt`).
- `DELETE /sub-portfolios/{subPortfolioId}/user-tokens/{userTokenId}` — revoke token.

Scope IDs: 200 = real:read, 201 = demo:read, 202 = real:write, 203 = demo:write.

## Responses & Schemas

For response schemas and full examples, refer to:
- The `etoro-api-docs` MCP server (`https://api-portal.etoro.com/mcp`)
- https://api-portal.etoro.com/
