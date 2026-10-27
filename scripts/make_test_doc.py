from pathlib import Path

out_dir = Path("../data/rag_docs")
out_dir.mkdir(parents=True, exist_ok=True)

content = """# 项目预算说明

## 一、总体预算

本项目总预算为 1200 万元人民币，分三期拨付：
- 第一期：2025 年 1 月，拨付 500 万元
- 第二期：2025 年 7 月，拨付 400 万元
- 第三期：2026 年 1 月，拨付 300 万元

## 二、费用构成

1. 人员费用：约 600 万元，占 50%
2. 设备采购：约 360 万元，占 30%
3. 差旅与会议：约 120 万元，占 10%
4. 其他支出：约 120 万元，占 10%

## 三、责任分工

- 项目负责人：张三
- 财务负责人：李四
- 技术负责人：王五

## 四、验收标准

项目需在 2026 年 6 月前完成全部交付物，并通过第三方审计。
"""

(out_dir / "project_budget.md").write_text(content, encoding="utf-8")
print(f"已生成 {out_dir / 'project_budget.md'}")
