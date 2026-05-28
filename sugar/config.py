__all__ = ['hyperlane_relay_url', 'hyperlane_relayers', 'XCHAIN_GAS_LIMIT_UPPERBOUND', 'base_default_settings',
           'superchain_default_settings', 'GetEnv',
           'ChainSettings', 'validate_settings', 'get_env', 'make_settings', 'make_op_chain_settings',
           'make_base_chain_settings', 'make_lisk_chain_settings', 'make_uni_chain_settings',
           'make_mode_chain_settings', 'make_fraxtal_chain_settings', 'make_ink_chain_settings',
           'make_soneium_chain_settings', 'make_superseed_chain_settings', 'make_celo_chain_settings']

import os
from dataclasses import dataclass, make_dataclass, fields
from .helpers import normalize_address
from typing import List, Callable, Any, Dict

hyperlane_relay_url = "https://offchain-lookup.services.hyperlane.xyz/callCommitments/calls"
hyperlane_relayers = ["0x74Cae0ECC47B02Ed9B9D32E000Fd70B9417970C5", "0x09B96417602Ed6AC76651F7A8c4860E60e3aA6d0"]
XCHAIN_GAS_LIMIT_UPPERBOUND = 600000

base_default_settings = {
  "price_batch_size": int(os.getenv("SUGAR_PRICE_BATCH_SIZE","40")),
  "price_threshold_filter": int(os.getenv("SUGAR_PRICE_THRESHOLD_FILTER","10")),
  "pagination_limit": int(os.getenv("SUGAR_PAGINATION_LIMIT","2000")),
  # adaptive pool pagination: page = pool_count // target_calls, clamped to [min, max]
  "pool_pagination_target_calls": int(os.getenv("SUGAR_POOL_PAGINATION_TARGET_CALLS","90")),
  "pool_pagination_min_size": int(os.getenv("SUGAR_POOL_PAGINATION_MIN_SIZE","10")),
  "pool_pagination_max_size": int(os.getenv("SUGAR_POOL_PAGINATION_MAX_SIZE","400")),
  "native_token_symbol": "ETH",
  "native_token_decimals": 18,
  "swap_slippage": 0.01,
  "pricing_cache_timeout_seconds": 5,
  "threading_max_workers": 5
}

# Settings shared across Velo "leaf" superchain deployments (Lisk, Uni, Mode,
# Fraxtal, Ink, Soneium, Superseed, Celo). Each chain's make_*_chain_settings
# spreads these defaults then overrides chain-specific addresses.
superchain_default_settings = {
    "wrapped_native_token_addr": "0x4200000000000000000000000000000000000006",
    "bridge_token_addr": "0x1217BfE6c773EEC6cc4A38b5Dc45B92292B6E189",
    "message_module_contract_addr": "0x2BbA7515F7cF114B45186274981888D8C2fBA15E",
    "slipstream_factory_addr": "0x718E46d0962A66942E233760a8bd6038Ce54EdCD",
    "old_slipstream_factory_addr": "0x04625B046C69577EfC40e6c0Bb83CDBAfab5a55F",
    "nfpm_contract_addr": "0xefD0f78F93f578036AE34D52A813a4BE7D8D2D52",
    "router_contract_addr": "0x3a63171DD9BebF4D07BC782FECC7eb0b890C2A45",
    "quoter_contract_addr": "0x910c887157A0B6F048dA241e013fedbd5323851F",
    "swapper_contract_addr": "0xcAF22ce31298CF2BF1D152862F80216478ad7c67",
    "token_addr": "",
    "excluded_tokens_addrs": "",
}

