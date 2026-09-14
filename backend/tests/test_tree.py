"""核心算法测试：最优树、并列裁决、锁定无解、其他无解、未知值保护。"""

from app.core.tree import (
    FALSE,
    Matrix,
    TRUE,
    UNKNOWN,
    Solver,
    build_tree,
)


def m(objs, rows):
    """rows: {attr_id: [按 objs 顺序的值列表]}"""
    cells = {}
    for aid, vals in rows.items():
        for oid, v in zip(objs, vals):
            if v is not None:
                cells[(oid, aid)] = v
    return Matrix(list(objs), cells)


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
