from typing import Any

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.schemas.game import GameStateUpdate


class GameStateAgent(BaseAgent):
    """
    Parses, validates, and enriches the raw game-state snapshot.

    Outputs:
        validated_state   – clean GameStateUpdate dict
        score_differential – home minus away
        momentum_window   – list of last-5-play descriptions
        foul_trouble      – players with >= 4 fouls
    """

    def __init__(self) -> None:
        super().__init__("game_state_agent")

    async def run(self, context: AgentContext) -> AgentResult:
        raw = context.game_state

        # Re-validate against our Pydantic schema to guarantee shape
        state = GameStateUpdate.model_validate(raw)

        score_diff = state.home_score - state.away_score

        momentum_window = [p.description for p in state.recent_plays[-5:]]

        foul_trouble = self._identify_foul_trouble(state)

        on_court_home = [p for p in state.home_players if p.is_on_court]
        on_court_away = [p for p in state.away_players if p.is_on_court]

        data: dict[str, Any] = {
            "validated_state": state.model_dump(),
            "score_differential": score_diff,
            "momentum_window": momentum_window,
            "foul_trouble": foul_trouble,
            "on_court_home": [p.model_dump() for p in on_court_home],
            "on_court_away": [p.model_dump() for p in on_court_away],
            "is_close_game": abs(score_diff) <= 5,
            "is_blowout": abs(score_diff) >= 20,
            "leading_team": "home" if score_diff > 0 else ("away" if score_diff < 0 else "tied"),
        }

        # Merge into shared pipeline so downstream agents can read without
        # re-parsing the raw dict
        context.pipeline_data["game_state"] = data

        return AgentResult(agent_name=self.name, success=True, data=data)

    def _identify_foul_trouble(self, state: GameStateUpdate) -> list[dict[str, Any]]:
        trouble = []
        for player in state.home_players + state.away_players:
            if player.fouls >= 4:
                trouble.append(
                    {
                        "player_id": player.player_id,
                        "name": player.name,
                        "fouls": player.fouls,
                        "team": "home" if player in state.home_players else "away",
                    }
                )
        return trouble
