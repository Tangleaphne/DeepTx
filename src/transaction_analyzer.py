#!/usr/bin/env python3
import os
import json
import re
import time
import pandas as pd
from pathlib import Path
from collections import defaultdict
from web3 import Web3

# Import modules
from .heimdall_client import inspect_transaction
from .contract_fetcher import ContractDecompilerTool, ContractFetcher

def run_transaction_analysis(tx_hash, tx_dir, chain_id):
    """Run comprehensive transaction analysis (analyze.py functionality)"""

    # === Configurations ===
    api_key = os.environ.get("TRANSPOSE_API_KEY")
    if not api_key:
        raise ValueError("TRANSPOSE_API_KEY environment variable is required")
    
    rpc_url = os.environ.get("RPC_URL", "https://ethereum.therpc.io")
    etherscan_api_url = os.environ.get("ETHERSCAN_API_URL")
    etherscan_api = os.environ.get("ETHERSCAN_API_KEY")
    if not etherscan_api:
        raise ValueError("ETHERSCAN_API_KEY environment variable is required")
    
    TRACE_PATH = os.path.join(tx_dir, "decoded_trace.json")
    # TRACE_TXT_PATH = os.path.join(tx_dir, "trace.txt")
    OUTPUT_CODE_PATH = os.path.join(tx_dir, "code.txt")
    ASSET_FLOWS_PATH = os.path.join(tx_dir, "asset_flows.csv")
    CALL_TRACE_PATH = os.path.join(tx_dir, "call_trace.csv")
    GAS_INFO_PATH = os.path.join(tx_dir, "gas_info.txt")
    STATE_CHANGES_PATH = os.path.join(tx_dir, "state_changes.csv") 

    # Initialize Web3
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    # === Step 1: Heimdall Inspect ===
    inspect_transaction(tx_hash=tx_hash, api_key=api_key, rpc_url=rpc_url, tx_dir=tx_dir)

    # === Step 2: Extract Gas Info ===
    if not os.path.exists(TRACE_PATH):
        print(f"Error: decoded_trace.json not found")
        return False

    with open(TRACE_PATH, "r", encoding="utf-8") as f:
        trace_data = json.load(f)

    tx = w3.eth.get_transaction(tx_hash)
    block = w3.eth.get_block(tx.blockNumber)
    tx_gas_price = tx.gasPrice
    block_base_fee = getattr(block, "baseFeePerGas", None)
    
    with open(GAS_INFO_PATH, "w", encoding="utf-8") as f:
        f.write(f"tx_gas_price: {tx_gas_price}\n")
        if block_base_fee is not None:
            f.write(f"block_base_fee: {block_base_fee}\n")
        else:
            f.write("block_base_fee: None\n")

    # === Step 3: Call Trace and Gas Usage Analysis ===
    call_trace = []
    def hex_to_int(h):
        try:
            return int(h, 16)
        except:
            return None
    
    def collect_func_info(item, depth=0):
        if item is None:
            return
        action = item.get("action", {})
        result = item.get("result", {})
        func_info = action.get("resolvedFunction", {}) or {}
        fn_name = func_info.get("name", "") if func_info else ""
        gas_alloc = hex_to_int(action.get("gas", "0x0"))
        gas_used = hex_to_int(result.get("gasUsed", "0x0"))
        gas_remain = (gas_alloc - gas_used) if gas_alloc is not None and gas_used is not None else None
        call_type = (action.get("callType", "") or "").lower()
        call_trace.append({
            "depth": depth,
            "from": action.get("from", "").lower(),
            "to": action.get("to", "").lower(),
            "call_type": call_type,
            "function": fn_name,
            "gas_allocated": gas_alloc,
            "gas_used": gas_used,
            "gas_remaining": gas_remain
        })
        for sub in item.get("subtraces", []):
            collect_func_info(sub, depth+1)

    if trace_data:
        collect_func_info(item=trace_data)
    else:
        print("✗ No trace data to analyze")

    df_call_trace = pd.DataFrame(call_trace)
    df_call_trace = df_call_trace[[
        "depth", "from", "to", "call_type", "function",
        "gas_allocated", "gas_used", "gas_remaining"
    ]]
    df_call_trace.to_csv(CALL_TRACE_PATH, index=False)

    # === Step 4: Fetch Contracts ===   
    df_call_trace = pd.read_csv(CALL_TRACE_PATH)
    from_addresses = df_call_trace["from"].dropna()
    to_addresses = df_call_trace["to"].dropna()
    involved_addresses = set()
    involved_addresses.update(from_addresses.str.lower().unique())
    if not to_addresses.empty:
        involved_addresses.update(to_addresses.str.lower().unique())

    print(f"Found {len(involved_addresses)} contract addresses")

    fetcher = ContractFetcher(tx_dir, chain_id, api_key=etherscan_api)
    tool = ContractDecompilerTool(fetcher)
    contract_names = {}
    for addr in sorted(involved_addresses):
        try:
            contract_name = tool.run(addr)
            if contract_name:
                contract_names[addr] = contract_name
        except Exception as e:
            print(f"Failed to process {addr}: {e}")

    # === Step 5: Extract Functions ===
    called_functions = set()
    for _, row in df_call_trace.iterrows():
        if pd.notna(row['function']): 
            called_functions.add((
                row['to'].lower().replace("0x", ""),
                row['function']
            ))
    # === Step 6: Extract Function Code ===
    Path(os.path.dirname(OUTPUT_CODE_PATH)).mkdir(parents=True, exist_ok=True)
    buffer = []

    for addr, func in called_functions:      
        contract_path = os.path.join(os.path.dirname(tx_dir), "contracts", addr)
        if not os.path.exists(contract_path):
            continue
        
        main_contract_file = contract_names.get(addr, f"{addr}.sol")
        matched = False
        
        if os.path.exists(os.path.join(contract_path, main_contract_file)):
            file_path = os.path.join(contract_path, main_contract_file)
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    code = f.read()
                pattern = rf"(function\s+{re.escape(func)}\s*\(.*?\)[\s\S]*?\{{[\s\S]*?\n\}})"
                matches = re.findall(pattern, code, re.IGNORECASE)
                if matches:
                    buffer.append(f"\n< Function from {addr} - {func} in {main_contract_file} >\n")
                    buffer.append(matches[0])
                    buffer.append("\n")
                    matched = True
        
        # search other files
        if not matched:
            for file in os.listdir(contract_path):
                if not file.endswith(".sol") or (main_contract_file and file == main_contract_file):
                    continue
                
                file_path = os.path.join(contract_path, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    code = f.read()
                
                pattern = rf"(function\s+{re.escape(func)}\s*\(.*?\)[\s\S]*?\{{[\s\S]*?\n\}})"
                matches = re.findall(pattern, code, re.IGNORECASE)
                
                if matches:
                    buffer.append(f"\n< Function from {addr} - {func} in {file} >\n")
                    buffer.append(matches[0])
                    buffer.append("\n")
                    matched = True
                    break
        if not matches:
            buffer.append(f"\n< Function {func} not found in {addr} >\n")

    def strip_comments(text: str) -> str:
        text = re.sub(r"/\*[\s\S]*?\*/", "", text)
        text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
        text = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", text)
        return text.strip() + "\n"

    clean = strip_comments("".join(buffer))

    with open(OUTPUT_CODE_PATH, "w", encoding="utf-8") as output_file:
        output_file.write(clean)

    # === Step 7: Asset Flow Analysis ===
    def collect_transfers(trace_item, transfers):
        native_token_map = {
            1: "ETH",    # Ethereum Mainnet
            56: "BNB",   # BSC
            137: "POL",  # Polygon
            146: "S",    # Sonic
            1329: "Sei", # Sei
            314: "FIL",  # Filecoin
        }
        native_token_symbol = native_token_map.get(chain_id, "ETH")

        error_field = trace_item.get("error")
        has_error = error_field is not None and error_field != "None" and error_field != ""
        
        if has_error:
            return

        action = trace_item.get("action", {})
        value_hex = action.get("value", "0x0")
        if value_hex not in ("0x", "", "0x0"):
            try:
                value = int(value_hex, 16)
            except Exception:
                value = 0
            if value > 0:
                from_addr = action.get("from", "")
                to_addr = action.get("to", "")
                if from_addr and to_addr:
                    transfers.append({
                        "token_address": native_token_symbol,
                        "from": Web3.to_checksum_address(from_addr),
                        "to": Web3.to_checksum_address(to_addr),
                        "value": value
                    })
        
        for log in trace_item.get("logs", []):
            topics = log.get("topics", [])
            if len(topics) >= 3 and topics[0].lower().startswith("0xddf252ad"):
                from_addr = "0x" + topics[1][-40:]
                to_addr = "0x" + topics[2][-40:]
                data_hex = log.get("data", "0x0")
                if data_hex == "0x" or data_hex == "":
                    value = 0
                else:
                    try:
                        value = int(data_hex, 16)
                    except Exception:
                        value = 0
                token = log["address"].lower()
                transfers.append({
                    "token_address": token,
                    "from": Web3.to_checksum_address(from_addr),
                    "to": Web3.to_checksum_address(to_addr),
                    "value": value
                })
        for sub in trace_item.get("subtraces", []):
            collect_transfers(sub, transfers)

    transfers = []
    collect_transfers(trace_data, transfers)

    # Get token metadata
    token_meta = {}
    abi = [
        {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
        {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
        {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"}
    ]

    def get_token_info(addr):
        if addr in token_meta:
            return token_meta[addr]
        contract = w3.eth.contract(address=Web3.to_checksum_address(addr), abi=abi)
        try:
            name = contract.functions.name().call()
            time.sleep(1)
        except:
            name = "N/A"
        try:
            symbol = contract.functions.symbol().call()
            time.sleep(1)
        except:
            symbol = "N/A"
            
        try:
            decimals = contract.functions.decimals().call()
            time.sleep(1)
        except:
            decimals = 18
        token_meta[addr] = {"name": name, "symbol": symbol, "decimals": decimals}
        return token_meta[addr]
    
    native_token_meta = {
        1: {"name": "Ether", "symbol": "ETH", "decimals": 18},
        56: {"name": "Binance Coin", "symbol": "BNB", "decimals": 18},
        137: {"name": "Polygon", "symbol": "POL", "decimals": 18},
        146: {"name": "Sonic", "symbol": "S", "decimals": 18},
        1329: {"name": "Sei", "symbol": "SEI", "decimals": 18},
        314: {"name": "Filecoin", "symbol": "FIL", "decimals": 18}
    }

    # Enrich transfers with token metadata
    for tx in transfers:
        if not tx["token_address"].startswith("0x"):
            meta_config = native_token_meta.get(chain_id, native_token_meta[1])
            meta = {
                "name": meta_config["name"],
                "symbol": meta_config["symbol"], 
                "decimals": meta_config["decimals"]
            }
        else:
            meta = get_token_info(tx["token_address"])
        tx.update(meta)
        tx["value"] = tx["value"] / (10 ** meta["decimals"])


    # Save asset flows
    if transfers:
        df_assets = pd.DataFrame(transfers)
        df_assets = df_assets[["token_address", "name", "symbol", "from", "to", "value"]]
        df_assets.to_csv(ASSET_FLOWS_PATH, index=False)

    # === Step 8: State Changes Analysis ===
    state_changes = defaultdict(list)

    def extract_state_diffs(trace_item):
        if "action" in trace_item:
            contract_address = trace_item["action"].get("to", "").lower()
            if not contract_address: 
                contract_address = trace_item["action"].get("from", "").lower()
            if "diff" in trace_item and isinstance(trace_item["diff"], list):
                for change in trace_item["diff"]:
                    key = change.get("key")
                    val = change.get("val")
                    if key and val:
                        state_changes[contract_address].append((key, val))
        for sub in trace_item.get("subtraces", []):
            extract_state_diffs(sub)

    extract_state_diffs(trace_data)

    state_rows = []
    for contract, changes in state_changes.items():
        for key, val in changes:
            state_rows.append({
                "Contract": contract,
                "Storage Slot": key,
                "New Value": val
            })

    if state_rows:
        df_state = pd.DataFrame(state_rows)
        df_state.to_csv(STATE_CHANGES_PATH, index=False) #?

    print(f"Analysis complete. Generated files:")
    print(f"  - decoded_trace.json: Transaction trace")
    print(f"  - call_trace.csv: Call trace and Gas usage analysis ({len(call_trace)} calls)")
    print(f"  - asset_flows.csv: Token transfers ({len(transfers)} transfers)")
    print(f"  - state_changes.csv: State changes ({len(state_rows)} changes)")
    
    return True


def ask_for_optional_files(tx_hash, tx_dir):
    """Ask user if they want to add optional files for security analysis"""
    
    print(f"\n[2/3] OPTIONAL SECURITY FILES")
    print(f"="*50)
    
    output_dir = tx_dir
    url_file = os.path.join(output_dir, "url.txt")
    js_file = os.path.join(output_dir, "js.txt")
    
    print("You can optionally add files for enhanced security analysis:")
    print(f"  {url_file} - One URL per line for domain checking")
    print(f"  {js_file} - JavaScript code for pattern analysis")
    
    while True:
        choice = input("\nDo you want to add optional files? (y/n/skip): ").strip().lower()
        
        if choice in ['n', 'no', 'skip', '']:
            print("Skipping optional files...")
            return
        elif choice in ['y', 'yes']:
            break
        else:
            print("Please enter 'y' for yes or 'n' for no")
    
    # URL file
    while True:
        add_urls = input("Add URL file? (y/n): ").strip().lower()
        if add_urls in ['y', 'yes']:
            print(f"\nCreate {url_file} with URLs (one per line):")
            print("Enter URLs (press Enter twice to finish):")
            urls = []
            while True:
                url = input("URL: ").strip()
                if not url:
                    break
                urls.append(url)
            
            if urls:
                with open(url_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(urls))
                print(f"Created {url_file} with {len(urls)} URLs")
            break
        elif add_urls in ['n', 'no', '']:
            break
    
    # JavaScript file
    while True:
        add_js = input("Add JavaScript file? (y/n): ").strip().lower()
        if add_js in ['y', 'yes']:
            print(f"\nCreate {js_file}:")
            print("Paste JavaScript code (press Ctrl+D when finished):")
            try:
                import sys
                js_content = sys.stdin.read()
                if js_content.strip():
                    with open(js_file, 'w', encoding='utf-8') as f:
                        f.write(js_content)
                    print(f"Created {js_file}")
            except:
                print("Error reading JavaScript content")
            break
        elif add_js in ['n', 'no', '']:
            break

# root cuase: 1.run_transaction_analysis 2. ask_for_optional_files 3. security_checker.analyze_transaction_output 