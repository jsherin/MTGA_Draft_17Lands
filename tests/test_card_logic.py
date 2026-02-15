import pytest
import os
import json
from src import constants
from src.set_metrics import SetMetrics
from src.configuration import Configuration, Settings
from src.card_logic import (
    CardResult,
    export_draft_to_csv,
    export_draft_to_json,
    field_process_sort,
)
from src.dataset import Dataset
from src.tier_list import TierList, Meta, Rating
from unittest.mock import MagicMock

# 17Lands OTJ data from 2024-4-16 to 2024-5-3
OTJ_PREMIER_SNAPSHOT = os.path.join(
    os.getcwd(), "tests", "data", "OTJ_PremierDraft_Data_2024_5_3.json"
)

TEST_TIER_LIST = {
    "TIER0": TierList(
        meta=Meta(collection_date="", label="", set="", version=3),
        ratings={
            "Push // Pull": Rating(rating="C+", comment=""),
            "Etali, Primal Conqueror": Rating(rating="A+", comment=""),
            "Virtue of Persistence": Rating(rating="A+", comment=""),
            "Consign // Oblivion": Rating(rating="C+", comment=""),
            "The Mightstone and Weakstone": Rating(rating="B-", comment=""),
            "Invasion of Gobakhan": Rating(rating="B+", comment=""),
        },
    )
}

TIER_TESTS = [
    ([{"name": "Push // Pull"}], "C+"),
    ([{"name": "Consign /// Oblivion"}], "C+"),
    ([{"name": "Etali, Primal Conqueror"}], "A+"),
    ([{"name": "Invasion of Gobakhan"}], "B+"),
    ([{"name": "The Mightstone and Weakstone"}], "B-"),
    ([{"name": "Virtue of Persistence"}], "A+"),
    ([{"name": "Fake Card"}], "NA"),
]

OTJ_GRADE_TESTS = [
    (
        "Colossal Rattlewurm",
        "All Decks",
        constants.DATA_FIELD_GIHWR,
        constants.LETTER_GRADE_A_MINUS,
    ),
    (
        "Colossal Rattlewurm",
        "All Decks",
        constants.DATA_FIELD_OHWR,
        constants.LETTER_GRADE_A_MINUS,
    ),
    (
        "Colossal Rattlewurm",
        "All Decks",
        constants.DATA_FIELD_GPWR,
        constants.LETTER_GRADE_B_PLUS,
    ),
    (
        "Colossal Rattlewurm",
        "WG",
        constants.DATA_FIELD_GIHWR,
        constants.LETTER_GRADE_A_MINUS,
    ),
    (
        "Colossal Rattlewurm",
        "WG",
        constants.DATA_FIELD_OHWR,
        constants.LETTER_GRADE_B_PLUS,
    ),
    (
        "Colossal Rattlewurm",
        "WG",
        constants.DATA_FIELD_GPWR,
        constants.LETTER_GRADE_B_PLUS,
    ),
]


@pytest.fixture(name="card_result", scope="module")
def fixture_card_result():
    return CardResult(SetMetrics(None), TEST_TIER_LIST, Configuration(), 1)


@pytest.fixture(name="otj_premier", scope="module")
def fixture_otj_premier():
    dataset = Dataset()
    dataset.open_file(OTJ_PREMIER_SNAPSHOT)
    set_metrics = SetMetrics(dataset, 2)

    return set_metrics, dataset


# The card data is pulled from the JSON set files downloaded from 17Lands, excluding the fake card
@pytest.mark.parametrize("card_list, expected_tier", TIER_TESTS)
def test_tier_results(card_result, card_list, expected_tier):
    # Go through a list of non-standard cards and confirm that the CardResults class is producing the expected result
    result_list = card_result.return_results(card_list, ["All Decks"], ["TIER0"])

    assert result_list[0]["results"][0] == expected_tier


@pytest.mark.parametrize("card_name, colors, field, expected_grade", OTJ_GRADE_TESTS)
def test_otj_grades(otj_premier, card_name, colors, field, expected_grade):
    metrics, dataset = otj_premier
    data_list = dataset.get_data_by_name([card_name])
    assert data_list

    config = Configuration(
        settings=Settings(result_format=constants.RESULT_FORMAT_GRADE)
    )
    results = CardResult(metrics, None, config, 2)
    card_data = data_list[0]
    result_list = results.return_results([card_data], [colors], [field])

    # GIHWR includes color pair breakdown; when filter is active, format is "WG: A-  ..."
    actual = result_list[0]["results"][0]
    if field == constants.DATA_FIELD_GIHWR:
        assert expected_grade in actual
    else:
        assert actual == expected_grade


