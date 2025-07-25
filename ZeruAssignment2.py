import pandas as pd
import requests
import time
import os
from dotenv import load_dotenv
from sklearn.preprocessing import MinMaxScaler
import numpy as np

# Load environment variables from .env file
load_dotenv()

# Configuration
ETHERSCAN_API_KEY=os.getenv('ETHERSCAN_API_KEY') # Retrieve API key from environment variable
if not ETHERSCAN_API_KEY:
    raise ValueError("Etherscan API key not found. Set the ETHERSCAN_API_KEY environment variable or .env file.")
COMPOUND_V2_COMPTROLLER = '0x3d9819210A31b4961b30EF54bE2aeD79B9c9Cd3B'  # Compound V2 Comptroller
GOOGLE_SHEET_URL='https://docs.google.com/spreadsheets/d/1ZzaeMgNYnxvriYYpe8PE7uMEblTI0GV5GIVUnsP-sBs/export?format=csv'

def fetch_transactions(wallet_address):
    """Fetch transactions for a wallet using Etherscan API"""
    url=f"https://api.etherscan.io/api?module=account&action=txlist&address={wallet_address}&startblock=0&endblock=99999999&sort=asc&apikey={ETHERSCAN_API_KEY}"
    try:
        response=requests.get(url)
        response.raise_for_status()
        data=response.json()
        if data['status'] == '1':
            return data['result']
        else:
            print(f"No transactions found for {wallet_address}")
            return []
    except requests.RequestException as e:
        print(f"Error fetching transactions for {wallet_address}: {e}")
        return []

def filter_compound_transactions(transactions):
    """Filter transactions related to Compound V2"""
    compound_txs=[
        tx for tx in transactions
        if tx.get('to', '').lower()==COMPOUND_V2_COMPTROLLER.lower() or
           tx.get('from', '').lower()==COMPOUND_V2_COMPTROLLER.lower()
    ]
    return compound_txs

def extract_features(wallet,transactions):
    """Extract risk-relevant features from Compound transactions"""
    if not transactions:
        return {
            'wallet_id': wallet,
            'tx_count': 0,
            'total_value_eth': 0.0,
            'avg_value_eth': 0.0,
            'failed_txs': 0,
            'recent_activity_ratio': 0.0,
            'unique_contracts': 0
        }
    
    # Convert transaction values (in wei) to ETH
    total_value=sum(float(tx['value'])/1e18 for tx in transactions)
    tx_count=len(transactions)
    failed_txs=sum(1 for tx in transactions if tx.get('isError', '0') == '1')
    
    # Time-based features
    timestamps=[int(tx['timeStamp']) for tx in transactions]
    if timestamps:
        recent_activity_ratio=sum(1 for ts in timestamps if (int(pd.Timestamp.now().timestamp()) - ts) < 30 * 24 * 60 * 60) / tx_count if tx_count > 0 else 0
    else:
        recent_activity_ratio=0
    
    # Unique contracts interacted with
    unique_contracts=len(set(tx.get('to', '').lower() for tx in transactions).union(
        set(tx.get('from', '').lower() for tx in transactions)))
    
    return {
        'wallet_id': wallet,
        'tx_count': tx_count,
        'total_value_eth': total_value,
        'avg_value_eth': total_value / tx_count if tx_count > 0 else 0,
        'failed_txs': failed_txs,
        'recent_activity_ratio': recent_activity_ratio,
        'unique_contracts': unique_contracts
    }

def score_wallets(features_df):
    """Assign risk scores (0=high risk, 1000=low risk)"""
    scaler = MinMaxScaler(feature_range=(0, 1000))
    
    # Risk scoring: lower scores for higher risk
    features_df['inv_tx_count'] = 1 / (features_df['tx_count'] + 1)
    features_df['inv_avg_value_eth'] = 1 / (features_df['avg_value_eth'] + 1)
    features_df['inv_failed_txs'] = 1 / (features_df['failed_txs'] + 1)
    
    # Features for scoring
    score_features = ['inv_tx_count', 'total_value_eth', 'inv_avg_value_eth', 'inv_failed_txs', 'recent_activity_ratio', 'unique_contracts']
    
    # Weighted sum scoring
    weights = {
        'inv_tx_count': 0.2,        # High tx count = higher risk
        'total_value_eth': 0.3,     # Higher volume = lower risk
        'inv_avg_value_eth': 0.1,   # High avg value = higher risk
        'inv_failed_txs': 0.3,      # More failed txs = higher risk
        'recent_activity_ratio': 0.05,  # Recent activity = lower risk
        'unique_contracts': 0.05    # More contracts = lower risk
    }
    
    # Calculate raw scores
    features_df['raw_score'] = sum(features_df[feat] * weight for feat, weight in weights.items())
    
    # Normalize scores to 0-1000
    features_df['score'] = scaler.fit_transform(features_df[['raw_score']]).flatten()
    
    # Bot and high-risk detection (inspired by Aave task)
    features_df['is_high_risk'] = (features_df['tx_count'] > 500) | (features_df['failed_txs'] > 10)
    features_df.loc[features_df['is_high_risk'], 'score'] = 0
    
    return features_df[['wallet_id', 'score']]

def main():
    # Load wallet addresses from Google Sheet
    try:
        wallets_df = pd.read_csv(GOOGLE_SHEET_URL)
        wallet_addresses = wallets_df['wallet_id'].tolist()
    except Exception as e:
        print(f"Error loading wallet addresses: {e}")
        return
    
    # Fetch and process transactions for up to 100 wallets
    wallet_features = []
    for i, wallet in enumerate(wallet_addresses[:100]):
        print(f"Processing wallet {i+1}/100: {wallet}")
        transactions = fetch_transactions(wallet)
        compound_txs = filter_compound_transactions(transactions)
        features = extract_features(wallet, compound_txs)
        wallet_features.append(features)
        time.sleep(0.2)  # Respect Etherscan rate limits (~5 req/sec)
    
    # Convert to DataFrame and score
    features_df = pd.DataFrame(wallet_features)
    scores_df = score_wallets(features_df)
    
    # Save results
    scores_df.to_csv('wallet_risk_scores.csv', index=False)
    print("Wallet risk scores saved to wallet_risk_scores.csv")

if __name__ == '__main__':
    main()