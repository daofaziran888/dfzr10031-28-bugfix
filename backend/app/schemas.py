"""接口出入参模型：列表分页、动作结果与各模块的明细结构。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 20


class ActionResult(BaseModel):
    ok: bool
    message: str
    entry: dict[str, Any] | None = None


class EntryPayload(BaseModel):
    """登记或修改一条业务记录时提交的字段集合。"""

    values: dict[str, Any] = Field(default_factory=dict)
    remark: str | None = None



class MetricDefEntry(BaseModel):
    """指标明细结构。"""

    field_0: str | None = None  # 指标编号
    field_1: str | None = None  # 指标名称
    field_2: str | None = None  # 计算公式
    field_3: str | None = None  # 统计粒度
    field_4: str | None = None  # 时间窗口
    field_5: str | None = None  # 筛选条件
    field_6: str | None = None  # 精度位数
    field_7: str | None = None  # 口径版本

class DimensionEntry(BaseModel):
    """分析维度明细结构。"""

    field_0: str | None = None  # 维度编号
    field_1: str | None = None  # 维度名称
    field_2: str | None = None  # 维度类型
    field_3: str | None = None  # 关联数据集
    field_4: str | None = None  # 层级结构
    field_5: str | None = None  # 默认取值
    field_6: str | None = None  # 排序规则
    field_7: str | None = None  # 维度状态

class DatasetEntry(BaseModel):
    """分析数据集明细结构。"""

    field_0: str | None = None  # 数据集编号
    field_1: str | None = None  # 数据集名称
    field_2: str | None = None  # 来源类型
    field_3: str | None = None  # 字段数量
    field_4: str | None = None  # 行数估算
    field_5: str | None = None  # 刷新周期
    field_6: str | None = None  # 负责人
    field_7: str | None = None  # 数据集状态

class ExperimentEntry(BaseModel):
    """实验方案明细结构。"""

    field_0: str | None = None  # 方案编号
    field_1: str | None = None  # 实验名称
    field_2: str | None = None  # 分析数据集
    field_3: str | None = None  # 样本范围
    field_4: str | None = None  # 分组字段
    field_5: str | None = None  # 目标度量
    field_6: str | None = None  # 基准区间
    field_7: str | None = None  # 显著阈值

class QueryBuilderEntry(BaseModel):
    """查询模板明细结构。"""

    field_0: str | None = None  # 模板编号
    field_1: str | None = None  # 模板名称
    field_2: str | None = None  # 查询语句
    field_3: str | None = None  # 参数定义
    field_4: str | None = None  # 数据集范围
    field_5: str | None = None  # 超时秒数
    field_6: str | None = None  # 缓存策略
    field_7: str | None = None  # 模板状态

class DashboardEntry(BaseModel):
    """看板配置明细结构。"""

    field_0: str | None = None  # 看板编号
    field_1: str | None = None  # 看板名称
    field_2: str | None = None  # 包含图表
    field_3: str | None = None  # 数据刷新
    field_4: str | None = None  # 可见范围
    field_5: str | None = None  # 创建人
    field_6: str | None = None  # 创建时间
    field_7: str | None = None  # 看板状态

class ChartEntry(BaseModel):
    """图表明细结构。"""

    field_0: str | None = None  # 图表编号
    field_1: str | None = None  # 图表名称
    field_2: str | None = None  # 图表类型
    field_3: str | None = None  # 数据来源
    field_4: str | None = None  # 坐标字段
    field_5: str | None = None  # 聚合方式
    field_6: str | None = None  # 颜色方案
    field_7: str | None = None  # 图表状态

class DataServiceEntry(BaseModel):
    """数据服务明细结构。"""

    field_0: str | None = None  # 服务编号
    field_1: str | None = None  # 服务名称
    field_2: str | None = None  # 输出数据集
    field_3: str | None = None  # 查询参数
    field_4: str | None = None  # 响应字段
    field_5: str | None = None  # 缓存秒数
    field_6: str | None = None  # 分页上限
    field_7: str | None = None  # 服务状态

class AlertEntry(BaseModel):
    """告警规则明细结构。"""

    field_0: str | None = None  # 规则编号
    field_1: str | None = None  # 告警名称
    field_2: str | None = None  # 监控指标
    field_3: str | None = None  # 阈值条件
    field_4: str | None = None  # 告警级别
    field_5: str | None = None  # 通知方式
    field_6: str | None = None  # 静默时段
    field_7: str | None = None  # 规则状态

class UserGroupEntry(BaseModel):
    """用户组明细结构。"""

    field_0: str | None = None  # 组编号
    field_1: str | None = None  # 组名称
    field_2: str | None = None  # 组描述
    field_3: str | None = None  # 成员数量
    field_4: str | None = None  # 数据可见性
    field_5: str | None = None  # 看板可见性
    field_6: str | None = None  # 创建日期
    field_7: str | None = None  # 组状态

class SnapshotEntry(BaseModel):
    """快照记录明细结构。"""

    field_0: str | None = None  # 快照编号
    field_1: str | None = None  # 数据集名称
    field_2: str | None = None  # 快照时间
    field_3: str | None = None  # 行数快照
    field_4: str | None = None  # 校验哈希
    field_5: str | None = None  # 快照策略
    field_6: str | None = None  # 存储位置
    field_7: str | None = None  # 快照状态

class SchedulerEntry(BaseModel):
    """调度任务明细结构。"""

    field_0: str | None = None  # 任务编号
    field_1: str | None = None  # 任务名称
    field_2: str | None = None  # 调度类型
    field_3: str | None = None  # 执行周期
    field_4: str | None = None  # 上次执行
    field_5: str | None = None  # 下次执行
    field_6: str | None = None  # 依赖关系
    field_7: str | None = None  # 任务状态

class CacheEntry(BaseModel):
    """缓存配置明细结构。"""

    field_0: str | None = None  # 缓存编号
    field_1: str | None = None  # 缓存目标
    field_2: str | None = None  # 缓存策略
    field_3: str | None = None  # 过期秒数
    field_4: str | None = None  # 最大容量
    field_5: str | None = None  # 命中统计
    field_6: str | None = None  # 淘汰策略
    field_7: str | None = None  # 缓存状态

class CacheSourceEntry(BaseModel):
    """缓存来源索引明细结构。"""

    field_0: str | None = None  # 索引编号
    field_1: str | None = None  # 源编号
    field_2: str | None = None  # 取数编号
    field_3: str | None = None  # 来源批次
    field_4: str | None = None  # 取数截面
    field_5: str | None = None  # 切片编号
    field_6: str | None = None  # 读数
    field_7: str | None = None  # 到期时间

class PipelineEntry(BaseModel):
    """分析节点明细结构。"""

    field_0: str | None = None  # 节点编号
    field_1: str | None = None  # 输入数据集
    field_2: str | None = None  # 分析算子
    field_3: str | None = None  # 输出结果
    field_4: str | None = None  # 执行顺序
    field_5: str | None = None  # 依赖节点
    field_6: str | None = None  # 失败策略
    field_7: str | None = None  # 节点状态

class ModelEntry(BaseModel):
    """模型配置明细结构。"""

    field_0: str | None = None  # 模型编号
    field_1: str | None = None  # 模型名称
    field_2: str | None = None  # 模型类型
    field_3: str | None = None  # 训练数据集
    field_4: str | None = None  # 特征字段
    field_5: str | None = None  # 目标字段
    field_6: str | None = None  # 评估指标
    field_7: str | None = None  # 模型状态

class DataMartEntry(BaseModel):
    """集市表明细结构。"""

    field_0: str | None = None  # 表编号
    field_1: str | None = None  # 表名称
    field_2: str | None = None  # 主题域
    field_3: str | None = None  # 事实粒度
    field_4: str | None = None  # 关联维度
    field_5: str | None = None  # 度量字段
    field_6: str | None = None  # 刷新周期
    field_7: str | None = None  # 表状态

class ExportEntry(BaseModel):
    """导出任务明细结构。"""

    field_0: str | None = None  # 任务编号
    field_1: str | None = None  # 导出对象
    field_2: str | None = None  # 导出格式
    field_3: str | None = None  # 筛选条件
    field_4: str | None = None  # 数据行数
    field_5: str | None = None  # 导出时间
    field_6: str | None = None  # 文件大小
    field_7: str | None = None  # 任务状态

class AuditEntry(BaseModel):
    """审计记录明细结构。"""

    field_0: str | None = None  # 记录编号
    field_1: str | None = None  # 操作类型
    field_2: str | None = None  # 操作人
    field_3: str | None = None  # 操作对象
    field_4: str | None = None  # 操作时间
    field_5: str | None = None  # 变更内容
    field_6: str | None = None  # 审计结果
    field_7: str | None = None  # 记录状态
