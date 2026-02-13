"""
主程式入口點
Deadlock 繁體中文翻譯自動更新工具
"""

import logging
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
    """主函式"""
    try:
        logger.info("=" * 50)
        logger.info("Deadlock 繁體中文翻譯自動更新工具")
        logger.info("=" * 50)
        
        # 初始化翻譯管理器
        manager = TranslationManager()
        
        logger.info(f"遊戲路徑: {manager.deadlock_path}")
        logger.info(f"論壇網址: {manager.forum_url}")
        
        # 下載翻譯檔案
        logger.info("\n開始下載翻譯檔案...")
        download_path = manager.download_translation()
        if not download_path:
            logger.error("下載翻譯檔案失敗")
            input("按 Enter 鍵關閉...")
            return False
        
        logger.info(f"下載成功: {download_path}")
        
        # 替換檔案
        logger.info("\n替換遊戲檔案...")
        if not manager.replace_translation_files(download_path):
            logger.error("替換檔案失敗")
            input("按 Enter 鍵關閉...")
            return False
        
        logger.info("檔案替換成功!")
        
        # 修改 gameinfo.gi 以啟用繁體中文
        logger.info("\n更新遊戲設定...")
        if not manager.update_gameinfo_language():
            logger.warning("更新遊戲設定失敗，但繼續執行")
        
        # 啟動遊戲
        if manager.auto_launch:
            logger.info("\n啟動 Deadlock 遊戲...")
            if manager.launch_game():
                logger.info("遊戲已啟動")
            else:
                logger.warning("無法自動啟動遊戲，請手動啟動")
        
        logger.info("\n完成！")
        logger.info("=" * 50)
        
        return True
        
    except Exception as e:
        logger.exception(f"發生錯誤: {str(e)}")
        return False


if __name__ == "__main__":
    success = main()
    input("按 Enter 鍵關閉...")
