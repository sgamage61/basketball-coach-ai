from typing import Any

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.schemas.recommendations import KeyMatchup, MatchupAdvantage, Priority, StrategyAdjustment


class StrategyAgent(BaseAgent):
    """
    Converts analytics insights into concrete strategic adjustments and matchup notes.

    Reads:   context.pipeline_data["game_state"], context.pipeline_data["analytics"]
    Outputs: strategy_adjustments, key_matchups
    """

    def __init__(self) -> None:
        super().__init__("strategy_agent")

    async def run(self, context: AgentContext) -> AgentResult:
        gs = context.pipeline_data.get("game_state", {})
        analytics = context.pipeline_data.get("analytics", {}).get("analytics_summary", {})
        validated = gs.get("validated_state", {})

        is_close = gs.get("is_close_game", True)
        is_blowout = gs.get("is_blowout", False)
        leading = gs.get("leading_team", "tied")
        momentum_team = analytics.get("momentum_team")
        foul_trouble = gs.get("foul_trouble", [])
        quarter = validated.get("quarter", 4)

        adjustments = self._build_adjustments(
            context.requesting_team,
            is_close,
            is_blowout,
            leading,
            momentum_team,
            foul_trouble,
            analytics,
            quarter,
        )

        home_players = validated.get("home_players", [])
        away_players = validated.get("away_players", [])
        key_matchups = self._build_key_matchups(
            home_players if context.requesting_team == "home" else away_players,
            away_players if context.requesting_team == "home" else home_players,
        )

        data: dict[str, Any] = {
            "strategy_adjustments": [a.model_dump() for a in adjustments],
            "key_matchups": [m.model_dump() for m in key_matchups],
        }
        context.pipeline_data["strategy"] = data

        return AgentResult(agent_name=self.name, success=True, data=data)

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _build_adjustments(
        self,
        team: str,
        is_close: bool,
        is_blowout: bool,
        leading: str,
        momentum_team: str | None,
        foul_trouble: list[dict],
        analytics: dict,
        quarter: int,
    ) -> list[StrategyAdjustment]:
        adj: list[StrategyAdjustment] = []
        is_leading = leading == team
        is_losing = leading != team and leading != "tied"

        if is_blowout and is_leading:
            adj.append(
                StrategyAdjustment(
                    category="pace",
                    recommendation="Slow the pace — use full shot clock, protect the ball",
                    priority=Priority.HIGH,
                    rationale="Large lead; protecting possession is more valuable than scoring quickly",
                    estimated_impact="Reduces opponent's number of possessions to close the gap",
                )
            )

        if is_blowout and is_losing:
            adj.append(
                StrategyAdjustment(
                    category="pace",
                    recommendation="Push tempo aggressively — run in transition, foul to stop the clock",
                    priority=Priority.HIGH,
                    rationale="Must generate possessions quickly to overcome the deficit",
                    estimated_impact="Could generate 6-8 additional possessions in final minutes",
                )
            )

        if momentum_team and momentum_team != team:
            adj.append(
                StrategyAdjustment(
                    category="defense",
                    recommendation="Call a set play to break opponent's rhythm — deny transition opportunities",
                    priority=Priority.HIGH,
                    rationale="Opponent has scoring momentum; timeout should disrupt it",
                    estimated_impact="Momentum breakers statistically improve defensive efficiency ~12%",
                )
            )

        trouble_on_our_team = [f for f in foul_trouble if f["team"] == team]
        if trouble_on_our_team and quarter >= 3:
            player_names = ", ".join(f["name"] for f in trouble_on_our_team)
            adj.append(
                StrategyAdjustment(
                    category="lineup",
                    recommendation=f"Sit {player_names} — foul trouble in a close game is too costly",
                    priority=Priority.HIGH,
                    rationale="Players with 4+ fouls risk fouling out at a critical moment",
                    estimated_impact="Prevents fouling out; preserves player for late-game execution",
                )
            )

        if analytics.get("three_point_differential", 0) < -3:
            adj.append(
                StrategyAdjustment(
                    category="defense",
                    recommendation="Switch to a tighter perimeter scheme — opponent is winning the three-point battle",
                    priority=Priority.MEDIUM,
                    rationale=f"Three-point differential is {analytics['three_point_differential']}",
                    estimated_impact="Reducing opponent three-point makes by 2 is equivalent to ~6 points",
                )
            )

        if is_close and quarter == 4:
            adj.append(
                StrategyAdjustment(
                    category="offense",
                    recommendation="Iso your best scorer or run pick-and-roll with your best ball-handler",
                    priority=Priority.HIGH,
                    rationale="Late close games favour high-execution half-court sets",
                    estimated_impact="High-IQ plays in the final minutes have >60% scoring efficiency",
                )
            )

        return adj

    def _build_key_matchups(
        self,
        our_players: list[dict],
        their_players: list[dict],
    ) -> list[KeyMatchup]:
        matchups: list[KeyMatchup] = []
        # Pair by position index as a heuristic
        pairs = zip(our_players[:3], their_players[:3])
        for ours, theirs in pairs:
            our_pts = ours.get("points", 0)
            their_pts = theirs.get("points", 0)
            advantage = (
                MatchupAdvantage.FAVORABLE
                if our_pts > their_pts + 4
                else (
                    MatchupAdvantage.UNFAVORABLE if their_pts > our_pts + 4 else MatchupAdvantage.NEUTRAL
                )
            )
            matchups.append(
                KeyMatchup(
                    player_name=ours.get("name", "Unknown"),
                    opponent_name=theirs.get("name", "Unknown"),
                    advantage=advantage,
                    notes=f"{ours.get('name')} has {our_pts} pts vs {theirs.get('name')}'s {their_pts} pts",
                    suggested_action=(
                        "Keep attacking this matchup"
                        if advantage == MatchupAdvantage.FAVORABLE
                        else "Provide help-side support"
                    ),
                )
            )
        return matchups
