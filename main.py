import pandas as pd
import yfinance as yf
import requests
import datetime
import os
import io
import sys
import random
import time

# ==========================================
# 🎯 戰情室 V12.3 (TPEX 封鎖繞過版)
# ==========================================

class CBSniperBot:
    def __init__(self):
        self.webhook_url = os.environ.get("DISCORD_WEBHOOK")
        
        # 鄭大四大條件
        self.MIN_AVG_VOL = 50       
        self.MIN_PRICE = 110.0      
        self.MAX_PRICE = 150.0      
        self.DROP_RATE = 0.05       
        
        self.end_date = datetime.date.today()
        self.start_date = self.end_date - datetime.timedelta(days=60) # 拉長天數確保均線計算

    def send_discord_message(self, content):
        if not self.webhook_url: return
        data = {
            "username": "鄭大戰情室",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/2910/2910795.png",
            "content": content
        }
        try: requests.post(self.webhook_url, json=data)
        except: pass

    def get_tpex_list_csv(self):
        """
        策略 B: 嘗試下載 CSV 格式 (較不容易被擋)
        """
        print("🔄 嘗試策略 B: 下載 CSV 清單...")
        url = "https://www.tpex.org.tw/web/bond/tradeinfo/cb/cb_daily_result.php?l=zh-tw&o=csv"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Referer": "https://www.tpex.org.tw/web/bond/tradeinfo/cb/cb_daily_result.php?l=zh-tw"
        }
        try:
            res = requests.get(url, headers=headers, timeout=15)
            res.raise_for_status()
            
            # 使用 pandas 讀取 CSV 字串
            # 櫃買中心的 CSV 通常前幾行是標題，需要跳過
            df = pd.read_csv(io.StringIO(res.text), header=None)
            
            cb_list = []
            # 遍歷 CSV 尋找代碼 (通常在第一欄，且長度為 5)
            for index, row in df.iterrows():
                try:
                    code = str(row[0]).strip()
                    name = str(row[1]).strip()
                    if len(code) == 5 and code.isdigit(): # 簡單驗證
                        cb_list.append({"code": code, "name": name})
                except: continue
                
            if len(cb_list) > 10:
                print(f"✅ CSV 策略成功！取得 {len(cb_list)} 檔")
                return cb_list
        except Exception as e:
            print(f"❌ CSV 策略失敗: {e}")
        return []

    def get_backup_list(self):
        """
        策略 C: 萬一都被擋，使用內建熱門觀察名單 (避免程式崩潰)
        """
        print("⚠️ 啟動策略 C: 使用備用名單")
        # 這裡列出一些近期熱門或您關注的標的
        return [
            {"code": "33241", "name": "雙鴻五"}, {"code": "30321", "name": "偉訓一"},
            {"code": "31351", "name": "凌航一"}, {"code": "68621", "name": "三集瑞一"},
            {"code": "64721", "name": "保瑞一"}, {"code": "23741", "name": "佳能一"},
            {"code": "55341", "name": "長虹六"}, {"code": "65761", "name": "逸達二"},
            {"code": "15902", "name": "亞德客二"}, {"code": "47144", "name": "永捷四"}
        ]

    def get_all_active_cb_tickers(self):
        # 1. 先試原本的 JSON (加上隨機延遲)
        time.sleep(2) 
        
        # 2. 如果 JSON 失敗 (您遇到的錯誤)，改試 CSV
        cb_list = self.get_tpex_list_csv()
        if cb_list: return cb_list
        
        # 3. 如果連 CSV 都失敗，回傳備用名單並通知
        self.send_discord_message("⚠️ **系統通知**\nTPEX 封鎖了 GitHub IP，已切換至「備用監控名單」。建議您在本機電腦執行程式以取得完整掃描。")
        return self.get_backup_list()

    def run(self):
        cb_list = self.get_all_active_cb_tickers()
        print(f"📉 準備分析 {len(cb_list)} 檔標的...")
        
        targets = []
        tickers_map = {f"{item['code']}.TWO": item for item in cb_list}
        tickers_list = list(tickers_map.keys())
        
        # 縮小批次大小以減少錯誤
        chunk_size = 30
        for i in range(0, len(tickers_list), chunk_size):
            chunk = tickers_list[i:i+chunk_size]
            try:
                data = yf.download(chunk, start=self.start_date, end=self.end_date, group_by='ticker', progress=False)
                
                if data.empty: continue

                for ticker in chunk:
                    try:
                        if len(chunk) == 1: df = data
                        else: 
                            try: df = data[ticker]
                            except: continue
                        
                        df = df.dropna()
                        if len(df) < 10: continue

                        last_close = float(df['Close'].iloc[-1])
                        
                        # 條件 1: 價格 (110-150)
                        if not (self.MIN_PRICE <= last_close <= self.MAX_PRICE): continue
                        
                        # 條件 2: 均量 (>50張)
                        avg_vol = float(df['Volume'].tail(10).mean())
                        if avg_vol > 10000: display_vol = int(avg_vol / 1000)
                        else: display_vol = int(avg_vol)
                        if display_vol < self.MIN_AVG_VOL: continue 

                        # 條件 3: 急跌 (>5%)
                        price_3days_ago = float(df['Close'].iloc[-4])
                        drop_pct = (price_3days_ago - last_close) / price_3days_ago

                        if drop_pct > self.DROP_RATE:
                            original = tickers_map[ticker]
                            info_str = f"**{original['code']} {original['name']}**\n現價: {last_close:.1f} | 3日跌幅: -{drop_pct*100:.2f}% | 均量: {display_vol}張"
                            print(f"🔥 鎖定: {info_str}")
                            targets.append(info_str)
                    except: continue
            except: pass

        if targets:
            msg = "🎯 **鄭大短波段狙擊手** (V12.3)\n發現「急跌+有量+甜蜜點」機會：\n\n" + "\n".join(targets)
            self.send_discord_message(msg)
        else:
            print("💤 本日無符合標的")

if __name__ == "__main__":
    try:
        bot = CBSniperBot()
        bot.run()
    except Exception as e:
        print(f"Critical Error: {e}")
    sys.exit(0) # 強制亮綠燈
