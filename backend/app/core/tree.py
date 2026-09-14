"""核心算法：从三值属性矩阵构造「逐步都能分开对象」的二分辨认树。

规则（对应需求）：

* 单元格取值：真 / 假 / 未知。某个属性在某个对象上若为「未知」，
  则该属性不能用于任何仍包含该对象的候选集——因为把未知当成假，
  就会把叶子认错。
* 只有当候选对象在该属性上全部已知，且真、假两组都非空时，
  该属性才是这个候选集上的「合法二分属性」。
* 在所有属性里选一个做根，递归构造两棵子树；通过动态规划，
  依次最小化「最大叶深」「叶深总和」；仍并列时，比较树的
  「属性编号前序序列」（假分支在前），取数值字典序最小者。
* 无法从根构造完整树时，给出对孩子友好的阻断诊断，绝不返回残缺树。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, FrozenSet, List, Optional, Tuple

TRUE = "true"
FALSE = "false"
UNKNOWN = "unknown"
VALUE_LABELS = {TRUE: "真", FALSE: "假", UNKNOWN: "未知"}

BitMatrix = Dict[int, int]  # attribute id -> 位掩码（第 i 位 = 第 i 个对象上的值）


class Matrix:
    """以位掩码保存的三值矩阵。

    对每个属性保存两个掩码：known（已知位）与 true（真位）。
    未知 = 已知位为 0；已知且真 = true 位为 1；已知且假 = 已知 1 且 真 0。
    """

    def __init__(self, object_ids: List[int], cells: Dict[Tuple[int, int], str]):
        if len(object_ids) != len(set(object_ids)):
            raise ValueError("对象编号重复")
        self.object_ids = list(object_ids)
        self.index = {oid: i for i, oid in enumerate(object_ids)}
        self.true_mask: BitMatrix = {}
        self.known_mask: BitMatrix = {}
        for (oid, aid), val in cells.items():
            if oid not in self.index or val not in VALUE_LABELS:
                continue
            bit = 1 << self.index[oid]
            self.true_mask.setdefault(aid, 0)
            self.known_mask.setdefault(aid, 0)
            if val == UNKNOWN:
                continue  # 未知：既不置已知位也不置真位
            self.known_mask[aid] |= bit
            if val == TRUE:
                self.true_mask[aid] |= bit
        self.all_mask = (1 << len(object_ids)) - 1
        self.attr_ids = sorted(set(self.known_mask) | set(self.true_mask))

    def is_legal(self, attr: int, subset: int) -> bool:
        """attr 能否把 subset 分成非空的真假两组（候选均非未知）。"""
        if subset == 0 or subset & (subset - 1) == 0:
            return False
        if (self.known_mask.get(attr, 0) & subset) != subset:
            return False
        t = self.true_mask.get(attr, 0) & subset
        return t != 0 and t != subset

    def split(self, attr: int, subset: int) -> Tuple[int, int]:
        """返回 (假组, 真组)，假在前。"""
        t = self.true_mask.get(attr, 0) & subset
        return subset ^ t, t

    def legal_attrs(self, subset: int) -> List[int]:
        return [a for a in self.attr_ids if self.is_legal(a, subset)]


# (最大叶深, 叶深总和, 前序属性序列)；单元素子集为叶子：(0, 0, ())
Score = Tuple[int, int, Tuple[int, ...]]


class Solver:
    def __init__(self, matrix: Matrix):
        self.m = matrix

    @lru_cache(maxsize=None)
    def solve(self, subset: int) -> Optional[Score]:
        """返回子集上的最优分数；无解返回 None。"""
        if subset & (subset - 1) == 0:  # 0 或单个对象
            return (0, 0, ()) if subset else None
        best: Optional[Score] = None
        for attr in self.m.attr_ids:
            if not self.m.is_legal(attr, subset):
                continue
            f_mask, t_mask = self.m.split(attr, subset)
            sf, st = self.solve(f_mask), self.solve(t_mask)
            if sf is None or st is None:
                continue
            # 子树挂到本节点下，每片叶子深度 +1
            score = (
                max(sf[0], st[0]) + 1,
                sf[1] + st[1] + subset.bit_count(),
                (attr,) + sf[2] + st[2],
            )
            if best is None or score < best:
                best = score
        return best

    @lru_cache(maxsize=None)
    def build(self, subset: int) -> Optional[dict]:
        """按 solve 选出的最优属性重建树；保证整树成功或整体为 None。"""
        if subset == 0:
            return None
        if subset & (subset - 1) == 0:
            oid = self.m.object_ids[subset.bit_length() - 1]
            return {"type": "leaf", "objectId": oid}
        chosen: Optional[Tuple[Score, int]] = None
        for attr in self.m.attr_ids:
            if not self.m.is_legal(attr, subset):
                continue
            f_mask, t_mask = self.m.split(attr, subset)
            sf, st = self.solve(f_mask), self.solve(t_mask)
            if sf is None or st is None:
                continue
            score = (
                max(sf[0], st[0]) + 1,
                sf[1] + st[1] + subset.bit_count(),
                (attr,) + sf[2] + st[2],
            )
            if chosen is None or score < chosen[0]:
                chosen = (score, attr)
        if chosen is None:
            return None
        _, attr = chosen
        f_mask, t_mask = self.m.split(attr, subset)
        f_node, t_node = self.build(f_mask), self.build(t_mask)
        if f_node is None or t_node is None:
            return None  # 双保险：拒绝残缺树
        return {
            "type": "question",
            "attributeId": attr,
            "false": f_node,
            "true": t_node,
        }

    # ---------- 无解诊断 ----------

    @lru_cache(maxsize=None)
    def is_bad(self, subset: int) -> bool:
        """subset 是否无法被完整分开（自身或某棵子树无解）。"""
        if subset & (subset - 1) == 0:
            return subset == 0
        for attr in self.m.attr_ids:
            if not self.m.is_legal(attr, subset):
                continue
            f_mask, t_mask = self.m.split(attr, subset)
            if not self.is_bad(f_mask) and not self.is_bad(t_mask):
                return False
        return True

    def root_blocked(self) -> bool:
        return self.is_bad(self.m.all_mask)

    def smallest_bad_subset(self) -> FrozenSet[int]:
        """其他无解：基数最小、对象编号升序字典序最小的、
        含至少两个对象且没有任何合法二分属性的子集。"""
        n = len(self.m.object_ids)
        best: Optional[Tuple[int, Tuple[int, ...]]] = None
        for bits in range(1, 1 << n):
            if bits.bit_count() < 2 or self.m.legal_attrs(bits):
                continue
            ids = tuple(
                self.m.object_ids[i] for i in range(n) if (bits >> i) & 1
            )
            key = (len(ids), ids)
            if best is None or key < best:
                best = key
        assert best is not None
        return frozenset(best[1])

    @lru_cache(maxsize=None)
    def best_block(
        self, subset: int
    ) -> Tuple[int, Tuple[int, ...], Tuple[int, ...]]:
        """坏集合上的最小阻断路径，返回 (长度, 假/真序列, 属性序列)。

        比较顺序：长度最短；再按假(0)先于真(1)的分支字典序；
        分支序列相同时按属性编号序列取小（保证结果唯一）。
        终止于无合法属性的集合时长度为 0。
        """
        if not self.m.legal_attrs(subset):
            return (0, (), ())
        best: Optional[Tuple[int, Tuple[int, ...], Tuple[int, ...]]] = None
        for attr in self.m.attr_ids:  # 属性编号升序
            if not self.m.is_legal(attr, subset):
                continue
            f_mask, t_mask = self.m.split(attr, subset)
            for branch, child in ((0, f_mask), (1, t_mask)):  # 0=假 先于 1=真
                if not self.is_bad(child):
                    continue
                bl, bb, ba = self.best_block(child)
                cand = (bl + 1, (branch,) + bb, (attr,) + ba)
                if best is None or cand < best:
                    best = cand
        assert best is not None
        return best

    def blocking_path(self) -> List[dict]:
        """锁定无解：从根到一个「多对象且无合法二分属性」集合的
        长度最短、假先于真字典序最小的阻断路径。"""
        _, branches, attrs = self.best_block(self.m.all_mask)
        return [
            {"attributeId": a, "branch": FALSE if b == 0 else TRUE}
            for a, b in zip(attrs, branches)
        ]

    def explain_blocked_subset(self, obj_ids: FrozenSet[int]) -> List[dict]:
        """逐属性说明该候选集为何无法二分：存在未知，或真假同值。"""
        bits = 0
        for oid in obj_ids:
            bits |= 1 << self.m.index[oid]
        reasons: List[dict] = []
        members = sorted(obj_ids)
        n = len(self.m.object_ids)
        for attr in self.m.attr_ids:
            known = self.m.known_mask.get(attr, 0)
            unknown_objs = [
                self.m.object_ids[i]
                for i in range(n)
                if (bits >> i) & 1 and not ((known >> i) & 1)
            ]
            if unknown_objs:
                reasons.append(
                    {
                        "attributeId": attr,
                        "reason": "unknown",
                        "objectIds": sorted(unknown_objs),
                    }
                )
                continue
            t = self.m.true_mask.get(attr, 0) & bits
            if t == 0 or t == bits:
                reasons.append(
                    {
                        "attributeId": attr,
                        "reason": "same",
                        "value": TRUE if t == bits else FALSE,
                        "objectIds": members,
                    }
                )
        return reasons


def _terminal_subset(matrix: Matrix, path: List[dict]) -> int:
    cur = matrix.all_mask
    for step in path:
        f_mask, t_mask = matrix.split(step["attributeId"], cur)
        cur = f_mask if step["branch"] == FALSE else t_mask
    return cur


def _ids_of(matrix: Matrix, bits: int) -> List[int]:
    return [
        matrix.object_ids[i]
        for i in range(len(matrix.object_ids))
        if (bits >> i) & 1
    ]


def build_tree(matrix: Matrix) -> dict:
    """构造完整树或返回无解诊断；任何情况下都不返回残缺树。"""
    n = len(matrix.object_ids)
    if n == 0:
        return {"status": "empty"}
    if n == 1:
        return {
            "status": "ok",
            "tree": {"type": "leaf", "objectId": matrix.object_ids[0]},
            "score": {"maxDepth": 0, "sumDepth": 0, "preorder": []},
        }
    solver = Solver(matrix)
    if not solver.root_blocked():
        tree = solver.build(matrix.all_mask)
        score = solver.solve(matrix.all_mask)
        assert tree is not None and score is not None
        return {
            "status": "ok",
            "tree": tree,
            "score": {
                "maxDepth": score[0],
                "sumDepth": score[1],
                "preorder": list(score[2]),
            },
        }
    if matrix.legal_attrs(matrix.all_mask):
        # 锁定无解：根上有可问的属性，但任何锁定序列都会走进死胡同。
        path = solver.blocking_path()
        terminal = _terminal_subset(matrix, path)
        terminal_ids = _ids_of(matrix, terminal)
        return {
            "status": "no_lock",
            "blockingPath": path,
            "terminalObjectIds": terminal_ids,
            "reasons": solver.explain_blocked_subset(frozenset(terminal_ids)),
        }
    # 其他无解：根集合本身含多对象且无任何合法二分属性，
    # 在所有同样卡死的子集中取基数最小、升序字典序最小者。
    subset = solver.smallest_bad_subset()
    return {
        "status": "inseparable",
        "subset": sorted(subset),
        "reasons": solver.explain_blocked_subset(subset),
    }