@dataclass
class ChainSettings:
    # chain IDs come from: https://chainlist.org/
    chain_id: str
    chain_name: str
    wrapped_native_token_addr: str
    rpc_uri: str
    # interchain account address for superswaps
    interchain_router_contract_addr: str
    # bridge contract for superswaps
    bridge_contract_addr: str
    # bridge token address for superswaps
    bridge_token_addr: str
    # message module contract address for superswaps
    message_module_contract_addr: str
    sugar_contract_addr: str
    sugar_rewards_contract_addr: str
    # slipstream operates on concentrated liquidity (CL) pools
    slipstream_contract_addr: str
    # slipstream pool factories; used to OR a bitmask into the mixed-route
    # quoter path so the quoter resolves the right pool. The `new` factory
    # uses bitmask 0x080000, the `old` factory uses bitmask 0x100000.
    slipstream_factory_addr: str
    old_slipstream_factory_addr: str
    # Non-Fungible Position Manager for CL pools
    nfpm_contract_addr: str
    price_oracle_contract_addr: str
    router_contract_addr: str
    quoter_contract_addr: str
    # aka Universal Router
    swapper_contract_addr: str
    token_addr: str
    stable_token_addr: str
    connector_tokens_addrs: List[str]
    # tokens to exclude from quote search graph
    excluded_tokens_addrs: List[str]
    # default swap slippage in % (0.0-1.0)
    swap_slippage: float
    price_batch_size: int
    price_threshold_filter: int
    pagination_limit: int
    pool_pagination_target_calls: int
    pool_pagination_min_size: int
    pool_pagination_max_size: int
    native_token_symbol: str
    native_token_decimals: int
    # how often to check for new prices
    pricing_cache_timeout_seconds: int
    # how many max workers to use for threading in sync methods
    threading_max_workers: int

    def __str__(self):
        # go over all attributes of self
        lines = ["🍭 Chain settings:","----------------"]
        attributes = [attr for attr in dir(self) if not attr.startswith('_')]
        for attr in attributes:
            # Skip methods
            if callable(getattr(self, attr)): continue
            value = getattr(self, attr)
            if isinstance(value, list):
                value = "\n" + "\n".join([f"{' ' * 4 }- {v}" for v in value])
            lines.append(f"{attr}: {value}")
        return "\n".join(lines)
    
    def __repr__(self): return str(self)

def validate_settings(settings: ChainSettings) -> ChainSettings:
    # TODO: this should actually validate stuff, duh
    floats = ["swap_slippage"]
    ints = ["price_batch_size", "price_threshold_filter", "pagination_limit", "native_token_decimals",
            "pricing_cache_timeout_seconds", "threading_max_workers",
            "pool_pagination_target_calls", "pool_pagination_min_size", "pool_pagination_max_size"]
    for k in floats: setattr(settings, k, float(getattr(settings, k)))
    for k in ints: setattr(settings, k, int(getattr(settings, k)))
    return settings

def get_env(key: str, default: Any) -> Any: return os.getenv(key, default)

GetEnv = Callable[[str, Any], Any]

def make_settings(chain_id: str, chain_name: str, chain_settings: Dict[str, Any], get_env: GetEnv, **kwargs) -> ChainSettings:
    d = { **base_default_settings, **chain_settings, **{ "chain_id": chain_id, "chain_name": chain_name } }

    for k,v in d.items():
        if k in ["chain_id", "chain_name"]: continue
        # look for env vars (i.e stable_token_addr for chain_id="10" should be SUGAR_STABLE_TOKEN_ADDR_10)
        d[k] = get_env(f"SUGAR_{k.upper()}_{chain_id}", v)

    # keywords override env vars
    d = d | kwargs

    for k,v in d.items():
        # anything that ends in "_addr", should be normalized
        if k.endswith("_addr"): d[k] = normalize_address(d[k]) if d[k] else None
        # anything that ends in "_addrs", should be a list of normalized addresses
        if k.endswith("_addrs"): d[k] = list(map(lambda a: normalize_address(a), d[k].split(","))) if d[k] else []

    # we only want fields that are in the ChainSettings dataclass
    d =  {k: v for k, v in d.items() if k in [field.name for field in fields(ChainSettings)]}

    return validate_settings(make_dataclass(ChainSettings.__name__, ((k, type(v)) for k, v in d.items()))(**d)) 

