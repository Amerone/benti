"""本体注册表。

本模块负责扫描本地 ``mvp/ontology`` 目录中的 Turtle 本体文件，读取文件头
约定的 ``# ontology-*`` 元信息，并为后续 Fuseki 加载阶段生成稳定的 named
graph IRI。它只处理本地文件元数据，不连接 Fuseki，也不执行 Owlready2/Pellet
加载，避免把注册发现和运行时图谱操作耦合在一起。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
from pathlib import Path
import re
from typing import Iterable

LOGGER = logging.getLogger(__name__)

GRAPH_IRI_PREFIX = "https://hifar.top/mto/graph"
DEFAULT_ONTOLOGY_DIR = Path(__file__).resolve().parents[1] / "ontology"
_HEADER_PATTERN = re.compile(r"^#\s*(ontology-(?:id|label|version|swrl))\s*:\s*(.*?)\s*$")


@dataclass(frozen=True)
class OntologyDescriptor:
    """单个本体文件的注册描述。

    字段来自 TTL 头部元信息和固定 graph IRI 契约。``swrl_path`` 允许为 ``None``，
    因为 SWRL 对照规则在 MVP 第一阶段是可选通道，规则文件缺失不能阻断本体发现。
    """

    ontology_id: str
    label: str
    version: str
    ttl_path: Path
    swrl_path: Path | None
    graph_iri: str
    data_graph_iri: str
    result_graph_iri: str
    spec_graph_iri: str

    def to_dict(self) -> dict[str, str | None]:
        """转换为 API 易序列化字典。

        Path 字段在这里转为字符串，便于 FastAPI/Streamlit 后续直接展示；核心注册
        逻辑仍保留 Path 类型，方便调用方做路径存在性和读取操作。
        """

        data = asdict(self)
        data["ttl_path"] = str(self.ttl_path)
        data["swrl_path"] = str(self.swrl_path) if self.swrl_path is not None else None
        return data


class OntologyRegistry:
    """本体注册表。

    负责在一个目录内发现所有 ``.ttl`` 本体文件，并按头部声明生成
    :class:`OntologyDescriptor`。缺少 ``# ontology-id:`` 的文件会被跳过并记录
    WARNING，明确禁止使用文件名 fallback，以保证多本体 ID 稳定且可审计。
    """

    def __init__(self, ontology_dir: str | Path = DEFAULT_ONTOLOGY_DIR) -> None:
        """创建注册表。

        参数 ``ontology_dir`` 指向本地本体目录；目录不存在时返回空发现结果并记录
        WARNING，不抛异常，便于 API 健康检查阶段给出可见降级信息。
        """

        self.ontology_dir = Path(ontology_dir)

    def discover(self) -> list[OntologyDescriptor]:
        """扫描目录并返回按 ``ontology_id`` 排序的本体描述。

        发现过程只依赖 TTL 头部元信息。SWRL 文件存在时返回路径，缺失时记录
        WARNING 并将 ``swrl_path`` 置为 ``None``，调用方仍可继续加载本体图。
        """

        if not self.ontology_dir.exists():
            LOGGER.warning("ontology directory missing: %s", self.ontology_dir)
            return []

        descriptors: list[OntologyDescriptor] = []
        seen_ids: set[str] = set()
        for ttl_path in sorted(self.ontology_dir.glob("*.ttl")):
            descriptor = self._descriptor_from_ttl(ttl_path)
            if descriptor is None:
                continue
            if descriptor.ontology_id in seen_ids:
                LOGGER.warning(
                    "duplicate ontology-id skipped: %s path=%s",
                    descriptor.ontology_id,
                    ttl_path,
                )
                continue
            seen_ids.add(descriptor.ontology_id)
            descriptors.append(descriptor)

        return sorted(descriptors, key=lambda item: item.ontology_id)

    def _descriptor_from_ttl(self, ttl_path: Path) -> OntologyDescriptor | None:
        metadata = _parse_header(ttl_path)
        ontology_id = metadata.get("ontology-id", "").strip()
        if not ontology_id:
            LOGGER.warning("missing ontology-id; skipped path=%s", ttl_path)
            return None

        swrl_path = _resolve_swrl_path(ttl_path.parent, metadata.get("ontology-swrl"))
        graph_iri = graph_iri_for(ontology_id)
        return OntologyDescriptor(
            ontology_id=ontology_id,
            label=metadata.get("ontology-label", ontology_id).strip() or ontology_id,
            version=metadata.get("ontology-version", "").strip(),
            ttl_path=ttl_path,
            swrl_path=swrl_path,
            graph_iri=graph_iri,
            data_graph_iri=graph_iri_for(ontology_id, "data"),
            result_graph_iri=graph_iri_for(ontology_id, "result"),
            spec_graph_iri=graph_iri_for(ontology_id, "spec"),
        )


def discover(ontology_dir: str | Path = DEFAULT_ONTOLOGY_DIR) -> list[OntologyDescriptor]:
    """发现本地本体文件。

    这是模块级便捷入口，供 API、测试和脚本直接调用；需要复用同一目录配置时可使用
    :class:`OntologyRegistry`。
    """

    return OntologyRegistry(ontology_dir).discover()


def list_ontologies(ontology_dir: str | Path = DEFAULT_ONTOLOGY_DIR) -> list[dict[str, str | None]]:
    """返回可 JSON 序列化的本体列表。

    该函数保持注册表边界清晰：它只序列化发现结果，不附加 loaded/triples 等运行时
    Fuseki 状态，后续图谱加载模块可在此基础上合并运行时字段。
    """

    return [descriptor.to_dict() for descriptor in discover(ontology_dir)]


def graph_iri_for(ontology_id: str, kind: str = "ontology") -> str:
    """生成稳定 named graph IRI。

    ``kind`` 支持 ``ontology``、``data``、``result``、``spec`` 四类。默认本体图不带
    后缀，其余三类按验收契约追加路径段。
    """

    if kind == "ontology":
        return f"{GRAPH_IRI_PREFIX}/{ontology_id}"
    if kind in {"data", "result", "spec"}:
        return f"{GRAPH_IRI_PREFIX}/{ontology_id}/{kind}"
    raise ValueError(f"unsupported graph kind: {kind}")


def _parse_header(ttl_path: Path) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in _read_lines(ttl_path):
        match = _HEADER_PATTERN.match(line)
        if match:
            metadata[match.group(1)] = match.group(2).strip()
    return metadata


def _read_lines(path: Path) -> Iterable[str]:
    try:
        return path.read_text(encoding="utf-8-sig").splitlines()
    except UnicodeDecodeError:
        LOGGER.warning("ttl header decode failed; skipped path=%s", path)
        return []


def _resolve_swrl_path(ontology_dir: Path, swrl_name: str | None) -> Path | None:
    if not swrl_name:
        return None

    swrl_path = ontology_dir / swrl_name.strip()
    if swrl_path.exists():
        return swrl_path

    LOGGER.warning("missing swrl file; swrl_path=None path=%s", swrl_path)
    return None

