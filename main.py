"""
主程式入口點
Deadlock 繁體中文翻譯自動更新工具
"""

import logging
from logging.handlers import RotatingFileHandler
import sys
import os
from translator import TranslationManager
import argparse

# 設定日誌
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('deadlock_translator.log', maxBytes=1*1024*1024, backupCount=1),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)


def main():
    """主函式：執行步驟並回傳 success（True/False）。
    同時在成功時提示是否啟動遊戲；失敗時等待 Enter 關閉。"""
    try:
        parser = argparse.ArgumentParser()
        # parser.add_argument("--forum_url", default="https://forum.gamer.com.tw/C.php?bsn=80911&snA=76")
        # parser.add_argument("--download_timeout", type=int, default=30)
        # parser.add_argument("--translation_filename", default="taiwan_translation.zip")
        parser.add_argument("--no_auto_launch", action="store_false", dest="auto_launch", help="阻止遊戲啟動")
        parser.add_argument("--log_level", default="INFO")
        args, _ = parser.parse_known_args()

        logging.getLogger().setLevel(getattr(logging, args.log_level))
        logger.info("=" * 50)
        logger.info("Deadlock 繁體中文翻譯自動更新工具")
        logger.info("=" * 50)
        
        # 初始化翻譯管理器
        manager = TranslationManager(args)
        
        # logger.info(f"遊戲路徑: {manager.deadlock_path}")
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

        # 啟動遊戲
        if manager.auto_launch:
            logger.info("\n啟動 Deadlock 遊戲...")
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
