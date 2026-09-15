"""把保存的项目输入送进核心算法，统一结果结构。"""

from __future__ import annotations

from typing import List, Optional

from app.core.tree import Matrix, build_tree


def _to_matrix(objects: list, attributes: list, cells: dict) -> Matrix:
    obj_ids = [o["id"] for o in objects]
    attr_ids = [a["id"] for a in attributes]
    parsed = {}
    for key, val in cells.items():
        oid_s, aid_s = key.split(":")
        parsed[(int(oid_s), int(aid_s))] = val
    return Matrix(obj_ids, parsed, attr_ids=attr_ids)


def compute_project(
    objects: list,
    attributes: list,
    cells: dict,
    locks: Optional[List[dict]] = None,
) -> dict:
    """保证返回值是完整树或无解诊断，永远不包含残缺树。"""
    matrix = _to_matrix(objects, attributes, cells)
    return build_tree(matrix, raw_locks=locks or [])
