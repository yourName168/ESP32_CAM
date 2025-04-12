from flask import Flask, render_template, request, redirect, url_for, jsonify, Response
import os
import cv2
import logging
import numpy as np
import base64
import json
from datetime import datetime
import time
from database import db, User, Attendance, init_db
from face_recognition_model import FaceRecognitionSystem
import requests
from io import BytesIO
import base64
from PIL import Image
from flask_cors import CORS

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///attendance.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
CORS(app) 

# Khởi tạo cơ sở dữ liệu
db.init_app(app)

# Khởi tạo hệ thống nhận diện khuôn mặt
face_system = FaceRecognitionSystem()

# Tạo thư mục lưu trữ nếu chưa tồn tại
os.makedirs("known_faces", exist_ok=True)
os.makedirs("attendance_records", exist_ok=True)


# @app.before_first_request
def create_tables():
    init_db(app)
    # Tải các khuôn mặt đã biết từ cơ sở dữ liệu
    users = User.query.all()
    for user in users:
        if os.path.exists(user.face_image_path):
            face_system.add_known_face(user.id, user.face_image_path)

            
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
ESP32_REQUEST_TIMEOUT = 10  # seconds


@app.route('/api/proxy/esp32cam/capture', methods=['GET'])
def proxy_esp32cam_capture():
    """
    Proxy endpoint for ESP32-CAM capture to handle CORS and timeouts
    """
    ip = request.args.get('ip')
    if not ip:
        return jsonify({"error": "Missing IP parameter"}), 400
    
    timestamp = request.args.get('t', '')
    
    # Log the request
    logger.info(f"Proxying request to ESP32-CAM at {ip}")
    
    try:
        # Make request to ESP32-CAM with increased timeout
        url = f"http://{ip}/capture"
        if timestamp:
            url += f"?t={timestamp}"
            
        logger.info(f"Requesting: {url}")
        
        # Use session for better connection reuse
        session = requests.Session()
        
        # Configure the request with proper headers to prevent caching
        headers = {
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
        
        # Make the request with a generous timeout
        resp = session.get(
            url, 
            headers=headers,
            timeout=ESP32_REQUEST_TIMEOUT,
            stream=True  # Use streaming to handle large responses
        )
        
        # Check if request was successful
        if not resp.ok:
            logger.error(f"ESP32-CAM returned error: {resp.status_code}")
            return jsonify({
                "error": f"ESP32-CAM returned {resp.status_code}"
            }), resp.status_code
        
        # Return the response with proper headers
        return Response(
            resp.content,
            status=resp.status_code,
            content_type=resp.headers.get('Content-Type', 'image/jpeg'),
            headers={
                'Access-Control-Allow-Origin': '*',  # Enable CORS
                'Cache-Control': 'no-store'  # Prevent caching
            }
        )
        
    except requests.Timeout:
        logger.error(f"Request to ESP32-CAM timed out after {ESP32_REQUEST_TIMEOUT}s")
        return jsonify({"error": "Connection to ESP32-CAM timed out"}), 504
        
    except requests.ConnectionError:
        logger.error(f"Failed to connect to ESP32-CAM at {ip}")
        return jsonify({"error": "Failed to connect to ESP32-CAM"}), 502
        
    except Exception as e:
        logger.error(f"Unexpected error proxying to ESP32-CAM: {str(e)}")
        return jsonify({"error": str(e)}), 500

# @app.route('/api/proxy/esp32cam/<path:endpoint>', methods=['GET'])
# def esp32_proxy(endpoint):
#     """
#     Proxy endpoint to forward requests to ESP32-CAM
#     """
#     camera_ip = request.args.get('ip')
#     logging.debug(f"Received proxy request for endpoint: {endpoint}, IP: {camera_ip}")
    
#     if not camera_ip:
#         logging.error("Camera IP not provided in request")
#         return jsonify({"error": "Camera IP not provided"}), 400
    
#     timestamp = int(time.time() * 1000)
#     url = f"http://{camera_ip}/{endpoint}?t={timestamp}"
#     print(f"Forwarding request to: {url}")
    
#     try:
#         # Create a session with specific timeouts
#         session = requests.Session()
#         # Set longer timeout values: connect timeout 10 sec, read timeout 15 sec
#         response = session.get(url, timeout=(10, 15), stream=True)
        
#         logging.info(f"Received response from ESP32-CAM: {response.status_code}")
        
#         # Stream the response back to client to avoid memory issues with large images
#         def generate():
#             for chunk in response.iter_content(chunk_size=8192):
#                 yield chunk
#         headers = dict(response.headers)
#         # Add CORS headers
#         headers['Access-Control-Allow-Origin'] = '*'
#         headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
#         headers['Access-Control-Allow-Headers'] = 'Content-Type'

#         # Return a streaming response
#         return Response(
#             generate(),
#             status=response.status_code,
#             headers=headers,
#             content_type=response.headers.get('content-type', 'image/jpeg')
#         )
#     except requests.exceptions.ConnectTimeout:
#         logging.error(f"Connection timeout to ESP32-CAM: {camera_ip}")
#         return jsonify({"error": "Unable to connect to ESP32-CAM - connection timeout"}), 504
#     except requests.exceptions.ReadTimeout:
#         logging.error(f"Read timeout from ESP32-CAM: {camera_ip}")
#         return jsonify({"error": "Timeout while reading response from ESP32-CAM"}), 504
#     except requests.RequestException as e:
#         logging.error(f"Request to ESP32-CAM failed: {e}")
#         return jsonify({"error": str(e)}), 500

# Route cho trang chủ
@app.route("/")
def index():
    return render_template("index.html")


# Route cho trang đăng ký người dùng
@app.route("/register")
def register():
    return render_template("register.html")

# Route cho trang điểm danh
@app.route("/attendance")
def attendance():
    return render_template("attendance.html")


# API xử lý điểm danh
@app.route("/api/recognize", methods=["POST"])
def api_recognize():
    data = request.get_json()
    face_image_base64 = data.get("faceImage").split(",")[1]

    # Chuyển ảnh base64 thành mảng numpy
    img_bytes = base64.b64decode(face_image_base64)
    img_np = np.frombuffer(img_bytes, np.uint8)
    frame = cv2.imdecode(img_np, cv2.IMREAD_COLOR)

    # Nhận diện khuôn mặt
    user_id = face_system.recognize_face(frame)

    if user_id:
        # Tìm thông tin người dùng
        user = User.query.get(user_id)

        # Kiểm tra xem đã điểm danh hôm nay chưa
        today = datetime.now().date()
        existing_attendance = Attendance.query.filter_by(
            user_id=user.id, date=today
        ).first()

        if not existing_attendance:
            # Tạo bản ghi điểm danh mới
            new_attendance = Attendance(
                user_id=user.id, date=today, time=datetime.now().time()
            )
            db.session.add(new_attendance)
            db.session.commit()

            return jsonify(
                {
                    "success": True,
                    "message": f"Điểm danh thành công cho {user.name}",
                    "user": {"id": user.user_id, "name": user.name},
                }
            )
        else:
            return jsonify(
                {
                    "success": True,
                    "message": f"{user.name} đã điểm danh rồi hôm nay",
                    "user": {"id": user.user_id, "name": user.name},
                }
            )
    else:
        return jsonify(
            {
                "success": False,
                "message": "Không nhận diện được khuôn mặt. Vui lòng thử lại.",
            }
        )


# API để lấy danh sách người dùng
@app.route("/api/users")
def api_users():
    users = User.query.all()
    users_list = [
        {
            "id": user.id,
            "userId": user.user_id,
            "name": user.name,
            "imagePath": user.face_image_path,
        }
        for user in users
    ]
    return jsonify(users_list)


# API để lấy danh sách điểm danh
@app.route("/api/attendance")
def api_attendance():
    date_str = request.args.get("date")
    if date_str:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        date = datetime.now().date()

    attendance_records = Attendance.query.filter_by(date=date).all()

    records = []
    for record in attendance_records:
        user = User.query.get(record.user_id)
        records.append(
            {
                "id": record.id,
                "userId": user.user_id,
                "name": user.name,
                "time": record.time.strftime("%H:%M:%S"),
            }
        )

    return jsonify(records)


# Route cho trang báo cáo
@app.route("/reports")
def reports():
    return render_template("reports.html")


# API để xuất báo cáo Excel
@app.route("/api/export")
def export_report():
    from openpyxl import Workbook
    from io import BytesIO

    date_str = request.args.get("date")
    if date_str:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        date = datetime.now().date()

    # Tạo workbook mới
    wb = Workbook()
    ws = wb.active
    ws.title = f"Điểm danh {date.strftime('%d-%m-%Y')}"

    # Thêm tiêu đề
    ws.append(["STT", "Họ tên", "ID", "Thời gian điểm danh", "Trạng thái"])

    # Lấy dữ liệu điểm danh
    attendance_records = Attendance.query.filter_by(date=date).all()

    # Thêm dữ liệu
    for i, record in enumerate(attendance_records, 1):
        user = User.query.get(record.user_id)
        time_str = record.time.strftime("%H:%M:%S")

        # Xác định trạng thái
        hours = record.time.hour
        if hours < 8:
            status = "Đúng giờ"
        elif hours < 9:
            status = "Trễ"
        else:
            status = "Muộn"

        ws.append([i, user.name, user.user_id, time_str, status])

    # Lưu tệp
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    # Tạo response
    from flask import send_file

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"attendance_report_{date.strftime('%Y-%m-%d')}.xlsx",
    )


