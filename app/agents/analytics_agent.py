from typing import Any

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.schemas.recommendations import AnalyticsSummary


class AnalyticsAgent(BaseAgent):
    """
    Derives statistical insights from the validated game state.

    Reads:   context.pipeline_data["game_state"]
    Outputs: analytics_summary (AnalyticsSummary dict)
    """

    def __init__(self) -> None:
        super().__init__("analytics_agent")

    async def run(self, context: AgentContext) -> AgentResult:
        gs = context.pipeline_data.get("game_state", {})
        validated = gs.get("validated_state", {})

        home_players: list[dict] = validated.get("home_players", [])
        away_players: list[dict] = validated.get("away_players", [])
        recent_plays: list[dict] = validated.get("recent_plays", [])

        scoring_run, momentum_team = self._detect_scoring_run(recent_plays)
        hot_players = self._find_hot_players(home_players + away_players)
        cold_players = self._find_cold_players(home_players + away_players)

        home_stats = self._aggregate_team_stats(home_players)
        away_stats = self._aggregate_team_stats(away_players)

        three_pt_diff = (
            home_stats["three_pointers_made"] - away_stats["three_pointers_made"]
        )
        paint_diff = self._estimate_paint_scoring(recent_plays, "home") - self._estimate_paint_scoring(
            recent_plays, "away"
        )
        turnover_diff = home_stats["turnovers"] - away_stats["turnovers"]
        rebound_diff = home_stats["rebounds"] - away_stats["rebounds"]

        pace = self._estimate_pace(recent_plays)

        def_vulns = self._find_defensive_vulnerabilities(away_players if context.requesting_team == "home" else home_players)
        off_opps = self._find_offensive_opportunities(
            home_players if context.requesting_team == "home" else away_players
        )

        summary = AnalyticsSummary(
            scoring_run=scoring_run,
            momentum_team=momentum_team,
            hot_players=hot_players,
            cold_players=cold_players,
            defensive_vulnerabilities=def_vulns,
            offensive_opportunities=off_opps,
            pace_rating=pace,
            three_point_differential=three_pt_diff,
            paint_scoring_differential=paint_diff,
            turnover_differential=turnover_diff,
            rebounding_differential=rebound_diff,
        )

        data: dict[str, Any] = {"analytics_summary": summary.model_dump()}
        context.pipeline_data["analytics"] = data

        return AgentResult(agent_name=self.name, success=True, data=data)

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _detect_scoring_run(self, plays: list[dict]) -> tuple[str, str | None]:
        if len(plays) < 3:
            return ("Not enough data", None)
        home_pts = sum(p.get("points", 0) for p in plays[-6:] if p.get("team") == "home")
        away_pts = sum(p.get("points", 0) for p in plays[-6:] if p.get("team") == "away")
        if home_pts == 0 and away_pts == 0:
            return ("No scoring run detected", None)
        if home_pts > away_pts:
            return (f"Home team on a {home_pts}-{away_pts} run", "home")
        if away_pts > home_pts:
            return (f"Away team on a {away_pts}-{home_pts} run", "away")
        return ("Even exchange", None)

    def _aggregate_team_stats(self, players: list[dict]) -> dict[str, int]:
        keys = ("rebounds", "turnovers", "three_pointers_made", "steals", "blocks")
        return {k: sum(p.get(k, 0) for p in players) for k in keys}

    def _find_hot_players(self, players: list[dict]) -> list[str]:
        return [
            p["name"]
            for p in players
            if p.get("points", 0) >= 15 and p.get("field_goals_attempted", 0) > 0
            and p.get("field_goals_made", 0) / p["field_goals_attempted"] >= 0.55
        ]

    def _find_cold_players(self, players: list[dict]) -> list[str]:
        return [
            p["name"]
            for p in players
            if p.get("field_goals_attempted", 0) >= 5
            and p.get("field_goals_made", 0) / p["field_goals_attempted"] <= 0.25
        ]

    def _estimate_paint_scoring(self, plays: list[dict], team: str) -> int:
        return sum(
            p.get("points", 0)
            for p in plays
            if p.get("team") == team and p.get("event_type") in ("field_goal", "layup", "dunk")
        )

    def _estimate_pace(self, plays: list[dict]) -> str:
        if len(plays) > 10:
            return "fast"
        if len(plays) > 5:
            return "moderate"
        return "slow"

    def _find_defensive_vulnerabilities(self, opponent_players: list[dict]) -> list[str]:
        vulns = []
        for p in opponent_players:
            if p.get("three_pointers_made", 0) >= 3:
                vulns.append(f"{p['name']} is hot from three — close out harder")
            if p.get("fouls", 0) >= 3:
                vulns.append(f"{p['name']} is in foul trouble — attack in the paint")
        return vulns

    def _find_offensive_opportunities(self, team_players: list[dict]) -> list[str]:
        opps = []
        for p in team_players:
            if p.get("assists", 0) >= 5:
                opps.append(f"Run plays through {p['name']} — excellent vision tonight")
            if p.get("plus_minus", 0) >= 10:
                opps.append(f"Keep {p['name']} on the court — strong plus/minus")
        return opps