def test_export_draft_to_csv():
    history = [
        {"Pack": 1, "Pick": 1, "Cards": ["123", "789"]},
    ]

    # Mock Picked Cards (List of lists)
    # Pack 1, Pick 1 was "123"
    picked_cards = [["123"]]

    # Mock Dataset
    mock_dataset = MagicMock()
    mock_dataset.get_data_by_id.side_effect = [
        [
            {constants.DATA_FIELD_NAME: "Card A", constants.DATA_FIELD_CMC: 2},
            {constants.DATA_FIELD_NAME: "Card B", constants.DATA_FIELD_CMC: 3},
        ]
    ]

    csv_output = export_draft_to_csv(history, mock_dataset, picked_cards)

    lines = csv_output.strip().split("\n")
    header = lines[0].split(",")
    assert "Picked" in header

    # Row 1 (Card A, ID 123) should be picked (1)
    row1 = lines[1].split(",")
    assert row1[2] == "1"
    assert "Card A" in lines[1]

    # Row 2 (Card B, ID 789) should not be picked (0)
    row2 = lines[2].split(",")
    assert row2[2] == "0"
    assert "Card B" in lines[2]


def test_export_draft_to_json():
    history = [{"Pack": 1, "Pick": 1, "Cards": ["123"]}]
    picked_cards = [["123"]]

    mock_dataset = MagicMock()
    mock_dataset.get_data_by_id.return_value = [
        {constants.DATA_FIELD_NAME: "Card A", constants.DATA_FIELD_CMC: 2}
    ]

    json_output = export_draft_to_json(history, mock_dataset, picked_cards)
    data = json.loads(json_output)

    assert data[0]["Cards"][0]["Picked"] == True


def test_gihwr_color_pairs_sorted_by_winrate(card_result):
    """Verify GIHWR color pair breakdown is ordered by highest winrate first."""
    card = {
        constants.DATA_FIELD_NAME: "Test Card",
        constants.DATA_FIELD_DECK_COLORS: {
            "All Decks": {constants.DATA_FIELD_GIHWR: 55.0},
            "WU": {constants.DATA_FIELD_GIHWR: 51.2},
            "UB": {constants.DATA_FIELD_GIHWR: 58.7},
            "BR": {constants.DATA_FIELD_GIHWR: 53.1},
        },
    }
    result_list = card_result.return_results(
        [card], ["All Decks"], [constants.DATA_FIELD_GIHWR]
    )
    actual = result_list[0]["results"][0]
    # Pairs should be ordered: UB (58.7) > BR (53.1) > WU (51.2)
    assert "UB: 58.7" in actual
    assert "BR: 53.1" in actual
    assert "WU: 51.2" in actual
    u_idx = actual.index("UB:")
    br_idx = actual.index("BR:")
    wu_idx = actual.index("WU:")
    assert u_idx < br_idx < wu_idx


def test_gihwr_ordering_when_filter_selected(card_result):
    """Verify GIHWR when filter is active: filter value on left, other pairs by winrate, AD at end."""
    card = {
        constants.DATA_FIELD_NAME: "Test Card",
        constants.DATA_FIELD_DECK_COLORS: {
            "All Decks": {constants.DATA_FIELD_GIHWR: 54.0},
            "WU": {constants.DATA_FIELD_GIHWR: 52.0},
            "UB": {constants.DATA_FIELD_GIHWR: 58.7},
            "BR": {constants.DATA_FIELD_GIHWR: 53.1},
            "BG": {constants.DATA_FIELD_GIHWR: 51.0},
        },
    }
    # Filter = WU (single color filter)
    result_list = card_result.return_results(
        [card], ["WU"], [constants.DATA_FIELD_GIHWR]
    )
    actual = result_list[0]["results"][0]
    # Left: WU: 52.0
    assert actual.startswith("WU: 52.0")
    # Other pairs sorted by winrate desc: UB > BR > BG
    assert "UB: 58.7" in actual
    assert "BR: 53.1" in actual
    assert "BG: 51.0" in actual
    ub_idx = actual.index("UB:")
    br_idx = actual.index("BR:")
    bg_idx = actual.index("BG:")
    assert ub_idx < br_idx < bg_idx
    # AD (All Decks) at end
    assert "AD: 54.0" in actual
    ad_idx = actual.index("AD:")
    assert ad_idx > bg_idx


def test_field_process_sort_filter_format_percentage():
    """Verify field_process_sort extracts primary value for percentage format when filter active."""
    # "WU: 55.0  UB: 58.7 BR: 53.1 AD: 54.2" -> sort by 55.0 (filter's GIHWR)
    assert field_process_sort("WU: 55.0  UB: 58.7 BR: 53.1 AD: 54.2") == 55.0


