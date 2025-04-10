// static/js/attendance.js
document.addEventListener("DOMContentLoaded", function () {
  // Các phần tử DOM
  const video = document.getElementById("video");
  const facePreview = document.getElementById("facePreview");
  const startCameraBtn = document.getElementById("startCamera");
  const attendanceList = document.getElementById("attendanceList");
  const dateTimeDisplay = document.getElementById("dateTimeDisplay");

  let streamRef = null;
  let faceDetectionInterval = null;
  let recognitionInterval = null;

  // Hàm cập nhật hiển thị ngày giờ
  function updateDateTime() {
    const now = new Date();
    const options = {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    };
    dateTimeDisplay.textContent = now.toLocaleDateString("vi-VN", options);
  }

  // Cập nhật thời gian mỗi giây
  updateDateTime();
  setInterval(updateDateTime, 1000);

  // Xử lý sự kiện khi nhấn nút "Bật camera"
  startCameraBtn.addEventListener("click", async function () {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      streamRef = stream;
      video.srcObject = stream;

      // Kích hoạt canvas
      facePreview.classList.remove("d-none");

      // Cập nhật giao diện nút
      startCameraBtn.textContent = "Đang nhận diện...";
      startCameraBtn.disabled = true;

      // Bắt đầu nhận diện khuôn mặt
      startFaceRecognition();
    } catch (error) {
      console.error("Lỗi khi truy cập camera:", error);
      alert("Không thể truy cập camera. Vui lòng kiểm tra quyền truy cập.");
    }
  });

  // Phát hiện và nhận diện khuôn mặt
  function startFaceRecognition() {
    // Gửi các frame video để phát hiện và nhận diện khuôn mặt
    faceDetectionInterval = setInterval(() => {
      // Cập nhật kích thước canvas nếu video đã load
      if (video.videoWidth && facePreview.width !== video.videoWidth) {
        facePreview.width = video.videoWidth;
        facePreview.height = video.videoHeight;
      }

      const context = facePreview.getContext("2d");
      context.drawImage(video, 0, 0, facePreview.width, facePreview.height);

      // Gửi frame đến server để phát hiện khuôn mặt
      const frameData = facePreview.toDataURL("image/jpeg");
      recognizeFaces(frameData);
    }, 300); // Cập nhật mỗi 300ms
  }

  // Gửi frame để nhận diện khuôn mặt
  async function recognizeFaces(frameData) {
    try {
      const response = await fetch("/api/recognize_faces", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ frame: frameData }),
      });

      const result = await response.json();

      if (result.success) {
        // Vẽ hình vuông và tên người được nhận diện
        drawFaceBoxesWithNames(result.faces);

        // Cập nhật danh sách điểm danh nếu có người được nhận diện thành công
        if (result.attendance) {
          loadAttendanceList();
        }
      }
    } catch (error) {
      console.error("Lỗi khi nhận diện khuôn mặt:", error);
    }
  }

  // Vẽ hình vuông và tên người được nhận diện
  function drawFaceBoxesWithNames(faces) {
    const context = facePreview.getContext("2d");

    // Xóa các hình vuông cũ
    context.drawImage(video, 0, 0, facePreview.width, facePreview.height);

    // Vẽ hình vuông và tên mới
    context.strokeStyle = "#00FF00"; // Màu xanh lá
    context.lineWidth = 3;
    context.fillStyle = "rgba(0, 0, 0, 0.7)"; // Nền đen mờ cho tên
    context.font = "16px Arial";

    faces.forEach((face) => {
      // Vẽ hình vuông
      context.strokeRect(face.x, face.y, face.width, face.height);

      // Vẽ nền cho tên
      const nameText = face.name || "Unknown";
      const textWidth = context.measureText(nameText).width;
      context.fillRect(face.x, face.y - 25, textWidth + 10, 25);

      // Vẽ tên người dùng
      context.fillStyle = face.name ? "#00FF00" : "#FF0000"; // Xanh cho người dùng đã biết, đỏ cho unknown
      context.fillText(nameText, face.x + 5, face.y - 8);
      context.fillStyle = "rgba(0, 0, 0, 0.7)"; // Đặt lại màu nền
    });
  }

  // Hàm tải danh sách điểm danh từ server
  async function loadAttendanceList() {
    try {
      const response = await fetch("/api/attendance");
      const attendanceData = await response.json();

      // Xóa dữ liệu cũ
      attendanceList.innerHTML = "";

      // Thêm dữ liệu mới
      if (attendanceData.length === 0) {
        attendanceList.innerHTML =
          '<tr><td colspan="3" class="text-center">Chưa có điểm danh hôm nay</td></tr>';
      } else {
        attendanceData.forEach((record) => {
          const row = document.createElement("tr");
          row.innerHTML = `
                        <td>${record.name}</td>
                        <td>${record.userId}</td>
                        <td>${record.time}</td>
                    `;
          attendanceList.appendChild(row);
        });
      }
    } catch (error) {
      console.error("Lỗi khi tải danh sách điểm danh:", error);
    }
  }

  // Tải danh sách điểm danh khi trang được tải
  loadAttendanceList();

  // Dọn dẹp khi người dùng rời trang
  window.addEventListener("beforeunload", function () {
    if (streamRef) {
      const tracks = streamRef.getTracks();
      tracks.forEach((track) => track.stop());
    }
    if (faceDetectionInterval) {
      clearInterval(faceDetectionInterval);
    }
    if (recognitionInterval) {
      clearInterval(recognitionInterval);
    }
  });
});