# Route để hiển thị video từ webcam với nhận diện khuôn mặt
def gen_frames():
    camera = cv2.VideoCapture(0)

    while True:
        success, frame = camera.read()
        if not success:
            break

        # Nhận diện khuôn mặt trong frame
        frame = face_system.detect_and_draw_faces(frame)

        # Chuyển frame thành JPEG
        ret, buffer = cv2.imencode(".jpg", frame)
        frame_bytes = buffer.tobytes()

        yield (
            b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )

        time.sleep(0.03)  # Giới hạn FPS


@app.route("/video_feed")
def video_feed():
    return Response(gen_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/detect_faces", methods=["POST"])
def api_detect_faces():
    data = request.get_json()
    frame_base64 = data.get("frame").split(",")[1]

    # Chuyển ảnh base64 thành mảng numpy
    img_bytes = base64.b64decode(frame_base64)
    img_np = np.frombuffer(img_bytes, np.uint8)
    frame = cv2.imdecode(img_np, cv2.IMREAD_COLOR)

    # Phát hiện khuôn mặt
    faces = face_system.detect_faces(frame)

    return jsonify({"success": True, "faces": faces})


# API để đăng ký nhiều ảnh khuôn mặt
@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json()

    # Lấy thông tin người dùng
    name = data.get("name")
    user_id = data.get("userId")
    face_images = data.get("faceImages", [])

    if not face_images:
        return jsonify(
            {"success": False, "message": "Không có ảnh khuôn mặt được gửi lên"}
        )

    # Kiểm tra xem ID đã tồn tại chưa
    existing_user = User.query.filter_by(user_id=user_id).first()
    if existing_user:
        return jsonify({"success": False, "message": "ID này đã được đăng ký"})

    # Tạo thư mục lưu trữ ảnh người dùng
    user_folder = f"known_faces/{user_id}"
    os.makedirs(user_folder, exist_ok=True)

    # Lưu các ảnh khuôn mặt
    saved_images = []
    for i, face_image_base64 in enumerate(face_images):
        if "," in face_image_base64:
            face_image_base64 = face_image_base64.split(",")[1]

        face_image_path = f"{user_folder}/face_{i}.jpg"
        with open(face_image_path, "wb") as f:
            f.write(base64.b64decode(face_image_base64))
        saved_images.append(face_image_path)

    # Lưu ảnh chính (ảnh cuối cùng)
    main_face_path = f"{user_folder}/main.jpg"
    with open(main_face_path, "wb") as f:
        f.write(
            base64.b64decode(
                face_images[-1].split(",")[1]
                if "," in face_images[-1]
                else face_images[-1]
            )
        )

    # Tạo người dùng mới
    new_user = User(name=name, user_id=user_id, face_image_path=main_face_path)
    db.session.add(new_user)
    db.session.commit()

    # Thêm khuôn mặt vào hệ thống nhận diện
    for image_path in saved_images:
        face_system.add_known_face(new_user.id, image_path)

    return jsonify(
        {
            "success": True,
            "message": f"Đăng ký thành công với {len(saved_images)} ảnh khuôn mặt",
        }
    )


# API để nhận diện khuôn mặt (cho trang điểm danh)
@app.route("/api/recognize_faces", methods=["POST"])
def api_recognize_faces():
    data = request.get_json()
    frame_base64 = data.get("frame").split(",")[1]

    # Chuyển ảnh base64 thành mảng numpy
    img_bytes = base64.b64decode(frame_base64)
    img_np = np.frombuffer(img_bytes, np.uint8)
    frame = cv2.imdecode(img_np, cv2.IMREAD_COLOR)

    # Nhận diện khuôn mặt
    recognized_faces = face_system.recognize_faces(frame)
    attendance_created = False

    logger.info(f"Recognized faces: {recognized_faces}")
    # Tạo bản ghi điểm danh cho những khuôn mặt đã nhận diện được
    today = datetime.now().date()

    for face in recognized_faces:
        if face.get("user_id"):  # Chỉ xử lý những khuôn mặt đã nhận diện thành công
            user = User.query.get(face["user_id"])
            if user:
                # Kiểm tra xem đã điểm danh hôm nay chưa
                existing_attendance = Attendance.query.filter_by(
                    user_id=user.id, date=today
                ).first()

                # Nếu chưa điểm danh, tạo bản ghi mới
                if not existing_attendance:
                    new_attendance = Attendance(
                        user_id=user.id, date=today, time=datetime.now().time()
                    )
                    db.session.add(new_attendance)
                    db.session.commit()
                    attendance_created = True

                # Thêm tên người dùng vào kết quả
                face["name"] = user.name

    return jsonify(
        {"success": True, "faces": recognized_faces, "attendance": attendance_created}
    )
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
