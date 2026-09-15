"""核心算法测试：最优树、并列裁决、路径锁定、两类无解、未知值保护、乱序编号。"""

from app.core.tree import (
    FALSE,
    Matrix,
    TRUE,
    UNKNOWN,
    LockedSolver,
    Solver,
    build_tree,
    normalize_locks,
)


def m(objs, rows, attr_ids=None):
    """rows: {attr_id: [按 objs 顺序的值列表]}"""
    cells = {}
    for aid, vals in rows.items():
        for oid, v in zip(objs, vals):
            if v is not None:
                cells[(oid, aid)] = v
    return Matrix(list(objs), cells, attr_ids=sorted(attr_ids or rows))


def root(result):
    return result["tree"]["attributeId"]


def test_unique_tree():
    r = build_tree(m([1, 2, 3, 4], {
        1: [TRUE, TRUE, FALSE, FALSE],
        2: [TRUE, FALSE, UNKNOWN, UNKNOWN],
        3: [UNKNOWN, UNKNOWN, TRUE, FALSE],
    }))
    assert r["status"] == "ok"
    assert root(r) == 1
    # 前序序列：根 → 假子树(属性3) → 真子树(属性2)
    assert r["score"] == {"maxDepth": 2, "sumDepth": 8, "preorder": [1, 3, 2]}


def test_prefers_balanced_over_chain():
    # 属性 1 会逼出链式树（最大深 3），属性 4 可以平衡（最大深 2）
    r = build_tree(m([1, 2, 3, 4], {
        1: [TRUE, FALSE, FALSE, FALSE],
        2: [UNKNOWN, TRUE, TRUE, FALSE],
        3: [UNKNOWN, TRUE, FALSE, UNKNOWN],
        4: [TRUE, TRUE, FALSE, FALSE],
        5: [TRUE, FALSE, UNKNOWN, UNKNOWN],
        6: [UNKNOWN, UNKNOWN, TRUE, FALSE],
    }))
    assert r["status"] == "ok"
    assert root(r) == 4
    assert r["score"]["maxDepth"] == 2
    assert r["score"]["sumDepth"] == 8
    # 假分支在前：{3,4} 上属性2、6并列取2；{1,2} 上属性1、5并列取1
    assert r["score"]["preorder"] == [4, 2, 1]


def test_tie_picks_smaller_preorder_and_subtree_attr():
    # 根属性 1 与 4 都能构造最大深 2、总深 8 的树；前序序列取小 => 选 1。
    # 子集 {1,2} 上属性 2、7 并列合法，取编号小者 2。
    r = build_tree(m([1, 2, 3, 4], {
        1: [TRUE, TRUE, FALSE, FALSE],
        2: [TRUE, FALSE, UNKNOWN, UNKNOWN],
        3: [UNKNOWN, UNKNOWN, TRUE, FALSE],
        4: [TRUE, FALSE, TRUE, FALSE],
        5: [TRUE, UNKNOWN, FALSE, UNKNOWN],
        6: [UNKNOWN, TRUE, UNKNOWN, FALSE],
        7: [FALSE, TRUE, UNKNOWN, UNKNOWN],
    }))
    assert r["status"] == "ok"
    assert r["score"]["maxDepth"] == 2
    assert r["score"]["sumDepth"] == 8
    # 根 1 的前序 [1,3,2] 小于根 4 的 [4,6,5]
    assert r["score"]["preorder"] == [1, 3, 2]
    # 真子树 {1,2} 上属性 2、7 并列合法，取编号小者 2
    assert r["tree"]["true"]["attributeId"] == 2


def test_unknown_is_not_treated_as_false():
    # 两个对象在唯一属性上一真一未知：禁止把未知当假，必须判无解
    r = build_tree(m([1, 2], {1: [TRUE, UNKNOWN]}))
    assert r["status"] == "inseparable"
    assert r["subset"] == [1, 2]
    reason = {x["attributeId"]: x for x in r["reasons"]}[1]
    assert reason["reason"] == "unknown"
    assert reason["objectIds"] == [2]


