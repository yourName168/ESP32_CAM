// static/js/attendance.js
document.addEventListener("DOMContentLoaded", function () {
  // Các phần tử DOM
  const cameraStream = document.getElementById("cameraStream");
  const facePreview = document.getElementById("facePreview");
  const startCameraBtn = document.getElementById("startCamera");
  const attendanceList = document.getElementById("attendanceList");
  const dateTimeDisplay = document.getElementById("dateTimeDisplay");
  const cameraIpInput = document.getElementById("cameraIp");
  const connectCameraBtn = document.getElementById("connectCamera");

  let cameraIp = "";
  let streamActive = false;
  let faceDetectionInterval = null;
  let frameCapturingInterval = null;
  loadCameraIpFromLocalStorage();

  // Hàm cập nhật hiển thị ngày giờ
  function updateDateTime() {
    const now = new Date();
    const options = {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
      // hour: "2-digit",
      // minute: "2-digit",
      // second: "2-digit",
    };
    dateTimeDisplay.textContent = now.toLocaleDateString("vi-VN", options);
  }

  // Cập nhật thời gian mỗi giây
  // updateDateTime();
  // setInterval(updateDateTime, 1000);

  // Xử lý sự kiện khi nhấn nút kết nối camera
  connectCameraBtn.addEventListener("click", function() {
    cameraIp = cameraIpInput.value.trim();
    
    if (!cameraIp) {
      alert("Vui lòng nhập địa chỉ IP của ESP32-CAM");
      return;
    }

    // Kiểm tra xem IP có đúng định dạng không
    const ipPattern = /^(\d{1,3}\.){3}\d{1,3}$/;
    if (!ipPattern.test(cameraIp)) {
      alert("Địa chỉ IP không hợp lệ. Vui lòng kiểm tra lại.");
      return;
    }
    connectToCameraViaProxy();
  });

  // Kết nối đến camera ESP32-CAM
  function connectToCamera() {
    // Hiển thị stream camera từ ESP32-CAM
    cameraStream.src = `http://${cameraIp}/`;
    cameraStream.style.display = "block";
    
    // Thử tải hình ảnh để kiểm tra kết nối
    cameraStream.onload = function() {
      streamActive = true;
      startCameraBtn.disabled = false;
      connectCameraBtn.textContent = "Đã kết nối";
      connectCameraBtn.classList.remove("btn-outline-primary");
      connectCameraBtn.classList.add("btn-success");
      alert("Đã kết nối thành công đến ESP32-CAM!");
    };
    
    cameraStream.onerror = function() {
      streamActive = false;
      startCameraBtn.disabled = true;
      alert("Không thể kết nối đến ESP32-CAM. Vui lòng kiểm tra địa chỉ IP và thử lại.");
      cameraStream.style.display = "none";
    };
  }

  function connectToCameraViaProxy() {
    // Test the connection first using a fetch call to the proxy endpoint
    const timestamp = new Date().getTime();
    const proxyUrl = `/api/proxy/esp32cam/capture?ip=${encodeURIComponent(cameraIp)}&t=${timestamp}`;
    
    // Use a timeout to avoid hanging if the server is not responding
    const timeoutPromise = new Promise((_, reject) => 
      setTimeout(() => reject(new Error('Connection timed out')), 5000)
    );
    
    Promise.race([
      fetch(proxyUrl, { 
        method: 'GET',
        cache: 'no-store'
      }),
      timeoutPromise
    ])
    .then(response => {
      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      return response.blob();
    })
    .then(blob => {
      if (blob.size < 100) {
        throw new Error("Invalid image received - too small");
      }
      
      // Connection successful, proceed with setup
      setupCameraStream();
    })
    .catch(error => {
      connectionAttempts++;
      console.error(`Connection attempt ${connectionAttempts} failed:`, error);
      
      if (connectionAttempts < MAX_CONNECTION_ATTEMPTS) {
        // Retry after a short delay
        setTimeout(connectToCameraViaProxy, 1000);
        
        photoStatus.textContent = `Đang thử kết nối lần ${connectionAttempts + 1}/${MAX_CONNECTION_ATTEMPTS}...`;
      } else {
        // All attempts failed, update UI
        connectCameraBtn.disabled = false;
        connectCameraBtn.textContent = "Kết nối";
        
        photoStatus.textContent = `Không thể kết nối đến ESP32-CAM: ${error.message}. Vui lòng kiểm tra địa chỉ IP.`;
        photoStatus.classList.remove("alert-info");
        photoStatus.classList.add("alert-danger");
        
        // Offer direct connection as a fallback
        showDirectConnectionFallback();
      }
    });
  }

  function setupCameraStream() {
    // Set up a placeholder image first
    const placeholderImg = document.createElement('img');
    placeholderImg.src = "/static/images/camera-placeholder.png";
    if (!placeholderImg.src.includes('camera-placeholder.png')) {
      placeholderImg.src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='480' height='360' viewBox='0 0 480 360'%3E%3Crect width='480' height='360' fill='%23f0f0f0'/%3E%3Ctext x='240' y='180' text-anchor='middle' fill='%23999999' font-family='Arial' font-size='18'%3ECamera Stream Loading...%3C/text%3E%3C/svg%3E";
    }
    
    // Create an image element for ESP32-CAM stream
    cameraStream.style.display = "none";
    startCameraBtn.disabled = false;

    streamActive = true;
    connectCameraBtn.disabled = false;
    connectCameraBtn.textContent = "Đã kết nối";
    connectCameraBtn.classList.remove("btn-outline-primary");
    connectCameraBtn.classList.add("btn-success");
    
    facePreview.classList.remove("d-none");
    facePreview.width = cameraStream.width || 480;
    facePreview.height = cameraStream.height || 360;
    
    startFaceRecognition();
    
    saveCameraIpToLocalStorage();
  }

  function saveCameraIpToLocalStorage() {
    if (cameraIp) {
      localStorage.setItem('esp32CamIp', cameraIp);
    }
  }

  function loadCameraIpFromLocalStorage() {
    const savedIp = localStorage.getItem('esp32CamIp');
    if (savedIp) {
      cameraIpInput.value = savedIp;
    }
  }

  // Xử lý sự kiện khi nhấn nút "Bắt đầu nhận diện"
  startCameraBtn.addEventListener("click", function () {
    if (!streamActive) {
      alert("Vui lòng kết nối ESP32-CAM trước khi bắt đầu nhận diện");
      return;
    }

    // Kích hoạt canvas
    facePreview.classList.remove("d-none");

    // Cập nhật giao diện nút
    startCameraBtn.textContent = "Đang nhận diện...";
    startCameraBtn.disabled = true;

    // Bắt đầu nhận diện khuôn mặt
    startFaceRecognition();
  });

  // Phát hiện và nhận diện khuôn mặt
  function startFaceRecognition() {
    // Gửi các frame video để phát hiện và nhận diện khuôn mặt
    frameCapturingInterval = setInterval(() => {
      // Cập nhật frame từ ESP32-CAM
      captureFrameFromESP32();
    }, 500); // Cập nhật mỗi 500ms
  }

  // Chụp frame từ ESP32-CAM
  async function captureFrameFromESP32() {
    try {
      // Sử dụng endpoint /capture của ESP32-CAM để lấy một frame
      
      const timestamp = new Date().getTime();
      const proxyUrl = `/api/proxy/esp32cam/capture?ip=${encodeURIComponent(cameraIp)}&t=${timestamp}`;
      
      const response = await fetch(proxyUrl, {
        cache: 'no-store',
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0'
        }
      });

      console.log(response);
      
      const blob = await response.blob();
      console.log("Đã nhận frame từ ESP32-CAM:", blob);

      const reader = new FileReader();
      reader.onloadend = function() {
        const frameData = reader.result;
        
        drawFrameToCanvas(frameData);
        
        recognizeFaces(frameData);
      };
      reader.readAsDataURL(blob);
    } catch (error) {
      console.error("Lỗi khi chụp frame từ ESP32-CAM:", error);
    }
  }
  
  // Vẽ frame lên canvas
  function drawFrameToCanvas(frameData) {
    const img = new Image();
    img.onload = function() {
      // Điều chỉnh kích thước canvas theo kích thước thực của hình ảnh
      if (facePreview.width !== img.width || facePreview.height !== img.height) {
        facePreview.width = img.width;
        facePreview.height = img.height;
      }
      
      const context = facePreview.getContext("2d");
      context.drawImage(img, 0, 0, facePreview.width, facePreview.height);
    };
    img.src = frameData;
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
        drawFaceBoxesWithNames(result.faces, frameData);

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
  function drawFaceBoxesWithNames(faces, frameData) {
    const img = new Image();
    img.onload = function() {
      const context = facePreview.getContext("2d");
      
      // Clear canvas and draw new frame
      context.drawImage(img, 0, 0, facePreview.width, facePreview.height);

      // Draw face boxes and names
      faces.forEach((face) => {
        // Draw face rectangle
        context.strokeStyle = face.name ? "#00FF00" : "#FF0000"; // Green for known, red for unknown
        context.lineWidth = 3;
        context.strokeRect(face.x, face.y, face.width, face.height);

        // Draw background for name
        const nameText = face.name || "Unknown";
        const confidence = face.confidence ? ` (${Math.round(face.confidence * 100)}%)` : '';
        const displayText = nameText + confidence;
        
        const textMetrics = context.measureText(displayText);
        const textWidth = textMetrics.width;
        const textHeight = 25;
        
        context.fillStyle = "rgba(0, 0, 0, 0.7)";
        context.fillRect(face.x, face.y - textHeight, textWidth + 10, textHeight);

        // Draw name text
        context.fillStyle = face.name ? "#00FF00" : "#FF0000";
        context.font = "16px Arial";
        context.fillText(displayText, face.x + 5, face.y - 8);
      });
    };
    
    // Use the captured frame data
    img.src = frameData;
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
    if (frameCapturingInterval) {
      clearInterval(frameCapturingInterval);
    }
    if (faceDetectionInterval) {
      clearInterval(faceDetectionInterval);
    }
  });
});