def make_op_chain_settings(get_env: GetEnv = get_env, **kwargs) -> ChainSettings:
    d = {
        "rpc_uri": "https://optimism-mainnet.wallet.coinbase.com",
        "wrapped_native_token_addr": "0x4200000000000000000000000000000000000006",
        "interchain_router_contract_addr": "0x3E343D07D024E657ECF1f8Ae8bb7a12f08652E75",
        "bridge_contract_addr": "0x7bd2676c85cca9fa2203eba324fb8792fbd520b8",
        "bridge_token_addr": "0x1217bfe6c773eec6cc4a38b5dc45b92292b6e189",
        "sugar_contract_addr": "0x347512180804A8B40AA7525AE932a31198F074aA",
        "sugar_rewards_contract_addr": "0x62CCFB2496f49A80B0184AD720379B529E9152fB",
        "slipstream_contract_addr": "0xD45624bf2CB9f65ecbdF3067d21992b099b56202",
        "slipstream_factory_addr": "0xe13Dd1fbA721Aa81a1826D9523AC9BC7d260c879",
        "old_slipstream_factory_addr": "0xCc0bDDB707055e04e497aB22a59c2aF4391cd12F",
        "nfpm_contract_addr": "0xf7f8ccce99Ca2896eC75D3A399D152dB96808399",
        "price_oracle_contract_addr": "0x58238e3d556226defE35d3056335f48938707324",
        "router_contract_addr": "0xa062aE8A9c5e11aaA026fc2670B0D65cCc8B2858",
        "quoter_contract_addr": "0xAf6EBdf4c70061C5961994Ae9c9956fBc2bCC32E",
        "swapper_contract_addr": "0xcAF22ce31298CF2BF1D152862F80216478ad7c67",
        "token_addr": "0x9560e827aF36c94D2Ac33a39bCE1Fe78631088Db",
        "stable_token_addr": "0x7f5c764cbc14f9669b88837ca1490cca17c31607",
        "connector_tokens_addrs": "0x9560e827aF36c94D2Ac33a39bCE1Fe78631088Db,0x4200000000000000000000000000000000000042,0x4200000000000000000000000000000000000006,0x9bcef72be871e61ed4fbbc7630889bee758eb81d,0x2e3d870790dc77a83dd1d18184acc7439a53f475,0x8c6f28f2f1a3c87f0f938b96d27520d9751ec8d9,0x1f32b1c2345538c0c6f582fcb022739c4a194ebb,0xbfd291da8a403daaf7e5e9dc1ec0aceacd4848b9,0xc3864f98f2a61a7caeb95b039d031b4e2f55e0e9,0x9485aca5bbbe1667ad97c7fe7c4531a624c8b1ed,0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1,0x73cb180bf0521828d8849bc8cf2b920918e23032,0x6806411765af15bddd26f8f544a34cc40cb9838b,0x6c2f7b6110a37b3b0fbdd811876be368df02e8b0,0xc5b001dc33727f8f26880b184090d3e252470d45,0x6c84a8f1c29108f47a79964b5fe888d4f4d0de40,0xc40f949f8a4e094d1b49a23ea9241d289b7b2819,0x94b008aa00579c1307b0ef2c499ad98a8ce58e58,0x0b2c639c533813f4aa9d7837caf62653d097ff85",
        "excluded_tokens_addrs": "0x74ccbe53f77b08632ce0cb91d3a545bf6b8e0979,0x139283255069ea5deef6170699aaef7139526f1f,0x88a89866439f4c2830986b79cbe6f69d1bd548bb,0x8901cb2e82cc95c01e42206f8d1f417fe53e7af0",
        "message_module_contract_addr": "0x2BbA7515F7cF114B45186274981888D8C2fBA15E"
    } 
    return make_settings("10", "OP", chain_settings=d, get_env=get_env, **kwargs)

