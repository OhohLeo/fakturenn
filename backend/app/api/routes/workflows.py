import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Message,
    Workflow,
    WorkflowCreate,
    WorkflowPublic,
    WorkflowsPublic,
    WorkflowUpdate,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("/", response_model=WorkflowsPublic)
def read_workflows(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve workflows for the current user.
    """
    count_statement = (
        select(func.count())
        .select_from(Workflow)
        .where(Workflow.user_id == current_user.id)
    )
    count = session.exec(count_statement).one()
    statement = (
        select(Workflow)
        .where(Workflow.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
    )
    workflows = session.exec(statement).all()

    return WorkflowsPublic(data=workflows, count=count)


@router.get("/{id}", response_model=WorkflowPublic)
def read_workflow(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Any:
    """
    Get workflow by ID.
    """
    workflow = session.get(Workflow, id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if workflow.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return workflow


@router.post("/", response_model=WorkflowPublic)
def create_workflow(
    *, session: SessionDep, current_user: CurrentUser, workflow_in: WorkflowCreate
) -> Any:
    """
    Create new workflow.
    """
    workflow = Workflow.model_validate(
        workflow_in, update={"user_id": current_user.id}
    )
    session.add(workflow)
    session.commit()
    session.refresh(workflow)
    return workflow


@router.put("/{id}", response_model=WorkflowPublic)
def update_workflow(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    workflow_in: WorkflowUpdate,
) -> Any:
    """
    Update a workflow.
    """
    workflow = session.get(Workflow, id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if workflow.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    update_dict = workflow_in.model_dump(exclude_unset=True)
    workflow.sqlmodel_update(update_dict)
    session.add(workflow)
    session.commit()
    session.refresh(workflow)
    return workflow


@router.delete("/{id}")
def delete_workflow(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete a workflow.
    """
    workflow = session.get(Workflow, id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if workflow.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    session.delete(workflow)
    session.commit()
    return Message(message="Workflow deleted successfully")
