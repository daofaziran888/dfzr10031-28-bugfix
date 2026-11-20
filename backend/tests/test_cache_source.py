"""缓存来源索引与数据服务缓存评估的口径核对。

直接运行：cd backend && python3 tests/test_cache_source.py
也可用 pytest 运行：cd backend && python3 -m pytest tests/test_cache_source.py

覆盖的口径：
- 同一取数编号重送（含并发补报）只记一次，不产生分页重复；
- 过期行从当前取数排除，但仍可在历史截面定位；
- 筛选范围与合计使用同一页组边界，分页不重不漏；
- 同源两版切片排在分页边缘，到期前后两次取数的定位、排序、过滤与来源记录一致；
- 数据API发布按来源索引筛可服务截面、计算命中与缺批，并定位上一页末行来源。
"""
from __future__ import annotations

import os
import sys
import threading
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.seed import SEED_ROWS
from app.services.cache_source import CacheSourceService, format_time
from app.services.data_service import DELIVERY_POLICY, DataServiceService
from app.store import store

T0 = datetime(2026, 11, 20, 8, 0, 0, tzinfo=timezone.utc)

index = CacheSourceService()
data_service = DataServiceService()


def reset() -> None:
    store.rows("cache_source").clear()


def restore_seed() -> None:
    store.rows("cache_source")[:] = [dict(row) for row in SEED_ROWS["cache_source"]]


def reg(fetch_id: str, *, source: str = "SRC-T", section: str = "SEC-1", slice_id: str = "SLICE-A",
        batch: str = "BATCH-1", reading: str = "1", registered: datetime = T0,
        expires: datetime = T0 + timedelta(hours=2)) -> dict:
    entry, missing, _ = index.register({
        "源编号": source,
        "取数编号": fetch_id,
        "来源批次": batch,
        "取数截面": section,
        "切片编号": slice_id,
        "读数": reading,
        "数据内容": f"{fetch_id} 的交付内容",
        "到期时间": format_time(expires),
    }, now=registered)
    assert not missing, f"登记不应缺字段: {missing}"
    assert entry is not None
    return entry


def test_seed_scenario_assessment() -> None:
    """种子场景：上一截面两片不重叠切片，新批仅一片有效，另一片旧数据已过期。"""
    restore_seed()
    result, message = data_service.cache_assessment(1, page=2, size=1)
    assert result is not None, message
    assert result["交付策略"] == DELIVERY_POLICY == "先交付有效切片并显式计入缺批"
    assert result["当前截面"] == "SEC-2026-11-20"
    assert result["上一截面"] == "SEC-2026-11-19"
    assert result["可服务截面"] == ["SEC-2026-11-20"]
    assert result["命中数"] == 1 and result["缺批数"] == 1
    assert result["缺批明细"] == [
        {"切片编号": "SLICE-B", "原因": "旧批已过期，新批未送达", "最近来源批次": "BATCH-20261119"}
    ]
    # 分页总数与当前取数截面一致：当前只有 SLICE-A 一片有效切片
    assert result["分页"] == {"page": 2, "size": 1, "total": 1}
    # 同一分页请求核对上一页末行保存的来源与当时结果
    last = result["上一页末行来源"]
    assert last is not None and last["取数编号"] == "FETCH-0001-A2"
    assert last["来源批次"] == "BATCH-20261120" and last["取数截面"] == "SEC-2026-11-20"
    assert last["当时结果"]["读数"] == "150"
    first_page, _ = data_service.cache_assessment(1, page=1, size=1)
    assert first_page is not None and first_page["上一页末行来源"] is None
    # 当前视图先交付有效切片；历史截面仍能定位已过期的旧批
    current, current_total = index.list_entries(source="DATA-0001")
    assert current_total == 1 and current[0]["切片编号"] == "SLICE-A"
    history, history_total = index.list_entries(source="DATA-0001", section="SEC-2026-11-19")
    assert history_total == 2 and all(row["有效期状态"] == "已过期" for row in history)


