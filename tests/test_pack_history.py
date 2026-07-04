"""
tests/test_pack_history.py

Unit tests for PackHistoryPanel._rebuild_slot_list().

All tests operate purely on the data-layer method; no Tkinter event loop
is exercised (the panel is constructed with a real ttk.Frame parent so the
widget tree builds, but no mainloop is started).
"""

import pytest
from unittest.mock import MagicMock, patch
from tkinter import ttk


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_card(card_id, name="Card"):
    """Minimal card dict as returned by set_data.get_data_by_id."""
    return {"id": card_id, "name": name, "deck_colors": {}}


def _make_scanner(pack=1, pick=1, history=None):
    """
    Returns a MagicMock that satisfies the scanner interface used by
    PackHistoryPanel._rebuild_slot_list().
    """
    scanner = MagicMock()
    scanner.retrieve_current_pack_and_pick.return_value = (pack, pick)
    scanner.retrieve_draft_history.return_value = history or []
    scanner.set_data.get_data_by_id.side_effect = (
        lambda ids: [_make_card(i) for i in ids]
    )
    return scanner


def _make_config():
    cfg = MagicMock()
    cfg.settings.deck_filter = "All Decks"
    cfg.settings.result_format = "percent"
    cfg.settings.card_colors_enabled = 0
    return cfg


@pytest.fixture
def panel(session_tk_root):
    """Construct a bare PackHistoryPanel attached to the session root."""
    with patch("src.ui.windows.pack_history.DynamicTreeviewManager") as mock_dtm, \
         patch("src.ui.styles.Theme.scaled_val", side_effect=lambda x: x), \
         patch("src.ui.styles.Theme.scaled_font", return_value=("Helvetica", 9)):

        mock_dtm.return_value = MagicMock()
        mock_dtm.return_value.tree = MagicMock()
        mock_dtm.return_value.tree.get_children.return_value = []
        mock_dtm.return_value.active_fields = ["name"]

        from src.ui.windows.pack_history import PackHistoryPanel

        parent = ttk.Frame(session_tk_root)
        scanner = _make_scanner()
        config = _make_config()
        p = PackHistoryPanel(parent, scanner, config)
        yield p
        try:
            parent.destroy()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Label format tests
# ---------------------------------------------------------------------------

class TestLabelFormat:
    """Dropdown labels must use the P<pack>P<pick> format."""

    def test_label_p1p1(self, panel):
        panel.draft = _make_scanner(
            pack=1, pick=1,
            history=[{"Pack": 1, "Pick": 1, "Cards": [101]}],
        )
        panel._rebuild_slot_list()
        assert panel._pack_slots[0]["label"] == "P1P1"

    def test_label_p2p5(self, panel):
        panel.draft = _make_scanner(
            pack=2, pick=5,
            history=[{"Pack": 2, "Pick": 5, "Cards": [201]}],
        )
        panel._rebuild_slot_list()
        assert panel._pack_slots[0]["label"] == "P2P5"

    def test_label_p3p8(self, panel):
        panel.draft = _make_scanner(
            pack=3, pick=8,
            history=[{"Pack": 3, "Pick": 8, "Cards": [301]}],
        )
        panel._rebuild_slot_list()
        assert panel._pack_slots[0]["label"] == "P3P8"

    def test_no_old_slot_format(self, panel):
        """Old 'Pack X — Slot Y' format must NOT appear."""
        panel.draft = _make_scanner(
            pack=1, pick=3,
            history=[{"Pack": 1, "Pick": 3, "Cards": [101]}],
        )
        panel._rebuild_slot_list()
        label = panel._pack_slots[0]["label"]
        assert "—" not in label
        assert "Slot" not in label


# ---------------------------------------------------------------------------
# Sorting & deduplication tests
# ---------------------------------------------------------------------------

