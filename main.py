"""
主程式入口點
Deadlock 繁體中文翻譯自動更新工具
"""

import logging
import sys
import os
from translator import TranslationManager

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deadlock_translator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    """主函式：執行步驟並回傳 success（True/False）。
    同時在成功時提示是否啟動遊戲；失敗時等待 Enter 關閉。"""
    try:
        logger.info("=" * 50)
        logger.info("Deadlock 繁體中文翻譯自動更新工具")
        logger.info("=" * 50)
        
        # 初始化翻譯管理器
        manager = TranslationManager()
        
        logger.info(f"遊戲路徑: {manager.deadlock_path}")
        logger.info(f"論壇網址: {manager.forum_url}")
        
        # 下載翻譯檔案
        logger.info("開始下載翻譯檔案...")
        download_path = manager.download_translation()
        if not download_path:
            logger.error("下載翻譯檔案失敗")
            input("按 Enter 鍵關閉...")
            return False
        
        logger.info(f"下載成功: {download_path}")
        
        # 替換檔案
        logger.info("替換遊戲檔案...")
        if not manager.replace_translation_files(download_path):
            logger.error("替換檔案失敗")
            input("按 Enter 鍵關閉...")
            return False
        
        logger.info("檔案替換成功!")
        
        # 修改 gameinfo.gi 以啟用繁體中文
        logger.info("更新遊戲設定...")
        if not manager.update_gameinfo_language():
            logger.warning("更新遊戲設定失敗，但繼續執行")

        logger.info("完成！")
        logger.info("=" * 50)
        
        # 生成啟動參數供使用者使用
        exe_path = os.path.abspath(sys.argv[0])
        launch_parameters = f'"{exe_path}" %command% '
        logger.info("【重要】請複製以下內容到 Steam 啟動選項：")
        logger.info(launch_parameters)
        logger.info("=" * 50)

        # 成功路徑：在互動式 Windows 終端提示按任意鍵啟動遊戲；若不想啟動可直接關閉視窗
        try:
            import msvcrt
        except Exception:
            msvcrt = None

        if msvcrt is not None and sys.stdin.isatty():
            print("所有步驟完成。按任意鍵啟動遊戲；若不想啟動請直接關閉視窗（點選叉叉）。")
            try:
                msvcrt.getch()
                if manager and manager.launch_game():
                    logger.info("遊戲已啟動")
                else:
                    logger.warning("無法自動啟動遊戲，請手動啟動")
            except Exception:
                pass
        else:
            # 非互動環境：依照 auto_launch 決定是否自動啟動
            if manager and manager.auto_launch:
                if manager.launch_game():
                    logger.info("遊戲已啟動")
                else:
                    logger.warning("無法自動啟動遊戲，請手動啟動")

        return True
        
    except Exception as e:
        logger.exception(f"發生錯誤: {str(e)}")
        input("發生錯誤，按 Enter 鍵關閉...")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
