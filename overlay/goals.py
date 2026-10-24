# SPDX-License-Identifier: GPL-3.0-or-later
"""Detects new goals in focus-team matches between two refreshes."""
from overlay.model import Match
from overlay.selection import team_of

Key = tuple[str, str, object]


def _key(m: Match) -> Key:
    return (m.home, m.away, m.kickoff)


class GoalTracker:
    def __init__(self):
        self.scores: dict[Key, tuple[int, int]] | None = None

    def update(self, matches: list[Match]) -> dict[Match, str]:
        """Returns {match: "for" | "against"} for focus matches whose score went up."""
        current = {_key(m): (m.home_goals, m.away_goals) for m in matches
                   if m.home_goals is not None and m.away_goals is not None}
        goals = {}
        if self.scores is not None:
            for m in matches:
                before, after = self.scores.get(_key(m)), current.get(_key(m))
                if before is None or after is None:
                    continue
                home_scored, away_scored = after[0] > before[0], after[1] > before[1]
                if not (home_scored or away_scored):
                    continue
                if team_of(m.home):
                    goals[m] = "for" if home_scored else "against"
                elif team_of(m.away):
                    goals[m] = "for" if away_scored else "against"
        self.scores = current
        return goals
