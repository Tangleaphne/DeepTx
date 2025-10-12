#!/usr/bin/env python3
from typing import List, Dict

def extract_transfer_events(result: dict) -> List[Dict]:
    """
    Extract Transfer events from simulation result
    
    Args:
        result: Simulation result JSON
    
    Returns:
        List of transfer records
    """
    transfers = []
    
    # Check if transaction succeeded
    if not result.get('transaction', {}).get('status', False):
        return transfers
    
    # Extract from logs
    logs = result.get('transaction', {}).get('transaction_info', {}).get('logs')
    
    # Handle null logs
    if logs is None:
        return transfers
    
    for log in logs:
        # Look for Transfer events (ERC20/ERC721)
        if log.get('name') == 'Transfer':
            inputs = log.get('inputs', [])
            
            # Parse inputs
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
            
            # Get token contract address
            token_address = log.get('raw', {}).get('address', '')
            
            if from_addr and to_addr and value:
                transfers.append({
                    'token_address': token_address,
                    'name': '',  # Will be filled if available
                    'symbol': '',  # Will be filled if available
                    'from': from_addr,
                    'to': to_addr,
                    'value': str(value)
                })
    
    return transfers


def extract_eth_transfers(result: dict) -> List[Dict]:
    """
    Extract ETH transfers from balance_diff
    
    Args:
        result: Simulation result JSON
    
    Returns:
        List of ETH transfer records
    """
    transfers = []
    
    balance_diff = result.get('transaction', {}).get('transaction_info', {}).get('balance_diff')
    
    # Handle null balance_diff
    if balance_diff is None:
        return transfers
    
    # Group balance changes to identify transfers
    balance_changes = {}
    for change in balance_diff:
        addr = change.get('address', '')
        original = int(change.get('original', '0'))
        dirty = int(change.get('dirty', '0'))
        diff = dirty - original
        
        if diff != 0 and not change.get('is_miner', False):
            balance_changes[addr] = diff
    
    # Match decreases with increases
    decreases = {addr: -diff for addr, diff in balance_changes.items() if diff < 0}
    increases = {addr: diff for addr, diff in balance_changes.items() if diff > 0}
    
    for from_addr, amount in decreases.items():
        for to_addr, recv_amount in increases.items():
            if amount == recv_amount:
                transfers.append({
                    'token_address': '0x0000000000000000000000000000000000000000',  # ETH
                    'name': 'Ethereum',
                    'symbol': 'ETH',
                    'from': from_addr,
                    'to': to_addr,
                    'value': str(amount)
                })
                break
    
    return transfers


def extract_asset_changes(result: dict) -> List[Dict]:
    """
    Extract asset changes from Tenderly's asset_changes field
    
    Args:
        result: Simulation result JSON
    
    Returns:
        List of asset transfer records
    """
    transfers = []
    
    asset_changes = result.get('transaction', {}).get('transaction_info', {}).get('asset_changes')
    
    # Handle null asset_changes
    if asset_changes is None:
        return transfers
    
    for change in asset_changes:
        change_type = change.get('type', '').upper()
        
        # Handle different asset types
        if change_type in ['TRANSFER', 'ERC20_TRANSFER', 'ERC721_TRANSFER', 'ERC1155_TRANSFER']:
            token_info = change.get('token_info', {})
            
            # Get token address from multiple possible locations
            token_address = (
                token_info.get('contract_address', '') or  # Most common location
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