def make_base_chain_settings(get_env: GetEnv = get_env, **kwargs) -> ChainSettings:
    d = {
        "rpc_uri": "https://base-mainnet.g.alchemy.com/public",
        "wrapped_native_token_addr": "0x4200000000000000000000000000000000000006",
        "interchain_router_contract_addr": "0x44647Cd983E80558793780f9a0c7C2aa9F384D07",
        "bridge_contract_addr": "0x4F0654395d621De4d1101c0F98C1Dba73ca0a61f",
        "bridge_token_addr": "0x1217BfE6c773EEC6cc4A38b5Dc45B92292B6E189",
        "sugar_contract_addr": "0x69dD9db6d8f8E7d83887A704f447b1a584b599A1",
        "sugar_rewards_contract_addr": "0x1b121EfDaF4ABb8785a315C51D29BCE0552A7678",
        "slipstream_contract_addr": "0x9c62ab10577fB3C20A22E231b7703Ed6D456CC7a",
        "slipstream_factory_addr": "0xf8f2eB4940CFE7d13603DDDD87f123820Fc061Ef",
        "old_slipstream_factory_addr": "0x5e7BB104d84c7CB9B682AaC2F3d509f5F406809A",
        "nfpm_contract_addr": "0xe1f8cd9AC4e4A65F54f38a5CdAfCA44f6dD68b53",
        "price_oracle_contract_addr": "0xfbC91Fc9C6E70Afbea84b69FB0bF5EBa7F90aaFd",
        "router_contract_addr": "0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43",
        "quoter_contract_addr": "0xCd2A7D98e82D6107eac1828ce8DeAA6acB65b555",
        "swapper_contract_addr": "0xcAF22ce31298CF2BF1D152862F80216478ad7c67",
        "token_addr": "0x940181a94A35A4569E4529A3CDfB74e38FD98631",
        "stable_token_addr": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "connector_tokens_addrs": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913,0x940181a94A35A4569E4529A3CDfB74e38FD98631,0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb,0x4621b7a9c75199271f773ebd9a499dbd165c3191,0x4200000000000000000000000000000000000006,0xb79dd08ea68a908a97220c76d19a6aa9cbde4376,0xf7a0dd3317535ec4f4d29adf9d620b3d8d5d5069,0xcfa3ef56d303ae4faaba0592388f19d7c3399fb4,0xcb327b99ff831bf8223cced12b1338ff3aa322ff,0x2ae3f1ec7f1f5012cfeab0185bfc7aa3cf0dec22,0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452,0x60a3e35cc302bfa44cb288bc5a4f316fdb1adb42,0xd9aaec86b65d86f6a7b5b1b0c42ffa531710b6ca,0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
        "excluded_tokens_addrs": "0x74ccbe53f77b08632ce0cb91d3a545bf6b8e0979,0x8901cb2e82cc95c01e42206f8d1f417fe53e7af0,0x9cbd543f1b1166b2df36b68eb6bb1dce24e6abdf,0x025f99977db78317a4eba606998258b502bb256f,0xd260115030b9fb6849da169a01ed80b6496d1e99,0x608d5401d377228e465ba6113517dcf9bd1f95ca,0xd260115030b9fB6849da169a01ed80b6496d1e99,0x728cDA34D732a87fD6429129e23D4742d9Ff0064,0x728cda34d732a87fd6429129e23d4742d9ff0064,0xAC1Bd2486aAf3B5C0fc3Fd868558b082a531B2B4,0x0f929C29dcE303F96b1d4104505F2e60eE795caC,0x47E78d664E6c339693e8638B7A7D9543AbCc99D4,0xFF0C532FDB8Cd566Ae169C1CB157ff2Bdc83E105,0x373504da48418c67e6fcd071f33cb0b3b47613c7,0x0f929c29dce303f96b1d4104505f2e60ee795cac,0x628c5Ba9B775DACEcd14E237130c537f497d1CC7",
        "message_module_contract_addr": "0x2BbA7515F7cF114B45186274981888D8C2fBA15E"
    }
    return make_settings("8453", "Base", chain_settings=d, get_env=get_env, **kwargs)