class TestSortAndDedup:
    """Entries must be sorted ascending by pick and deduplicated."""

    def test_sorted_ascending(self, panel):
        panel.draft = _make_scanner(
            pack=1, pick=1,
            history=[
                {"Pack": 1, "Pick": 3, "Cards": [103]},
                {"Pack": 1, "Pick": 1, "Cards": [101]},
                {"Pack": 1, "Pick": 2, "Cards": [102]},
            ],
        )
        panel._rebuild_slot_list()
        picks = [s["pick"] for s in panel._pack_slots]
        assert picks == sorted(picks)

    def test_deduplication_keeps_first(self, panel):
        """When the same pick number appears twice, first-seen wins."""
        panel.draft = _make_scanner(
            pack=1, pick=1,
            history=[
                {"Pack": 1, "Pick": 2, "Cards": [201]},  # first
                {"Pack": 1, "Pick": 2, "Cards": [299]},  # duplicate — must be dropped
            ],
        )
        panel._rebuild_slot_list()
        assert len(panel._pack_slots) == 1
        assert panel._pack_slots[0]["cards"][0]["id"] == 201

    def test_deduplication_multiple_picks(self, panel):
        panel.draft = _make_scanner(
            pack=1, pick=1,
            history=[
                {"Pack": 1, "Pick": 1, "Cards": [1]},
                {"Pack": 1, "Pick": 1, "Cards": [9]},  # dup
                {"Pack": 1, "Pick": 2, "Cards": [2]},
                {"Pack": 1, "Pick": 2, "Cards": [8]},  # dup
                {"Pack": 1, "Pick": 3, "Cards": [3]},
            ],
        )
        panel._rebuild_slot_list()
        assert len(panel._pack_slots) == 3
        assert [s["pick"] for s in panel._pack_slots] == [1, 2, 3]


# ---------------------------------------------------------------------------
# 8-entry cap tests
# ---------------------------------------------------------------------------

class TestEightEntryCap:
    """At most 8 slots may appear regardless of history length."""

    def test_cap_at_8(self, panel):
        history = [
            {"Pack": 1, "Pick": i, "Cards": [i * 10]}
            for i in range(1, 15)  # 14 entries
        ]
        panel.draft = _make_scanner(pack=1, pick=1, history=history)
        panel._rebuild_slot_list()
        assert len(panel._pack_slots) <= 8

    def test_exactly_8_picks(self, panel):
        history = [
            {"Pack": 1, "Pick": i, "Cards": [i]}
            for i in range(1, 9)  # exactly 8
        ]
        panel.draft = _make_scanner(pack=1, pick=1, history=history)
        panel._rebuild_slot_list()
        assert len(panel._pack_slots) == 8

    def test_fewer_than_8_not_padded(self, panel):
        history = [
            {"Pack": 1, "Pick": i, "Cards": [i]}
            for i in range(1, 4)  # 3 entries
        ]
        panel.draft = _make_scanner(pack=1, pick=1, history=history)
        panel._rebuild_slot_list()
        assert len(panel._pack_slots) == 3


# ---------------------------------------------------------------------------
# Pack-round filter tests
# ---------------------------------------------------------------------------

class TestPackRoundFilter:
    """Only entries for the current pack round should be included."""

    def test_filters_other_packs(self, panel):
        history = [
            {"Pack": 1, "Pick": 1, "Cards": [11]},
            {"Pack": 2, "Pick": 1, "Cards": [21]},  # different round
            {"Pack": 3, "Pick": 1, "Cards": [31]},  # different round
        ]
        panel.draft = _make_scanner(pack=1, pick=1, history=history)
        panel._rebuild_slot_list()
        assert len(panel._pack_slots) == 1
        assert panel._pack_slots[0]["label"] == "P1P1"

    def test_all_entries_from_correct_round(self, panel):
        history = [
            {"Pack": 2, "Pick": 1, "Cards": [21]},
            {"Pack": 2, "Pick": 2, "Cards": [22]},
            {"Pack": 1, "Pick": 1, "Cards": [11]},  # wrong round
        ]
        panel.draft = _make_scanner(pack=2, pick=1, history=history)
        panel._rebuild_slot_list()
        assert len(panel._pack_slots) == 2
        assert all(s["label"].startswith("P2") for s in panel._pack_slots)


