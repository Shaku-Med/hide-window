import unittest

from screen_guard.backends.base import Backend
from screen_guard.controller import Guard, MAX_RETRIES, matches_keyword
from screen_guard.model import WindowInfo


class FakeBackend(Backend):
    can_hide_other_apps = True
    supports_keep_active = True

    def __init__(self, hide_ok=True, show_ok=True):
        self.hide_ok = hide_ok
        self.show_ok = show_ok
        self.hide_calls = []
        self.show_calls = []
        self.unprotect_calls = 0
        self.shield_calls = []
        self.shield_clears = 0
        self.windows = set()
        self.shielded = None

    def hide(self, win_id):
        self.hide_calls.append(win_id)
        return self.hide_ok

    def show(self, win_id):
        self.show_calls.append(win_id)
        return self.show_ok

    def unprotect_self(self):
        self.unprotect_calls += 1

    def is_window(self, win_id):
        return win_id in self.windows if self.windows else True

    def ensure_focus_shield(self, win_id):
        self.shield_calls.append(win_id)
        self.shielded = win_id
        return True

    def clear_focus_shield(self):
        self.shield_clears += 1
        self.shielded = None


def window(win_id, title="window", app="app"):
    return WindowInfo(id=win_id, title=title, app=app)


class KeywordTests(unittest.TestCase):
    def test_matches_substring(self):
        self.assertTrue(matches_keyword("My password vault", ".env, password"))

    def test_is_case_insensitive(self):
        self.assertTrue(matches_keyword("Top SECRET", "secret"))

    def test_no_match(self):
        self.assertFalse(matches_keyword("holiday photos", "secret, password"))

    def test_empty_keywords(self):
        self.assertFalse(matches_keyword("anything", "   ,  "))


class ApplyTests(unittest.TestCase):
    def test_hide_wanted_window(self):
        backend = FakeBackend(hide_ok=True)
        guard = Guard(backend)
        self.assertTrue(guard.apply(1, wanted=True))
        self.assertIn(1, guard.hidden)
        self.assertEqual(backend.hide_calls, [1])

    def test_already_hidden_is_not_hidden_again(self):
        backend = FakeBackend()
        guard = Guard(backend)
        guard.apply(1, wanted=True)
        guard.apply(1, wanted=True)
        self.assertEqual(backend.hide_calls, [1])

    def test_failure_counts_and_stops_after_max(self):
        backend = FakeBackend(hide_ok=False)
        guard = Guard(backend)
        for _ in range(MAX_RETRIES):
            self.assertFalse(guard.apply(7, wanted=True))
        self.assertEqual(len(backend.hide_calls), MAX_RETRIES)
        self.assertFalse(guard.apply(7, wanted=True))
        self.assertEqual(len(backend.hide_calls), MAX_RETRIES)

    def test_unwanted_shows_previously_hidden(self):
        backend = FakeBackend()
        guard = Guard(backend)
        guard.apply(1, wanted=True)
        self.assertTrue(guard.apply(1, wanted=False))
        self.assertNotIn(1, guard.hidden)
        self.assertEqual(backend.show_calls, [1])

    def test_unwanted_untouched_window_does_nothing(self):
        backend = FakeBackend()
        guard = Guard(backend)
        self.assertTrue(guard.apply(9, wanted=False))
        self.assertEqual(backend.show_calls, [])


class WantedTests(unittest.TestCase):
    def test_pinned_window_is_wanted_without_auto(self):
        guard = Guard(FakeBackend())
        guard.toggle_pin(3)
        self.assertTrue(guard.wanted(window(3), auto=False, keywords=""))

    def test_keyword_only_applies_when_auto_on(self):
        guard = Guard(FakeBackend())
        win = window(3, title="secret notes")
        self.assertFalse(guard.wanted(win, auto=False, keywords="secret"))
        self.assertTrue(guard.wanted(win, auto=True, keywords="secret"))