def make_lisk_chain_settings(get_env: GetEnv = get_env, **kwargs) -> ChainSettings:
    d = {
        **superchain_default_settings,
        "rpc_uri": "https://lisk.drpc.org",
        "interchain_router_contract_addr": "0xE59592a179c4f436d5d2e4caA6e2750beA4E3166",
        "bridge_contract_addr": "0x910FF91a92c9141b8352Ad3e50cF13ef9F3169A1",
        "sugar_contract_addr": "0xD39E277B327705026dB4fb4E2b63E09ACBCD1754",
        "sugar_rewards_contract_addr": "0x066D31221152f1f483DA474d1Ce47a4F50433e22",
        "slipstream_contract_addr": "0xB98fB4C9C99dE155cCbF5A14af0dBBAd96033D6f",
        "price_oracle_contract_addr": "0x37B2349932F24D9235a4553bbda38d73bFc95bDE",
        "stable_token_addr": "0xf242275d3a6527d877f2c927a82d9b057609cc71",
        "connector_tokens_addrs": "0x4200000000000000000000000000000000000006,0xac485391eb2d7d88253a7f1ef18c37f4242d1a24,0x05d032ac25d322df992303dca074ee7392c117b9,0x03c7054bcb39f7b2e5b2c7acb37583e32d70cfa3",
    }
    return make_settings("1135", "Lisk", chain_settings=d, get_env=get_env, **kwargs)

def make_uni_chain_settings(get_env: GetEnv = get_env, **kwargs) -> ChainSettings:
    d = {
        **superchain_default_settings,
        "rpc_uri": "https://unichain-rpc.publicnode.com",
        "interchain_router_contract_addr": "0x43320f6B410322Bf5ca326a0DeAaa6a2FC5A021B",
        "bridge_contract_addr": "0x4A8149B1b9e0122941A69D01D23EaE6bD1441b4f",
        "sugar_contract_addr": "0xE002AF2176f604C250c6C368baB5F27e871559c2",
        "sugar_rewards_contract_addr": "0x215cEad02e0b9E0E494DD179585C18a772048a43",
        "slipstream_contract_addr": "0x222ed297aF0560030136AE652d39fa40E1B72818",
        "price_oracle_contract_addr": "0xd4C6eDDBE963aFA2D7b1562d0F2F3F9462E6525b",
        "stable_token_addr": "0x078d782b760474a361dda0af3839290b0ef57ad6",
        "connector_tokens_addrs": "0x4200000000000000000000000000000000000006,0x078d782b760474a361dda0af3839290b0ef57ad6",
    }
    return make_settings("130", "Uni", chain_settings=d, get_env=get_env, **kwargs)

def make_mode_chain_settings(get_env: GetEnv = get_env, **kwargs) -> ChainSettings:
    d = {
        **superchain_default_settings,
        "rpc_uri": "https://mode.drpc.org",
        "interchain_router_contract_addr": "0x860ec58b115930EcbC53EDb8585C1B16AFFF3c50",
        "bridge_contract_addr": "0x324d0b921C03b1e42eeFD198086A64beC3d736c2",
        "sugar_contract_addr": "0x1A3C63c8D442948085E47f88CB377183E23EA01f",
        "sugar_rewards_contract_addr": "0xc0373b68246A65ff8a3ae138dDc179020c905f76",
        "slipstream_contract_addr": "0xD24a61656AB0d70994Ef5F42fE11AA95c0a1d329",
        "price_oracle_contract_addr": "0x17F3dAaeE276D7bfB6F45dE4C6771b87940e2550",
        "stable_token_addr": "0xd988097fb8612cc24eec14542bc03424c656005f",
        "connector_tokens_addrs": "0x4200000000000000000000000000000000000006,0xdfc7c877a950e49d2610114102175a06c2e3167a,0xf0f161fda2712db8b566946122a5af183995e2ed,0xe7798f023fc62146e8aa1b36da45fb70855a77ea",
    }
    return make_settings("34443", "Mode", chain_settings=d, get_env=get_env, **kwargs)

