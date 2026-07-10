import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import CurrentUser, get_assignment_or_404, get_current_user, require_assignment_teacher
from app.models import Assignment
from app.schemas import AssignmentCreate, AssignmentOut, AssignmentTaskOut, AssignmentUpdate
from app.services import assignments as assignments_svc

router = APIRouter(prefix="/assignments", tags=["assignments"])


async def _to_out(db: AsyncSession, assignment: Assignment) -> dict:
    tasks = await assignments_svc.get_tasks(db, assignment_id=assignment.id)
    return {
        **AssignmentOut.model_validate(assignment).model_dump(exclude={"tasks"}),
        "tasks": [AssignmentTaskOut.model_validate(t).model_dump() for t in tasks],
    }


@router.post("", response_model=AssignmentOut)
async def create_assignment(
    body: AssignmentCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    assignment = await assignments_svc.create_assignment(db, teacher_id=user.user_id, body=body)
    await db.commit()
    return await _to_out(db, assignment)


@router.get("", response_model=list[AssignmentOut])
async def list_assignments(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    items = await assignments_svc.list_assignments_for_teacher(db, teacher_id=user.user_id)
    return [await _to_out(db, a) for a in items]


@router.get("/{assignment_id}", response_model=AssignmentOut)
async def get_assignment(
    assignment: Assignment = Depends(get_assignment_or_404),
    db: AsyncSession = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
):
    return await _to_out(db, assignment)


@router.patch("/{assignment_id}", response_model=AssignmentOut)
async def update_assignment(
    body: AssignmentUpdate,
    assignment: Assignment = Depends(require_assignment_teacher),
    db: AsyncSession = Depends(get_db),
):
    assignment = await assignments_svc.update_assignment(db, assignment=assignment, body=body)
    await db.commit()
    return await _to_out(db, assignment)


@router.delete("/{assignment_id}", status_code=204)
async def delete_assignment(
    assignment: Assignment = Depends(require_assignment_teacher),
    db: AsyncSession = Depends(get_db),
) -> None:
    await assignments_svc.delete_assignment(db, assignment=assignment)
    await db.commit()
