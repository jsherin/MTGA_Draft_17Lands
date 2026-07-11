"""Tests for constants.py color pair consistency.

Covers the bug where TWO_COLOR_PAIRS used "GW" instead of "WG",
causing Selesnya to be silently dropped from the GIHWR breakdown.
"""
import pytest
from src import constants


class TestTwoColorPairsConsistency:
    """TWO_COLOR_PAIRS must be a subset of COLOR_NAMES_DICT keys."""

    def test_all_pairs_in_color_names_dict(self):
        """Every entry in TWO_COLOR_PAIRS must exist as a key in COLOR_NAMES_DICT."""
        missing = [
            pair
            for pair in constants.TWO_COLOR_PAIRS
            if pair not in constants.COLOR_NAMES_DICT
        ]
        assert missing == [], (
            f"TWO_COLOR_PAIRS contains keys not found in COLOR_NAMES_DICT: {missing}"
        )

    def test_selesnya_pair_is_wg(self):
        """Selesnya must be keyed as 'WG' (WUBRG order), not 'GW'."""
        assert "WG" in constants.TWO_COLOR_PAIRS, (
            "'WG' (Selesnya) is missing from TWO_COLOR_PAIRS"
        )
        assert "GW" not in constants.TWO_COLOR_PAIRS, (
            "'GW' should not appear in TWO_COLOR_PAIRS — use 'WG' instead"
        )

    def test_pair_count(self):
        """There should be exactly 10 two-color guild pairs."""
        assert len(constants.TWO_COLOR_PAIRS) == 10

    def test_no_duplicate_pairs(self):
        """TWO_COLOR_PAIRS should have no duplicates."""
        assert len(constants.TWO_COLOR_PAIRS) == len(set(constants.TWO_COLOR_PAIRS))

    def test_all_pairs_are_two_letters(self):
        """Every entry in TWO_COLOR_PAIRS should be exactly 2 characters."""
        bad = [p for p in constants.TWO_COLOR_PAIRS if len(p) != 2]
        assert bad == [], f"Non-two-letter entries in TWO_COLOR_PAIRS: {bad}"

    def test_all_known_guilds_present(self):
        """All ten Ravnica guilds must be represented."""
        expected = {"WU", "UB", "BR", "RG", "WG", "WB", "BG", "UG", "UR", "WR"}
        actual = set(constants.TWO_COLOR_PAIRS)
        assert actual == expected, (
            f"Guild mismatch. Missing: {expected - actual}, Extra: {actual - expected}"
        )

    @pytest.mark.parametrize("pair,expected_name", [
        ("WU", "Azorius"),
        ("UB", "Dimir"),
        ("BR", "Rakdos"),
        ("RG", "Gruul"),
        ("WG", "Selesnya"),
        ("WB", "Orzhov"),
        ("BG", "Golgari"),
        ("UG", "Simic"),
        ("UR", "Izzet"),
        ("WR", "Boros"),
    ])
    def test_pair_names_match_color_names_dict(self, pair, expected_name):
        """Each TWO_COLOR_PAIRS entry must map to the correct guild name."""
        assert constants.COLOR_NAMES_DICT.get(pair) == expected_name, (
            f"Expected COLOR_NAMES_DICT['{pair}'] == '{expected_name}', "
            f"got '{constants.COLOR_NAMES_DICT.get(pair)}'"
        )