def make_fraxtal_chain_settings(get_env: GetEnv = get_env, **kwargs) -> ChainSettings:
    d = {
        **superchain_default_settings,
        "rpc_uri": "https://fraxtal-rpc.publicnode.com",
        "wrapped_native_token_addr": "0xfc00000000000000000000000000000000000006",
        "interchain_router_contract_addr": "0xD59a200cCEc5b3b1bF544dD7439De452D718f594",
        "bridge_contract_addr": "0xa0bd9e96556e27e6fff0cc0f77496390d9844e1e",
        "sugar_contract_addr": "0xCAaf4556fF489521d4c722CB275510B602d6276d",
        "sugar_rewards_contract_addr": "0x03010FCe5BECD2a8B52F0C01A02E5EcaC1168845",
        "slipstream_contract_addr": "0x593D092BB28CCEfe33bFdD3d9457e77Bd3084271",
        "price_oracle_contract_addr": "0x45f65a5d0eA9f9D375c5E43d2eA4A5F0aE2D22B3",
        "router_contract_addr": "0xb8242875A76be3cB6E252eD3096dB3C2aA07AD6B",
        "stable_token_addr": "0xfc00000000000000000000000000000000000001",
        "connector_tokens_addrs": "0xfc00000000000000000000000000000000000006,0xfc00000000000000000000000000000000000005,0x5d3a1ff2b6bab83b63cd9ad0787074081a52ef34,0x211cc4dd073734da055fbf44a2b4667d5e5fe5d2,0xdcc0f2d8f90fde85b10ac1c8ab57dc0ae946a543,0xfc00000000000000000000000000000000000001",
    }
    return make_settings("252", "Fraxtal", chain_settings=d, get_env=get_env, **kwargs)

def make_ink_chain_settings(get_env: GetEnv = get_env, **kwargs) -> ChainSettings:
    d = {
        **superchain_default_settings,
        "rpc_uri": "https://ink.drpc.org",
        "interchain_router_contract_addr": "0x55Ba00F1Bac2a47e0A73584d7c900087642F9aE3",
        "bridge_contract_addr": "0x69158d1A7325Ca547aF66C3bA599F8111f7AB519",
        "sugar_contract_addr": "0x215cEad02e0b9E0E494DD179585C18a772048a43",
        "sugar_rewards_contract_addr": "0x9972174fcE4bdDFFff14bf2e18A287FDfE62c45E",
        "slipstream_contract_addr": "0x222ed297aF0560030136AE652d39fa40E1B72818",
        "price_oracle_contract_addr": "0x19AcF6D29102324eD478ffD3e54E534ABB329010",
        "stable_token_addr": "0xf1815bd50389c46847f0bda824ec8da914045d14",
        "connector_tokens_addrs": "0x4200000000000000000000000000000000000006,0x0200c29006150606b650577bbe7b6248f58470c1,0x73e0c0d45e048d25fc26fa3159b0aa04bfa4db98",
    }
    return make_settings("57073", "Ink", chain_settings=d, get_env=get_env, **kwargs)

