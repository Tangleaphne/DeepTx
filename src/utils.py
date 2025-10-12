from typing import List, Dict

def extract_call_trace_recursive(call_trace: dict, depth: int = 0, traces: List[Dict] = None) -> List[Dict]:
    if traces is None:
        traces = []
    
    from_addr = call_trace.get('from', '')
    to_addr = call_trace.get('to', '')
    call_type = call_trace.get('call_type', '')
    function_name = call_trace.get('function_name', '') or call_trace.get('function_selector', '')
    
    gas = call_trace.get('gas', 0)
    gas_used = call_trace.get('gas_used', 0)
    gas_remaining = gas - gas_used if gas and gas_used else 0
    
    traces.append({
        'depth': depth,
        'from': from_addr,
        'to': to_addr,
        'call_type': call_type,
        'function': function_name,
        'gas_allocated': gas,
        'gas_used': gas_used,
        'gas_remaining': gas_remaining
    })
    
    # Process subcalls
    calls = call_trace.get('calls')
    if calls and isinstance(calls, list):
        for subcall in calls:
            extract_call_trace_recursive(subcall, depth + 1, traces)
    
    return traces

def extract_all_call_traces(result: dict, exclude_types: List[str] = None) -> List[Dict]:
    traces = []
    
    call_trace = result.get('transaction', {}).get('transaction_info', {}).get('call_trace')
    
    if call_trace is None:
        return traces
    
    traces = extract_call_trace_recursive(call_trace, depth=0)
    
    if exclude_types:
        traces = [t for t in traces if t['call_type'] not in exclude_types]
    
    return traces

def extract_transfer_events(result: dict) -> List[Dict]:
    transfers = []
    
    if not result.get('transaction', {}).get('status', False):
        return transfers
    
    logs = result.get('transaction', {}).get('transaction_info', {}).get('logs')
    
    if logs is None:
        return transfers
    
    for log in logs:
        if log.get('name') == 'Transfer':
            inputs = log.get('inputs', [])
            
            from_addr = None
            to_addr = None
            value = None
            
            for input_item in inputs:
                param_name = input_item.get('name', '').lower()
                param_value = input_item.get('value')
                
                if param_name == 'from':
                    from_addr = param_value
                elif param_name == 'to':
                    to_addr = param_value
                elif param_name in ['value', 'amount', 'tokenid']:
                    value = param_value
            
            token_address = log.get('raw', {}).get('address', '')
            
            if from_addr and to_addr and value:
                transfers.append({
                    'token_address': token_address,
                    'name': '',  
                    'symbol': '',  
                    'from': from_addr,
                    'to': to_addr,
                    'value': str(value)
                })
    
    return transfers


def extract_eth_transfers(result: dict) -> List[Dict]:
    transfers = []
    
    balance_diff = result.get('transaction', {}).get('transaction_info', {}).get('balance_diff')
    
    if balance_diff is None:
        return transfers
    
    balance_changes = {}
    for change in balance_diff:
        addr = change.get('address', '')
        original = int(change.get('original', '0'))
        dirty = int(change.get('dirty', '0'))
        diff = dirty - original
        
        if diff != 0 and not change.get('is_miner', False):
            balance_changes[addr] = diff
    
    decreases = {addr: -diff for addr, diff in balance_changes.items() if diff < 0}
    increases = {addr: diff for addr, diff in balance_changes.items() if diff > 0}
    
    for from_addr, amount in decreases.items():
        for to_addr, recv_amount in increases.items():
            if amount == recv_amount:
                transfers.append({
                    'token_address': '0x0000000000000000000000000000000000000000',  
                    'name': 'Ethereum',
                    'symbol': 'ETH',
                    'from': from_addr,
                    'to': to_addr,
                    'value': str(amount)
                })
                break
    
    return transfers


def extract_asset_changes(result: dict) -> List[Dict]:
    transfers = []
    
    asset_changes = result.get('transaction', {}).get('transaction_info', {}).get('asset_changes')
    
    if asset_changes is None:
        return transfers
    
    for change in asset_changes:
        change_type = change.get('type', '').upper()
        
        if change_type in ['TRANSFER', 'ERC20_TRANSFER', 'ERC721_TRANSFER', 'ERC1155_TRANSFER']:
            token_info = change.get('token_info', {})
            
            token_address = (
                token_info.get('contract_address', '') or 
                change.get('token_address', '') or 
                change.get('asset', '')
            )
            
            transfers.append({
                'token_address': token_address,
                'name': token_info.get('name', ''),
                'symbol': token_info.get('symbol', ''),
                'from': change.get('from', ''),
                'to': change.get('to', ''),
                'value': str(change.get('amount', '') or change.get('value', '') or change.get('token_id', ''))
            })
    
    return transfers