def test_no_lock_path_false_then_true():
    # 根上只有属性 1 合法，假组 {3,4} 与真组 {1,2} 都直接卡死 => 取假分支
    r = build_tree(m([1, 2, 3, 4], {
        1: [TRUE, TRUE, FALSE, FALSE],
        2: [TRUE, UNKNOWN, UNKNOWN, FALSE],
    }))
    assert r["status"] == "no_lock"
    assert r["blockingPath"] == [{"attributeId": 1, "branch": FALSE}]
    assert r["terminalObjectIds"] == [3, 4]


def test_no_lock_shortest_path():
    # 根属性 2 的真分支一步就到死胡同（长度1）；
    # 根属性 1 要走两步（长度2）。必须选最短路径。
    r = build_tree(m([1, 2, 3, 4], {
        1: [TRUE, FALSE, FALSE, FALSE],
        2: [FALSE, FALSE, TRUE, TRUE],
        3: [UNKNOWN, FALSE, TRUE, TRUE],
        4: [TRUE, FALSE, UNKNOWN, UNKNOWN],
    }))
    assert r["status"] == "no_lock"
    assert r["blockingPath"] == [{"attributeId": 2, "branch": TRUE}]
    assert r["terminalObjectIds"] == [3, 4]
    reasons = {x["attributeId"]: x for x in r["reasons"]}
    assert reasons[3]["reason"] == "same"
    assert reasons[3]["value"] == TRUE


def test_no_lock_reasons_unknown_and_same():
    r = build_tree(m([1, 2, 3], {
        1: [TRUE, FALSE, FALSE],          # 根唯一合法属性
        2: [UNKNOWN, FALSE, FALSE],       # {2,3} 同假
        3: [TRUE, UNKNOWN, TRUE],         # {2,3} 中对象2未知
    }))
    assert r["status"] == "no_lock"
    assert r["blockingPath"] == [{"attributeId": 1, "branch": FALSE}]
    assert r["terminalObjectIds"] == [2, 3]
    by = {x["attributeId"]: x for x in r["reasons"]}
    assert by[2] == {"attributeId": 2, "reason": "same",
                     "value": FALSE, "objectIds": [2, 3]}
    assert by[3]["reason"] == "unknown"
    assert by[3]["objectIds"] == [2]


def test_inseparable_smallest_lex_subset():
    # 根无合法属性；坏对有 {1,2},{1,4},{2,4},{3,4}，取升序最小 {1,2}
    r = build_tree(m([1, 2, 3, 4], {
        1: [TRUE, TRUE, FALSE, UNKNOWN],
        2: [TRUE, TRUE, TRUE, TRUE],
    }))
    assert r["status"] == "inseparable"
    assert r["subset"] == [1, 2]
    by = {x["attributeId"]: x for x in r["reasons"]}
    assert by[1]["reason"] == "same" and by[1]["value"] == TRUE
    assert by[2]["reason"] == "same" and by[2]["value"] == TRUE


def test_inseparable_unknown_reason():
    r = build_tree(m([1, 2, 3], {
        1: [TRUE, TRUE, TRUE],
        2: [TRUE, UNKNOWN, FALSE],
    }))
    assert r["status"] == "inseparable"
    assert r["subset"] == [1, 2]
    by = {x["attributeId"]: x for x in r["reasons"]}
    assert by[1]["reason"] == "same"
    assert by[2]["reason"] == "unknown"
    assert by[2]["objectIds"] == [2]


def test_no_partial_tree_on_failure():
    # 无解时结果里绝不带 tree 字段
    r = build_tree(m([1, 2, 3], {1: [TRUE, FALSE, UNKNOWN]}))
    assert r["status"] in {"no_lock", "inseparable"}
    assert "tree" not in r


def test_single_object_is_leaf():
    r = build_tree(m([7], {1: [TRUE]}))
    assert r["status"] == "ok"
    assert r["tree"] == {"type": "leaf", "objectId": 7}


