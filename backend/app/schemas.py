"""请求/响应模型与输入校验。"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

Tribool = Literal["true", "false", "unknown"]


class ObjectIn(BaseModel):
    id: int = Field(gt=0)
    label: str = Field(min_length=1, max_length=60)
    note: str = Field(default="", max_length=300)


class AttributeIn(BaseModel):
    id: int = Field(gt=0)
    label: str = Field(min_length=1, max_length=60)


class ProjectIn(BaseModel):
    name: str = Field(default="我的辨认卡", min_length=1, max_length=100)
    # 小组录入 4–20 张对象卡
    objects: List[ObjectIn] = Field(min_length=4, max_length=20)
    attributes: List[AttributeIn] = Field(min_length=1, max_length=20)
    # 键形如 "对象id:属性id"，缺省单元格按「未知」处理
    cells: Dict[str, Tribool] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _name_strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("名称不能为空")
        return v

    @field_validator("objects", "attributes")
    @classmethod
    def _unique_ids(cls, v):
        ids = [x.id for x in v]
        if len(ids) != len(set(ids)):
            raise ValueError("编号必须唯一")
        for x in v:
            x.label = x.label.strip()
        return v

    @field_validator("cells")
    @classmethod
    def _cell_keys(cls, v: Dict[str, Tribool]) -> Dict[str, Tribool]:
        for key in v:
            parts = key.split(":")
            if len(parts) != 2 or not all(
                p.isdigit() and int(p) > 0 for p in parts
            ):
                raise ValueError(
                    f"单元格键必须是 “对象编号:属性编号”，收到 {key!r}"
                )
        return v

    def normalized(self) -> dict:
        """统一单元格键顺序为 "oid:aid" 并只保留属于现有对象/属性的单元。"""
        obj_ids = {o.id for o in self.objects}
        attr_ids = {a.id for a in self.attributes}
        cells: Dict[str, Tribool] = {}
        for key, val in self.cells.items():
            oid, aid = (int(p) for p in key.split(":"))
            if oid in obj_ids and aid in attr_ids:
                cells[f"{oid}:{aid}"] = val
        return self.model_copy(update={"cells": cells}).model_dump()


class ProjectOut(BaseModel):
    id: int
    name: str
    objects: list
    attributes: list
    cells: dict
    inputVersion: int
    result: Optional[dict]
    resultVersion: Optional[int]
    resultFresh: bool
    createdAt: str
    updatedAt: str


class SnapshotOut(BaseModel):
    id: int
    projectId: int
    inputVersion: int
    objects: list
    attributes: list
    cells: dict
    result: dict
    createdAt: str


class ComputeOut(BaseModel):
    result: dict
    savedSnapshot: bool
    snapshotId: Optional[int] = None
