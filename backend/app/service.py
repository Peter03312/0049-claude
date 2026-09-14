"""把保存的项目输入送进核心算法，统一结果结构。"""

from __future__ import annotations

from typing import Tuple

from app.core.tree import Matrix, build_tree


def _to_matrix(objects: list, attributes: list, cells: dict) -> Matrix:
    obj_ids = [o["id"] for o in objects]
    parsed = {}
    for key, val in cells.items():
        oid_s, aid_s = key.split(":")
        parsed[(int(oid_s), int(aid_s))] = val
    return Matrix(obj_ids, parsed)


def compute_project(objects: list, attributes: list, cells: dict) -> dict:
    """保证返回值是完整树或无解诊断，永远不包含残缺树。"""
    matrix = _to_matrix(objects, attributes, cells)
    return build_tree(matrix)