def test_solver_caches_are_independent():
    s1 = Solver(m([1, 2], {1: [TRUE, FALSE]}))
    assert s1.solve(0b11) is not None
    s2 = Solver(m([1, 2], {1: [TRUE, UNKNOWN]}))
    assert s2.solve(0b11) is None


# ---------- 路径锁定 ----------

def test_lock_forces_root_attribute():
    # 自由最优根是 4；把根锁成 1 后，根必须是 1
    matrix = m([1, 2, 3, 4], {
        1: [TRUE, FALSE, FALSE, FALSE],
        2: [UNKNOWN, TRUE, TRUE, FALSE],
        3: [UNKNOWN, TRUE, FALSE, UNKNOWN],
        4: [TRUE, TRUE, FALSE, FALSE],
        5: [TRUE, FALSE, UNKNOWN, UNKNOWN],
        6: [UNKNOWN, UNKNOWN, TRUE, FALSE],
    })
    free = build_tree(matrix)
    assert root(free) == 4

    locked = build_tree(matrix, [{"path": [], "attributeId": 1}])
    assert locked["status"] == "ok"
    assert root(locked) == 1
    assert locked["tree"]["locked"] is True
    # 仍是完整树：4 张卡全到叶子
    assert locked["score"]["maxDepth"] == 3


def test_lock_deep_path_forces_node():
    matrix = m([1, 2, 3, 4], {
        1: [TRUE, TRUE, FALSE, FALSE],
        2: [TRUE, FALSE, UNKNOWN, UNKNOWN],
        3: [UNKNOWN, UNKNOWN, TRUE, FALSE],
        7: [FALSE, TRUE, UNKNOWN, UNKNOWN],
    })
    # 路径 (真,) 对应根 1 的真组 {1,2}；锁该节点必须用 7
    r = build_tree(matrix, [{"path": [TRUE], "attributeId": 7}])
    assert r["status"] == "ok"
    assert r["tree"]["true"]["attributeId"] == 7
    assert r["tree"]["true"]["locked"] is True
    # 假子树仍自由选编号最小的 3
    assert r["tree"]["false"]["attributeId"] == 3


def test_lock_illegal_attribute_gives_no_lock():
    # 属性 1 在根合法；属性 2 在根含未知（对象3、4未知），锁根=2 => 无解
    matrix = m([1, 2, 3, 4], {
        1: [TRUE, TRUE, FALSE, FALSE],
        2: [TRUE, FALSE, UNKNOWN, UNKNOWN],
        3: [UNKNOWN, UNKNOWN, TRUE, FALSE],
    })
    r = build_tree(matrix, [{"path": [], "attributeId": 2}])
    assert r["status"] == "no_lock"
    assert "tree" not in r
    assert r["blockingPath"] == []  # 阻断点就是根
    assert r["terminalObjectIds"] == [1, 2, 3, 4]
    assert r["violatedLock"] == {"path": [], "attributeId": 2}
    reasons = {x["attributeId"]: x for x in r["reasons"]}
    assert reasons[2]["reason"] == "unknown"
    assert reasons[2]["objectIds"] == [3, 4]


def test_lock_dead_end_down_path():
    # 锁根=2；2 的真分支通向 {3,4}，那里属性3 同真、属性1 同假 => 死胡同
    matrix = m([1, 2, 3, 4], {
        1: [TRUE, FALSE, FALSE, FALSE],
        2: [FALSE, FALSE, TRUE, TRUE],
        3: [UNKNOWN, FALSE, TRUE, TRUE],
        4: [TRUE, FALSE, UNKNOWN, UNKNOWN],
    })
    r = build_tree(matrix, [{"path": [], "attributeId": 2}])
    assert r["status"] == "no_lock"
    assert r["blockingPath"] == [{"attributeId": 2, "branch": TRUE}]
    assert r["terminalObjectIds"] == [3, 4]
    assert "violatedLock" not in r  # 死路不是被锁的节点本身
    kinds = {x["reason"] for x in r["reasons"]}
    assert "same" in kinds


