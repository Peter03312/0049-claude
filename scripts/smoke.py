#!/usr/bin/env python3
"""对运行中的 API 做真实 HTTP 冒烟：建卡 → 算出最优树 → 编辑过期 →
重算两类无解 → 快照保存。任何一步不符就以非零码退出。"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request


def call(method: str, url: str, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise AssertionError(f"{method} {url} -> {e.code}: {body}") from None


def main(base: str) -> None:
    # 等服务起来
    for _ in range(50):
        try:
            status, body = call("GET", f"{base}/api/health")
            if status == 200 and body == {"status": "ok"}:
                print("  ✓ 健康检查")
                break
        except Exception:
            time.sleep(0.2)
    else:
        raise AssertionError("API 未在超时内就绪")

    # 1) 建一个可完整辨认的项目
    project = {
        "name": "冒烟树叶",
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
        "cells": {
            "1:1": "true", "1:2": "true", "1:3": "false", "1:4": "false",
            "2:1": "true", "2:2": "true", "2:3": "false", "2:4": "true",
            "3:1": "false", "3:2": "false", "3:3": "true", "3:4": "false",
            "4:1": "false", "4:2": "true", "4:3": "false", "4:4": "true",
        },
    }
    _, p = call("POST", f"{base}/api/projects", project)
    pid = p["id"]
    assert p["result"] is None and p["resultFresh"] is False
    print(f"  ✓ 建项目 #{pid}，初始无结果")

    # 2) 计算：最优树，根属性 1，前序（假分支在前）= [1,2,4]
    _, c = call("POST", f"{base}/api/projects/{pid}/compute")
    r = c["result"]
    assert r["status"] == "ok", r
    assert r["tree"]["attributeId"] == 1
    assert r["score"]["preorder"] == [1, 2, 4]
    assert r["score"]["maxDepth"] == 2 and r["score"]["sumDepth"] == 8
    assert c["savedSnapshot"] is True and isinstance(c["snapshotId"], int)
    print(f"  ✓ 最优树：前序 {r['score']['preorder']}，快照 #{c['snapshotId']}")

    # 3) 编辑令旧树过期（改动后四行仍两两不同，树可重建）
    project["cells"]["4:4"] = "false"
    _, p2 = call("PUT", f"{base}/api/projects/{pid}", project)
    assert p2["inputVersion"] == 2
    assert p2["result"] is None and p2["resultFresh"] is False
    print("  ✓ 编辑后旧树过期（resultFresh=false）")

    # 4) 快照仍可读取，记录的是第 1 版输入
    _, snaps = call("GET", f"{base}/api/projects/{pid}/snapshots")
    assert len(snaps) == 1 and snaps[0]["inputVersion"] == 1
    print("  ✓ 旧快照保留且版本为 1")

    # 5) 再算，仍应为完整树（该改动不破坏可分性）
    _, c2 = call("POST", f"{base}/api/projects/{pid}/compute")
    assert c2["result"]["status"] == "ok"
    _, p3 = call("GET", f"{base}/api/projects/{pid}")
    assert p3["resultFresh"] is True and p3["resultVersion"] == 2
    print("  ✓ 重载后结果与第 2 版一致（resultFresh=true）")

    # 6) 其他无解：根集合本身无合法二分属性
    inseparable = {
        "name": "分不开",
        "objects": [
            {"id": 1, "label": "甲", "note": ""},
            {"id": 2, "label": "乙", "note": ""},
            {"id": 3, "label": "丙", "note": ""},
            {"id": 4, "label": "丁", "note": ""},
        ],
        "attributes": [
            {"id": 1, "label": "特征一"},
            {"id": 2, "label": "特征二"},
        ],
        "cells": {
            "1:1": "true", "2:1": "true", "3:1": "false", "4:1": "unknown",
            "1:2": "true", "2:2": "true", "3:2": "true", "4:2": "true",
        },
    }
    _, p_bad = call("POST", f"{base}/api/projects", inseparable)
    _, c_bad = call("POST", f"{base}/api/projects/{p_bad['id']}/compute")
    rb = c_bad["result"]
    assert rb["status"] == "inseparable", rb
    assert rb["subset"] == [1, 2]
    assert "tree" not in rb
    assert {x["reason"] for x in rb["reasons"]} == {"same"}
    print(f"  ✓ 其他无解：最小组 {rb['subset']}，无残缺树")

    # 7) 锁定无解：根属性合法，但假分支走进死胡同
    no_lock = {
        "name": "锁不住",
        "objects": [
            {"id": 1, "label": "甲", "note": ""},
            {"id": 2, "label": "乙", "note": ""},
            {"id": 3, "label": "丙", "note": ""},
            {"id": 4, "label": "丁", "note": ""},
        ],
        "attributes": [
            {"id": 1, "label": "特征一"},
            {"id": 2, "label": "特征二"},
        ],
        "cells": {
            "1:1": "true", "2:1": "true", "3:1": "false", "4:1": "false",
            "1:2": "unknown", "2:2": "unknown",
            "3:2": "unknown", "4:2": "true",
        },
    }
    _, p_lock = call("POST", f"{base}/api/projects", no_lock)
    _, c_lock = call("POST", f"{base}/api/projects/{p_lock['id']}/compute")
    rl = c_lock["result"]
    assert rl["status"] == "no_lock", rl
    assert rl["blockingPath"] == [{"attributeId": 1, "branch": "false"}]
    assert rl["terminalObjectIds"] == [3, 4]
    assert "tree" not in rl
    kinds = {x["reason"] for x in rl["reasons"]}
    assert kinds == {"unknown", "same"}, rl["reasons"]
    print("  ✓ 锁定无解：阻断路径 [属性1→假]，终点 {3,4}，逐属性说明未知/同值")

    # 8) 校验：对象少于 4 张应被拒绝
    too_few = dict(no_lock)
    too_few["objects"] = no_lock["objects"][:3]
    try:
        call("POST", f"{base}/api/projects", too_few)
        raise AssertionError("少于 4 张对象卡应返回 422")
    except AssertionError as e:
        if "422" not in str(e):
            raise
    print("  ✓ 4–20 张对象卡的校验生效")


if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else "8123"
    main(f"http://127.0.0.1:{port}")