class HousekeepingTests(unittest.TestCase):
    def test_toggle_pin_adds_then_removes(self):
        guard = Guard(FakeBackend())
        guard.toggle_pin(5)
        self.assertIn(5, guard.pinned)
        guard.toggle_pin(5)
        self.assertNotIn(5, guard.pinned)

    def test_sync_drops_dead_windows(self):
        guard = Guard(FakeBackend())
        guard.pinned = {1, 2}
        guard.hidden = {2, 3}
        guard.fail_count = {3: 1, 4: 2}
        guard.sync(live={2})
        self.assertEqual(guard.pinned, {2})
        self.assertEqual(guard.hidden, {2})
        self.assertEqual(guard.fail_count, {})

    def test_restore_all_shows_everything_and_unprotects(self):
        backend = FakeBackend()
        guard = Guard(backend)
        guard.apply(1, wanted=True)
        guard.apply(2, wanted=True)
        guard.restore_all()
        self.assertEqual(guard.hidden, set())
        self.assertEqual(sorted(backend.show_calls), [1, 2])
        self.assertEqual(backend.unprotect_calls, 1)

    def test_restore_all_retries_on_failure(self):
        backend = FakeBackend(show_ok=False)
        guard = Guard(backend)
        guard.hidden = {1}
        guard.restore_all()
        self.assertEqual(backend.show_calls, [1, 1])
        self.assertEqual(guard.hidden, set())

    def test_unhide_all_clears_state(self):
        backend = FakeBackend()
        guard = Guard(backend)
        guard.pinned = {1}
        guard.hidden = {1}
        guard.fail_count = {1: 2}
        guard.keep_active = 1
        guard.unhide_all([window(1), window(2)])
        self.assertEqual(guard.pinned, set())
        self.assertEqual(guard.hidden, set())
        self.assertEqual(guard.fail_count, {})
        self.assertIsNone(guard.keep_active)
        self.assertEqual(sorted(backend.show_calls), [1, 2])


class KeepActiveTests(unittest.TestCase):
    def test_toggle_keep_active(self):
        backend = FakeBackend()
        guard = Guard(backend)
        guard.toggle_keep_active(4)
        self.assertEqual(guard.keep_active, 4)
        self.assertEqual(backend.shield_calls, [4])
        guard.toggle_keep_active(4)
        self.assertIsNone(guard.keep_active)
        self.assertGreaterEqual(backend.shield_clears, 1)

    def test_toggle_switches_target(self):
        backend = FakeBackend()
        guard = Guard(backend)
        guard.toggle_keep_active(1)
        guard.toggle_keep_active(2)
        self.assertEqual(guard.keep_active, 2)
        self.assertEqual(backend.shielded, 2)

    def test_sync_clears_dead_keep_active(self):
        backend = FakeBackend()
        guard = Guard(backend)
        guard.keep_active = 9
        guard.sync(live={1, 2})
        self.assertIsNone(guard.keep_active)
        self.assertGreaterEqual(backend.shield_clears, 1)

    def test_tick_focus_installs_shield_without_stealing_focus(self):
        backend = FakeBackend()
        backend.windows = {5}
        guard = Guard(backend)
        guard.keep_active = 5
        guard.tick_focus()
        self.assertEqual(backend.shield_calls, [5])
        self.assertEqual(backend.shielded, 5)
        self.assertTrue(guard.keep_active_ok)

    def test_clear_keep_active_removes_shield(self):
        backend = FakeBackend()
        guard = Guard(backend)
        guard.toggle_keep_active(1)
        self.assertTrue(guard.keep_active_ok)
        guard.clear_keep_active()
        self.assertIsNone(guard.keep_active)
        self.assertFalse(guard.keep_active_ok)
        self.assertIsNone(backend.shielded)
        self.assertGreaterEqual(backend.shield_clears, 1)


if __name__ == "__main__":
    unittest.main()
