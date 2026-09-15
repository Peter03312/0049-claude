"""API 端到端测试：CRUD、计算保存快照、编辑过期、重载一致、两类无解。"""


def _payload(cells=None):
    return {
        "name": "四种树叶",
        "objects": [
            {"id": 1, "label": "枫叶", "note": ""},
            {"id": 2, "label": "橡树叶", "note": ""},
            {"id": 3, "label": "松针", "note": ""},
            {"id": 4, "label": "银杏叶", "note": ""},
        ],
        "attributes": [
            {"id": 1, "label": "有裂片"},
            {"id": 2, "label": "扁平宽大"},
            {"id": 3, "label": "针形"},
            {"id": 4, "label": "边缘光滑"},
        ],
        "cells": cells
        or {
            "1:1": "true", "1:2": "true", "1:3": "false", "1:4": "false",
            "2:1": "true", "2:2": "true", "2:3": "false", "2:4": "true",
            "3:1": "false", "3:2": "false", "3:3": "true", "3:4": "false",
            "4:1": "false", "4:2": "true", "4:3": "false", "4:4": "true",
        },
    }


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_create_get_reload_consistency(client):
    r = client.post("/api/projects", json=_payload())
    assert r.status_code == 201
    pid = r.json()["id"]
    assert r.json()["result"] is None
    assert r.json()["resultFresh"] is False

    got = client.get(f"/api/projects/{pid}").json()
    assert got["objects"] == _payload()["objects"]
    assert got["cells"]["3:3"] == "true"


def test_compute_saves_tree_and_snapshot(client):
    pid = client.post("/api/projects", json=_payload()).json()["id"]
    r = client.post(f"/api/projects/{pid}/compute")
    assert r.status_code == 200
    body = r.json()
    assert body["savedSnapshot"] is True
    assert body["result"]["status"] == "ok"
    assert body["result"]["tree"]["type"] == "question"
    sid = body["snapshotId"]
    assert isinstance(sid, int)

    # 项目上的结果已更新为新鲜
    p = client.get(f"/api/projects/{pid}").json()
    assert p["resultFresh"] is True
    assert p["result"]["status"] == "ok"

    # 快照与当前结果一致
    snap = client.get(f"/api/snapshots/{sid}").json()
    assert snap["result"] == p["result"]
    snaps = client.get(f"/api/projects/{pid}/snapshots").json()
    assert [s["id"] for s in snaps] == [sid]


def test_editing_expires_old_tree(client):
    pid = client.post("/api/projects", json=_payload()).json()["id"]
    client.post(f"/api/projects/{pid}/compute")
    assert client.get(f"/api/projects/{pid}").json()["resultFresh"] is True

    # 编辑一个单元格：旧树必须过期
    changed = _payload()
    changed["cells"]["1:1"] = "false"
    r = client.put(f"/api/projects/{pid}", json=changed)
    assert r.status_code == 200
    body = r.json()
    assert body["inputVersion"] == 2
    assert body["result"] is None
    assert body["resultFresh"] is False

    # 重新计算后再次一致（重载后一致）
    r2 = client.post(f"/api/projects/{pid}/compute")
    assert r2.status_code == 200
    p = client.get(f"/api/projects/{pid}").json()
    assert p["resultFresh"] is True
    assert p["resultVersion"] == 2
    assert p["result"] == r2.json()["result"]

    # 旧快照仍保留，记录的是当时版本
    snaps = client.get(f"/api/projects/{pid}/snapshots").json()
    assert len(snaps) == 2
    assert snaps[-1]["inputVersion"] == 1


def test_no_lock_result_has_path_and_reasons(client):
    payload = _payload(
        cells={
            "1:1": "true", "1:2": "unknown",
            "2:1": "true", "2:2": "unknown",
            "3:1": "false", "3:2": "unknown",
            "4:1": "false", "4:2": "true",
        }
    )
    pid = client.post("/api/projects", json=payload).json()["id"]
    r = client.post(f"/api/projects/{pid}/compute").json()["result"]
    assert r["status"] == "no_lock"
    assert "tree" not in r
    assert r["blockingPath"] == [{"attributeId": 1, "branch": "false"}]
    assert r["terminalObjectIds"] == [3, 4]
    kinds = {x["reason"] for x in r["reasons"]}
    assert kinds == {"unknown", "same"}


def test_inseparable_returns_smallest_subset(client):
    payload = _payload(
        cells={
            "1:1": "true", "2:1": "true", "3:1": "false", "4:1": "unknown",
            "1:2": "true", "2:2": "true", "3:2": "true", "4:2": "true",
        }
    )
    pid = client.post("/api/projects", json=payload).json()["id"]
    r = client.post(f"/api/projects/{pid}/compute").json()["result"]
    assert r["status"] == "inseparable"
    assert "tree" not in r
    assert r["subset"] == [1, 2]
    assert all(x["reason"] in {"unknown", "same"} for x in r["reasons"])


def test_validation_duplicate_ids_and_cell_keys(client):
    bad = _payload()
    bad["objects"][1]["id"] = 1
    assert client.post("/api/projects", json=bad).status_code == 422

    bad2 = _payload()
    bad2["cells"]["9:1"] = "true"  # 不存在的对象：键被规范化时忽略，不报错
    r = client.post("/api/projects", json=bad2)
    assert r.status_code == 201
    assert "9:1" not in r.json()["cells"]

    bad3 = _payload()
    bad3["cells"]["oops"] = "true"
    assert client.post("/api/projects", json=bad3).status_code == 422


