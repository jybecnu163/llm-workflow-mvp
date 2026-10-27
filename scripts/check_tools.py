import sys

sys.path.insert(0, ".")

try:
    from app import tools

    print("✅ tools.py 加载成功")
    names = sorted(tools.TOOLS.keys())
    print(f"已注册 {len(names)} 个工具:")
    for n in names:
        print(" -", n)
    print()
    print("excel_describe 是否注册:", "✅ 是" if "excel_describe" in tools.TOOLS else "❌ 否")
except Exception:
    import traceback

    print("❌ tools.py 加载失败:")
    traceback.print_exc()
