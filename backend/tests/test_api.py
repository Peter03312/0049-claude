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
