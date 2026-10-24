# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import datetime, timezone

from overlay.goals import GoalTracker
from overlay.model import Match, Status

KICKOFF = datetime(2026, 10, 14, 19, 0, tzinfo=timezone.utc)


def m(home, away, h, a, comp="UCL"):
    return Match(comp, home, away, h, a, Status.LIVE, KICKOFF)


def test_first_update_reports_nothing():
    assert GoalTracker().update([m("Slovan Bratislava", "VfB Stuttgart", 0, 2)]) == {}


def test_goal_for_focus_team_away():
    t = GoalTracker()
    t.update([m("Slovan Bratislava", "VfB Stuttgart", 0, 0)])
    new = m("Slovan Bratislava", "VfB Stuttgart", 0, 1)
    assert t.update([new]) == {new: "for"}


def test_goal_against_focus_team_home():
    t = GoalTracker()
    t.update([m("VfB Stuttgart", "Atlético Madrid", 1, 0)])
    new = m("VfB Stuttgart", "Atlético Madrid", 1, 1)
    assert t.update([new]) == {new: "against"}


def test_non_focus_goal_ignored():
    t = GoalTracker()
    t.update([m("FC Bayern München", "SC Freiburg", 0, 0, comp="BL")])
    assert t.update([m("FC Bayern München", "SC Freiburg", 1, 0, comp="BL")]) == {}


def test_match_appearing_later_with_score_is_not_a_goal():
    t = GoalTracker()
    t.update([])
    assert t.update([m("1860 Munich", "Bayreuth", 1, 0, comp="RLB")]) == {}


def test_score_correction_downwards_ignored():
    t = GoalTracker()
    t.update([m("VfB Stuttgart", "Atlético Madrid", 2, 0)])
    assert t.update([m("VfB Stuttgart", "Atlético Madrid", 1, 0)]) == {}
