"""Unit tests for adaptive pool pagination sizing (no network)."""
from sugar.config import make_base_chain_settings
from sugar.chains import CommonChain


def _chain():
    return CommonChain(make_base_chain_settings())


def test_optimal_batch_size_small_chain_clamps_to_min():
    # 100 // 90 = 1, clamped up to min_size (10)
    assert _chain().calculate_optimal_batch_size(100) == 10


def test_optimal_batch_size_medium_chain():
    # 2500 // 90 = 27
    optimal = _chain().calculate_optimal_batch_size(2500)
    assert optimal == 27
    assert 10 <= optimal <= 300


def test_optimal_batch_size_large_chain():
    # 9000 // 90 = 100
    assert _chain().calculate_optimal_batch_size(9000) == 100


def test_optimal_batch_size_clamps_to_max():
    # 30000 // 90 = 333, clamped down to max_size (300)
    assert _chain().calculate_optimal_batch_size(30000) == 300


def test_optimal_batch_size_targets_about_90_calls():
    optimal = _chain().calculate_optimal_batch_size(8100)
    assert 80 <= 8100 / optimal <= 100


def test_paginator_uses_optimal_sizing_when_pool_count_known():
    batches = list(_chain().get_pool_paginator(batch_size=1, pool_count=2700, use_optimal_sizing=True))
    _, first_limit = batches[0][0]
    assert first_limit == 30  # 2700 // 90


def test_paginator_backwards_compatible_when_optimal_disabled():
    batches = list(_chain().get_pool_paginator(batch_size=1, pool_count=2700, use_optimal_sizing=False))
    _, first_limit = batches[0][0]
    assert first_limit == 500  # pool_page_size


def test_paginator_without_pool_count_uses_defaults():
    batches = list(_chain().get_pool_paginator(batch_size=1, pool_count=None, use_optimal_sizing=True))
    _, first_limit = batches[0][0]
    assert first_limit == 500  # pool_page_size


def test_optimal_sizing_reduces_page_size_for_large_chains():
    old = list(_chain().get_pool_paginator(batch_size=1, pool_count=9000, use_optimal_sizing=False))[0][0][1]
    new = list(_chain().get_pool_paginator(batch_size=1, pool_count=9000, use_optimal_sizing=True))[0][0][1]
    assert new < old
    assert new == 100
