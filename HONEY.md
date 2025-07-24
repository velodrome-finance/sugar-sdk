<p>
<h1 style="font-size:60px; text-align:center;">🍯Honey</h1>
</p>

Honey is Sugar's best friend, a configuration-driven development environment for multi-chain testing using [supersim](https://github.com/ethereum-optimism/supersim).

Instead of having to maintain test wallet with tons of different tokens across different chains, you can provide desired target configuration in `honey.yaml` and focus on tests intead. YAML configuration defines:

- Wallet private keys for testing
- Target chains
- Token balances to fund on each chain
- Large holder addresses for token transfers

> Note: you do have to manually identify token holders right now (the easiest way is to check [holders tab in etherscan](https://optimistic.etherscan.io/token/0x0b2c639c533813f4aa9d7837caf62653d097ff85#balances)). Honey can automate this in the future using [this API](https://docs.etherscan.io/etherscan-v2/api-endpoints/tokens#get-token-holder-list-by-contract-address)  

Honey uses [anvil_impersonateAccount](https://getfoundry.sh/anvil/reference#custom-methods) to impersonate holders accounts and send funds to your wallet when bootstrapping.

## Configuration Structure

Honey uses `honey.yaml` for configuration with this structure:

```yaml
honey:
  - wallet:
    - pk: "0x..." # Private key for test wallet - we are using Anvil's preset
  - chains:
    - name: "OP"
      id: "11155420"
      balance:
        - token: "USDC"
          address: "0x..."
          amount: 1000000000000000000000
          holder: "0x..." # Large holder to transfer from
```
