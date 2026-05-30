from typing import Any

from app.agents.base import AgentContext, AgentResult, BaseAgent


class RecommendationAgent(BaseAgent):
    """
    Terminal agent — synthesises all upstream pipeline data into a single,
    human-readable coaching recommendation with a confidence score.

    Reads:   context.pipeline_data (all upstream keys)
    Outputs: primary_recommendation, alternative_recommendations,
             reasoning, confidence_score
    """

    def __init__(self) -> None:
        super().__init__("recommendation_agent")

    async def run(self, context: AgentContext) -> AgentResult:
        gs = context.pipeline_data.get("game_state", {})
        analytics = context.pipeline_data.get("analytics", {}).get("analytics_summary", {})
        strategy = context.pipeline_data.get("strategy", {})

        adjustments: list[dict] = strategy.get("strategy_adjustments", [])
        validated: dict = gs.get("validated_state", {})

        primary, alternatives = self._derive_primary_recommendation(adjustments, gs, analytics)
        reasoning = self._build_reasoning(gs, analytics, adjustments)
        confidence = self._compute_confidence(gs, analytics, adjustments)

        data: dict[str, Any] = {
            "primary_recommendation": primary,
            "alternative_recommendations": alternatives,
            "reasoning": reasoning,
            "confidence_score": confidence,
            "quarter": validated.get("quarter", 0),
            "time_remaining": validated.get("time_remaining", ""),
        }

        # Publish to the shared pipeline so the orchestrator can read the
        # synthesised recommendation directly (same pattern as upstream agents)
        context.pipeline_data["recommendation_agent"] = data

        return AgentResult(agent_name=self.name, success=True, data=data)

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _derive_primary_recommendation(
        self,
        adjustments: list[dict],
        gs: dict,
        analytics: dict,
    ) -> tuple[str, list[str]]:
        high = [a for a in adjustments if a.get("priority") == "high"]
        medium = [a for a in adjustments if a.get("priority") == "medium"]

        if not adjustments:
            return (
                "Maintain current rotations and defensive assignments",
                ["Take a strategic breather and reinforce execution on both ends"],
            )

        primary = (high or medium)[0]["recommendation"]
        alternatives = [a["recommendation"] for a in (high + medium)[1:3]]

        if not alternatives:
            alternatives = ["Stay disciplined on defense and trust your offense"]

        return primary, alternatives

    def _build_reasoning(
        self, gs: dict, analytics: dict, adjustments: list[dict]
    ) -> str:
        parts: list[str] = []

        leading = gs.get("leading_team", "tied")
        score_diff = abs(gs.get("score_differential", 0))
        momentum = analytics.get("momentum_team")
        foul_trouble = gs.get("foul_trouble", [])

        if leading == "tied":
            parts.append("Game is tied — every possession is critical.")
        elif score_diff <= 5:
            parts.append(f"Close game with a {score_diff}-point margin; execution wins from here.")
        else:
            parts.append(f"Team is {'up' if leading == 'home' else 'down'} {score_diff} points.")

        if momentum:
            parts.append(
                f"Opponent has scoring momentum — this timeout is the right call to disrupt their rhythm."
            )

        if foul_trouble:
            names = ", ".join(f["name"] for f in foul_trouble)
            parts.append(f"{names} in foul trouble — lineup decisions are crucial.")

        hot = analytics.get("hot_players", [])
        if hot:
            parts.append(f"Hot players to exploit: {', '.join(hot)}.")

        high_adj = [a["recommendation"] for a in adjustments if a.get("priority") == "high"]
        if high_adj:
            parts.append(f"Top priority action: {high_adj[0]}")

        return " ".join(parts) if parts else "Execute the game plan with full focus."

    def _compute_confidence(
        self, gs: dict, analytics: dict, adjustments: list[dict]
    ) -> float:
        """
        Heuristic confidence score (0.0–1.0).
        Higher when: data is rich, situation is clear-cut, and there are strong signals.
        """
        score = 0.5

        if gs.get("validated_state", {}).get("home_players"):
            score += 0.1  # We have player-level data
        if gs.get("foul_trouble"):
            score += 0.05  # Clear decision trigger
        if analytics.get("momentum_team"):
            score += 0.1  # Momentum signal detected
        if len(adjustments) >= 2:
            score += 0.1  # Multiple corroborating signals
        if analytics.get("hot_players"):
            score += 0.05
        if gs.get("is_close_game"):
            score += 0.05  # Close game = clearer marginal-value decisions

        return min(round(score, 2), 0.95)  # Cap at 0.95 — never fully certain
