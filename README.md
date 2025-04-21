# Face Recognition Attendance System with ESP32

## Project Overview

This is a face recognition-based attendance system that uses a web interface to register users, take attendance, and generate reports. The system uses OpenCV for face detection and recognition and is designed to work with ESP32-based cameras.

## Features

- **User Registration**: Register new users with multiple face images for better recognition
- **Real-time Face Detection**: Detect faces in real-time using webcam or ESP32 camera
- **Attendance Tracking**: Automatically record attendance with date and time
- **Reporting**: Generate and export attendance reports in Excel format
- **Web Interface**: User-friendly web interface for all operations

## System Requirements

- Python 3.6 or higher
- Flask web server
- OpenCV for face detection and recognition
- SQLite database for storage
- Web browser with JavaScript enabled
- ESP32-Cam module (for hardware implementation)

## Installation

1. Clone the repository:
```
git clone https://github.com/yourusername/Face_Recognize_ESP32.git
cd Face_Recognize_ESP32
```

2. Install the required Python packages:
```
pip install -r requirements.txt
```

3. Create required folders if they don't exist:
```
mkdir -p known_faces attendance_records
```

## Running the Application

Start the Flask web server:

```
python app.py
```

Open your web browser and navigate to:
```
http://localhost:5000
```

For accessing from other devices on the same network, use the server's IP address:
```
http://[your-server-ip]:5000
```

## Usage Guide

### Registration

1. Navigate to the "Register" page
2. Enter the user's name and ID
3. Capture multiple face images from different angles for better recognition
4. Submit the registration

### Taking Attendance

1. Navigate to the "Attendance" page
2. The system will automatically detect and recognize faces
3. Recognized users will be marked present in the database
4. The system prevents duplicate attendance entries on the same day

### Viewing Reports

1. Navigate to the "Reports" page
2. Select a date to view attendance records
3. Export the report in Excel format if needed

## Project Structure

- `app.py`: The main Flask application
- `database.py`: Database models and configuration
- `face_recognition_model.py`: Face detection and recognition logic
- `templates/`: HTML templates for web pages
- `static/`: Static files (CSS, JavaScript, images)
- `known_faces/`: Directory for storing registered faces
- `attendance_records/`: Directory for storing attendance reports

## Database Schema

- **User**: Stores registered users with their name, ID, and face image path
- **Attendance**: Records attendance data with user ID, date, and time

## API Endpoints

- `/api/register`: Register a new user with face images
- `/api/recognize`: Recognize a face and mark attendance
- `/api/recognize_faces`: Recognize multiple faces
- `/api/users`: Get a list of registered users
- `/api/attendance`: Get attendance records for a specific date
- `/api/export`: Export attendance data to Excel

## Hardware Setup (ESP32-Cam)

To connect an ESP32-Cam module:

1. Flash the ESP32 with compatible camera firmware
2. Configure the ESP32 to connect to your WiFi network
3. Update the camera URL in the JavaScript files if needed

## Troubleshooting

- **Recognition Issues**: Try registering the user with more face images from different angles
- **Camera Not Working**: Check browser permissions and camera connections
- **Database Errors**: Ensure the instance folder has write permissions

## License

[Include your license information here]

## Contributors

[List contributors here]

## Contact

[Your contact information]

---

Created by [Your Name/Organization]