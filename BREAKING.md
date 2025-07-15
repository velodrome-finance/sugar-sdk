# Breaking Changes Migration Guide

This document outlines all breaking changes introduced in the amount handling refactoring and provides migration strategies for updating your code.

## Overview

The refactoring changes the amount handling system from a dual-parameter approach (`amount` + `amount_wei`) to a single integer-based approach. **All amounts are now expected to be in wei format (smallest unit) as integers.**

## 🚨 Breaking Changes

### 1. API Method Signatures Changed

**Files**: `sugar/chains.py`

#### `get_quote()` Method
```python
# BEFORE
async def get_quote(self, from_token: Token, to_token: Token, 
                   amount: Optional[float] = None, 
                   amount_wei: Optional[int] = None, 
                   filter_quotes: Optional[Callable[[Quote], bool]] = None) -> Optional[Quote]

# AFTER
async def get_quote(self, from_token: Token, to_token: Token, 
                   amount: int, 
                   filter_quotes: Optional[Callable[[Quote], bool]] = None) -> Optional[Quote]
```

#### `swap()` Method
```python
# BEFORE
async def swap(self, from_token: Token, to_token: Token, 
              amount: Optional[float] = None, 
              amount_wei: Optional[int] = None, 
              slippage: Optional[float] = None)

# AFTER
async def swap(self, from_token: Token, to_token: Token, 
              amount: int, 
              slippage: Optional[float] = None)
```

**Migration Strategy:**
```python
# OLD CODE
amount_float = 1.5
quote = await chain.get_quote(from_token, to_token, amount=amount_float)

# NEW CODE
amount_wei = from_token.parse_units(1.5)  # Convert to wei
quote = await chain.get_quote(from_token, to_token, amount=amount_wei)
```

### 2. Token Method Names Changed

**File**: `sugar/token.py`

#### Method Renaming
```python
# BEFORE
def to_wei(self, value: float) -> int:
    """Convert a value to wei based on the token's decimals."""

def to_decimal(self, value: int) -> float:
    """Convert a value from wei to decimal based on the token's decimals."""

# AFTER
def parse_units(self, value: float) -> int:
    """Convert a value to wei/kwei/gwei/mwei based on the token's decimals."""

def to_float(self, value: int) -> float:
    """Convert a value from wei/kwei/gwei/mwei to decimal based on the token's decimals."""
```

**Migration Strategy:**
```python
# OLD CODE
wei_amount = token.to_wei(1.5)
float_amount = token.to_decimal(1500000000000000000)

# NEW CODE
wei_amount = token.parse_units(1.5)
float_amount = token.to_float(1500000000000000000)
```

### 3. Amount Class Changes

**File**: `sugar/pool.py`

#### Data Type Changes
```python
# BEFORE
@dataclass(frozen=True)
class Amount:
    token: Token
    amount: float  # Was float
    price: "Price"

# AFTER
@dataclass(frozen=True)
class Amount:
    token: Token
    amount: int    # Now int (wei format)
    price: "Price"
```

#### New Method Added
```python
# NEW METHOD
@property
def as_float(self) -> float:
    """Returns the amount converted from wei/kwei/gwei/mwei to float on the token's decimals."""
    return self.token.to_float(self.amount)
```

**Migration Strategy:**
```python
# OLD CODE
amount_obj = Amount(token=token, amount=1.5, price=price)
stable_value = amount_obj.amount * price.price

# NEW CODE
amount_wei = token.parse_units(1.5)
amount_obj = Amount(token=token, amount=amount_wei, price=price)
stable_value = amount_obj.as_float() * price.price
# OR use the built-in property:
stable_value = amount_obj.amount_in_stable
```

### 4. Deposit Class Changes

**File**: `sugar/deposit.py`

```python
# BEFORE
@dataclass
class Deposit:
    pool: LiquidityPool
    amount_token0: float  # Was float

# AFTER
@dataclass
class Deposit:
    pool: LiquidityPool
    amount_token0: int    # Now int (wei format)
```

**Migration Strategy:**
```python
# OLD CODE
deposit = Deposit(pool=pool, amount_token0=1.5)

# NEW CODE
amount_wei = pool.token0.parse_units(1.5)
deposit = Deposit(pool=pool, amount_token0=amount_wei)
```

### 5. Superswap Method Signatures

**File**: `sugar/superswap.py`

