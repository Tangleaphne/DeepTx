# Tenderly Transaction Simulator

Simulate Ethereum transactions using Tenderly API and extract structured data.

---

## Quick Start

```bash
# Install dependencies
pip install web3 requests

# Replay a transaction
python3 main.py --tx-hash 0xYourTxHash --rpc-url https://eth.llamarpc.com

# Simulate a contract call
python3 main.py --contract 0xContractAddr --function 'balanceOf(address)' 0xAddr
```

**Output:**
```
output/1/0xabc123.../
Success
```

---

## Configuration

Edit `config.txt` or `main.py` with your Tenderly credentials:
```
api_key = "YOUR_API_KEY"
account_id = "YOUR_ACCOUNT_SLUG"
project_slug = "YOUR_PROJECT_SLUG"
```

---

## Usage

### Method 1: Replay Transaction

```bash
python3 main.py --tx-hash <tx_hash> --rpc-url <rpc_url>
```

**Example:**
```bash
python3 main.py --tx-hash 0xff8e9226091d513fc936ecc670030eba03f34dbe60cd012122bd18be44248d32 --rpc-url https://eth.llamarpc.com
```

### Method 2: Simulate Contract Call

```bash
python3 main.py --contract <address> --function '<signature>' [params...] [options]
```

**Examples:**
```bash
# No parameters
python3 main.py --contract 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 --function 'totalSupply()'

# With parameters
python3 main.py --contract 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 --function 'balanceOf(address)' 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0

# With sender
python3 main.py --contract 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 --function 'transfer(address,uint256)' 0xRecipient 1000000 --from 0xYourAddress

# With ETH value
python3 main.py --contract 0xContract --function 'deposit()' --from 0xAddr --value 0xDE0B6B3A7640000

# At specific block
python3 main.py --contract 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 --function 'balanceOf(address)' 0xAddr --block 18000000
```

### Optional Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--from <address>` | Sender address | `0x0000...0000` |
| `--value <hex>` | ETH amount to send | `0x0` |
| `--block <number>` | Block number for simulation | Latest |

---

## Output

All results are saved to: `output/[chain_id]/[tx_hash]/`

### Generated Files

| File | Description | Format |
|------|-------------|--------|
| `decoded_trace.json` | Full simulation result from Tenderly | JSON |
| `asset_flows.csv` | Token and ETH transfers | CSV |
| `call_trace.csv` | Function call sequence | CSV |
| `state_changes.csv` | Storage slot changes | CSV |
| `address.txt` | Involved contract addresses | TXT |

### CSV Formats

**asset_flows.csv:**
```csv
token_address,name,symbol,from,to,value
0xa0b86991...,USDC,usdc,0xbbbb...,0x80bf...,10000000
```

**call_trace.csv:**
```csv
depth,from,to,call_type,function
0,0x37305...,0xa0b86...,CALL,transfer
1,0xa0b86...,0x43506...,DELEGATECALL,transfer
```

**state_changes.csv:**
```csv
Contract,Storage Slot,New Value
0x04c154b66cb340f3ae24111cc767e0184ed00cc6,0x1f,0x67ebef4c1500000000000000000000007b36768623
```
*(Hex values automatically simplified: `0x000...01f` → `0x1f`)*

**address.txt:**
```
0x37305b1cd40574e4c5ce33f8e8306be057fd7341
0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48
0x43506849d7c04f9138d1a2050bbf3a0c054402dd
```
*(Extracted from `contract_ids`, one address per line)*

### Output Format

The script outputs two lines:
```
output/[chain_id]/[tx_hash]
Success
```
or
```
output/[chain_id]/[tx_hash]
Failed
```

---

## File Structure

```
simulation/
├── main.py                    # Main script (use this)
├── tenderly.py                # Tenderly API wrapper
├── extract_asset_flows.py     # Asset extraction (internal)
├── extract_call_trace.py      # Call trace extraction (internal)
├── config.txt                 # API configuration
└── output/                    # Results
    └── [chain_id]/
        └── [tx_hash]/
            ├── decoded_trace.json
            ├── asset_flows.csv
            ├── call_trace.csv
            ├── state_changes.csv
            └── address.txt
```

**Common Chain IDs:**
- `1` - Ethereum Mainnet
- `137` - Polygon
- `56` - BSC
- `42161` - Arbitrum One
- `10` - Optimism

---

## Features

- ✅ Simulate any transaction without on-chain execution
- ✅ Automatic function encoding
- ✅ Extract asset transfers (ERC20/ERC721/ETH)
- ✅ Extract call traces (filters JUMPDEST/STATICCALL)
- ✅ Extract storage state changes
- ✅ Organized by chain ID
- ✅ All CSV files created even if empty (with headers)
- ✅ Simplified hex values in state changes

---

## Implementation Details

### Core Modules

**main.py** (307 lines)
- Entry point for all operations
- Handles CLI arguments parsing
- Orchestrates simulation and extraction

**tenderly.py** (125 lines)
- `TenderlySimulator` class: API communication
- `get_transaction_params_by_hash()`: Fetch tx from blockchain
- `generate_query_hash()`: Cache key generation

**extract_asset_flows.py** (155 lines)
- `extract_asset_changes()`: From Tenderly's asset_changes
- `extract_transfer_events()`: From event logs
- `extract_eth_transfers()`: From balance_diff

**extract_call_trace.py** (78 lines)
- `extract_call_trace_recursive()`: Recursive trace extraction
- `extract_all_call_traces()`: Main extraction with filtering

### Data Extraction Logic

1. **Asset Flows**: Combines data from `asset_changes`, event `logs`, and `balance_diff`
2. **Call Trace**: Recursively extracts calls, excludes `JUMPDEST` and `STATICCALL`
3. **State Changes**: Extracts from `state_diff.raw`, simplifies hex values

---

## Notes

- Empty CSV files are created with headers only when no data is available
- `state_diff` may be `null` for simple custom simulations (use `--tx-hash` mode for full analysis)
- All modules except `main.py` are internal libraries - do not run directly
- Results automatically organized by chain ID to support multi-chain analysis

---

## License

MIT

