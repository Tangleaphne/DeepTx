import subprocess
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def run_heimdall(command, rpc_url=None, tx_hash=None, tx_dir=None):
    """Run a heimdall command with optional RPC URL and selectively save trace output."""
    if rpc_url:
        command += ['--rpc-url', rpc_url]

    result = subprocess.run(
        ['heimdall'] + command + ['-q'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    if result.returncode != 0:
        logging.error(f"Command failed: {stderr}")
        sys.exit(1)

    if tx_hash and command[0] == 'inspect':
        out_dir = tx_dir
        os.makedirs(out_dir, exist_ok=True)

        filtered_output = ""
        found = False
        for line in stdout.splitlines():
            if not found and "heimdall::inspect(" in line:
                found = True
            if found:
                filtered_output += line + "\n"

        if not found:
            logging.warning("Could not find 'heimdall::inspect(' in stdout, saving full stdout instead.")
            filtered_output = stdout

    return stdout


def decompile_bytecode(bytecode, name='Contract', include_sol=True, include_yul=False, use_default=True, rpc_url=None, output=None):
    """Decompile contract bytecode, optionally inferring output directory."""
    command = ['decompile', bytecode, '-n', name]

    if include_sol:
        command.append('--include-sol')
    if include_yul:
        command.append('--include-yul')
    if use_default:
        command.append('--default')

    if output:
        command += ['--output', output]  

    return run_heimdall(command, rpc_url)


def inspect_transaction(tx_hash, api_key=None, rpc_url=None, tx_dir=None):
    """Inspect Ethereum transaction trace."""
    command = ['inspect', tx_hash]
    if api_key:
        command += ['-t', api_key]

    output = run_heimdall(command, rpc_url, tx_hash, tx_dir)
    if not output:
        logging.error(f"Failed to inspect transaction {tx_hash}")
        return None
