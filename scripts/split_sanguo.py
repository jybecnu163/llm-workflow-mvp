import re
from pathlib import Path

CN_NUM = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
          "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNIT = {"十": 10, "百": 100, "千": 1000}


def cn_to_int(s):
    s = s.strip()
    if not s:
        return 0
    if any(u in s for u in "十百千"):
        total, number = 0, 0
        for ch in s:
            if ch in CN_NUM:
                number = CN_NUM[ch]
            elif ch in CN_UNIT:
                unit = CN_UNIT[ch]
                if number == 0:
                    number = 1
                total += number * unit
                number = 0
        return total + number
    digits = [str(CN_NUM[ch]) for ch in s if ch in CN_NUM]
    return int("".join(digits)) if digits else 0


CHAPTER_RE = re.compile(
    r"^\s*第([零一二三四五六七八九十百千]+)回[\s　]*(.{1,40})$",
    re.MULTILINE,
)


def main():
    src = Path(r"D:\IdeaProject\python\llm-workflow-mvp\data\rag_docs\《三国演义》.txt")
    out_dir = Path("../data/rag_docs/sanguo")
    out_dir.mkdir(parents=True, exist_ok=True)

    text = src.read_text(encoding="utf-8", errors="ignore")
    matches = list(CHAPTER_RE.finditer(text))
    print(f"匹配到 {len(matches)} 个回目")

    last_num = 0
    count = 0
    for i, m in enumerate(matches):
        cn_num = m.group(1)
        title = m.group(2).strip()
        num = cn_to_int(cn_num)
        if num <= last_num:
            print(f"  跳过疑似误匹配: 第{cn_num}回 {title}")
            continue
        last_num = num

        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        safe_title = re.sub(r'[\\/:*?"<>|]', "_", title)[:20]
        filename = f"第{num:03d}回_{safe_title}.txt"
        (out_dir / filename).write_text(body, encoding="utf-8")
        count += 1
        print(f"  {filename}  {len(body)} 字")

    print(f"共写出 {count} 个文件到 {out_dir}")


if __name__ == "__main__":
    main()