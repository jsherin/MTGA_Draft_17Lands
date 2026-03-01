"""
tests/test_integration_log_pipeline.py
"""

import pytest
import tkinter
import os
import shutil
import time
from unittest.mock import patch
from src.ui.app import DraftApp
from src.log_scanner import ArenaScanner
from src.configuration import Configuration
from src.limited_sets import SetDictionary, SetInfo
from src.ui.styles import Theme

OTJ_SNAPSHOT = os.path.join(
    os.getcwd(), "tests", "data", "OTJ_PremierDraft_Data_2024_5_3.json"
)


class TestLogPipelineIntegration:
    @pytest.fixture
    def env(self, tmp_path, monkeypatch):
        temp_sets = tmp_path / "Sets"
        temp_sets.mkdir()
        temp_logs = tmp_path / "Logs"
        temp_logs.mkdir()
        monkeypatch.setattr("src.constants.SETS_FOLDER", str(temp_sets))
        monkeypatch.setattr("src.constants.DRAFT_LOG_FOLDER", str(temp_logs))
        # utils imports SETS_FOLDER at load time; patch it so list/read use temp path
        monkeypatch.setattr("src.utils.SETS_FOLDER", str(temp_sets))

        log_file = tmp_path / "Player.log"
        log_file.write_text("MTGA Log Start\n")
        target_path = temp_sets / "OTJ_PremierDraft_All_Data.json"
        shutil.copy(OTJ_SNAPSHOT, target_path)

        mock_sets = SetDictionary(
            data={
                "Outlaws": SetInfo(
                    arena=["OTJ"], seventeenlands=["OTJ"], set_code="OTJ"
                )
            }
        )
        mock_data = (
            [
                (
                    "OTJ",
                    "PremierDraft",
                    "All",
                    "2024-04-16",
                    "2024-05-03",
                    500,
                    str(target_path),
                    "2024-05-03 12:00:00",
                )
            ],
            [],
        )
        monkeypatch.setattr(
            "src.log_scanner.retrieve_local_set_list", lambda *a, **k: mock_data
        )
        monkeypatch.setattr(
            "src.utils.retrieve_local_set_list", lambda *a, **k: mock_data
        )
        # App imports retrieve_local_set_list at load time; patch at use site so UI sees mock
        monkeypatch.setattr(
            "src.ui.app.retrieve_local_set_list", lambda *a, **k: mock_data
        )
        # Real download runs; decline the "Would you like to update now?" dialog so test doesn't block
        monkeypatch.setattr(
            "tkinter.messagebox.askyesno",
            lambda *a, **k: False,
        )
        # Never write to the real app config so tests do not reset user settings
        monkeypatch.setattr("src.configuration.write_configuration", lambda *a, **k: None)

        config = Configuration()
        config.settings.arena_log_location = str(log_file)
        config.card_data.latest_dataset = "OTJ_PremierDraft_All_Data.json"

        root = tkinter.Tk()
        # Initialize theme to stabilize style database
        Theme.apply(root, "Dark")
        root.withdraw()

        scanner = ArenaScanner(
            str(log_file),
            mock_sets,
            sets_location=str(temp_sets),
            retrieve_unknown=True,
        )
        scanner.file_size = 0

        # We must prevent the scheduled update loop from running wild during tests
        with patch("src.ui.app.DraftApp._schedule_update"):
            app = DraftApp(root, scanner, config)
            # Cancel any potentially lingering tasks (though patch should catch them)
            if app._update_task_id:
                try:
                    root.after_cancel(app._update_task_id)
                except:
                    pass

            yield {"app": app, "log": log_file, "root": root}

        try:
            root.destroy()
        except tkinter.TclError:
            pass

    def test_full_draft_cycle_and_auto_filter_logic(self, env):
        app, log, root = env["app"], env["log"], env["root"]
        with open(log, "a") as f:
            f.write(
                f'[UnityCrossThreadLogger]==> Event_Join {{"id":"1","request":"{{\\"EventName\\":\\"PremierDraft_OTJ_20240416\\"}}"}}\n'
            )

        # Manually trigger the update loop logic since we patched the scheduler
        app._update_loop()

        # Wait for draft to be detected and set label (UI shows display name "Outlaws", not code "OTJ")
        # Allow time for real 17lands update check + dialog decline
        ready = False
        set_label = app.vars["set_label"].get
        for _ in range(150):
            root.update()
            label = set_label()
            if not app._loading and ("OTJ" in label or "Outlaws" in label):
                ready = True
                break
            time.sleep(0.1)
        assert ready, f"timed out: _loading={app._loading}, set_label={set_label()!r}"

        p1p1 = (
            '[UnityCrossThreadLogger]==> LogBusinessEvents {"id":"2","request":"{\\"PackNumber\\":1,\\"PickNumber\\":1,'
            '\\"CardsInPack\\":[90734,90584,90631,90362,90440,90349,90486,90527,90406,90439,90488,90480,90388,90459]}"}\n'
        )
        with open(log, "a") as f:
            f.write(p1p1)

        # Pumping the loop to ensure detection
        for _ in range(2):
            app._update_loop()
            root.update()

        tree = app.dashboard.get_treeview("pack")
        rows = []
        for _ in range(50):  # Increase wait for slow CI environments
            root.update()
            rows = tree.get_children()
            if len(rows) >= 14:
                break
            time.sleep(0.1)

        assert len(rows) >= 14

        # Verify that the table is populated with known cards from the pack.
        first_row_val = str(tree.item(rows[0])["values"][0])
        assert any(
            x in first_row_val for x in ["Back for More", "90734", "Vadmir", "90459"]
        )

    def test_signals_and_missing_cards_logic(self, env):
        app, log, root = env["app"], env["log"], env["root"]
        with open(log, "a") as f:
            f.write(
                f'[UnityCrossThreadLogger]==> Event_Join {{"id":"1","request":"{{\\"EventName\\":\\"PremierDraft_OTJ\\"}}"}}\n'
            )
        app._update_loop()
        for _ in range(30):
            root.update()
            if not app._loading and "OTJ" in app.vars["set_label"].get():
                break
            time.sleep(0.1)

        p1p1 = (
            '[UnityCrossThreadLogger]==> LogBusinessEvents {"id":"2","request":"{\\"PackNumber\\":1,\\"PickNumber\\":1,'
            '\\"CardsInPack\\":[90734, 90584, 90459]}"}\n'
        )
        with open(log, "a") as f:
            f.write(p1p1)
        app._update_loop()
        root.update()

        pick1 = '[UnityCrossThreadLogger]==> Event_PlayerDraftMakePick {"id":"3","request":"{\\"Pack\\":1,\\"Pick\\":1,\\"GrpId\\":90734}"}\n'
        with open(log, "a") as f:
            f.write(pick1)
        app._update_loop()
        root.update()

        p1p9 = '[UnityCrossThreadLogger]Draft.Notify {"draftId":"1","SelfPick":9,"SelfPack":1,"PackCards":"90459"}\n'
        with open(log, "a") as f:
            f.write(p1p9)
        app._update_loop()
        root.update()

        tree = app.dashboard.get_treeview("missing")
        rows = []
        for _ in range(30):
            root.update_idletasks()
            root.update()
            rows = tree.get_children()
            if len(rows) > 0:
                break
            time.sleep(0.1)

        assert len(rows) > 0
        missing_names = [str(tree.item(r)["values"][0]) for r in rows]
        assert any("Wrangler" in name or "90584" in name for name in missing_names)

    def test_new_draft_started_while_app_running(self, env):
        """Simulate: app is running (log already read), then a new draft starts (new lines appended).
        Verifies that the new draft is detected and the UI resets with the new pack."""
        app, log, root = env["app"], env["log"], env["root"]
        scanner = app.orchestrator.scanner

        # 1. Warm run: process initial log content so search_offset advances (simulates "app running")
        app._update_loop()
        root.update()
        initial_offset = scanner.search_offset
        assert initial_offset >= len("MTGA Log Start\n")

        # 2. Simulate a new draft starting: append EventJoin + P1P1 pack to the fake log
        event_join = (
            '[UnityCrossThreadLogger]==> Event_Join {"id":"new-draft-123","request":"{\\"EventName\\":\\"PremierDraft_OTJ_20240416\\",\\"EntryCurrencyType\\":\\"Gem\\",\\"EntryCurrencyPaid\\":1500,\\"CustomTokenId\\":null}"}\n'
        )
        p1p1_pack = (
            '[UnityCrossThreadLogger]==> LogBusinessEvents {"id":"p1p1-456","request":"{\\"DraftId\\":\\"new-draft-123\\",\\"EventId\\":\\"PremierDraft_OTJ_20240416\\",\\"PackNumber\\":1,\\"PickNumber\\":1,\\"CardsInPack\\":[90734,90584,90631,90362,90440,90349,90486,90527,90406,90439,90488,90480,90388,90459]}"}\n'
        )
        with open(log, "a") as f:
            f.write(event_join)
            f.write(p1p1_pack)

        # 3. Trigger update (orchestrator sees file grew, reads from search_offset, sees new event)
        changed = app.orchestrator.update_cycle()
        assert changed, "update_cycle should see new log content and detect the draft"

        # 4. Assert new draft was detected and scanner state reset
        assert app.orchestrator.new_event_detected, "new_event_detected should be True when a new draft starts"
        assert scanner.draft_sets is not None and len(scanner.draft_sets) > 0
        assert scanner.draft_sets[0] == "OTJ"
        assert scanner.current_pack == 1
        assert scanner.current_pick == 1

        # 5. UI should show the new pack (allow a few update cycles for UI to repopulate)
        for _ in range(30):
            root.update()
            root.update_idletasks()
            tree = app.dashboard.get_treeview("pack")
            rows = tree.get_children()
            if len(rows) >= 10:
                break
            time.sleep(0.05)

        assert len(rows) >= 10, (
            f"Pack table should show new draft cards (got {len(rows)} rows)"
        )
