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

# Configuration - set this to use a predefined wallet
# If None, a new wallet will be generated each time
PREDEFINED_PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"

starting_port = 4444
chains = [chain | { "port": starting_port + i } for i, chain in enumerate([
    { "name": "OP", "id": "10" },
    { "name": "Unichain", "id": "130" },
    { "name": "Lisk", "id": "1135" },
    { "name": "Base", "id": "8453"}
])]

# Token configurations
TOKENS = {
    "VELO": {
        "address": "0x9560e827af36c94d2ac33a39bce1fe78631088db",
        "decimals": 18,
        "symbol": "VELO",
        "large_holder": "0xF977814e90dA44bFA03b6295A0616a897441aceC",
        "chains": ["OP"]  # VELO is native to OP
    },
    "USDC": {
        "address": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
        "decimals": 6,
        "symbol": "USDC",
        "large_holder": "0xF977814e90dA44bFA03b6295A0616a897441aceC",  # Same large holder often has many tokens
        "chains": ["OP"]  # Native USDC on OP
    }
}


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
    """Create or load a wallet and return address and private key"""
    # Check if we have a predefined private key
    if PREDEFINED_PRIVATE_KEY:
        try:
            # Derive address from private key
            result = subprocess.run([
                "cast", "wallet", "address", 
                "--private-key", PREDEFINED_PRIVATE_KEY
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                address = result.stdout.strip()
                logger.info(f"Using predefined wallet: {address}")
                return address, PREDEFINED_PRIVATE_KEY
            else:
                logger.error(f"Failed to derive address from predefined private key: {result.stderr}")
        except Exception as e:
            logger.error(f"Error using predefined private key: {e}")
    
    # Generate new wallet if no predefined key or if predefined key failed
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
                logger.info(f"Generated new wallet: {address}")
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

def check_token_balance(wallet_address: str, chain_port: int, token_address: str, decimals: int) -> float:
    """Check ERC20 token balance on a specific chain"""
    try:
        result = subprocess.run([
            "cast", "call", token_address,
            "balanceOf(address)(uint256)", wallet_address,
            "--rpc-url", f"http://localhost:{chain_port}"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            balance_str = result.stdout.strip()
            # Handle scientific notation like "1000000000000000000000 [1e21]"
            if '[' in balance_str:
                balance_str = balance_str.split('[')[0].strip()
            return int(balance_str) / (10**decimals)
        else:
            logger.debug(f"Token balance check failed for {token_address} on port {chain_port}: {result.stderr}")
            return 0.0
    except Exception as e:
        logger.error(f"Error checking token balance for {token_address} on port {chain_port}: {e}")
        return 0.0

def add_tokens(wallet_address: str, chain_port: int, token_symbol: str, amount: float) -> bool:
    """Add tokens to wallet by impersonating a large holder"""
    if token_symbol not in TOKENS:
        logger.error(f"Unknown token: {token_symbol}")
        return False
    
    token_config = TOKENS[token_symbol]
    token_address = token_config["address"]
    decimals = token_config["decimals"]
    large_holder = token_config["large_holder"]
    amount_wei = int(amount * (10**decimals))
    
    try:
        # Impersonate the large holder
        impersonate_result = subprocess.run([
            "cast", "rpc", "anvil_impersonateAccount", large_holder,
            "--rpc-url", f"http://localhost:{chain_port}"
        ], capture_output=True, text=True)
        
        if impersonate_result.returncode != 0:
            logger.error(f"Failed to impersonate account on port {chain_port}: {impersonate_result.stderr}")
            return False
        
        # Transfer tokens
        transfer_result = subprocess.run([
            "cast", "send", token_address,
            "transfer(address,uint256)", wallet_address, str(amount_wei),
            "--rpc-url", f"http://localhost:{chain_port}",
            "--from", large_holder, "--unlocked"
        ], capture_output=True, text=True)
        
        if transfer_result.returncode == 0:
            return True
        else:
            logger.error(f"Failed to transfer {token_symbol} on port {chain_port}: {transfer_result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error adding {token_symbol} tokens on port {chain_port}: {e}")
        return False

def add_tokens_to_wallet(wallet_address: str, token_requests: list) -> None:
    """Add multiple tokens to wallet based on requests
    
    Args:
        wallet_address: The wallet to fund
        token_requests: List of dicts with 'token', 'chain', 'amount' keys
        Example: [{"token": "VELO", "chain": "OP", "amount": 1000.0}]
    """
    for request in token_requests:
        token_symbol = request["token"]
        chain_name = request["chain"]
        amount = request["amount"]
        
        # Find the chain port
        chain = next((c for c in chains if c['name'] == chain_name), None)
        if not chain:
            logger.error(f"Unknown chain: {chain_name}")
            continue
            
        # Check if token is available on this chain
        if token_symbol not in TOKENS:
            logger.error(f"Unknown token: {token_symbol}")
            continue
            
        if chain_name not in TOKENS[token_symbol]["chains"]:
            logger.warning(f"{token_symbol} not available on {chain_name}")
            continue
        
        logger.info(f"Adding {amount} {token_symbol} tokens on {chain_name}...")
        success = add_tokens(wallet_address, chain['port'], token_symbol, amount)
        if success:
            logger.info(f"  ✓ Successfully added {amount} {token_symbol} on {chain_name}")
        else:
            logger.warning(f"  ✗ Failed to add {token_symbol} on {chain_name}")

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

def check_token_balances_all_chains(wallet_address: str) -> None:
    """Check ETH and token balances across all configured chains"""
    logger.info("Checking balances across all chains:")
    for chain in chains:
        # Check ETH balance
        eth_balance = check_balance(wallet_address, chain['port'])
        eth_str = f"{eth_balance / 10**18:.6f} ETH" if eth_balance is not None else "Failed"
        
        # Check token balances for tokens available on this chain
        token_balances = []
        for token_symbol, token_config in TOKENS.items():
            if chain['name'] in token_config["chains"]:
                token_balance = check_token_balance(
                    wallet_address, 
                    chain['port'], 
                    token_config["address"], 
                    token_config["decimals"]
                )
                if token_balance > 0:
                    token_balances.append(f"{token_balance:.2f} {token_symbol}")
        
        # Format output
        token_str = ""
        if token_balances:
            token_str = ", " + ", ".join(token_balances)
        
        logger.info(f"  {chain['name']}: {eth_str}{token_str}")

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
        
        # Check initial balance on all chains
        check_balances_all_chains(wallet_address)
        
        # Fund wallet with ETH for gas fees
        # fund_wallet_all_chains(wallet_address)
        
        # Check balances after funding
        check_balances_all_chains(wallet_address)
        
        # Add tokens to wallet
        token_requests = [
            {"token": "VELO", "chain": "OP", "amount": 1000.0},
            {"token": "USDC", "chain": "OP", "amount": 5000.0}
        ]
        add_tokens_to_wallet(wallet_address, token_requests)

        # Check final balances (ETH + tokens)
        check_token_balances_all_chains(wallet_address)
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
