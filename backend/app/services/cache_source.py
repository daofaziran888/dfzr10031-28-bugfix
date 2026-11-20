"""缓存来源索引业务规则：登记去重、截面视图、有效期口径与分页边界都收在这里。

缓存管理模块只登记缓存目标与过期秒数，本模块把数据服务每次交付的实际缓存内容
（读数、来源批次、取数截面、数据内容、到期时间）登记成来源索引，支持按源编号、
取数截面与有效期查询。

关键口径：
- 取数编号是幂等键：同一取数编号重送（含并发补报）只记一次补报，不产生分页重复行，
  首次登记的读数与数据内容保留为「当时结果」，不被补报覆盖；
- 当前取数视图只含各源编号最新取数截面里仍未过期的行，过期行从当前取数排除；
- 过期行不删除，按取数截面查询（历史截面）或 view=all 时仍可定位；
- 筛选、排序、合计与分页切片使用同一份过滤结果，保证页组边界一致；
- 缺批策略：先交付有效切片并显式计入缺批，不等待同批完整再开放查询。
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from app.store import store

MODULE = "cache_source"
REQUIRED_FIELDS = ["源编号", "取数编号", "来源批次", "取数截面", "切片编号", "读数", "数据内容", "到期时间"]
SORT_FIELDS = ("源编号", "取数截面", "切片编号", "取数编号")
VALIDITY_ORDER = ["有效中", "已过期"]
ACTION_RULES = {"立即到期": "已过期"}
NEGATIVE_ACTIONS = ["立即到期"]
VIEWS = ["current", "all"]

_register_lock = threading.Lock()


def parse_time(value: Any) -> datetime | None:
    """把 ISO 时间串或 datetime 归一到 UTC  aware datetime；无法解析时返回 None。"""
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_time(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()


class CacheSourceService:
    def _now(self, now: datetime | None) -> datetime:
        return parse_time(now) or datetime.now(timezone.utc)

    def _decorate(self, row: dict[str, Any], now: datetime) -> dict[str, Any]:
        """补出有效期派生字段；同时回写存储行的 status，让概览统计不过期。"""
        expires = parse_time(row.get("到期时间"))
        valid = expires is not None and expires > now
        row["status"] = "有效中" if valid else "已过期"
        row["pending"] = valid
        row["abnormal"] = False
        item = dict(row)
        item["有效期状态"] = row["status"]
        item["剩余秒数"] = int((expires - now).total_seconds()) if expires else 0
        return item

    def _current_sections(self, rows: list[dict[str, Any]]) -> dict[str, str]:
        """每个源编号的当前取数截面：登记时间最新（并列时截面编号较大）的截面。"""
        latest: dict[str, tuple[datetime, str]] = {}
        fallback = datetime.min.replace(tzinfo=timezone.utc)
        for row in rows:
            source = str(row.get("源编号", ""))
            registered = parse_time(row.get("登记时间")) or fallback
            key = (registered, str(row.get("取数截面", "")))
            if source not in latest or key > latest[source]:
                latest[source] = key
        return {source: section for source, (_, section) in latest.items()}

    def sorted_entries(
        self,
        *,
        source: str | None = None,
        section: str | None = None,
        validity: str | None = None,
        view: str | None = None,
        valid_at: Any = None,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """按视图与筛选条件返回排序后的全量行；分页由调用方在同一结果集上切片。"""
        moment = self._now(now)
        rows = [self._decorate(row, moment) for row in store.rows(MODULE)]
        if source:
            rows = [row for row in rows if str(row.get("源编号")) == source]
        if view == "all":
            pass
        elif section:
            # 历史截面定位：该截面登记过的行都在，包括现在已经过期的行
            rows = [row for row in rows if str(row.get("取数截面")) == section]
        else:
            # 当前取数视图：各源最新截面内仍未过期的行
            current = self._current_sections(rows)
            rows = [
                row
                for row in rows
                if str(row.get("取数截面")) == current.get(str(row.get("源编号", "")))
                and row["有效期状态"] == "有效中"
            ]
        if validity in VALIDITY_ORDER:
            rows = [row for row in rows if row["有效期状态"] == validity]
        if valid_at is not None:
            point = parse_time(valid_at)
            # valid_at 无法解析时视为不合法条件，宁可空结果也不静默放宽
            if point is None:
                return []
            rows = [
                row
                for row in rows
                if (parse_time(row.get("登记时间")) or moment) <= point
                and (parse_time(row.get("到期时间")) or moment) > point
            ]
        rows.sort(key=lambda row: tuple(str(row.get(field, "")) for field in SORT_FIELDS))
        return rows

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        source: str | None = None,
        section: str | None = None,
        validity: str | None = None,
        view: str | None = None,
        valid_at: Any = None,
        page: int = 1,
        size: int = 20,
        extra: dict[str, str] | None = None,
        now: datetime | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = self.sorted_entries(
            source=source,
            section=section,
            validity=validity or status,
            view=view,
            valid_at=valid_at,
            now=now,
        )
        if keyword:
            rows = [
                row
                for row in rows
                if keyword in str(row.get("索引编号", "")) or keyword in str(row.get("取数编号", ""))
            ]
        if extra:
            for field, val in extra.items():
                rows = [row for row in rows if val in str(row.get(field, ""))]
        # 筛选与合计共用这一份结果集，分页只在最后切片，保证页组边界一致
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int, *, now: datetime | None = None) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        if row is None:
            return None
        return self._decorate(row, self._now(now))

    def register(self, values: dict[str, Any], *, now: datetime | None = None) -> tuple[dict[str, Any] | None, list[str], int]:
        """登记一条来源索引。

        返回 (entry, missing, 补报次数)：补报次数为 0 表示新登记；大于 0 表示同一
        取数编号的重送，已按补报去重，不新增分页行，也不覆盖首次登记的当时结果。
        """
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, 0
        moment = self._now(now)
        expires = parse_time(values.get("到期时间"))
        if expires is None:
            return None, ["到期时间（需为 ISO 时间，如 2026-11-21T08:00:00Z）"], 0
        with _register_lock:
            rows = store.rows(MODULE)
            fetch_id = str(values.get("取数编号"))
            for row in rows:
                if str(row.get("取数编号")) == fetch_id:
                    row["补报次数"] = int(row.get("补报次数", 0)) + 1
                    row["最近补报时间"] = format_time(moment)
                    return self._decorate(row, moment), [], int(row["补报次数"])
            entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
            entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
            entry["索引编号"] = str(values.get("索引编号") or "").strip() or f"SRCI-{entry['id']:04d}"
            entry["登记时间"] = format_time(moment)
            entry["到期时间"] = format_time(expires)
            entry["补报次数"] = 0
            rows.append(entry)
            return self._decorate(entry, moment), [], 0

    def run_action(self, entry_id: int, action: str, *, now: datetime | None = None) -> tuple[dict[str, Any] | None, str]:
        row = store.find(MODULE, entry_id)
        if row is None:
            return None, f"缓存来源索引 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于缓存来源索引可执行范围"
        moment = self._now(now)
        row["到期时间"] = format_time(moment)
        return self._decorate(row, moment), "来源索引已立即到期，当前取数视图不再返回该行，历史截面仍可定位"
