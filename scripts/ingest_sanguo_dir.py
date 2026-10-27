import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import rag
from app.rag import _get_collection


async def main():
    collection = _get_collection()
    existing = collection.count()
    print(f"当前 collection 记录数: {existing}")

    if existing > 0:
        ans = input("是否清空现有数据后重新入库？(y/N): ").strip().lower()
        if ans == "y":
            all_ids = collection.get()["ids"]
            if all_ids:
                collection.delete(ids=all_ids)
            print(f"已清空 {len(all_ids)} 条记录")

    result = await rag.ingest_chapter_files("sanguo")
    print("\n入库完成:")
    for k, v in result.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())
