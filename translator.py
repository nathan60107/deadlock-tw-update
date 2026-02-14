"""
翻譯管理器
負責下載、驗證和替換翻譯檔案
"""

import logging
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote_to_bytes, unquote
from email.header import decode_header
import sys

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class TranslationManager:
    """翻譯下載和替換管理器"""
    
    def __init__(self):
        """初始化管理器"""
        self.forum_url = "https://forum.gamer.com.tw/C.php?bsn=80911&snA=76"
        self.download_timeout = 30
        self.auto_launch = True
        self.translation_filename = "taiwan_translation.zip"
        self.log_level = "INFO"
        
        # 自動偵測遊戲路徑
        self.deadlock_path = self._detect_deadlock_path()
        
        # 設定日誌級別
        logging.getLogger().setLevel(getattr(logging, self.log_level))
        
        # 使用遊戲根目錄作為工作目錄
        self.work_dir = self.deadlock_path

        # 下載目錄（所有翻譯檔統一下載到此處）
        self.download_dir = self.work_dir / "downloads"
        self.download_dir.mkdir(parents=True, exist_ok=True)
    
    def _detect_deadlock_path(self) -> Path:
        """獲取遊戲路徑（使用當前目錄）"""
        logger.info(f"使用當前目錄作為遊戲路徑: {Path.cwd()}")
        return Path.cwd()
    
    def download_translation(self) -> Path | None:
        """下載翻譯檔案"""
        try:
            logger.info(f"從論壇分析翻譯: {self.forum_url}")
            
            # 如果論壇 URL 是巴哈姆特論壇，先解析頁面取得 Google Drive 連結
            download_url = self.forum_url
            if 'gamer.com.tw' in self.forum_url or 'bahamut.com.tw' in self.forum_url:
                logger.info("偵測到論壇連結，嘗試解析頁面...")
                parsed_url = self._parse_forum_page(self.forum_url)
                if parsed_url:
                    download_url = parsed_url
                    logger.info(f"成功解析論壇頁面，取得: {download_url}")
                else:
                    logger.warning("無法從論壇頁面解析下載連結，使用預設 URL")
            
            # 如果是 Google Drive 連結，轉換為直接下載 URL
            if 'drive.google.com' in download_url or 'docs.google.com' in download_url:
                download_url = self._convert_gdrive_url(download_url)
            
            logger.info(f"開始下載: {download_url}")

            # 先嘗試 HEAD 取得檔名與大小（某些伺服器可能不支援 HEAD）
            filename = None
            total_size = 0
            try:
                head_resp = requests.head(
                    download_url,
                    timeout=self.download_timeout,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
                    allow_redirects=True
                )
                if head_resp.ok:
                    total_size = int(head_resp.headers.get('content-length', 0) or 0)
                    filename = self._extract_filename_from_headers(head_resp.headers, head_resp.url)
            except Exception:
                # 若 HEAD 失敗，繼續使用 GET 來取得資訊
                filename = None

            # 再嘗試從 URL 或預設名稱推斷檔名
            if not filename:
                try:
                    parsed = urlparse(download_url)
                    candidate = Path(parsed.path).name
                    if candidate:
                        filename = candidate
                except Exception:
                    filename = None

            # 最後回退到預設檔名
            if not filename:
                filename = self.translation_filename

            # 下載目標路徑（保留原始檔名，不重新命名）
            download_path = self.download_dir / filename

            # 如果檔案已存在且通過驗證，跳過下載
            if download_path.exists():
                logger.info(f"發現已存在的下載檔案: {download_path}，準備驗證...")
                if self._validate_download(download_path):
                    logger.info(f"檔案驗證成功，跳過下載: {download_path}")
                    return download_path
                else:
                    logger.warning(f"已存在檔案驗證失敗，將重新下載: {download_path}")

            # 建立下載請求（實際讀取內容）
            response = requests.get(
                download_url,
                timeout=self.download_timeout,
                stream=True,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
                allow_redirects=True
            )
            response.raise_for_status()

            # 若 HEAD 沒拿到 size，改用 GET 標頭
            if total_size == 0:
                total_size = int(response.headers.get('content-length', 0) or 0)

            # 嘗試用 GET 回應的 headers 判斷檔名（覆寫先前推測）
            filename_from_get = self._extract_filename_from_headers(response.headers, response.url)
            if filename_from_get and filename_from_get != filename:
                download_path = self.download_dir / filename_from_get
                filename = filename_from_get

            downloaded_size = 0

            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            percentage = (downloaded_size / total_size) * 100
                            logger.debug(f"下載進度: {percentage:.1f}%")

            logger.info(f"下載完成: {download_path} ({downloaded_size} bytes)")
            
            # 驗證下載的檔案
            if not self._validate_download(download_path):
                logger.error("下載的檔案驗證失敗")
                return None
            
            return download_path
            
        except requests.RequestException as e:
            logger.error(f"下載失敗: {str(e)}")
            return None
        except Exception as e:
            logger.exception(f"發生未預期的錯誤: {str(e)}")
            return None
    
    def _parse_forum_page(self, forum_url: str) -> str | None:
        """解析論壇頁面，提取下載連結"""
        try:
            response = requests.get(
                forum_url,
                timeout=self.download_timeout,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            response.encoding = 'utf-8'
            response.raise_for_status()
            
            # 使用 BeautifulSoup 解析 HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 尋找 Google Drive 連結
            # 模式 1: 直接的連結標籤
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                # 直接包含 Google Drive 的連結
                if 'drive.google.com' in href or 'docs.google.com' in href:
                    logger.info(f"找到 Google Drive 連結: {href}")
                    return href

                # 處理 Gamer 轉向 (ref.gamer.com.tw/redir.php?url=ENCODED_URL)
                try:
                    parsed_href = urlparse(href)
                    # 檢查是否為轉址路徑或主機
                    if 'redir.php' in parsed_href.path or 'ref.gamer.com.tw' in parsed_href.netloc:
                        qs = parse_qs(parsed_href.query)
                        if 'url' in qs and qs['url']:
                            decoded = unquote(qs['url'][0])
                            if 'drive.google.com' in decoded or 'docs.google.com' in decoded:
                                logger.info(f"從轉址連結解析到 Google Drive: {decoded}")
                                return decoded
                except Exception:
                    # 忽略解析錯誤，繼續搜尋其他連結
                    pass
            
            # 模式 2: 文本中的 URL
            text_content = soup.get_text()
            gdrive_pattern = r'https://drive\.google\.com/[^\s<>"{}|\\^`\[\]]+'
            matches = re.findall(gdrive_pattern, text_content)
            if matches:
                logger.info(f"從文本中找到 Google Drive 連結: {matches[0]}")
                return matches[0]
            
            logger.warning("無法從論壇頁面找到 Google Drive 連結")
            return None
            
        except Exception as e:
            logger.error(f"解析論壇頁面失敗: {str(e)}")
            return None
    
    def _convert_gdrive_url(self, gdrive_url: str) -> str:
        """轉換 Google Drive 連結為直接下載 URL"""
        try:
            # 先解碼 URL（處理 Gamer 轉址中的編碼連結）
            decoded_url = unquote(gdrive_url)
            logger.debug(f"解碼後的 URL: {decoded_url}")
            
            # 提取文件 ID - 支援多種格式:
            # 1. https://drive.google.com/file/d/{FILE_ID}/view?usp=drive_link
            # 2. https://drive.google.com/open?id={FILE_ID}
            # 3. https://drive.google.com/uc?id={FILE_ID}
            file_id_patterns = [
                r'/file/d/([a-zA-Z0-9-_]+)',  # /file/d/ID 格式
                r'(?:\?|&)id=([a-zA-Z0-9-_]+)',  # ?id=ID 或 &id=ID 格式
                r'/d/([a-zA-Z0-9-_]+)',  # /d/ID 格式
            ]
            
            file_id = None
            for pattern in file_id_patterns:
                match = re.search(pattern, decoded_url)
                if match:
                    file_id = match.group(1)
                    logger.debug(f"使用正規表達式 {pattern} 提取到 ID: {file_id}")
                    break
            
            if file_id:
                # 轉換為直接下載 URL
                direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                logger.info(f"提取文件 ID: {file_id}")
                logger.info(f"轉換為下載 URL: {direct_url}")
                return direct_url
            
            # 如果無法解析，嘗試返回原始 URL
            logger.warning(f"無法解析 Google Drive 文件 ID: {gdrive_url}，使用原始 URL")
            return gdrive_url
            
        except Exception as e:
            logger.error(f"轉換 Google Drive 連結失敗: {str(e)}")
            return gdrive_url
    
    def _validate_download(self, file_path: Path) -> bool:
        """驗證下載的檔案"""
        try:
            # 檢查檔案存在
            if not file_path.exists():
                logger.error("下載的檔案不存在")
                return False
            
            # 如果是 zip 檔案，驗證完整性
            if file_path.suffix.lower() == '.zip':
                with zipfile.ZipFile(file_path, 'r') as zip_file:
                    if zip_file.testzip() is not None:
                        logger.error("Zip 檔案損壞")
                        return False
            
            logger.info("檔案驗證成功")
            return True
            
        except Exception as e:
            logger.error(f"驗證失敗: {str(e)}")
            return False

    def _extract_filename_from_headers(self, headers: dict, url: str) -> str | None:
        """從 HTTP 回應標頭或 URL 推斷檔名"""
        try:
            cd = headers.get('content-disposition') or headers.get('Content-Disposition')
            if cd:
                # 支援 RFC2231 filename*=charset'lang'percent-encoded
                m_rfc2231 = re.search(r"filename\*=(?P<charset>[^']*)'(?P<lang>[^']*)'(?P<value>[^;]+)", cd, flags=re.I)
                if m_rfc2231:
                    try:
                        charset = (m_rfc2231.group('charset') or '').strip() or 'utf-8'
                        raw = m_rfc2231.group('value').strip().strip('"')
                        b = unquote_to_bytes(raw)
                        try:
                            return b.decode(charset, errors='replace')
                        except Exception:
                            return self._normalize_filename(b)
                    except Exception:
                        pass

                # 支援常見的 filename="name.ext" 或 filename=name.ext
                m = re.search(r'filename\s*=\s*"?([^";]+)"?', cd, flags=re.I)
                if m:
                    name = m.group(1).strip().strip('"')

                    # 若為 RFC2047 編碼 (=?charset?Q?...)，先解碼
                    if name.startswith('=?') and '?=' in name:
                        try:
                            parts = decode_header(name)
                            decoded = ''.join(
                                (part.decode(charset or 'utf-8', errors='replace') if isinstance(part, bytes) else part)
                                for part, charset in parts
                            )
                            return self._normalize_filename(decoded)
                        except Exception:
                            pass

                    # 若包含 percent-encoding，先解析為 bytes
                    try:
                        if '%' in name:
                            b = unquote_to_bytes(name)
                            return self._normalize_filename(b)
                    except Exception:
                        try:
                            return self._normalize_filename(unquote(name))
                        except Exception:
                            return name

                    return self._normalize_filename(name)

            # 從 URL path 取得檔名
            parsed = urlparse(url)
            name = Path(parsed.path).name
            if name:
                # 若 path 中有 percent-encoding，先解析為 bytes
                try:
                    if '%' in name:
                        b = unquote_to_bytes(name)
                        return self._normalize_filename(b)
                except Exception:
                    try:
                        return self._normalize_filename(unquote(name))
                    except Exception:
                        return name
                return self._normalize_filename(name)

        except Exception:
            pass

        return None

    def _decode_bytes_with_fallback(self, b: bytes) -> str:
        """嘗試以 UTF-8、CP950、latin-1 等編碼解碼 bytes，回傳最合理的字串。"""
        # 1. 優先 utf-8
        try:
            s = b.decode('utf-8')
            return s
        except Exception:
            pass

        # 2. 嘗試 CP950 (Big5 / 繁體中文環境)
        try:
            s = b.decode('cp950')
            return s
        except Exception:
            pass

        # 3. 退回 latin-1 再嘗試重新解碼為 utf-8 heuristic
        try:
            s = b.decode('latin-1')
            return s
        except Exception:
            pass

        # 最後使用 utf-8 replace
        try:
            return b.decode('utf-8', errors='replace')
        except Exception:
            return b.decode('latin-1', errors='replace')

    def _normalize_filename(self, value) -> str:
        """Normalize a filename-like value (bytes or str) into a best-effort str.

        - If `value` is bytes: try _decode_bytes_with_fallback.
        - If `value` is str: try to detect percent-encoding or mojibake and normalize.
        """
        try:
            # bytes -> decode with fallback
            if isinstance(value, (bytes, bytearray)):
                return self._decode_bytes_with_fallback(bytes(value))

            # str -> if percent-encoded, convert to bytes then decode
            if isinstance(value, str):
                if '%' in value:
                    try:
                        b = unquote_to_bytes(value)
                        return self._decode_bytes_with_fallback(b)
                    except Exception:
                        pass

                # try fixing common Latin-1 mojibake
                fixed = self._fix_latin1_mojibake(value)
                return fixed

        except Exception:
            pass
        # fallback
        return str(value)

    def _fix_latin1_mojibake(self, s: str) -> str:
        """嘗試修正把 UTF-8 bytes 當成 Latin-1 解成的錯亂字串。

        如果把字串先以 Latin-1 編碼為 bytes 再以 UTF-8 解碼後，結果包含 CJK 字元，
        且原始字串不包含 CJK，則回傳修復後字串，否則回傳原始字串。
        """
        try:
            if not s:
                return s
            has_cjk_orig = bool(re.search(r'[\u4e00-\u9fff]', s))
            # 先以 latin-1 編回 bytes，再解為 utf-8
            b = s.encode('latin-1', errors='replace')
            decoded = b.decode('utf-8', errors='replace')
            has_cjk_decoded = bool(re.search(r'[\u4e00-\u9fff]', decoded))
            if has_cjk_decoded and not has_cjk_orig:
                return decoded
            return s
        except Exception:
            return s
    
    def replace_translation_files(self, source_path: Path) -> bool:
        """替換翻譯檔案"""
        try:
            logger.info(f"開始替換檔案: {source_path}")
            
            # 如果是 zip 檔案，先解壓到下載目錄
            if source_path.suffix.lower() == '.zip':
                extract_dir = self.download_dir / source_path.stem
                logger.info(f"解壓檔案到下載目錄: {extract_dir}")
                extract_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(source_path, 'r') as zip_file:
                    zip_file.extractall(extract_dir)
            else:
                extract_dir = source_path
            
            # 替換翻譯檔案
            # 這裡需要根據實際的檔案結構調整
            translation_dir = extract_dir
            
            # 搜尋並複製翻譯檔案
            for src_file in translation_dir.rglob('*'):
                if src_file.is_file():
                    # 根據檔案路徑決定目標位置
                    # 預設: 直接複製到遊戲目錄對應位置
                    relative_path = src_file.relative_to(translation_dir)
                    dest_file = self.deadlock_path / relative_path
                    
                    # 建立目標目錄
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # 複製檔案
                    shutil.copy2(src_file, dest_file)
                    logger.debug(f"已複製: {src_file} -> {dest_file}")
            
            logger.info("檔案替換完成")
            
            return True
            
        except Exception as e:
            logger.error(f"替換檔案失敗: {str(e)}")
            return False
    
    def update_gameinfo_language(self) -> bool:
        """更新 gameinfo.gi 添加繁體中文語言支援"""
        try:
            gameinfo_path = self.deadlock_path / "game" / "citadel" / "gameinfo.gi"
            
            if not gameinfo_path.exists():
                logger.warning(f"找不到 gameinfo.gi: {gameinfo_path}")
                return False
            
            logger.info(f"開始修改 gameinfo.gi: {gameinfo_path}")
            
            # 讀取檔案
            with open(gameinfo_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 搜尋 SupportedLanguages 段落
            # 查找最後一個語言項目之後的位置，並在 } 之前插入繁體中文
            
            # 模式: 在 SupportedLanguages 的 } 之前插入 "tchinese" "3"
            pattern = r'(SupportedLanguages\s*\{[^}]*"ukrainian"\s*"3")\s*(\})'
            replacement = r'\1\n\t\t"tchinese" "3"\n\t\2'
            
            new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
            
            # 檢查是否已經有 tchinese
            if '"tchinese"' in new_content and '"tchinese"' not in content:
                # 成功添加
                with open(gameinfo_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                logger.info("成功在 gameinfo.gi 中添加繁體中文語言支援")
                return True
            elif '"tchinese"' in content:
                logger.info("gameinfo.gi 中已存在繁體中文語言支援")
                return True
            else:
                logger.warning("未能在 gameinfo.gi 中添加繁體中文語言支援")
                return False
            
        except Exception as e:
            logger.error(f"修改 gameinfo.gi 失敗: {str(e)}")
            return False
    
    def launch_game(self) -> bool:
        """啟動 Deadlock 遊戲"""
        try:
            # 使用預設路徑 \game\bin\win64\deadlock.exe
            deadlock_exe = self.deadlock_path / "game" / "bin" / "win64" / "deadlock.exe"
            
            if deadlock_exe.exists():
                # 將啟動此腳本時收到的命令列參數轉傳給遊戲
                args = []
                try:
                    args = sys.argv[1:]
                except Exception:
                    args = []

                cmd = [str(deadlock_exe)] + args
                logger.info(f"啟動遊戲: {deadlock_exe}，參數: {args}")
                subprocess.Popen(cmd)
                return True
            
        except Exception as e:
            logger.error(f"啟動遊戲失敗: {str(e)}")
            return False
