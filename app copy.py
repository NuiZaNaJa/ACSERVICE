from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler


app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

DB_FILE = 'database.json'

# --- การตั้งค่า Email (แก้ไขตรงนี้) ---
SENDER_EMAIL = "wattayutacservice@gmail.com"  # อีเมลของร้าน
SENDER_PASSWORD = "wqno oymv qwlu jhas" # รหัสผ่านแอป (App Password 16 หลักจาก Google)

def send_mail(receiver_email, subject, body):
    if not receiver_email: return
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = receiver_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"Email sent to {receiver_email}")
    except Exception as e:
        print(f"Error sending email: {e}")

# --- ระบบตรวจสอบคิวล่วงหน้า 1 วัน (Cron Job) ---
def check_and_notify_bookings():
    print("Checking for tomorrow's bookings...")
    db = load_db()
    # วันพรุ่งนี้
    tomorrow_str = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    for b in db['bookings']:
        if b['date'] == tomorrow_str and b['status'] != 'cancelled':
            # ส่งหาลูกค้า
            if b.get('customerEmail'):
                subject = f"แจ้งเตือน: นัดหมายล้างแอร์ในวันพรุ่งนี้ ({b['date']})"
                body = f"สวัสดีคุณ {b['customerName']}\n\nนี่คือการแจ้งเตือนนัดหมายล้างแอร์ในวันพรุ่งนี้\nเวลา: {b['time']}\nประเภทบริการ: {b['serviceType']}\n\nขอบคุณครับ"
                send_mail(b['customerEmail'], subject, body)
            
            # ส่งหา Admin
            admin_mail = db['config'].get('admin_email')
            if admin_mail:
                send_mail(admin_mail, "แจ้งเตือนงานวันพรุ่งนี้", f"พรุ่งนี้มีงานคุณ {b['customerName']} เวลา {b['time']}")

# ตั้งเวลาให้ทำงานทุกวันเวลา 08:00 น.
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_and_notify_bookings, trigger="cron", hour=8, minute=0)
scheduler.start()

# --- Database Logic ---
def load_db():
    if not os.path.exists(DB_FILE) or os.stat(DB_FILE).st_size == 0:
        default_data = {
            "config": {"promptpay_no": "0812345678", "admin_email": ""},
            "users": [
                {"id": 1, "name": "Admin User", "role": "admin", "username": "admin", "password": "1234", "phone": "0000000000", "email": ""}
            ],
            "bookings": []
        }
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_data, f, ensure_ascii=False, indent=4)
        return default_data
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- Configuration Routes ---
@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    db = load_db()
    if request.method == 'POST':
        db['config']['promptpay_no'] = request.json.get('promptpay_no')
        db['config']['admin_email'] = request.json.get('admin_email') # เพิ่มใหม่
        save_db(db)
        return jsonify({"status": "success"})
    return jsonify(db['config'])

# --- Auth Routes ---
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    db = load_db()
    user = next((u for u in db['users'] if u['username'] == data['username'] and u['password'] == data['password']), None)
    if user:
        return jsonify({"status": "success", "user": user})
    return jsonify({"status": "fail", "message": "Invalid credentials"}), 401

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    db = load_db()
    if any(u['username'] == data['username'] for u in db['users']):
        return jsonify({"status": "fail", "message": "Username exists"}), 400
    new_user = {
        "id": int(datetime.now().timestamp() * 1000),
        "name": data['name'],
        "phone": data['phone'],
        "email": data.get('email', ''), # เพิ่มรองรับ email
        "username": data['username'],
        "password": data['password'],
        "role": "member"
    }
    db['users'].append(new_user)
    save_db(db)
    return jsonify({"status": "success"})

# --- Member Management Routes ---
@app.route('/api/users', methods=['GET'])
def get_users():
    db = load_db()
    return jsonify(db['users'])

@app.route('/api/users/<int:uid>', methods=['PUT', 'DELETE'])
def manage_user(uid):
    db = load_db()
    if request.method == 'DELETE':
        db['users'] = [u for u in db['users'] if u['id'] != uid]
        save_db(db)
        return jsonify({"status": "success"})
    if request.method == 'PUT':
        data = request.json
        for u in db['users']:
            if u['id'] == uid:
                u.update(data)
                break
        save_db(db)
        return jsonify({"status": "success"})

# --- Booking Routes ---
# --- แก้ไขส่วน Booking Routes ในไฟล์ Python ---
@app.route('/api/bookings', methods=['GET', 'POST'])
def handle_bookings():
    db = load_db()
    if request.method == 'POST':
        try:
            data = request.json
            if not data:
                return jsonify({"status": "fail", "message": "No data received"}), 400
            
            # ลอง print เช็กดูใน Terminal ว่าข้อมูลมาไหม
            print(f"รับข้อมูลการจองจาก: {data.get('customerName')}")

            new_booking = {
                "id": int(datetime.now().timestamp() * 1000),
                **data,
                "status": "pending"
            }
            
            db['bookings'].append(new_booking)
            save_db(db)
            print("บันทึกลง database.json สำเร็จ")
            return jsonify({"status": "success"})
        except Exception as e:
            print(f"เกิดข้อผิดพลาด: {e}")
            return jsonify({"status": "fail", "message": str(e)}), 500
            
    return jsonify(db['bookings'])

@app.route('/api/bookings/<int:bid>/<string:action>', methods=['POST'])
def update_booking_status(bid, action):
    db = load_db()
    status_map = {"confirm": "completed", "cancel": "cancelled"}
    for b in db['bookings']:
        if b['id'] == bid:
            b['status'] = status_map.get(action, b['status'])
            break
    save_db(db)
    return jsonify({"status": "success"})

@app.route('/api/bookings/<int:bid>', methods=['DELETE'])
def delete_booking(bid):
    db = load_db()
    db['bookings'] = [b for b in db['bookings'] if b['id'] != bid]
    save_db(db)
    return jsonify({"status": "success"})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    db = load_db()
    revenue = sum(b['price'] for b in db['bookings'] if b['status'] == 'completed')
    return jsonify({"user_count": len(db['users']), "booking_count": len(db['bookings']), "revenue": revenue})
# เพิ่มลงในไฟล์ Python Backend ของคุณ
@app.route('/api/test-email', methods=['POST'])
def test_email():
    data = request.json
    target_email = data.get('email')
    
    if not target_email:
        return jsonify({"error": "No email provided"}), 400
        
    try:
        import smtplib
        from email.mime.text import MIMEText
        
        # ใช้ค่า SMTP เดียวกับที่คุณตั้งไว้ในระบบแจ้งเตือน
        msg = MIMEText(f"นี่คืออีเมลทดสอบจากระบบ Air Service\nส่งเมื่อ: {datetime.now().strftime('%H:%M:%S')}")
        msg['Subject'] = "Test Email - Air Service System"
        msg['From'] = SENDER_EMAIL
        msg['To'] = target_email
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, target_email, msg.as_string())
            
        return jsonify({"message": "Test email sent successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # สำหรับทดสอบระบบส่งเมลทันทีตอนรันโปรแกรม (เปิดบรรทัดล่างเพื่อทดสอบ)
    # check_and_notify_bookings()
    app.run(debug=True, host='0.0.0.0', port=5000)
