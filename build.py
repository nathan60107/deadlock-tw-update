"""
PyInstaller 構建指令
用於將 Python 專案轉換為獨立的 exe 檔案
"""

import subprocess
import sys
from pathlib import Path
import io


def build_exe():
    """構建 exe 檔案"""
    
    project_dir = Path.cwd()
    
    # PyInstaller 命令
    cmd = [
        "pyinstaller",
        "--onefile",                          # 單一檔案輸出
        "--console",                          # 顯示控制台窗口
        "--name=deadlock_translator",         # 可執行檔名稱
        "--distpath=dist",                    # 輸出目錄
        "--specpath=.",                       # spec 檔案位置
    ]
    
    # 添加主檔案
    cmd.append("main.py")
    
    print("=" * 50)
    print("開始構建 exe...")
    print("=" * 50)
    print(f"命令: {' '.join(cmd)}")
    print()
    
    try:
        # 執行 PyInstaller
        result = subprocess.run(cmd, check=True)
        
        if result.returncode == 0:
            print()
            print("=" * 50)
            print("構建成功!")
            print("=" * 50)
            exe_path = project_dir / "dist" / "deadlock_translator.exe"
            print(f"可執行檔位置: {exe_path}")
            return True
        else:
            print("構建失敗!")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"構建過程發生錯誤: {str(e)}")
        return False
    except FileNotFoundError:
        print("錯誤: PyInstaller 未安裝")
        print("請執行: pip install pyinstaller")
        return False


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    success = build_exe()
    sys.exit(0 if success else 1)
