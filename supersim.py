# @Claude we are primarily relying on https://github.com/ethereum-optimism/supersim and its dependencies here

from dotenv import dotenv_values
from typing import Optional, Tuple
import subprocess, os, time, sys, logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='🍭 %(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# supported chains: op, base, lisk, uni

starting_port = 4444
chains = [chain | { "port": starting_port + i } for i, chain in enumerate([
    { "name": "OP", "id": "10" },
    { "name": "Unichain", "id": "130" },
    { "name": "Lisk", "id": "1135" },
    { "name": "Base", "id": "8453"}
])]

def check_supersim_ready(timeout_seconds=60):
    """Check if supersim is ready by calling a test contract"""
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        try:
            result = subprocess.run([
                "cast", "call",
                # TODO: figure out what this address is supposed to be
                "0x7F6D3A4c8a1111DDbFe282794f4D608aB7Cb23A2", 
                "MAX_TOKENS()(uint256)", 
                "--rpc-url", f"http://localhost:{starting_port}"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip(): return True
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass
        time.sleep(2)
    return False

def create_wallet() -> Tuple[Optional[str], Optional[str]]:
    """Create a new wallet and return address and private key"""
    try:
        result = subprocess.run(["cast", "wallet", "new"], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            address = None
            private_key = None
            
            for line in lines:
                if line.startswith('Address:'):
                    address = line.split(':', 1)[1].strip()
                elif line.startswith('Private key:'):
                    private_key = line.split(':', 1)[1].strip()

            if address and private_key:
                return address, private_key
        
        logger.error(f"Failed to create wallet: {result.stderr}")
        return None, None
    except Exception as e:
        logger.error(f"Error creating wallet: {e}")
        return None, None

def check_balance(address, chain_port):
    """Check ETH balance for an address on a specific chain"""
    try:
        result = subprocess.run([
            "cast", "balance", address, 
            "--rpc-url", f"http://localhost:{chain_port}"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            return int(result.stdout.strip())
        else:
            logger.debug(f"Balance check failed for port {chain_port}: {result.stderr}")
            return None
    except Exception as e:
        logger.error(f"Error checking balance on port {chain_port}: {e}")
        return None

def check_balances_all_chains(wallet_address: str) -> None:
    """Check ETH balances across all configured chains"""
    logger.info("Checking ETH balances across all chains:")
    for chain in chains:
        balance = check_balance(wallet_address, chain['port'])
        if balance is not None:
            eth_balance = balance / 10**18  # Convert wei to ETH
            logger.info(f"  {chain['name']}: {eth_balance:.6f} ETH")
        else:
            logger.warning(f"  {chain['name']}: Failed to check balance")

def run_supersim():
    logger.info("Starting supersim in background mode...")
    process = subprocess.Popen([
        "supersim", "fork", 
        "--l2.host=0.0.0.0", 
        f"--l2.starting.port={starting_port}",
        f"--chains={','.join([chain['name'].lower() for chain in chains])}"
    ], env=os.environ.copy() | dotenv_values(".env"))    
    
    logger.info("Waiting for supersim to be ready...")
    if check_supersim_ready():
        logger.info("Supersim started successfully. Listening on ports:")
        for chain in chains:
            logger.info(f"  {chain['name']} (Chain ID {chain['id']}): http://localhost:{chain['port']}")
        return process
    else:
        logger.error("Supersim failed to start or become ready within timeout")
        process.terminate()
        sys.exit(1)

if __name__ == "__main__":
    process = run_supersim()
    
    # Create wallet for cross-chain operations
    logger.info("Creating new wallet...")
    wallet_address, private_key = create_wallet()
    
    if wallet_address and private_key:
        logger.info(f"Wallet created: {wallet_address}")
        
        # Check balance on all chains
        check_balances_all_chains(wallet_address)
    else:
        logger.error("Failed to create wallet")
        process.terminate()
        sys.exit(1)
    
    try:
        process.wait()
    except KeyboardInterrupt:
        logger.info("Shutting down supersim...")
        process.terminate()
        process.wait()


# @Claude: here are some additional commands that we have tested for various ops
# we will likely want to run these using subprocess or smth along these lines

# check my ETH balance on OP
# cast balance 0x1e7A6B63F98484514610A9F0D5b399d4F7a9b1dA --rpc-url http://127.0.0.1:4444

# check my ETH balance on Base
#cast balance 0x1e7A6B63F98484514610A9F0D5b399d4F7a9b1dA --rpc-url http://127.0.0.1:4445
# 3940090932400543
# Add my ETH balance on OP
# cast send 0x420beeF000000000000000000000000000000001 "mint(address _to, uint256 _amount)"  0x1e7A6B63F98484514610A9F0D5b399d4F7a9b1dA 1000  --rpc-url http://127.0.0.1:4444 --private-key PRIVATE_KEY
