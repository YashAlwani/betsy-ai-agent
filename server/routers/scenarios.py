from fastapi import APIRouter, HTTPException

from server.state import state, VALID_SCENARIOS

router = APIRouter(prefix="/api/scenario", tags=["scenarios"])


@router.get("")
def list_scenarios():
    return {
        "active": state.active_scenario,
        "available": ["reset"] + VALID_SCENARIOS,
    }


@router.post("/{name}")
def inject_scenario(name: str):
    if name == "reset":
        state.reset()
        return {"status": "reset", "active_scenario": "normal", "message": "State reset to base data"}
    if name not in VALID_SCENARIOS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown scenario '{name}'. Valid options: {['reset'] + VALID_SCENARIOS}",
        )
    scenario = state.apply_scenario(name)
    return {
        "status": "injected",
        "active_scenario": name,
        "description": scenario.get("description", ""),
        "expected_action": scenario.get("expected_agent_action", ""),
    }
