"""缓存来源索引接口：接收数据服务登记的交付缓存内容，按源编号、取数截面与有效期查询。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.cache_source import CacheSourceService

router = APIRouter(prefix="/api/cache_source", tags=["缓存来源索引"])

service = CacheSourceService()

LIST_FIELDS = ["索引编号", "源编号", "取数编号", "来源批次", "取数截面", "切片编号", "读数", "到期时间", "有效期状态"]
STATUSES = ["有效中", "已过期"]

RESERVED_PARAMS = ("keyword", "status", "source", "section", "validity", "view", "valid_at", "page", "size")


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出缓存来源索引清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "cache_source", "total": total, "items": items}


@router.get("", response_model=PageResult[dict])
def list_entries(
    request: Request,
    keyword: str | None = Query(default=None, description="按索引编号或取数编号检索"),
    status: str | None = Query(default=None, description="有效中、已过期"),
    source: str | None = Query(default=None, description="按源编号精确过滤"),
    section: str | None = Query(default=None, description="按取数截面定位历史截面，含已过期行"),
    validity: str | None = Query(default=None, description="按有效期过滤：有效中、已过期"),
    view: str | None = Query(default=None, description="current 为当前取数视图（默认），all 为全部索引行"),
    valid_at: str | None = Query(default=None, description="只保留该时间点处于有效期内的行"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按源编号、取数截面与有效期过滤来源索引；默认只返回当前取数截面未过期的行。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    extra = {k: v for k, v in request.query_params.items() if k not in RESERVED_PARAMS and v.strip()}
    items, total = service.list_entries(
        keyword=keyword,
        status=status,
        source=source,
        section=section,
        validity=validity,
        view=view,
        valid_at=valid_at,
        page=page,
        size=size,
        extra=extra,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条来源索引明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"缓存来源索引 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记数据服务交付的缓存内容；同一取数编号重送按补报去重，不产生分页重复。"""
    entry, missing, reports = service.register(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    if reports:
        return ActionResult(ok=True, message=f"取数编号已登记过，本次按第 {reports} 次补报处理，未产生分页重复", entry=entry)
    return ActionResult(ok=True, message="缓存来源索引已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条来源索引执行立即到期；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
