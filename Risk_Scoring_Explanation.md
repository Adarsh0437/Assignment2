# Wallet Risk Scoring Explanation

## Data Collection Method
Transaction data for 100 wallet addresses (from the Google Sheet: https://docs.google.com/spreadsheets/d/1ZzaeMgNYnxvriYYpe8PE7uMEblTI0GV5GIVUnsP-sBs) is fetched using the Etherscan API (`txlist` endpoint) with a masked API key (set via Command Prompt or `.env` file). Transactions are filtered for Compound V2 (`0x3d9819210A31b4961b30EF54bE2aeD79B9c9Cd3B`) and V3 (`0x1F98431c8aD98523631AE4a59f267346ea31F984`) Comptroller interactions, capturing all relevant protocol activity. A 0.2-second delay respects Etherscan’s free tier rate limit (~5 requests/second). The Google Sheet is accessed via its public CSV export URL, with error handling for access issues. Compared to your Aave V2 task’s pre-provided `user-wallet-transactions.json` (with structured `action` fields like deposit), Etherscan provides raw data (`hash`, `to`, `from`, `value`, `isError`, `timeStamp`), requiring contract-based filtering. The approach is scalable, supporting larger datasets with a premium Etherscan key or batch processing.

## Feature Selection Rationale
Six features are extracted from filtered Compound V2 and V3 transactions, inspired by your Aave task’s features (`num_txs`, `total_deposits_usd`, `deposit_borrow_ratio`):
- **tx_count**: Total number of Compound V2/V3 transactions, capturing activity level.
- **total_value_eth**: Sum of transaction values in ETH, reflecting financial engagement.
- **avg_value_eth**: Average transaction value, indicating transaction size patterns.
- **failed_txs**: Count of failed transactions (`isError=1`), highlighting errors or malicious behavior.
- **recent_activity_ratio**: Proportion of transactions in the last 30 days, measuring recency.
- **unique_contracts**: Number of unique contract addresses, indicating behavioral diversity.

These features are selected for their risk relevance and computability from Etherscan’s raw data, avoiding external dependencies (e.g., price APIs for USD conversion). They adapt Aave’s volume and frequency metrics (`num_txs`, `total_deposits_usd`) to Compound, adding `failed_txs` to emphasize risk, as required. The features are lightweight and scalable, supporting larger datasets and potential enhancements (e.g., event parsing via Web3).

## Scoring Method
A weighted sum model assigns risk scores from 0 (high risk) to 1000 (low risk), normalized using `MinMaxScaler`. Features are preprocessed: `tx_count`, `avg_value_eth`, and `failed_txs` are inverted (e.g., `1/(tx_count+1)`) to penalize high-risk behavior. Weights are:
- `inv_tx_count`: 0.2 (high transaction counts increase risk).
- `total_value_eth`: 0.3 (higher volume reduces risk).
- `inv_avg_value_eth`: 0.1 (high average values increase risk).
- `inv_failed_txs`: 0.3 (more failures increase risk).
- `recent_activity_ratio`: 0.05 (recent activity reduces risk).
- `unique_contracts`: 0.05 (more contracts reduce risk).

High-risk wallets (`tx_count > 500` or `failed_txs > 10`) score 0, mirroring Aave’s bot detection (`num_txs > 500`). Compared to Aave’s XGBoost model, this weighted sum is simpler for transparency but adaptable to XGBoost with training data. Normalization ensures consistent 0–1000 scaling, making scores interpretable and scalable for larger datasets.

## Justification of Risk Indicators
The risk indicators are justified based on blockchain transaction patterns and your Aave task’s insights:
- **High `tx_count` (>500)**: Suggests bot-like activity, as in Aave’s `wallet_scores.csv` (`num_txs >= 523` scored 0). Bots pose risks due to potential manipulation or spam.
- **High `failed_txs` (>10)**: Indicates errors, smart contract issues, or malicious intent, increasing risk (new for Compound).
- **Low `total_value_eth`**: Suggests minimal protocol engagement, increasing risk, similar to low `total_deposits_usd` in Aave.
- **High `avg_value_eth`**: May signal risky large transfers or manipulation attempts.
- **Low `recent_activity_ratio`**: Inactive wallets are riskier, potentially abandoned or suspicious.
- **Low `unique_contracts`**: Limited interactions suggest spam or bots, contrasting with diversified legitimate activity.

These indicators align with your Aave bot detection logic and are computable from Etherscan data, ensuring scalability. They can be extended with additional features (e.g., liquidation events) for richer risk profiling.