"""FastAPI 入口：项目 CRUD、计算并保存快照。"""

from __future__ import annotations

from typing import List

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.db import get_db, init_db
from app.models import Project, Snapshot
from app.schemas import ComputeOut, ProjectIn, ProjectOut, SnapshotOut
from app.service import compute_project


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="树叶辨认卡 API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


def _serialize_project(p: Project) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "objects": p.objects,
        "attributes": p.attributes,
        "cells": p.cells,
        "inputVersion": p.input_version,
        "result": p.result if p.result_fresh else None,
        "resultVersion": p.result_version if p.result_fresh else None,
        "resultFresh": p.result_fresh,
        "createdAt": p.created_at.isoformat() if p.created_at else None,
        "updatedAt": p.updated_at.isoformat() if p.updated_at else None,
    }


def _serialize_snapshot(s: Snapshot) -> dict:
    return {
        "id": s.id,
        "projectId": s.project_id,
        "inputVersion": s.input_version,
        "objects": s.objects,
        "attributes": s.attributes,
        "cells": s.cells,
        "result": s.result,
        "createdAt": s.created_at.isoformat() if s.created_at else None,
    }


def _get_project(db: Session, project_id: int) -> Project:
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(status_code=404, detail="找不到这个辨认卡项目")
    return p


@app.post("/api/projects", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectIn, db: Session = Depends(get_db)) -> dict:
    data = payload.normalized()
    p = Project(
        name=data["name"],
        objects=data["objects"],
        attributes=data["attributes"],
        cells=data["cells"],
        input_version=1,
        result=None,
        result_version=None,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _serialize_project(p)


@app.get("/api/projects", response_model=List[ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> list:
    return [_serialize_project(p) for p in db.query(Project).order_by(Project.id).all()]


@app.get("/api/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)) -> dict:
    return _serialize_project(_get_project(db, project_id))


@app.put("/api/projects/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int, payload: ProjectIn, db: Session = Depends(get_db)
) -> dict:
    """编辑输入：版本号 +1 并令旧树过期（不展示、不当作有效结果）。"""
    p = _get_project(db, project_id)
    data = payload.normalized()
    p.name = data["name"]
    p.objects = data["objects"]
    p.attributes = data["attributes"]
    p.cells = data["cells"]
    p.input_version += 1
    p.result = None
    p.result_version = None
    db.commit()
    db.refresh(p)
    return _serialize_project(p)


@app.delete("/api/projects/{project_id}", status_code=204, response_class=Response)
def delete_project(project_id: int, db: Session = Depends(get_db)) -> Response:
    p = _get_project(db, project_id)
    db.delete(p)
    db.commit()
    return Response(status_code=204)


@app.post("/api/projects/{project_id}/compute", response_model=ComputeOut)
def compute(project_id: int, db: Session = Depends(get_db)) -> dict:
    """按当前输入计算辨认树：保存结果，并把输入+结果存为快照。"""
    p = _get_project(db, project_id)
    result = compute_project(p.objects, p.attributes, p.cells)

    snapshot = Snapshot(
        project_id=p.id,
        input_version=p.input_version,
        objects=p.objects,
        attributes=p.attributes,
        cells=p.cells,
        result=result,
    )
    db.add(snapshot)
    p.result = result
    p.result_version = p.input_version
    db.commit()
    db.refresh(snapshot)
    return {"result": result, "savedSnapshot": True, "snapshotId": snapshot.id}


@app.get("/api/projects/{project_id}/snapshots", response_model=List[SnapshotOut])
def list_snapshots(project_id: int, db: Session = Depends(get_db)) -> list:
    _get_project(db, project_id)
    rows = (
        db.query(Snapshot)
        .filter(Snapshot.project_id == project_id)
        .order_by(Snapshot.id.desc())
        .all()
    )
    return [_serialize_snapshot(s) for s in rows]


@app.get("/api/snapshots/{snapshot_id}", response_model=SnapshotOut)
def get_snapshot(snapshot_id: int, db: Session = Depends(get_db)) -> dict:
    s = db.get(Snapshot, snapshot_id)
    if s is None:
        raise HTTPException(status_code=404, detail="找不到这个快照")
    return _serialize_snapshot(s)
