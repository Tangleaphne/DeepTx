from typing import List, Dict


def extract_call_trace_recursive(call_trace: dict, depth: int = 0, traces: List[Dict] = None) -> List[Dict]:
    """
    Recursively extract call trace information
    
    Args:
        call_trace: Call trace object
        depth: Current call depth
        traces: List to accumulate trace records
    
    Returns:
        List of call trace records
    """
    if traces is None:
        traces = []
    
    # Extract current call information
    from_addr = call_trace.get('from', '')
    to_addr = call_trace.get('to', '')
    call_type = call_trace.get('call_type', '')
    function_name = call_trace.get('function_name', '') or call_trace.get('function_selector', '')
    
    # Gas information
    gas = call_trace.get('gas', 0)
    gas_used = call_trace.get('gas_used', 0)
    gas_remaining = gas - gas_used if gas and gas_used else 0
    
    # Add current call to traces
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
    
    # Process nested calls (subcalls)
    calls = call_trace.get('calls')
    if calls and isinstance(calls, list):
        for subcall in calls:
            extract_call_trace_recursive(subcall, depth + 1, traces)
    
    return traces


def extract_all_call_traces(result: dict, exclude_types: List[str] = None) -> List[Dict]:
    """
    Extract all call traces from simulation result
    
    Args:
        result: Simulation result JSON
        exclude_types: List of call types to exclude (e.g., ['JUMPDEST', 'STATICCALL'])
    
    Returns:
        List of all call trace records
    """
    traces = []
    
    # Get the main call trace
    call_trace = result.get('transaction', {}).get('transaction_info', {}).get('call_trace')
    
    if call_trace is None:
        return traces
    
    # Extract traces recursively starting from depth 0
    traces = extract_call_trace_recursive(call_trace, depth=0)
    
    # Filter out excluded call types
    if exclude_types:
        traces = [t for t in traces if t['call_type'] not in exclude_types]
    
    return traces