def make_soneium_chain_settings(get_env: GetEnv = get_env, **kwargs) -> ChainSettings:
    d = {
        **superchain_default_settings,
        "rpc_uri": "https://soneium-rpc.publicnode.com",
        "interchain_router_contract_addr": "0xc08C1451979e9958458dA3387E92c9Feb1571f9C",
        "bridge_contract_addr": "0x2dC335bDF489f8e978477Ae53924324697e0f7BB",
        "sugar_contract_addr": "0x7A0225110765d2A14652323733f616215c5509cf",
        "sugar_rewards_contract_addr": "0x14b61ef12138c60AC8AB7B86556D6698E58Ec42D",
        "slipstream_contract_addr": "0x222ed297aF0560030136AE652d39fa40E1B72818",
        "price_oracle_contract_addr": "0x7b9644D43900da734f5a83DD0489Af1197DF2CF0",
        "stable_token_addr": "0xba9986d2381edf1da03b0b9c1f8b00dc4aacc369",
        "connector_tokens_addrs": "0x4200000000000000000000000000000000000006,0xba9986d2381edf1da03b0b9c1f8b00dc4aacc369,0x2cae934a1e84f693fbb78ca5ed3b0a6893259441",
    }
    return make_settings("1868", "Soneium", chain_settings=d, get_env=get_env, **kwargs)

def make_superseed_chain_settings(get_env: GetEnv = get_env, **kwargs) -> ChainSettings:
    d = {
        **superchain_default_settings,
        "rpc_uri": "https://superseed.drpc.org",
        "interchain_router_contract_addr": "0x3CA0e8AEfC14F962B13B40c6c4b9CEE3e4927Ae3",
        "bridge_contract_addr": "0x5beADE696E12aBE2839FEfB41c7EE6DA1f074C55",
        "sugar_contract_addr": "0x215cEad02e0b9E0E494DD179585C18a772048a43",
        "sugar_rewards_contract_addr": "0x9972174fcE4bdDFFff14bf2e18A287FDfE62c45E",
        "slipstream_contract_addr": "0x222ed297aF0560030136AE652d39fa40E1B72818",
        "price_oracle_contract_addr": "0x61d67B712812a3AdCc4b1A0C8Da9c26B524f7c20",
        "stable_token_addr": "0xc316c8252b5f2176d0135ebb0999e99296998f2e",
        "connector_tokens_addrs": "0x4200000000000000000000000000000000000006,0xc316c8252b5f2176d0135ebb0999e99296998f2e,0xc5068bb6803adbe5600de5189fe27a4dace31170,0x6f36dbd829de9b7e077db8a35b480d4329ceb331",
    }
    return make_settings("5330", "Superseed", chain_settings=d, get_env=get_env, **kwargs)

def make_celo_chain_settings(get_env: GetEnv = get_env, **kwargs) -> ChainSettings:
    d = {
        **superchain_default_settings,
        "rpc_uri": "https://celo-rpc.publicnode.com",
        "wrapped_native_token_addr": "0x0000000000000000000000000000000000000000",
        "interchain_router_contract_addr": "0x1eA7aC243c398671194B7e2C51d76d1a1D312953",
        "bridge_contract_addr": "0xbBa1938ff861c77eA1687225B9C33554379Ef327",
        "sugar_contract_addr": "0xa3a6F881A1Db3d5DA0F7c10659239F9FAdF74C5e",
        "sugar_rewards_contract_addr": "0x03D74f82AdcD10242864B1560c5e2467C2bC2Cc2",
        "slipstream_contract_addr": "0x928Bb6c9097d5C9c1eB5E99E71e24E4D773f2Be5",
        "price_oracle_contract_addr": "0x77bD18662B4DD6D2523653b145c978Ef1Bc5bc1b",
        "stable_token_addr": "0x48065fbbe25f71c9282ddf5e1cd6d6a887483d5e",
        "connector_tokens_addrs": "0xd221812de1bd094f35587ee8e174b07b6167d9af,0x48065fbbe25f71c9282ddf5e1cd6d6a887483d5e,0x471ece3750da237f93b8e339c536989b8978a438",
        "native_token_symbol": "CELO",
    }
    return make_settings("42220", "Celo", chain_settings=d, get_env=get_env, **kwargs)
