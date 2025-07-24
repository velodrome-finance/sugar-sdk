# @Claude we are primarily relying on https://github.com/ethereum-optimism/supersim and its dependencies here

from dotenv import dotenv_values
from typing import Tuple, List
from dataclasses import dataclass
import subprocess, os, time, sys, logging, yaml
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='🍯 %(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuration dataclasses based on honey.yaml structure

@dataclass
class TokenBalance:
    """Token balance configuration"""
    token: str; address: str; amount: int; holder: str

@dataclass
class ChainConfig:
    """Chain configuration"""
    name: str; id: str; balance: List[TokenBalance]; port: int

@dataclass
class Honey:
    """Main configuration class"""
    wallet: str; chains: List[ChainConfig]; starting_port: int
    
    @staticmethod
    def from_config(config_path: str = "honey.yaml") -> 'Honey':
        """Load configuration from honey.yaml"""
        
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)

        # Extract configuration values
        starting_port = next((item.get('starting_port') for item in data['honey'] if isinstance(item, dict) and 'starting_port' in item), 4444)
        
        # Extract wallet private key
        wallet_item = next((item for item in data['honey'] if isinstance(item, dict) and 'wallet' in item), {})
        wallet_pk = next((w.get('pk') for w in wallet_item.get('wallet', []) if isinstance(w, dict) and 'pk' in w), None)
        
        if not wallet_pk: raise ValueError("No wallet private key found in honey.yaml")

        # Extract chains
        chains_list = []
        chains_item = next((item for item in data['honey'] if isinstance(item, dict) and 'chains' in item), {})
        for chain_data in chains_item.get('chains', []):
            if chain_data.get('name'):
                balance_list = [
                    TokenBalance(
                        token=b.get('token', ''),
                        address=b.get('address', ''),
                        amount=int(b.get('amount', 0)),
                        holder=b.get('holder', '')
                    ) for b in chain_data.get('balance', []) if isinstance(b, dict)
                ]
                chains_list.append(ChainConfig(
                    name=chain_data.get('name', ''),
                    id=chain_data.get('id', ''),
                    balance=balance_list,
                    port=starting_port + len(chains_list)
                ))

        honey_config = Honey(
            wallet=wallet_pk,
            chains=chains_list,
            starting_port=starting_port
        )
        
        logger.info("🍯 Loaded Honey configuration:")
        logger.info(f"  Wallet: {honey_config.wallet[:10]}...")
        logger.info(f"  Chains: {len(honey_config.chains)} configured")

        return honey_config

# Load configuration from honey.yaml (mandatory)  
honey_config = Honey.from_config()

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
                "--rpc-url", f"http://localhost:{honey_config.starting_port}"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip(): return True
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError): pass
        time.sleep(2)
    return False

def create_wallet() -> Tuple[str, str]:
    """Load wallet from honey config and return address and private key"""
    try:
        # Derive address from private key
        result = subprocess.run([
            "cast", "wallet", "address", 
            "--private-key", honey_config.wallet
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            address = result.stdout.strip()
            logger.info(f"Using wallet from honey config: {address}")
            return address, honey_config.wallet
        else:
            logger.error(f"Failed to derive address from honey config private key: {result.stderr}")
            raise Exception("Failed to create wallet from honey config")
    except Exception as e:
        logger.error(f"Error using honey config private key: {e}")
        raise
    
def check_eth_balance(address, chain_port):
    """Check ETH balance for an address on a specific chain"""
    try:
        result = subprocess.run([
            "cast", "balance", address, 
            "--rpc-url", f"http://localhost:{chain_port}"
        ], capture_output=True, text=True)
        
        if result.returncode == 0: return int(result.stdout.strip())
        else:
            logger.debug(f"Balance check failed for port {chain_port}: {result.stderr}")
            return None
    except Exception as e:
        logger.error(f"Error checking balance on port {chain_port}: {e}")
        return None

def check_token_balance(wallet_address: str, chain_port: int, token_address: str) -> int:
    """Check ERC20 token balance on a specific chain - returns raw amount"""
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
            return int(balance_str)
        else:
            logger.debug(f"Token balance check failed for {token_address} on port {chain_port}: {result.stderr}")
            return 0
    except Exception as e:
        logger.error(f"Error checking token balance for {token_address} on port {chain_port}: {e}")
        return 0



def add_tokens_by_address(wallet_address: str, token_requests: list) -> None:
    """Add multiple tokens to wallet using token addresses directly
    
    Args:
        wallet_address: The wallet to fund
        token_requests: List of dicts with 'token' (address), 'chain', 'amount', 'holder' keys
        Example: [{"token": "0x9560e827af36c94d2ac33a39bce1fe78631088db", "chain": "OP", "amount": "10000000000000000000", "holder": "0x..."}]
    """
    def process_token_request(request, delay_seconds=0):
        """Process a single token request with retry logic for underpriced transactions"""
        # Add delay to prevent nonce conflicts when using same holder
        if delay_seconds > 0: time.sleep(delay_seconds)

        token_address, chain_name, amount, large_holder = request["token"], request["chain"], request["amount"], request["holder"] 
        chain_config = next((c for c in honey_config.chains if c.name == chain_name), None)
        if not chain_config: raise ValueError(f"Chain {chain_name} not found in honey config")

        chain = {"name": chain_config.name, "id": chain_config.id, "port": chain_config.port}
        
        max_retries, retry_delay = 3, 2.0

        for attempt in range(max_retries + 1):
            try:
                # Impersonate the large holder
                impersonate_result = subprocess.run([
                    "cast", "rpc", "anvil_impersonateAccount", large_holder,
                    "--rpc-url", f"http://localhost:{chain['port']}"
                ], capture_output=True, text=True)
                
                if impersonate_result.returncode != 0: raise Exception(f"Failed to impersonate account {large_holder} on {chain_name}")

                # Transfer tokens using raw amount
                transfer_result = subprocess.run([
                    "cast", "send", token_address,
                    "transfer(address,uint256)", wallet_address, str(amount),
                    "--rpc-url", f"http://localhost:{chain['port']}",
                    "--from", large_holder, "--unlocked"
                ], capture_output=True, text=True)
                
                if transfer_result.returncode == 0:
                    logger.info(f"  ✓ Successfully added {amount} tokens ({token_address[:10]}...) on {chain_name}")
                    return  # Success, exit retry loop
                else:
                    error_msg = transfer_result.stderr
                    
                    # Check if it's an underpriced transaction error
                    if "replacement transaction underpriced" in error_msg or "underpriced" in error_msg:
                        if attempt < max_retries:
                            logger.warning(f"  ⚠️  Underpriced transaction on {chain_name}, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries + 1})")
                            time.sleep(retry_delay)
                            retry_delay *= 1.5  # Exponential backoff
                            continue
                        else:
                            logger.error(f"Failed to transfer tokens on {chain_name} after {max_retries + 1} attempts: {error_msg}")
                    else:
                        logger.error(f"Failed to transfer tokens on {chain_name}: {error_msg}")
                        return  # Non-retryable error, exit
                        
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"  ⚠️  Error on {chain_name}, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5
                    continue
                else:
                    logger.error(f"Error adding tokens on {chain_name} after {max_retries + 1} attempts: {e}")
                    return
    
    # Process token requests in parallel with retry logic handling conflicts
    max_workers = min(len(token_requests), 4)  # Limit to 4 concurrent operations
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_token_request, request) for request in token_requests]
        for future in as_completed(futures):
            try:
                future.result()  # This will raise any exception that occurred
            except Exception as e:
                logger.error(f"Token request failed: {e}")