def test_lock_prefers_false_branch_when_both_blocked():
    matrix = m([1, 2, 3, 4], {
        1: [TRUE, TRUE, FALSE, FALSE],
        2: [TRUE, UNKNOWN, UNKNOWN, FALSE],
    })
    r = build_tree(matrix, [{"path": [], "attributeId": 1}])
    assert r["status"] == "no_lock"
    assert r["blockingPath"] == [{"attributeId": 1, "branch": FALSE}]
    assert r["terminalObjectIds"] == [3, 4]


def test_normalize_locks_validation():
    matrix = m([1, 2, 3, 4], {1: [TRUE, FALSE, TRUE, FALSE]})
    _, norm = normalize_locks(
        [
            {"path": [], "attributeId": 1},
            {"path": [], "attributeId": 1},  # 重复，去重
            {"path": [FALSE], "attributeId": 1},
        ],
        matrix,
    )
    assert norm == [
        {"path": [], "attributeId": 1},
        {"path": [FALSE], "attributeId": 1},
    ]

    import pytest
    with pytest.raises(ValueError):
        normalize_locks([{"path": [], "attributeId": 99}], matrix)
    with pytest.raises(ValueError):
        # 同路径锁两个特征
        normalize_locks(
            [{"path": [], "attributeId": 1},
             {"path": [], "attributeId": 2}],
            m([1, 2, 3, 4], {1: [1] * 4 and [TRUE, FALSE, TRUE, FALSE],
                              2: [FALSE, TRUE, FALSE, TRUE]}),
        )


# ---------- 未观察的特征也要出现在原因里 ----------

def test_never_observed_attribute_is_explained():
    # 属性 5 已声明但没有任何单元；卡 {1,2} 在 1 同真，在 5 全未知。
    matrix = m(
        [1, 2, 3, 4],
        {
            1: [TRUE, TRUE, FALSE, UNKNOWN],
            2: [TRUE, TRUE, TRUE, TRUE],
        },
        attr_ids=[1, 2, 5],
    )
    r = build_tree(matrix)
    assert r["status"] == "inseparable"
    by = {x["attributeId"]: x for x in r["reasons"]}
    assert 5 in by
    assert by[5]["reason"] == "unknown"
    assert by[5]["objectIds"] == r["subset"]


# ---------- 乱序录入对象编号 ----------

def test_scrambled_object_ids_same_subset():
    import random
    rows_base = {
        1: {1: FALSE, 2: TRUE, 4: FALSE},  # 只有 3 个单元，其余未知
    }
    cells = {(o, 1): v for o, v in rows_base[1].items()}

    def compute(order):
        mm = Matrix(order, cells, attr_ids=[1])
        return build_tree(mm)

    canonical = compute([1, 2, 3, 4])
    for order in ([2, 3, 4, 1], [4, 1, 3, 2], [3, 1, 4, 2]):
        r = compute(order)
        assert r["status"] == canonical["status"]
        assert r["subset"] == canonical["subset"]


def test_scrambled_ids_terminal_ids_sorted():
    cells = {
        (1, 1): TRUE, (2, 1): TRUE, (3, 1): FALSE, (4, 1): FALSE,
        (1, 2): TRUE, (2, 2): UNKNOWN,
        (3, 2): UNKNOWN, (4, 2): FALSE,
    }
    mm = Matrix([4, 3, 2, 1], cells, attr_ids=[1, 2])
    r = build_tree(mm)
    assert r["status"] == "no_lock"
    # 假分支终点对象必须按编号升序输出，而不是按录入位置
    assert r["terminalObjectIds"] == [3, 4]


def test_locked_solver_matches_free_when_unlocked():
    matrix = m([1, 2, 3, 4], {
        1: [TRUE, TRUE, FALSE, FALSE],
        2: [TRUE, FALSE, UNKNOWN, UNKNOWN],
        3: [UNKNOWN, UNKNOWN, TRUE, FALSE],
    })
    free = Solver(matrix).solve(matrix.all_mask)
    locked = LockedSolver(matrix, {}).solve((matrix.all_mask, ()))
    assert free == locked


