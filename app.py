from flask import Flask, render_template, request, redirect, url_for, jsonify, Response
import os
import cv2
import numpy as np
import base64
import json
from datetime import datetime
import time
from database import db, User, Attendance, init_db
from face_recognition_model import FaceRecognitionSystem

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///attendance.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Khởi tạo cơ sở dữ liệu
db.init_app(app)

# Khởi tạo hệ thống nhận diện khuôn mặt
face_system = FaceRecognitionSystem()

# Tạo thư mục lưu trữ nếu chưa tồn tại
os.makedirs("known_faces", exist_ok=True)
os.makedirs("attendance_records", exist_ok=True)


@app.before_first_request
def create_tables():
    init_db(app)
    # Tải các khuôn mặt đã biết từ cơ sở dữ liệu
    users = User.query.all()
    for user in users:
        if os.path.exists(user.face_image_path):
            face_system.add_known_face(user.id, user.face_image_path)


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