```python
# BEFORE
def swap(self, from_token: Token, to_token: Token, amount: float, slippage: Optional[float] = None) -> str
def get_super_quote(self, from_token: Token, to_token: Token, amount: float) -> Optional[SuperswapQuote]

# AFTER
def swap(self, from_token: Token, to_token: Token, amount: int, slippage: Optional[float] = None) -> str
def get_super_quote(self, from_token: Token, to_token: Token, amount: int) -> Optional[SuperswapQuote]
```

**Migration Strategy:**
```python
# OLD CODE
tx_hash = superswap.swap(from_token, to_token, amount=1.5)

# NEW CODE
amount_wei = from_token.parse_units(1.5)
tx_hash = superswap.swap(from_token, to_token, amount=amount_wei)
```

### 6. Removed Method

**File**: `sugar/token.py`

```python
# REMOVED METHOD
def value_from_bigint(self, value: float) -> float: 
    return value / 10**self.decimals
```

**Migration Strategy:**
Use `to_float()` instead:
```python
# OLD CODE
result = token.value_from_bigint(amount)

# NEW CODE
result = token.to_float(amount)
```

## 📋 Migration Checklist

### Step 1: Update Method Calls
- [ ] Replace all `get_quote()` calls to use single `amount` parameter (int)
- [ ] Replace all `swap()` calls to use single `amount` parameter (int)
- [ ] Update `get_super_quote()` calls to use int amounts
- [ ] Update `Superswap.swap()` calls to use int amounts

### Step 2: Update Token Method Names
- [ ] Replace `token.to_wei()` with `token.parse_units()`
- [ ] Replace `token.to_decimal()` with `token.to_float()`
- [ ] Replace `token.value_from_bigint()` with `token.to_float()`

### Step 3: Update Data Structures
- [ ] Update `Amount` class usage to expect int values
- [ ] Update `Deposit` class usage to pass int values
- [ ] Use `amount.as_float()` when you need float representation

### Step 4: Convert Float Amounts to Wei
For any existing float amounts, convert them before use:
```python
# Convert float to wei before API calls
float_amount = 1.5
wei_amount = token.parse_units(float_amount)
```

## 🔧 Common Migration Patterns

### Pattern 1: Quote and Swap Operations
```python
# BEFORE
quote = await chain.get_quote(from_token, to_token, amount=1.5)
tx = await chain.swap(from_token, to_token, amount=1.5)

# AFTER
amount_wei = from_token.parse_units(1.5)
quote = await chain.get_quote(from_token, to_token, amount=amount_wei)
tx = await chain.swap(from_token, to_token, amount=amount_wei)
```

### Pattern 2: Working with Amount Objects
```python
# BEFORE
amount_obj = Amount(token=token, amount=1.5, price=price)
display_amount = amount_obj.amount

# AFTER
amount_wei = token.parse_units(1.5)
amount_obj = Amount(token=token, amount=amount_wei, price=price)
display_amount = amount_obj.as_float()
```

### Pattern 3: Creating Deposits
```python
# BEFORE
deposit = Deposit(pool=pool, amount_token0=1.5)

# AFTER
amount_wei = pool.token0.parse_units(1.5)
deposit = Deposit(pool=pool, amount_token0=amount_wei)
```

## ⚠️ Important Notes

1. **No Automatic Conversion**: The automatic conversion from float to wei has been removed. You must manually convert using `token.parse_units()`.

2. **Type Safety**: All amount parameters are now strictly typed as `int`. Passing float values will cause type errors.

3. **Precision**: Working with wei (integers) maintains precision better than floating-point arithmetic.

4. **Testing**: Thoroughly test your migration with various token decimals (6, 8, 18) to ensure proper handling.

## 🧪 Testing Your Migration

```python
# Test with different token types
usdc_amount = usdc_token.parse_units(1000.0)  # USDC has 6 decimals
eth_amount = eth_token.parse_units(1.0)       # ETH has 18 decimals

# Verify conversion works correctly
assert usdc_token.to_float(usdc_amount) == 1000.0
assert eth_token.to_float(eth_amount) == 1.0
```

## 📞 Support

If you encounter issues during migration:
1. Check that all float amounts are converted to wei using `token.parse_units()`
2. Verify you're using the new method names (`parse_units`, `to_float`)
3. Ensure Amount objects use the `as_float()` method for display purposes
4. Test with small amounts first to verify correct behavior