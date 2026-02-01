# วิธีรันบน Windows VPS

## 📥 ขั้นตอนการติดตั้ง

### 1. ติดตั้ง Python

1. ดาวน์โหลด Python จาก https://python.org
2. ติดตั้งและ **ติ๊ก "Add Python to PATH"**

### 2. ติดตั้ง FFmpeg

1. ดาวน์โหลดจาก https://ffmpeg.org/download.html
2. แตกไฟล์ไปที่ `C:\ffmpeg`
3. เพิ่ม `C:\ffmpeg\bin` ลงใน System PATH

### 3. Clone Repository

```cmd
git clone https://github.com/onochiyama/BOT-MUSIC.git
cd BOT-MUSIC
```

### 4. สร้างไฟล์ .env

```cmd
copy .env.example .env
notepad .env
```

แก้ไขใส่ Token และค่าต่างๆ

### 5. ติดตั้ง Dependencies

```cmd
pip install -r requirements.txt
```

---

## 🚀 วิธีรันบอท

### วิธีที่ 1: ใช้ Batch File (ง่าย)

ดับเบิลคลิกที่ `start_bot.bat`

### วิธีที่ 2: ใช้ Task Scheduler (รัน 24/7)

1. เปิด **Task Scheduler** (ค้นหาใน Start Menu)
2. คลิก **Create Basic Task**
3. ตั้งชื่อ: `Music Bot`
4. Trigger: **When the computer starts**
5. Action: **Start a program**
6. Program: `C:\Path\To\BOT-MUSIC\start_bot.bat`
7. ติ๊ก **Run whether user is logged on or not**
8. คลิก Finish

### วิธีที่ 3: ใช้ NSSM (แนะนำ - รันเป็น Service)

1. ดาวน์โหลด NSSM จาก https://nssm.cc/download
2. แตกไฟล์และเปิด CMD ในโฟลเดอร์นั้น
3. รันคำสั่ง:

```cmd
nssm install MusicBot
```

4. ในหน้าต่างที่เปิดขึ้น:
   - Path: `C:\Python\python.exe` (path ของ Python)
   - Startup directory: `C:\Path\To\BOT-MUSIC`
   - Arguments: `bot.py`
5. คลิก **Install service**
6. เริ่ม service:

```cmd
nssm start MusicBot
```

---

## 🔥 เปิด Firewall Port 5000

1. เปิด **Windows Firewall with Advanced Security**
2. คลิก **Inbound Rules** → **New Rule**
3. เลือก **Port** → Next
4. **TCP**, Specific ports: `5000`
5. **Allow the connection**
6. ติ๊กทุกอัน (Domain, Private, Public)
7. ตั้งชื่อ: `Music Bot API`

---

## 📡 ตั้งค่า Web Dashboard

เมื่อบอทรันแล้ว ไปที่เว็บ Netlify และใส่:

```
http://YOUR_VPS_IP:5000
```

---

## 🔧 คำสั่งที่มีประโยชน์

```cmd
# ดู IP ของ VPS
ipconfig

# ทดสอบ API
curl http://localhost:5000/api/status

# ดู Python version
python --version
```
