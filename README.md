# Music Bot Dashboard

เว็บแดชบอร์ดสำหรับควบคุม Discord Music Bot

## 📁 โครงสร้างไฟล์

```
Bot Music/
├── bot.py              # บอท Discord + API Server
├── .env                # ตัวแปรสภาพแวดล้อม
├── requirements.txt    # Dependencies
├── ecosystem.config.js # PM2 Config
└── web/
    └── index.html      # Web Dashboard (deploy ไป Netlify)
```

## 🚀 การติดตั้งบน VPS

### 1. Clone และติดตั้ง Dependencies

```bash
git clone <your-repo>
cd "Bot Music"
pip install -r requirements.txt
```

### 2. ตั้งค่า .env

```env
DISCORD_TOKEN=your_token_here
API_PORT=5000
DEFAULT_GUILD_ID=your_server_id
```

### 3. รันด้วย PM2

```bash
# ติดตั้ง PM2 (ถ้ายังไม่มี)
npm install -g pm2

# สร้างโฟลเดอร์ logs
mkdir logs

# รันบอท
pm2 start ecosystem.config.js

# ดู logs
pm2 logs music-bot

# รีสตาร์ท
pm2 restart music-bot

# หยุด
pm2 stop music-bot

# เปิดเมื่อเครื่องเริ่ม
pm2 startup
pm2 save
```

## 🌐 Deploy Web ไป Netlify

### 1. สร้าง Repository ใหม่สำหรับ Web

สร้าง repo ใหม่และคัดลอกโฟลเดอร์ `web/` ไป

### 2. Deploy ไป Netlify

1. ไปที่ [netlify.com](https://netlify.com)
2. เชื่อมต่อกับ GitHub repo
3. ตั้งค่า:
   - Build command: (ว่าง)
   - Publish directory: `/`
4. Deploy!

### 3. ตั้งค่า API URL บนเว็บ

เมื่อเปิดเว็บ ใส่ URL ของ VPS:

```
http://YOUR_VPS_IP:5000
```

## 🔥 Firewall

เปิด port 5000 บน VPS:

```bash
# Ubuntu/Debian
sudo ufw allow 5000

# CentOS
sudo firewall-cmd --add-port=5000/tcp --permanent
sudo firewall-cmd --reload
```

## 📡 API Endpoints

| Endpoint       | Method | คำอธิบาย                                     |
| -------------- | ------ | -------------------------------------------- |
| `/api/status`  | GET    | สถานะบอท                                     |
| `/api/command` | POST   | ส่งคำสั่ง (pause, resume, skip, stop, leave) |
| `/api/play`    | POST   | เพิ่มเพลง                                    |
| `/api/volume`  | POST   | ปรับเสียง                                    |
| `/api/247`     | POST   | เปิด/ปิดโหมด 24/7                            |
| `/api/remove`  | POST   | ลบเพลงจากคิว                                 |
| `/api/clear`   | POST   | ล้างคิว                                      |

## 🎵 คำสั่งบอท

| คำสั่ง         | คำอธิบาย     |
| -------------- | ------------ |
| `!play <เพลง>` | เล่นเพลง     |
| `!pause`       | หยุดชั่วคราว |
| `!resume`      | เล่นต่อ      |
| `!skip`        | ข้ามเพลง     |
| `!stop`        | หยุดเล่น     |
| `!queue`       | ดูคิว        |
| `!247`         | โหมด 24/7    |
| `!leave`       | ออกจากห้อง   |
