"""Offline evaluation harness (REVAMP_PLAN §8).

Pure ranking metrics, dataset loaders, drift-guarded fixture loading, and the
local hybrid-retrieval harness live here so the CI retrieval gate and the nightly
generation eval reuse identical, unit-tested logic.
"""