def check_token_balances_all_chains(wallet_address: str) -> None:
    """Check ETH and token balances across all configured chains"""
    logger.info("Checking balances across all chains:")
    
    def check_chain_balances(chain_config):
        """Check balances for a single chain"""
        # Check ETH balance
        eth_balance = check_eth_balance(wallet_address, chain_config.port)
        eth_str = f"{eth_balance} ETH" if eth_balance is not None else "Failed"
        
        # Check token balances for tokens configured on this chain
        token_balances = []
        for token_config in chain_config.balance:
            token_balance = check_token_balance(wallet_address, chain_config.port, token_config.address)
            if token_balance > 0: token_balances.append(f"{token_balance} {token_config.token}")
        
        # Format output
        token_str = ""
        if token_balances: token_str = ", " + ", ".join(token_balances)

        return chain_config.name, eth_str, token_str
    
    # Process all chains in parallel
    max_workers = min(len(honey_config.chains), 4)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(check_chain_balances, chain_config) 
                  for chain_config in honey_config.chains]
        
        # Collect results and log them in order
        results = []
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Error checking chain balances: {e}")
        
        # Sort results by chain name for consistent output
        results.sort(key=lambda x: x[0])
        
        # Log all results
        for chain_name, eth_str, token_str in results:
            if token_str is None:  # Error case
                logger.warning(f"  {chain_name}: {eth_str}")
            else:
                logger.info(f"  {chain_name}: {eth_str}{token_str}")

def run_supersim():
    logger.info("Starting supersim in background mode...")
    process = subprocess.Popen([
        "supersim", "fork", 
        "--l2.host=0.0.0.0", 
        f"--l2.starting.port={honey_config.starting_port}",
        f"--chains={','.join([chain.name.lower() for chain in honey_config.chains])}"
    ], env=os.environ.copy() | dotenv_values(".env"))    
    
    logger.info("Waiting for supersim to be ready...")

    if check_supersim_ready():
        logger.info("Supersim started successfully. Listening on ports:")
        for chain in honey_config.chains:
            logger.info(f"  {chain.name} (Chain ID {chain.id}): http://localhost:{chain.port}")
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
    
    logger.info(f"Wallet loaded: {wallet_address}")

    # Add tokens to wallet from honey config
    token_requests = []
    for chain_config in honey_config.chains:
        for balance in chain_config.balance:
            token_requests.append({
                "token": balance.address,  # Using address as token identifier
                "chain": chain_config.name,
                "amount": str(balance.amount),  # Convert int to string for subprocess
                "holder": balance.holder  # Use custom holder from config
            })
    
    if token_requests:
        logger.info("🍯 Adding tokens from honey.yaml configuration...")
        add_tokens_by_address(wallet_address, token_requests)
    else:
        logger.info("🍯 No token balances configured in honey.yaml")
    
    # Check final balances (ETH + tokens)
    check_token_balances_all_chains(wallet_address)
    
    try:
        process.wait()
    except KeyboardInterrupt:
        logger.info("Shutting down supersim...")
        process.terminate()
        process.wait()
