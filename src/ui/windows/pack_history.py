"""
src/ui/windows/pack_history.py
Pack History Viewer.
Shows all known cards from previous packs in the current pack round (P1, P2, P3).
A dropdown selects the pack slot to view; resets automatically on new pack rounds.
"""

import tkinter
from tkinter import ttk
from typing import List, Dict, Any, Optional

from src import constants
from src.card_logic import format_gihwr_column, format_gpwr_column, format_win_rate, row_color_tag
from src.mana_images import ManaImageCache
from src.ui.styles import Theme
from src.ui.components import DynamicTreeviewManager


class PackHistoryPanel(ttk.Frame):
    """Tab panel that displays known cards from previous packs in the current round."""

    def __init__(self, parent, draft_manager, configuration):
        super().__init__(parent)
        self.draft = draft_manager
        self.configuration = configuration

        self._mana_cache: Optional[ManaImageCache] = None
        self._last_known_pack_round: int = 0

        # Populated in refresh(): list of (label, card_list) per known pack slot
        self._pack_slots: List[Dict[str, Any]] = []

        # The currently selected pack slot index (driven by the combobox)
        self._selected_slot_var = tkinter.StringVar()

        self._build_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # --- Top control bar ---
        control_frame = ttk.Frame(self, padding=Theme.scaled_val(5))
        control_frame.pack(fill="x", pady=Theme.scaled_val((0, 5)))

        ttk.Label(
            control_frame,
            text="Pack:",
            font=Theme.scaled_font(9, "bold"),
            bootstyle="primary",
        ).pack(side="left", padx=(Theme.scaled_val(5), Theme.scaled_val(3)))

        self._combo = ttk.Combobox(
            control_frame,
            textvariable=self._selected_slot_var,
            state="readonly",
            width=28,
        )
        self._combo.pack(side="left", padx=Theme.scaled_val(3))
        self._combo.bind("<<ComboboxSelected>>", self._on_slot_selected)

        self._lbl_info = ttk.Label(
            control_frame,
            text="",
            font=Theme.scaled_font(8),
            bootstyle="secondary",
        )
        self._lbl_info.pack(side="left", padx=Theme.scaled_val(10))

        # --- Card table ---
        self.table_manager = DynamicTreeviewManager(
            self,
            view_id="pack_history_table",
            configuration=self.configuration,
            on_update_callback=self._update_table,
        )
        self.table_manager.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Public refresh entry-point (called by the orchestrator / tab switch)
    # ------------------------------------------------------------------

    def refresh(self):
        """Re-reads draft state and rebuilds the dropdown + table."""
        self._rebuild_slot_list()
        self._update_table()

    # ------------------------------------------------------------------
    # Data layer
    # ------------------------------------------------------------------

    def _rebuild_slot_list(self):
        """
        Builds `self._pack_slots` from `draft_history` for the current pack round.

        Each entry in draft_history looks like:
            {"Pack": <round 1-3>, "Pick": <pick number 1-N>, "Cards": [card_id, ...]}

        We collect every history entry that belongs to the *current* pack round,
        then resolve card IDs through `set_data.get_data_by_id`.  The player's own
        current pack is excluded because it is already shown in the Live Pack table.
        """
        current_pack, current_pick = self.draft.retrieve_current_pack_and_pick()

        # Detect pack-round transition and auto-reset the dropdown selection
        if current_pack != self._last_known_pack_round:
            self._last_known_pack_round = current_pack
            self._selected_slot_var.set("")

        history: List[Dict] = self.draft.retrieve_draft_history()

        # Keep only entries for the current pack round
        round_entries = [e for e in history if e.get("Pack") == current_pack]

        # Build slot labels; skip the current pick slot (it duplicates the Live Pack)
        slots = []
        for entry in round_entries:
            pick_num = entry.get("Pick", 0)
            card_ids = entry.get("Cards", [])
            if not card_ids:
                continue
            # Skip the entry that matches the current live pick
            if pick_num == current_pick:
                continue
            cards = self.draft.set_data.get_data_by_id(card_ids)
            label = f"Pack {current_pack} — Slot {pick_num}  ({len(cards)} cards)"
            slots.append({"label": label, "cards": cards, "pick": pick_num})

        self._pack_slots = slots

        # Rebuild combobox values
        labels = [s["label"] for s in self._pack_slots]
        self._combo["values"] = labels

        if not labels:
            self._selected_slot_var.set("")
            self._lbl_info.config(
                text="No previous pack data available for this round yet."
            )
        else:
            # Preserve existing selection if still valid; otherwise default to last entry
            current_sel = self._selected_slot_var.get()
            if current_sel not in labels:
                self._selected_slot_var.set(labels[-1])
            info_text = (
                f"Round P{current_pack}  •  {len(labels)} known pack slot(s)"
            )
            self._lbl_info.config(text=info_text)

    def _get_selected_cards(self) -> List[Dict[str, Any]]:
        """Returns the card list for the currently selected dropdown slot."""
        sel = self._selected_slot_var.get()
        for slot in self._pack_slots:
            if slot["label"] == sel:
                return slot["cards"]
        return []

    # ------------------------------------------------------------------
    # Table rendering
    # ------------------------------------------------------------------

    def _on_slot_selected(self, event=None):
        self._update_table()

    def _update_table(self):
        t = self.table_manager.tree if hasattr(self, "table_manager") else None
        if t is None:
            return

        for item in t.get_children():
            t.delete(item)

        cards = self._get_selected_cards()
        if not cards:
            return

        if self._mana_cache is None:
            self._mana_cache = ManaImageCache(size=16)

        metrics = self.draft.retrieve_set_metrics()
        color_ratings = self.draft.set_data.get_color_ratings()
        tier_data = self.draft.retrieve_tier_data()

        # Determine active color filter (mirrors TakenCardsPanel logic)
        try:
            from src.card_logic import filter_options
            raw_pool = self.draft.retrieve_taken_cards()
            colors = filter_options(
                raw_pool or [],
                self.configuration.settings.deck_filter,
                metrics,
                self.configuration,
            )
            active_filter = colors[0] if colors else "All Decks"
        except Exception:
            active_filter = "All Decks"

        t._gihwr_filter = active_filter

        processed_rows = []
        for idx, card in enumerate(cards):
            row_values = []
            deck_colors = card.get("deck_colors", {})

            mana_photo = self._mana_cache.get_for_card(
                card.get(constants.DATA_FIELD_MANA_COST)
                or card.get(constants.DATA_FIELD_COLORS, [])
            )
            gihwr_display, gihwr_sort = format_gihwr_column(
                deck_colors, active_filter, color_ratings
            )
            gpwr_display, _ = format_gpwr_column(
                deck_colors, active_filter, color_ratings
            )

            for field in self.table_manager.active_fields:
                if field == "name":
                    row_values.append(card.get(constants.DATA_FIELD_NAME, "Unknown"))
                elif field == "count":
                    row_values.append(card.get("count", 1))
                elif field == "gihwr":
                    row_values.append(gihwr_display)
                elif field == "gpwr":
                    row_values.append(gpwr_display)
                elif field == "colors":
                    row_values.append("".join(card.get("colors", [])))
                elif field == "tags":
                    raw_tags = card.get("tags", [])
                    if raw_tags:
                        icons_only = [
                            constants.TAG_VISUALS.get(tg, tg).split(" ")[0]
                            for tg in raw_tags
                        ]
                        row_values.append(" ".join(icons_only))
                    else:
                        row_values.append("-")
                elif "TIER" in field:
                    if tier_data and field in tier_data:
                        tier_obj = tier_data[field]
                        raw_name = card.get(constants.DATA_FIELD_NAME, "")
                        if raw_name in tier_obj.ratings:
                            row_values.append(tier_obj.ratings[raw_name].rating)
                        else:
                            row_values.append("NA")
                    else:
                        row_values.append("NA")
                else:
                    val = deck_colors.get(active_filter, {}).get(field, 0.0)
                    row_values.append(
                        format_win_rate(
                            val,
                            active_filter,
                            field,
                            metrics,
                            self.configuration.settings.result_format,
                        )
                    )

            tag = "bw_odd" if idx % 2 == 0 else "bw_even"
            if int(self.configuration.settings.card_colors_enabled):
                tag = row_color_tag(card.get(constants.DATA_FIELD_MANA_COST, ""))

            processed_rows.append(
                {
                    "vals": row_values,
                    "tag": tag,
                    "sort_key": gihwr_sort,
                    "image": mana_photo,
                }
            )

        processed_rows.sort(key=lambda x: x["sort_key"], reverse=True)

        for i, row in enumerate(processed_rows):
            if not self.configuration.settings.card_colors_enabled and row["tag"] in (
                "bw_odd",
                "bw_even",
            ):
                row["tag"] = "bw_odd" if i % 2 == 0 else "bw_even"

            t.insert(
                "",
                "end",
                text="",
                values=row["vals"],
                tags=(row["tag"],),
                image=row.get("image"),
            )

        if hasattr(t, "reapply_sort"):
            t.reapply_sort()
