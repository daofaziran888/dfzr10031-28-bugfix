"""数据API发布业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.cache_source import CacheSourceService, parse_time
from app.store import store

MODULE = "data_service"
REQUIRED_FIELDS = ["服务编号", "服务名称", "输出数据集"]
STATUS_ORDER = ["草稿", "已配置", "已发布", "已停用"]
ACTION_RULES = {"保存配置": "已配置", "发布服务": "已发布", "停用服务": "已停用"}
NEGATIVE_ACTIONS = ["停用服务"]

# 缺批策略：先交付有效切片并显式计入缺批，不等待同批完整再开放查询。
DELIVERY_POLICY = "先交付有效切片并显式计入缺批"


class DataServiceService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
        extra: dict[str, str] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("服务编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if extra:
            for field, val in extra.items():
                rows = [row for row in rows if val in str(row.get(field, ""))]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"数据服务 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于数据API发布可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"数据服务已{action}"

    def cache_assessment(
        self,
        entry_id: int,
        *,
        page: int = 1,
        size: int = 20,
        now: Any = None,
    ) -> tuple[dict[str, Any] | None, str]:
        """用缓存来源索引评估一个数据服务的可服务截面、命中与缺批。

        - 可服务截面：该服务编号下仍至少有一片有效切片的取数截面；
        - 命中/缺批：以上一截面的切片集合为应到口径，当前截面仍有效的记命中，
          已过期或未送达的显式计入缺批（先交付有效切片，不等待同批完整）；
        - 上一页末行来源：按与来源索引列表相同的过滤与排序，定位上一页最后一条
          所关联的来源批次与当时结果，用于跨页核对交付口径。
        """
        entry = self.get_entry(entry_id)
        if entry is None:
            return None, f"数据服务 {entry_id} 不存在或已归档"
        source = str(entry.get("服务编号") or "").strip()
        if not source:
            return None, f"数据服务 {entry_id} 缺少服务编号，无法评估缓存来源"
        index = CacheSourceService()
        all_rows = index.sorted_entries(source=source, view="all", now=now)
        current_rows = index.sorted_entries(source=source, now=now)

        sections: dict[str, list[dict[str, Any]]] = {}
        for row in all_rows:
            sections.setdefault(str(row.get("取数截面", "")), []).append(row)

        def section_recency(rows: list[dict[str, Any]]) -> tuple[Any, str]:
            stamps = [parse_time(row.get("登记时间")) for row in rows]
            stamps = [stamp for stamp in stamps if stamp is not None]
            fallback = datetime.min.replace(tzinfo=timezone.utc)
            return (max(stamps) if stamps else fallback, str(rows[0].get("取数截面", "")))

        ordered = sorted(sections, key=lambda name: section_recency(sections[name]), reverse=True)
        servable = [
            name
            for name in ordered
            if any(row["有效期状态"] == "有效中" for row in sections[name])
        ]
        current_section = ordered[0] if ordered else None
        previous_section = ordered[1] if len(ordered) > 1 else None

        expected_from = previous_section or current_section
        expected = {str(row.get("切片编号")) for row in sections.get(expected_from, [])} if expected_from else set()
        current_valid = {str(row.get("切片编号")) for row in current_rows}
        hits = expected & current_valid
        missing = expected - current_valid

        missing_detail = []
        for slice_id in sorted(missing):
            candidates = [row for row in all_rows if str(row.get("切片编号")) == slice_id]
            newest = max(candidates, key=lambda row: str(row.get("登记时间", ""))) if candidates else None
            if newest is not None and str(newest.get("取数截面")) == current_section:
                reason = "新批已过期"
            else:
                reason = "旧批已过期，新批未送达"
            missing_detail.append({
                "切片编号": slice_id,
                "原因": reason,
                "最近来源批次": str(newest.get("来源批次")) if newest else None,
            })

        previous_last = None
        note = "第一页没有上一页"
        boundary = (page - 1) * size - 1
        if page >= 2:
            if 0 <= boundary < len(current_rows):
                row = current_rows[boundary]
                previous_last = {
                    "索引编号": row.get("索引编号"),
                    "取数编号": row.get("取数编号"),
                    "来源批次": row.get("来源批次"),
                    "取数截面": row.get("取数截面"),
                    "切片编号": row.get("切片编号"),
                    "当时结果": {
                        "读数": row.get("读数"),
                        "数据内容": row.get("数据内容"),
                        "登记时间": row.get("登记时间"),
                    },
                }
                note = "已定位上一页末行来源"
            else:
                note = "上一页末行超出当前取数截面"

        result = {
            "服务编号": source,
            "交付策略": DELIVERY_POLICY,
            "当前截面": current_section,
            "上一截面": previous_section,
            "可服务截面": servable,
            "有效切片数": len(current_rows),
            "命中数": len(hits),
            "缺批数": len(missing),
            "缺批明细": missing_detail,
            "分页": {"page": page, "size": size, "total": len(current_rows)},
            "上一页末行来源": previous_last,
            "定位说明": note,
        }
        return result, "缓存来源评估完成"
