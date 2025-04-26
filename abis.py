# download and save abis from etherscan

from dotenv import load_dotenv
load_dotenv()

from sugar.abi import download_contract_abi
from sugar.config import make_op_chain_settings

settings =  make_op_chain_settings()
abi_config = {
    'sugar': settings.sugar_contract_addr,
    'slipstream': settings.slipstream_contract_addr,
    'nfpm': settings.nfpm_contract_addr,
    'price_oracle': settings.price_oracle_contract_addr,
    'router': settings.router_contract_addr,
    'quoter': settings.quoter_contract_addr,
    'swapper': settings.swapper_contract_addr,
}
for name, addr in abi_config.items():
    download_contract_abi(name=name, address=addr)
    print(f"Downloaded {name} ABI")