def test_unknown_never_treated_as_false(client):
    payload = _payload(
        cells={"1:1": "true", "2:1": "unknown"}
    )
    pid = client.post("/api/projects", json=payload).json()["id"]
    r = client.post(f"/api/projects/{pid}/compute").json()["result"]
    assert r["status"] == "inseparable"
    assert r["subset"] == [1, 2]


def test_404_and_delete(client):
    assert client.get("/api/projects/999").status_code == 404
    pid = client.post("/api/projects", json=_payload()).json()["id"]
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    assert client.get(f"/api/projects/{pid}").status_code == 404


# ---------- 路径锁定 ----------

def _balanced_payload():
    return {
        "name": "锁定树叶",
        "objects": [
            {"id": 1, "label": "甲", "note": ""},
            {"id": 2, "label": "乙", "note": ""},
            {"id": 3, "label": "丙", "note": ""},
            {"id": 4, "label": "丁", "note": ""},
        ],
        "attributes": [
            {"id": 1, "label": "特征一"},
            {"id": 2, "label": "特征二"},
            {"id": 3, "label": "特征三"},
            {"id": 4, "label": "特征四"},
            {"id": 5, "label": "特征五"},
        ],
        "cells": {
            "1:1": "true", "1:2": "true", "1:3": "unknown", "1:4": "true", "1:5": "true",
            "2:1": "false", "2:2": "true", "2:3": "unknown", "2:4": "true", "2:5": "false",
            "3:1": "false", "3:2": "true", "3:3": "true", "3:4": "false", "3:5": "unknown",
            "4:1": "false", "4:2": "false", "4:3": "false", "4:4": "false", "4:5": "unknown",
        },
    }


def test_lock_root_attribute_changes_tree(client):
    payload = _balanced_payload()
    pid = client.post("/api/projects", json=payload).json()["id"]

    free = client.post(f"/api/projects/{pid}/compute").json()["result"]
    assert free["status"] == "ok"
    free_root = free["tree"]["attributeId"]

    # 编辑项目，锁根为属性 1
    payload["locks"] = [{"path": [], "attributeId": 1}]
    r = client.put(f"/api/projects/{pid}", json=payload)
    assert r.status_code == 200
    assert r.json()["locks"] == [{"path": [], "attributeId": 1}]

    locked = client.post(f"/api/projects/{pid}/compute").json()["result"]
    assert locked["status"] == "ok"
    assert locked["tree"]["attributeId"] == 1
    assert locked["tree"].get("locked") is True
    if free_root != 1:
        # 若自由最优根不是 1，说明锁定确实改变了树
        assert locked["score"]["preorder"] != free["score"]["preorder"]


def test_lock_impossible_returns_no_lock_and_snapshot(client):
    payload = _balanced_payload()
    # 根锁为属性 2：对象 1、2、3 为真、4 为假（都已知、两边非空，合法）；
    # 但真组 {1,2,3} 继续锁不下去的可能性——这里直接验证接口透传结果。
    payload["locks"] = [{"path": [], "attributeId": 3}]
    # 属性 3 在对象 1、2 上未知，根锁必然无解
    pid = client.post("/api/projects", json=payload).json()["id"]
    r = client.post(f"/api/projects/{pid}/compute").json()["result"]
    assert r["status"] == "no_lock"
    assert r["violatedLock"] == {"path": [], "attributeId": 3}
    assert "tree" not in r
    snaps = client.get(f"/api/projects/{pid}/snapshots").json()
    assert snaps[0]["result"]["status"] == "no_lock"
    assert snaps[0]["locks"] == [{"path": [], "attributeId": 3}]


def test_lock_validation_rejects_unknown_attribute(client):
    payload = _balanced_payload()
    payload["locks"] = [{"path": [], "attributeId": 99}]
    r = client.post("/api/projects", json=payload)
    assert r.status_code == 400
    assert "锁定" in r.json()["detail"]


def test_locks_default_to_empty(client):
    pid = client.post("/api/projects", json=_balanced_payload()).json()["id"]
    p = client.get(f"/api/projects/{pid}").json()
    assert p["locks"] == []


def test_unobserved_attribute_appears_in_reasons(client):
    # 属性 3 完全没有任何单元
    payload = _payload(
        cells={
            "1:1": "true", "2:1": "true", "3:1": "false", "4:1": "unknown",
            "1:2": "true", "2:2": "true", "3:2": "true", "4:2": "true",
        }
    )
    # 额外补一个属性 9（无任何单元）
    payload["attributes"].append({"id": 9, "label": "完全没观察"})
    pid = client.post("/api/projects", json=payload).json()["id"]
    r = client.post(f"/api/projects/{pid}/compute").json()["result"]
    assert r["status"] == "inseparable"
    ids = [x["attributeId"] for x in r["reasons"]]
    assert 9 in ids
    reason9 = next(x for x in r["reasons"] if x["attributeId"] == 9)
    assert reason9["reason"] == "unknown"
