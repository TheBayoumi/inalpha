"""Evolver run/candidate 查询与取消端点。"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from inalpha_paper.account_id import account_id_from_user
from inalpha_shared.auth import User, get_current_user
from inalpha_shared.db import DBConn

from ..storage import candidates, run_queries, runs
from .presenters import candidate_response, run_response
from .schemas import CandidateResponse, RunStatusResponse

router = APIRouter()


@router.get("/runs/{run_id}", response_model=RunStatusResponse)
async def get_run(
    run_id: UUID,
    db: DBConn,
    user: Annotated[User, Depends(get_current_user)],
) -> RunStatusResponse:
    owner = account_id_from_user(user)
    row = await runs.get_run(db, run_id, owner)
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    slots = await candidates.list_candidates(db, run_id, owner)
    summary = await candidates.summarize(db, run_id)
    return run_response(row, candidate_rows=slots, summary=summary)


@router.get("/candidates/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: UUID,
    db: DBConn,
    user: Annotated[User, Depends(get_current_user)],
) -> CandidateResponse:
    row = await candidates.get_candidate(db, candidate_id, account_id_from_user(user))
    if row is None:
        raise HTTPException(status_code=404, detail="candidate not found")
    return candidate_response(row)


@router.post("/runs/{run_id}/abort", response_model=RunStatusResponse)
async def abort_run(
    run_id: UUID,
    request: Request,
    db: DBConn,
    user: Annotated[User, Depends(get_current_user)],
) -> RunStatusResponse:
    owner = account_id_from_user(user)
    transitioned = await run_queries.abort_owned(db, run_id, owner)
    row = transitioned
    if row is None:
        row = await runs.get_run(db, run_id, owner)
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    if transitioned is not None and transitioned["status"] == "cancelling":
        await request.app.state.evolution_manager.abort(run_id)
    return run_response(row)