# ---------------------------------------------------------------------------
# Current-pick inclusion test
# ---------------------------------------------------------------------------

class TestCurrentPickNotExcluded:
    """The current pick's entry must NOT be excluded (old behaviour removed)."""

    def test_current_pick_included(self, panel):
        panel.draft = _make_scanner(
            pack=1, pick=3,
            history=[
                {"Pack": 1, "Pick": 1, "Cards": [1]},
                {"Pack": 1, "Pick": 2, "Cards": [2]},
                {"Pack": 1, "Pick": 3, "Cards": [3]},  # current pick
            ],
        )
        panel._rebuild_slot_list()
        pick_nums = [s["pick"] for s in panel._pack_slots]
        assert 3 in pick_nums, "Current pick must be included in the slot list"

    def test_all_picks_present(self, panel):
        """With picks 1-5 in history and current_pick=3, all 5 should appear."""
        history = [{"Pack": 1, "Pick": i, "Cards": [i]} for i in range(1, 6)]
        panel.draft = _make_scanner(pack=1, pick=3, history=history)
        panel._rebuild_slot_list()
        assert len(panel._pack_slots) == 5


# ---------------------------------------------------------------------------
# Pack-round reset / auto-clear tests
# ---------------------------------------------------------------------------

class TestPackRoundReset:
    """Dropdown selection must be cleared when the pack round changes."""

    def test_selection_cleared_on_round_change(self, panel):
        panel.draft = _make_scanner(
            pack=1, pick=2,
            history=[{"Pack": 1, "Pick": 1, "Cards": [1]},
                     {"Pack": 1, "Pick": 2, "Cards": [2]}],
        )
        panel._rebuild_slot_list()
        panel._selected_slot_var.set("P1P1")
        panel._last_known_pack_round = 1

        panel.draft = _make_scanner(
            pack=2, pick=1,
            history=[{"Pack": 2, "Pick": 1, "Cards": [21]}],
        )
        panel._rebuild_slot_list()

        assert panel._selected_slot_var.get() != "P1P1", \
            "Selection from P1 should have been cleared on P2 transition"
        assert panel._last_known_pack_round == 2

    def test_no_reset_within_same_round(self, panel):
        """Selection must not be cleared when still in the same pack round."""
        history = [
            {"Pack": 1, "Pick": 1, "Cards": [1]},
            {"Pack": 1, "Pick": 2, "Cards": [2]},
        ]
        panel.draft = _make_scanner(pack=1, pick=1, history=history)
        panel._rebuild_slot_list()
        panel._selected_slot_var.set("P1P1")

        panel.draft = _make_scanner(pack=1, pick=2, history=history)
        panel._rebuild_slot_list()

        assert panel._selected_slot_var.get() == "P1P1"


# ---------------------------------------------------------------------------
# Empty / edge case tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_history(self, panel):
        panel.draft = _make_scanner(pack=1, pick=1, history=[])
        panel._rebuild_slot_list()
        assert panel._pack_slots == []

    def test_entries_with_no_cards_skipped(self, panel):
        history = [
            {"Pack": 1, "Pick": 1, "Cards": []},   # empty — should be skipped
            {"Pack": 1, "Pick": 2, "Cards": [2]},
        ]
        panel.draft = _make_scanner(pack=1, pick=1, history=history)
        panel._rebuild_slot_list()
        assert len(panel._pack_slots) == 1
        assert panel._pack_slots[0]["label"] == "P1P2"

    def test_cards_resolved_via_set_data(self, panel):
        """Cards must be resolved through scanner.set_data.get_data_by_id."""
        scanner = _make_scanner(
            pack=1, pick=1,
            history=[{"Pack": 1, "Pick": 1, "Cards": [42, 43]}],
        )
        panel.draft = scanner
        panel._rebuild_slot_list()
        scanner.set_data.get_data_by_id.assert_called_once_with([42, 43])
        assert len(panel._pack_slots[0]["cards"]) == 2