def test_lock_on_leaf_is_rejected():
    # 根属性 1 真分支只剩 {1}；若把路径 (真,) 锁到任意特征，
    # 叶子无处可问，应判锁定无解并指出违反的锁定。
    matrix = m([1, 2, 3, 4], {
        1: [TRUE, FALSE, FALSE, FALSE],
        2: [UNKNOWN, TRUE, TRUE, FALSE],
        4: [UNKNOWN, TRUE, FALSE, FALSE],
    })
    r = build_tree(matrix, [{"path": [TRUE], "attributeId": 2}])
    assert r["status"] == "no_lock"
    assert r["violatedLock"] == {"path": [TRUE], "attributeId": 2}
    assert r["terminalObjectIds"] == [1]


# ---------- 预定路径提前到达答案 ----------

def _chain_matrix():
    # 自由树（根=1）：真→叶子1；假→属性2：真→叶2，假→属性3：真→叶3/假→叶4
    return m([1, 2, 3, 4], {
        1: [TRUE, FALSE, FALSE, FALSE],
        2: [UNKNOWN, TRUE, FALSE, FALSE],
        3: [UNKNOWN, UNKNOWN, TRUE, FALSE],
    })


def test_lock_after_answer_rejected_static():
    matrix = _chain_matrix()
    # 锁路径 (真,真)->属性3：第一步真后已是叶子1，必问题被漏掉
    r = build_tree(matrix, [{"path": [TRUE, TRUE], "attributeId": 3}])
    assert r["status"] == "no_lock"
    assert r["earlyAnswer"] is True
    assert r["violatedLock"] == {"path": [TRUE, TRUE], "attributeId": 3}
    assert r["terminalObjectIds"] == [1]
    assert "tree" not in r


def test_lock_after_answer_via_free_prefix_rejected_by_tree_walk():
    matrix = _chain_matrix()
    # 路径 (假,真) 在自由树里到达叶子2；没有锁 (假,)，静态检查放行，
    # 必须由建树后的兜底检查拦住。
    r = build_tree(matrix, [{"path": [FALSE, TRUE], "attributeId": 3}])
    assert r["status"] == "no_lock"
    assert r.get("earlyAnswer") is True
    assert r["violatedLock"] == {"path": [FALSE, TRUE], "attributeId": 3}
    assert r["terminalObjectIds"] == [2]
    assert "tree" not in r


def test_lock_path_that_still_has_question_is_ok():
    matrix = _chain_matrix()
    # 路径 (假,假) 到达 {3,4}，那里确实还要问属性3 —— 合法锁定
    r = build_tree(matrix, [{"path": [FALSE, FALSE], "attributeId": 3}])
    assert r["status"] == "ok"
    node = r["tree"]["false"]["false"]
    assert node["attributeId"] == 3
    assert node.get("locked") is True


def test_lock_illegal_at_deep_terminal_gives_reasons():
    matrix = _chain_matrix()
    # 路径 (假,假) 到达 {3,4}，但锁的属性 1 在那里两张卡都为假（同值，不合法）
    r = build_tree(matrix, [{"path": [FALSE, FALSE], "attributeId": 1}])
    assert r["status"] == "no_lock"
    assert r["violatedLock"] == {"path": [FALSE, FALSE], "attributeId": 1}
    assert r["terminalObjectIds"] == [3, 4]
    assert any(x["attributeId"] == 1 and x["reason"] == "same"
               for x in r["reasons"])


def test_lock_prefix_illegal_reports_prefix():
    matrix = _chain_matrix()
    # 锁 (假,)->属性3，但在根1的假组 {2,3,4} 上属性3含未知（对象2未知）
    r = build_tree(matrix, [{"path": [FALSE, FALSE], "attributeId": 3},
                            {"path": [FALSE], "attributeId": 3}])
    assert r["status"] == "no_lock"
    assert r["violatedLock"] == {"path": [FALSE], "attributeId": 3}
