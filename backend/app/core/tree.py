"""核心算法：从三值属性矩阵构造「逐步都能分开对象」的二分辨认树。

规则（对应需求）：

* 单元格取值：真 / 假 / 未知。某个属性在某个对象上若为「未知」，
  则该属性不能用于任何仍包含该对象的候选集——因为把未知当成假，
  就会把叶子认错。
* 只有当候选对象在该属性上全部已知，且真、假两组都非空时，
  该属性才是这个候选集上的「合法二分属性」。
* 可以**锁定**：指定一条从根开始的假/真路径，以及该路径终点节点
  必须询问的属性。
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
Path = Tuple[int, ...]  # 从根开始的分支序列：0=假，1=真
# 锁定：路径 -> 该节点必须使用的属性
LockMap = Dict[Path, int]


class Matrix:
    """以位掩码保存的三值矩阵。

    对每个属性保存两个掩码：known（已知位）与 true（真位）。
    未知 = 已知位为 0；已知且真 = true 位为 1；已知且假 = 已知 1 且 真 0。
    """

    def __init__(
        self,
        object_ids: List[int],
        cells: Dict[Tuple[int, int], str],
        attr_ids: Optional[List[int]] = None,
    ):
        if len(object_ids) != len(set(object_ids)):
            raise ValueError("对象编号重复")
        self.object_ids = list(object_ids)
        self.index = {oid: i for i, oid in enumerate(object_ids)}
        self.true_mask: BitMatrix = {}
        self.known_mask: BitMatrix = {}
        for (oid, aid), val in cells.items():
            if oid not in self.index or val not in VALUE_LABELS:
                continue
            self.true_mask.setdefault(aid, 0)
            self.known_mask.setdefault(aid, 0)
            if val == UNKNOWN:
                continue  # 未知：不置已知位、不置真位
            bit = 1 << self.index[oid]
            self.known_mask[aid] |= bit
            if val == TRUE:
                self.true_mask[aid] |= bit
        self.all_mask = (1 << len(object_ids)) - 1
        # 「已声明但尚无任何单元」的属性也要纳入，
        # 否则一个还没观察过的特征不会出现在无解原因里。
        seen = set(self.known_mask) | set(self.true_mask)
        self.attr_ids = sorted(seen | set(attr_ids or []))

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
    """无锁定时的最优树 DP（也用于诊断最小组合）。"""

    def __init__(self, matrix: Matrix):
        self.m = matrix

    @lru_cache(maxsize=None)
    def solve(self, subset: int) -> Optional[Score]:
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
            score = (
                max(sf[0], st[0]) + 1,
                sf[1] + st[1] + subset.bit_count(),
                (attr,) + sf[2] + st[2],
            )
            if best is None or score < best:
                best = score
        return best

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
                sorted(
                    self.m.object_ids[i]
                    for i in range(n)
                    if (bits >> i) & 1
                )
            )
            key = (len(ids), ids)
            if best is None or key < best:
                best = key
        assert best is not None
        return frozenset(best[1])

    def explain(self, obj_ids: FrozenSet[int]) -> List[dict]:
        """逐属性说明该候选集为何无法二分：存在未知，或真假同值。"""
        return explain_reasons(self.m, obj_ids)


class LockedSolver:
    """带路径锁定的最优树 DP。

    状态为 (候选子集, 从根到该节点的假/真路径)。
    若该路径被锁定，则该节点只能使用指定属性；否则在所有合法属性中
    按 (最大叶深, 叶深总和, 前序属性序列) 选最优。
    """

    def __init__(self, matrix: Matrix, locks: LockMap):
        self.m = matrix
        self.locks = locks

    def choices(self, subset: int, path: Path) -> List[int]:
        required = self.locks.get(path)
        if required is not None:
            return [required] if self.m.is_legal(required, subset) else []
        return self.m.legal_attrs(subset)

    @lru_cache(maxsize=None)
    def solve(self, state: Tuple[int, Path]) -> Optional[Score]:
        subset, path = state
        if subset & (subset - 1) == 0:
            if subset == 0 or path in self.locks:
                return None  # 空集，或叶子上还挂着锁定（无处可问）
            return (0, 0, ())
        best: Optional[Score] = None
        for attr in self.choices(subset, path):
            f_mask, t_mask = self.m.split(attr, subset)
            sf = self.solve((f_mask, path + (0,)))
            st = self.solve((t_mask, path + (1,)))
            if sf is None or st is None:
                continue
            score = (
                max(sf[0], st[0]) + 1,
                sf[1] + st[1] + subset.bit_count(),
                (attr,) + sf[2] + st[2],
            )
            if best is None or score < best:
                best = score
        return best

    @lru_cache(maxsize=None)
    def build(self, state: Tuple[int, Path]) -> Optional[dict]:
        subset, path = state
        if subset == 0 or (subset & (subset - 1) == 0 and path in self.locks):
            return None
        if subset & (subset - 1) == 0:
            return {
                "type": "leaf",
                "objectId": self.m.object_ids[subset.bit_length() - 1],
            }
        chosen: Optional[Tuple[Score, int]] = None
        for attr in self.choices(subset, path):
            f_mask, t_mask = self.m.split(attr, subset)
            sf = self.solve((f_mask, path + (0,)))
            st = self.solve((t_mask, path + (1,)))
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
        f_node = self.build((f_mask, path + (0,)))
        t_node = self.build((t_mask, path + (1,)))
        if f_node is None or t_node is None:
            return None  # 双保险：拒绝残缺树
        node = {
            "type": "question",
            "attributeId": attr,
            "false": f_node,
            "true": t_node,
        }
        if path in self.locks:
            node["locked"] = True
            node["lockPath"] = list(path)
        return node

    # ---------- 锁定无解诊断 ----------

    @lru_cache(maxsize=None)
    def is_bad(self, state: Tuple[int, Path]) -> bool:
        """该状态在锁定约束下能否长出完整子树。"""
        subset, path = state
        if subset & (subset - 1) == 0:
            if subset == 0:
                return True
            # 只剩一张卡就是叶子，不会再问问题；
            # 若这里还挂着锁定，则该锁定无处可问 => 无解。
            return path in self.locks
        for attr in self.choices(subset, path):
            f_mask, t_mask = self.m.split(attr, subset)
            if not self.is_bad((f_mask, path + (0,))) and not self.is_bad(
                (t_mask, path + (1,))
            ):
                return False
        return True

    @lru_cache(maxsize=None)
    def best_block(
        self, state: Tuple[int, Path]
    ) -> Tuple[int, Tuple[int, ...], Tuple[int, ...]]:
        """坏状态上的最小阻断路径。

        返回 (长度, 假/真分支序列, 节点属性序列)。
        比较：长度最短；假(0)先于真(1)字典序；再按属性编号。
        终止节点（无可用选择）长度为 0。
        """
        subset, path = state
        choices = self.choices(subset, path)
        if not choices:
            return (0, (), ())
        best: Optional[Tuple[int, Tuple[int, ...], Tuple[int, ...]]] = None
        for attr in choices:
            f_mask, t_mask = self.m.split(attr, subset)
            for branch, child in ((0, f_mask), (1, t_mask)):
                child_state = (child, path + (branch,))
                if not self.is_bad(child_state):
                    continue
                bl, bb, ba = self.best_block(child_state)
                cand = (bl + 1, (branch,) + bb, (attr,) + ba)
                if best is None or cand < best:
                    best = cand
        assert best is not None
        return best

    def blocking_path(self) -> List[dict]:
        _, branches, attrs = self.best_block((self.m.all_mask, ()))
        return [
            {"attributeId": a, "branch": FALSE if b == 0 else TRUE}
            for a, b in zip(attrs, branches)
        ]

    def terminal_required(self, path_steps: List[dict]) -> Optional[int]:
        path = tuple(0 if s["branch"] == FALSE else 1 for s in path_steps)
        return self.locks.get(path)


def explain_reasons(matrix: Matrix, obj_ids: FrozenSet[int]) -> List[dict]:
    """逐属性说明该候选集为何无法二分：存在未知，或真假同值。

    包含「已声明但整张卡都还没观察」的属性——此时组内每张卡都是未知。
    """
    bits = 0
    for oid in obj_ids:
        bits |= 1 << matrix.index[oid]
    reasons: List[dict] = []
    members = sorted(obj_ids)
    n = len(matrix.object_ids)
    for attr in matrix.attr_ids:
        known = matrix.known_mask.get(attr, 0)
        unknown_objs = [
            matrix.object_ids[i]
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
        t = matrix.true_mask.get(attr, 0) & bits
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


def normalize_locks(
    raw: Optional[List[dict]],
    matrix: Matrix,
) -> Tuple[LockMap, List[dict]]:
    """校验并规范化前端提交的锁定列表。

    接受 [{"path": ["false"|"true", ...], "attributeId": int}]，
    空 path 表示锁定根节点。返回 (锁定映射, 规范化列表)。
    """
    locks: LockMap = {}
    normalized: List[dict] = []
    if not raw:
        return locks, normalized

    valid_attrs = set(matrix.attr_ids)
    seen_paths: set[Tuple[Path, int]] = set()
    parsed: List[Tuple[Path, int]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"第 {i + 1} 条锁定格式不正确")
        aid = item.get("attributeId")
        path_vals = item.get("path", [])
        if not isinstance(aid, int) or aid <= 0:
            raise ValueError(f"第 {i + 1} 条锁定的特征编号必须是正整数")
        if aid not in valid_attrs:
            raise ValueError(f"第 {i + 1} 条锁定了不存在的特征 {aid}")
        if not isinstance(path_vals, list) or len(path_vals) > 19:
            raise ValueError(f"第 {i + 1} 条锁定的路径格式不正确")
        path_parts: List[int] = []
        for b in path_vals:
            if b == FALSE:
                path_parts.append(0)
            elif b == TRUE:
                path_parts.append(1)
            else:
                raise ValueError(f"第 {i + 1} 条锁定的路径只能包含真/假")
        path = tuple(path_parts)
        key = (path, aid)
        if key in seen_paths:
            continue
        seen_paths.add(key)
        parsed.append((path, aid))

    # 同一路径不能被锁到两个不同特征。
    # 不同路径之间无需校验：一条路径必然经过其全部前缀，
    # 兄弟路径（如 (0,) 与 (1,)）会落到不同节点，互不影响。
    by_path: Dict[Path, int] = {}
    for path, aid in parsed:
        if path in by_path and by_path[path] != aid:
            raise ValueError(
                f"同一条路径被锁到了两个特征（{by_path[path]} 和 {aid}）"
            )
        by_path[path] = aid

    normalized = [
        {
            "path": [FALSE if b == 0 else TRUE for b in path],
            "attributeId": aid,
        }
        for path, aid in sorted(by_path.items(), key=lambda kv: (len(kv[0]), kv[0]))
    ]
    return by_path, normalized


def _terminal_subset(matrix: Matrix, path: List[dict]) -> int:
    cur = matrix.all_mask
    for step in path:
        f_mask, t_mask = matrix.split(step["attributeId"], cur)
        cur = f_mask if step["branch"] == FALSE else t_mask
    return cur


def _ids_of(matrix: Matrix, bits: int) -> List[int]:
    return sorted(
        matrix.object_ids[i]
        for i in range(len(matrix.object_ids))
        if (bits >> i) & 1
    )


def build_tree(matrix: Matrix, raw_locks: Optional[List[dict]] = None) -> dict:
    """构造完整树或返回无解诊断；任何情况下都不返回残缺树。"""
    n = len(matrix.object_ids)
    if n == 0:
        return {"status": "empty"}

    locks, lock_list = normalize_locks(raw_locks or [], matrix)

    if n == 1:
        if locks:
            # 只有一张卡就没有问题可问，任何锁定都无从满足。
            locked_path, aid = next(iter(locks.items()))
            return {
                "status": "no_lock",
                "locks": lock_list,
                "blockingPath": [],
                "terminalObjectIds": [matrix.object_ids[0]],
                "violatedLock": {
                    "path": [FALSE if b == 0 else TRUE for b in locked_path],
                    "attributeId": aid,
                },
                "reasons": [],
            }
        return {
            "status": "ok",
            "tree": {"type": "leaf", "objectId": matrix.object_ids[0]},
            "score": {"maxDepth": 0, "sumDepth": 0, "preorder": []},
            "locks": [],
        }

    solver = LockedSolver(matrix, locks)
    root_state = (matrix.all_mask, ())
    if not solver.is_bad(root_state):
        tree = solver.build(root_state)
        score = solver.solve(root_state)
        assert tree is not None and score is not None
        return {
            "status": "ok",
            "tree": tree,
            "score": {
                "maxDepth": score[0],
                "sumDepth": score[1],
                "preorder": list(score[2]),
            },
            "locks": lock_list,
        }

    if locks:
        # 锁定无解：找出最短、假先于真的阻断路径
        path = solver.blocking_path()
        terminal = _terminal_subset(matrix, path)
        terminal_ids = _ids_of(matrix, terminal)
        term_path = tuple(0 if s["branch"] == FALSE else 1 for s in path)
        required = locks.get(term_path)
        result: dict = {
            "status": "no_lock",
            "locks": lock_list,
            "blockingPath": path,
            "terminalObjectIds": terminal_ids,
            "reasons": explain_reasons(matrix, frozenset(terminal_ids)),
        }
        if required is not None:
            result["violatedLock"] = {
                "path": [FALSE if b == 0 else TRUE for b in term_path],
                "attributeId": required,
            }
        return result

    # 没有锁定但根仍坏：
    # 根集合本身连一个合法属性都没有 => 其他无解（最小不可分组合）
    if not matrix.legal_attrs(matrix.all_mask):
        subset = Solver(matrix).smallest_bad_subset()
        return {
            "status": "inseparable",
            "subset": sorted(subset),
            "reasons": explain_reasons(matrix, subset),
        }

    # 根上有可问属性但递归走进死胡同 => 同样以阻断路径呈现
    path = solver.blocking_path()
    terminal = _terminal_subset(matrix, path)
    terminal_ids = _ids_of(matrix, terminal)
    return {
        "status": "no_lock",
        "locks": [],
        "blockingPath": path,
        "terminalObjectIds": terminal_ids,
        "reasons": explain_reasons(matrix, frozenset(terminal_ids)),
    }
