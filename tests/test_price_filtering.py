"""Oracle-input filtering in `_get_prices` (no network)."""
from sugar.chains import CommonChain
from sugar.config import make_base_chain_settings
from sugar.token import Token


def _chain(): return CommonChain(make_base_chain_settings())


def _t(addr, *, listed=False, emerging=False, wrapped=None):
    return Token(chain_id="8453", chain_name="Base", token_address=addr, symbol=addr,
                 decimals=18, listed=listed, emerging=emerging, wrapped_token_address=wrapped)


def test_unlisted_tokens_filtered_out():
    listed, unlisted = _t("0xL", listed=True), _t("0xU")
    assert {t.token_address for t in _chain().get_price_request_tokens([listed, unlisted])} == {"0xL"}


def test_emerging_tokens_kept():
    assert {t.token_address for t in _chain().get_price_request_tokens([_t("0xE", emerging=True)])} == {"0xE"}


def test_native_token_kept():
    # `is_native` keys on wrapped_token_address being set, not `listed`
    native = _t("ETH", wrapped="0x4200000000000000000000000000000000000006")
    assert {t.token_address for t in _chain().get_price_request_tokens([native])} == {"ETH"}


def test_dedupes_by_address():
    a, a_dup = _t("0xA", listed=True), _t("0xA", listed=True)
    assert len(_chain().get_price_request_tokens([a, a_dup])) == 1
