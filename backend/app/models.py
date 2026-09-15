"""数据库模型：项目（对象卡 + 属性 + 三值矩阵）与结果快照。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="辨认卡")

    # 对象：[{"id": 正整数, "label": "名称", "note": "..."}]
    objects: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # 属性：[{"id": 正整数, "label": "名称"}]
    attributes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # 单元格：{"对象id:属性id": "true|false|unknown"}
    cells: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # 路径锁定：[{"path": ["false"|"true", ...], "attributeId": 正整数}]
    locks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # 输入版本号：任何编辑 +1，令旧结果过期
    input_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # 最近一次计算结果（完整树或无解诊断），null 表示尚未计算/已过期后清空
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now
    )

    snapshots: Mapped[list["Snapshot"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Snapshot.id.desc()",
    )

    @property
    def result_fresh(self) -> bool:
        return (
            self.result is not None
            and self.result_version is not None
            and self.result_version == self.input_version
        )


class Snapshot(Base):
    """一次「计算并保存」：同时保存当时的输入和辨认结果，永久留档。"""

    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    input_version: Mapped[int] = mapped_column(Integer, nullable=False)
    objects: Mapped[list] = mapped_column(JSON, nullable=False)
    attributes: Mapped[list] = mapped_column(JSON, nullable=False)
    cells: Mapped[dict] = mapped_column(JSON, nullable=False)
    locks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    project: Mapped[Project] = relationship(back_populates="snapshots")
