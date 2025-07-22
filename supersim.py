# @Claude we are primarily relying on https://github.com/ethereum-optimism/supersim and its dependencies here

from dotenv import dotenv_values
from typing import Tuple, List
from dataclasses import dataclass
import subprocess, os, time, sys, logging, yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='🍭 %(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuration dataclasses based on honey.yaml structure

@dataclass
class TokenBalance:
    """Token balance configuration"""
    token: str  # Token name/symbol
    address: str  # Token contract address
    amount: int  # Amount in wei as integer

@dataclass
class ChainConfig:
    """Chain configuration"""
    name: str
    id: str
    balance: List[TokenBalance]

@dataclass
class Honey:
    """Main configuration class"""
    wallet: str  # Private key directly
    chains: List[ChainConfig]
    
    @staticmethod
    def from_config(config_path: str = "honey.yaml") -> 'Honey':
        """Load configuration from honey.yaml"""
        
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
        # Parse the list structure in honey.yaml
        honey_data, wallet_pk, chains_list = data['honey'], None, []

        for item in honey_data:
            if isinstance(item, dict):
                # Check for wallet config
                if 'wallet' in item:
                    wallet_list = item['wallet']
                    for wallet_item in wallet_list:
                        if isinstance(wallet_item, dict) and 'pk' in wallet_item:
                            wallet_pk = wallet_item['pk']
                            break
                
                # Check for chains config
                elif 'chains' in item:
                    for chain_data in item['chains']:
                        if isinstance(chain_data, dict) and 'name' in chain_data:
                            # Parse balance list
                            balance_list = []
                            if 'balance' in chain_data:
                                for balance_item in chain_data['balance']:
                                    if isinstance(balance_item, dict):
                                        balance_list.append(TokenBalance(
                                            token=balance_item['token'],
                                            address=balance_item['address'],
                                            amount=int(balance_item['amount'])  # Convert to int
                                        ))
                            chains_list.append(ChainConfig(
                                name=chain_data['name'],
                                id=chain_data['id'],
                                balance=balance_list
                            ))
        
        if not wallet_pk:
            raise ValueError("No wallet private key found in honey.yaml")
        
        honey_config = Honey(
            wallet=wallet_pk,
            chains=chains_list
        )
        
        logger.info("🍭 Loaded Honey configuration:")
        logger.info(f"  Wallet: {honey_config.wallet[:10]}...")
        logger.info(f"  Chains: {len(honey_config.chains)} configured")
        for chain in honey_config.chains:
            logger.info(f"    {chain.name} (ID: {chain.id}) - {len(chain.balance)} token balances")
            for balance in chain.balance:
                logger.info(f"      {balance.token} ({balance.address[:10]}...): {balance.amount}")
        
        return honey_config

# supported chains: op, base, lisk, uni

# Load configuration from honey.yaml (mandatory)
honey_config = Honey.from_config()
PREDEFINED_PRIVATE_KEY = honey_config.wallet
starting_port = 4444

# Build chains configuration from honey.yaml
chains = [{"name": chain.name, "id": chain.id, "port": starting_port + i} 
          for i, chain in enumerate(honey_config.chains)]

# Default large holder for token transfers
DEFAULT_LARGE_HOLDER = "0xF977814e90dA44bFA03b6295A0616a897441aceC"

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

def check_token_balance(wallet_address: str, chain_port: int, token_address: str) -> int:
    """Check ERC20 token balance on a specific chain - returns raw wei amount"""
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
        token_requests: List of dicts with 'token' (address), 'chain', 'amount' keys
        Example: [{"token": "0x9560e827af36c94d2ac33a39bce1fe78631088db", "chain": "OP", "amount": "10000000000000000000"}]
    """
    for request in token_requests:
        token_address = request["token"]
        chain_name = request["chain"]
        amount = request["amount"]  # Raw amount as string from config
        
        # Find the chain port
        chain = next((c for c in chains if c['name'] == chain_name), None)
        if not chain:
            logger.error(f"Unknown chain: {chain_name}")
            continue
        
        # Use the default large holder
        large_holder = DEFAULT_LARGE_HOLDER
        
        try:
            # Impersonate the large holder
            impersonate_result = subprocess.run([
                "cast", "rpc", "anvil_impersonateAccount", large_holder,
                "--rpc-url", f"http://localhost:{chain['port']}"
            ], capture_output=True, text=True)
            
            if impersonate_result.returncode != 0:
                logger.error(f"Failed to impersonate account on {chain_name}: {impersonate_result.stderr}")
                continue
            
            # Transfer tokens using raw amount
            transfer_result = subprocess.run([
                "cast", "send", token_address,
                "transfer(address,uint256)", wallet_address, str(amount),
                "--rpc-url", f"http://localhost:{chain['port']}",
                "--from", large_holder, "--unlocked"
            ], capture_output=True, text=True)
            
            if transfer_result.returncode == 0:
                logger.info(f"  ✓ Successfully added {amount} wei tokens ({token_address[:10]}...) on {chain_name}")
            else:
                logger.error(f"Failed to transfer tokens on {chain_name}: {transfer_result.stderr}")
        except Exception as e:
            logger.error(f"Error adding tokens on {chain_name}: {e}")


def check_token_balances_all_chains(wallet_address: str) -> None:
    """Check ETH and token balances across all configured chains"""
    logger.info("Checking balances across all chains:")
    
    for chain_config in honey_config.chains:
        # Find the corresponding chain with port info
        chain = next((c for c in chains if c['name'] == chain_config.name), None)
        if not chain:
            logger.warning(f"Chain {chain_config.name} not found in port configuration")
            continue
            
        # Check ETH balance
        eth_balance = check_balance(wallet_address, chain['port'])
        eth_str = f"{eth_balance} wei ETH" if eth_balance is not None else "Failed"
        
        # Check token balances for tokens configured on this chain
        token_balances = []
        for token_config in chain_config.balance:
            token_balance = check_token_balance(
                wallet_address, 
                chain['port'], 
                token_config.address
            )
            if token_balance > 0:
                token_balances.append(f"{token_balance} wei {token_config.token}")
        
        # Format output
        token_str = ""
        if token_balances:
            token_str = ", " + ", ".join(token_balances)
        
        logger.info(f"  {chain_config.name}: {eth_str}{token_str}")

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
    
    logger.info(f"Wallet loaded: {wallet_address}")
    
    # Check initial balance on all chains
    check_token_balances_all_chains(wallet_address)
    
    # Add tokens to wallet from honey config
    token_requests = []
    for chain_config in honey_config.chains:
        for balance in chain_config.balance:
            token_requests.append({
                "token": balance.address,  # Using address as token identifier
                "chain": chain_config.name,
                "amount": str(balance.amount)  # Convert int to string for subprocess
            })
    
    if token_requests:
        logger.info("🍭 Adding tokens from honey.yaml configuration...")
        add_tokens_by_address(wallet_address, token_requests)
    else:
        logger.info("🍭 No token balances configured in honey.yaml")
    
    # Check final balances (ETH + tokens)
    check_token_balances_all_chains(wallet_address)
    
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