def test_register_dedup_and_concurrent_reports() -> None:
    reset()
    reg("FETCH-DEDUP", reading="10")
    again, missing, reports = index.register({
        "源编号": "SRC-T", "取数编号": "FETCH-DEDUP", "来源批次": "BATCH-1",
        "取数截面": "SEC-1", "切片编号": "SLICE-A", "读数": "999",
        "数据内容": "补报内容", "到期时间": format_time(T0 + timedelta(hours=3)),
    }, now=T0 + timedelta(minutes=10))
    assert not missing and reports == 1
    assert again is not None and again["读数"] == "10", "补报不得覆盖首次登记的当时结果"
    assert len(store.rows("cache_source")) == 1, "重送不得新增分页行"

    workers = 8
    barrier = threading.Barrier(workers)

    def supplement() -> None:
        barrier.wait()
        index.register({
            "源编号": "SRC-T", "取数编号": "FETCH-DEDUP", "来源批次": "BATCH-1",
            "取数截面": "SEC-1", "切片编号": "SLICE-A", "读数": "999",
            "数据内容": "并发补报", "到期时间": format_time(T0 + timedelta(hours=3)),
        }, now=T0 + timedelta(minutes=20))

    threads = [threading.Thread(target=supplement) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    row = store.rows("cache_source")[0]
    assert row["补报次数"] == 1 + workers, "并发补报每次都只记一次补报"
    _, total = index.list_entries(source="SRC-T", view="all", now=T0 + timedelta(minutes=30))
    assert total == 1, "并发补报不得造成分页重复"


def test_expiry_excluded_current_but_locatable_in_section() -> None:
    reset()
    reg("FETCH-EXP", expires=T0 + timedelta(hours=1))
    before, total_before = index.list_entries(source="SRC-T", now=T0 + timedelta(minutes=30))
    assert total_before == 1 and before[0]["有效期状态"] == "有效中"
    after, total_after = index.list_entries(source="SRC-T", now=T0 + timedelta(hours=2))
    assert total_after == 0 and after == [], "过期行须从当前取数排除"
    history, history_total = index.list_entries(source="SRC-T", section="SEC-1", now=T0 + timedelta(hours=2))
    assert history_total == 1 and history[0]["有效期状态"] == "已过期", "过期行仍可在历史截面定位"
    expired, expired_total = index.list_entries(source="SRC-T", view="all", validity="已过期", now=T0 + timedelta(hours=2))
    assert expired_total == 1 and expired[0]["取数编号"] == "FETCH-EXP"


def test_filter_and_total_share_page_boundary() -> None:
    reset()
    for seq in range(5):
        reg(f"FETCH-P1-{seq}", source="SRC-P1", slice_id=f"SLICE-{seq}")
    for seq in range(3):
        reg(f"FETCH-P2-{seq}", source="SRC-P2", slice_id=f"SLICE-{seq}")
    seen: list[str] = []
    for page in (1, 2, 3):
        items, total = index.list_entries(source="SRC-P1", page=page, size=2, now=T0 + timedelta(minutes=1))
        assert total == 5, "筛选范围与合计必须使用同一页组边界"
        seen.extend(str(row["取数编号"]) for row in items)
    assert len(seen) == 5 and len(set(seen)) == 5, "分页不得重复或遗漏"
    items, total = index.list_entries(keyword="FETCH-P2", view="all", now=T0 + timedelta(minutes=1))
    assert total == 3 and len(items) == 3


def test_pagination_edge_two_versions_across_expiry() -> None:
    """同源两版切片排在分页边缘，到期前后两次取数比对定位、排序、过滤与来源记录。"""
    reset()
    reg("FETCH-E0", source="EDGE-0000", section="SEC-1", batch="BATCH-E0", expires=T0 + timedelta(hours=10))
    reg("FETCH-E1-V1", source="EDGE-0001", section="SEC-1", batch="BATCH-E1", reading="111",
        expires=T0 + timedelta(hours=1))
    reg("FETCH-E1-V2", source="EDGE-0001", section="SEC-2", batch="BATCH-E2", reading="222",
        registered=T0 + timedelta(minutes=10), expires=T0 + timedelta(hours=10))

    def fetch(moment: datetime) -> tuple[list[dict], list[dict], int]:
        page1, total1 = index.list_entries(view="all", page=1, size=2, now=moment)
        page2, total2 = index.list_entries(view="all", page=2, size=2, now=moment)
        assert total1 == total2 == 3, "同一页组边界上合计必须一致"
        return page1, page2, total1

    page1, page2, _ = fetch(T0 + timedelta(minutes=30))
    assert [row["取数编号"] for row in page1] == ["FETCH-E0", "FETCH-E1-V1"]
    assert [row["取数编号"] for row in page2] == ["FETCH-E1-V2"], "同源两版切片应排在分页边缘"
    assert page1[-1]["有效期状态"] == "有效中" and page2[0]["有效期状态"] == "有效中"

    page1_after, page2_after, _ = fetch(T0 + timedelta(hours=2))
    assert [row["取数编号"] for row in page1_after] == ["FETCH-E0", "FETCH-E1-V1"], "到期后定位与排序不得漂移"
    assert [row["取数编号"] for row in page2_after] == ["FETCH-E1-V2"]
    assert page1_after[-1]["有效期状态"] == "已过期" and page2_after[0]["有效期状态"] == "有效中"
    assert page1_after[-1]["来源批次"] == "BATCH-E1" and page2_after[0]["来源批次"] == "BATCH-E2"

    current, current_total = index.list_entries(source="EDGE-0001", now=T0 + timedelta(hours=2))
    assert current_total == 1 and current[0]["取数编号"] == "FETCH-E1-V2", "新请求已读取更晚一批"
    history, history_total = index.list_entries(source="EDGE-0001", section="SEC-1", now=T0 + timedelta(hours=2))
    assert history_total == 1 and history[0]["读数"] == "111", "旧缓存仍用来解释上一份交付的来源"


def test_expire_between_two_queries_then_new_batch() -> None:
    reset()
    reg("FETCH-Q1", source="SRC-Q", section="SEC-1", batch="BATCH-Q1", reading="7",
        expires=T0 + timedelta(hours=1))
    first, first_total = index.list_entries(source="SRC-Q", page=1, size=10, now=T0 + timedelta(minutes=30))
    assert first_total == 1 and first[0]["读数"] == "7"
    second, second_total = index.list_entries(source="SRC-Q", page=1, size=10, now=T0 + timedelta(hours=2))
    assert second_total == 0 and second == [], "同一切片在两次查询间结束有效期后须退出当前取数"
    history, _ = index.list_entries(source="SRC-Q", section="SEC-1", now=T0 + timedelta(hours=2))
    assert history[0]["取数编号"] == "FETCH-Q1", "旧缓存仍解释上一份交付的来源"
    reg("FETCH-Q2", source="SRC-Q", section="SEC-2", batch="BATCH-Q2", reading="8",
        registered=T0 + timedelta(hours=2, minutes=5), expires=T0 + timedelta(hours=5))
    third, third_total = index.list_entries(source="SRC-Q", page=1, size=10, now=T0 + timedelta(hours=3))
    assert third_total == 1 and third[0]["取数编号"] == "FETCH-Q2", "新请求已读取更晚一批"


def test_valid_at_filter() -> None:
    reset()
    reg("FETCH-VA", expires=T0 + timedelta(hours=1))
    hit, hit_total = index.list_entries(source="SRC-T", view="all", valid_at=format_time(T0 + timedelta(minutes=30)),
                                        now=T0 + timedelta(hours=2))
    assert hit_total == 1 and hit[0]["取数编号"] == "FETCH-VA"
    miss, miss_total = index.list_entries(source="SRC-T", view="all", valid_at=format_time(T0 + timedelta(hours=2)),
                                          now=T0 + timedelta(hours=2))
    assert miss_total == 0 and miss == []


def test_run_action_expire_now() -> None:
    reset()
    entry = reg("FETCH-ACT", expires=T0 + timedelta(hours=9))
    updated, message = index.run_action(int(entry["id"]), "立即到期", now=T0 + timedelta(minutes=5))
    assert updated is not None and updated["有效期状态"] == "已过期", message
    _, total = index.list_entries(source="SRC-T", now=T0 + timedelta(minutes=6))
    assert total == 0
    unknown, _ = index.run_action(int(entry["id"]), "不存在的动作", now=T0)
    assert unknown is None


def test_assessment_boundary_matches_list_page() -> None:
    """用同样的分页请求核对当前总数和上一页最后一行保存的历史来源。"""
    reset()
    for seq in range(3):
        reg(f"FETCH-B{seq}", source="SRC-B", slice_id=f"SLICE-{seq}", reading=str(seq))
    store.rows("data_service").append({
        "id": 9001, "status": "已发布", "pending": False, "abnormal": False, "服务编号": "SRC-B",
    })
    try:
        page1, total = index.list_entries(source="SRC-B", page=1, size=2, now=T0 + timedelta(minutes=1))
        assert total == 3 and len(page1) == 2
        result, message = data_service.cache_assessment(9001, page=2, size=2, now=T0 + timedelta(minutes=1))
        assert result is not None, message
        assert result["分页"]["total"] == total, "缓存切片的分页总数与当前取数截面一致"
        last = result["上一页末行来源"]
        assert last is not None and last["取数编号"] == page1[-1]["取数编号"]
        assert last["当时结果"]["读数"] == page1[-1]["读数"]
        assert result["命中数"] == 3 and result["缺批数"] == 0, "只有一个截面时以当前截面为应到口径，有效切片全部命中"
    finally:
        store.rows("data_service").pop()


ALL_TESTS = [
    test_seed_scenario_assessment,
    test_register_dedup_and_concurrent_reports,
    test_expiry_excluded_current_but_locatable_in_section,
    test_filter_and_total_share_page_boundary,
    test_pagination_edge_two_versions_across_expiry,
    test_expire_between_two_queries_then_new_batch,
    test_valid_at_filter,
    test_run_action_expire_now,
    test_assessment_boundary_matches_list_page,
]


def main() -> int:
    failures = 0
    for test in ALL_TESTS:
        try:
            test()
        except AssertionError as error:
            failures += 1
            print(f"FAIL {test.__name__}: {error}")
        except Exception as error:  # noqa: BLE - 测试脚本直接暴露异常类型
            failures += 1
            print(f"ERROR {test.__name__}: {type(error).__name__}: {error}")
        else:
            print(f"PASS {test.__name__}")
    print(f"\n{len(ALL_TESTS) - failures}/{len(ALL_TESTS)} 项口径核对通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