def test_field_process_sort_filter_format_grade():
    """Verify field_process_sort extracts primary value for grade format when filter active."""
    # "WU: A-  UB: B+ BR: B AD: A-" -> sort by A- grade (12 in GRADE_ORDER_DICT)
    assert field_process_sort("WU: A-  UB: B+ BR: B AD: A-") == 12.0


def test_field_process_sort_all_decks_format():
    """Verify field_process_sort handles All Decks format (primary number first)."""
    assert field_process_sort("55.0  UB: 58.7 BR: 53.1 WU: 51.2") == 55.0


def test_field_process_sort_all_decks_grade_format():
    """Verify field_process_sort handles All Decks + grade format (primary grade first)."""
    # "A-  UB: 58.7 BR: 56.2 WU: 51.2" -> sort by A- (12 in GRADE_ORDER_DICT)
    assert field_process_sort("A-  UB: 58.7 BR: 56.2 WU: 51.2") == 12.0


def test_field_process_sort_grade_order_ranking():
    """Verify grade order: A+ > A > A- > B+ > B when sorting descending."""
    gihwr_values = [
        "B  UB: 55.0 BR: 54.0",
        "A-  UB: 58.7 BR: 56.2",
        "B+  UB: 57.0 BR: 55.0",
        "A  UB: 59.0 BR: 57.0",
        "A+  UB: 60.0 BR: 58.0",
    ]
    # Sort by field_process_sort descending (best first)
    sorted_desc = sorted(gihwr_values, key=field_process_sort, reverse=True)
    # Expected order: A+ (14) > A (13) > A- (12) > B+ (11) > B (10)
    assert sorted_desc[0].startswith("A+")
    assert sorted_desc[1].startswith("A ")
    assert sorted_desc[2].startswith("A-")
    assert sorted_desc[3].startswith("B+")
    assert sorted_desc[4].startswith("B ")


def test_win_rate_rounded_to_one_decimal(card_result):
    """Verify win rate percentages are rounded to 1 decimal place."""
    card = {
        constants.DATA_FIELD_NAME: "Test Card",
        constants.DATA_FIELD_DECK_COLORS: {
            "All Decks": {constants.DATA_FIELD_GIHWR: 54.789},
        },
    }
    config = Configuration(
        settings=Settings(result_format=constants.RESULT_FORMAT_WIN_RATE)
    )
    results = CardResult(SetMetrics(None), None, config, 1)
    result_list = results.return_results(
        [card], ["All Decks"], [constants.DATA_FIELD_GIHWR]
    )
    actual = result_list[0]["results"][0]
    assert actual == 54.8 or "54.8" in str(actual)


def test_filter_fields_alsa_rounded_to_one_decimal(card_result):
    """Verify non-win-rate fields (ALSA, IWD, ATA) are rounded to 1 decimal."""
    card = {
        constants.DATA_FIELD_NAME: "Test Card",
        constants.DATA_FIELD_DECK_COLORS: {
            "All Decks": {
                constants.DATA_FIELD_GIHWR: 55.0,
                constants.DATA_FIELD_ALSA: 2.345,
            },
        },
    }
    result_list = card_result.return_results(
        [card], ["All Decks"], [constants.DATA_FIELD_ALSA]
    )
    actual = result_list[0]["results"][0]
    assert actual == 2.3


def test_export_draft_to_csv_edge_cases():
    """Verify export handles missing picks, unicode names, and empty stats."""
    history = [{"Pack": 1, "Pick": 1, "Cards": ["999"]}]
    # Picked cards map is empty (user disconnect? parsing error?)
    picked_cards = []

    mock_dataset = MagicMock()
    # Mock a card with unicode and missing stats
    mock_dataset.get_data_by_id.return_value = [
        {
            constants.DATA_FIELD_NAME: "Æther Potion",
            # Missing CMC, Colors, etc.
            constants.DATA_FIELD_DECK_COLORS: {},  # Empty stats
        }
    ]

    csv_output = export_draft_to_csv(history, mock_dataset, picked_cards)

    lines = csv_output.strip().split("\n")
    assert len(lines) == 2
    row = lines[1].split(",")

    # 1. Picked should be 0 (False) safely
    assert row[2] == "0"

    # 2. Name should be preserved (CSV module handles quotes/encoding)
    assert "Æther Potion" in lines[1]

    # 3. Stats should be empty strings/zeros, not crash
    # ALSA is index 15
    assert row[15] == ""
