"""事件文件写入器——订阅 EventBus，将事件追加写入 events.jsonl"""

import json
from pathlib import Path

from pydantic import BaseModel

from hcode_claude.core.events.bus import EventBus


class EventWriter:
    """订阅 EventBus，每条事件写一行 NDJSON 到指定文件"""

    # 打开文件句柄并订阅所有事件类型
    async def start(self, bus: EventBus, path: Path) -> None:
        self._file = path.open("a", encoding="utf-8")

        # 写事件到文件：model_dump + json.dumps + 换行
        async def write_event(event: BaseModel) -> None:
            line = json.dumps(event.model_dump(), ensure_ascii=False) + "\n"
            self._file.write(line)
            self._file.flush()

        # 订阅 BaseModel —— 所有事件都是 BaseModel 子类
        bus.subscribe(BaseModel, write_event)
