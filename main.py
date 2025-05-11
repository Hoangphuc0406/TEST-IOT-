from flask import Flask, request, render_template, jsonify
from datetime import datetime
import os
import cv2
import numpy as np
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0


# Middleware để ngừng lưu trữ cache
@app.after_request
def add_no_cache(response):
    response.cache_control.no_store = True
    response.cache_control.no_cache = True
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return respons


UPLOAD_FOLDER = 'static'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize Firebase
cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

mode = "auto"
latest_result = {"status": "WAITING", "timestamp": "", "image": ""}


def detect_defect(img_path):
    img = cv2.imread(img_path)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    lower_red1 = np.array([0, 120, 70])
    upper_red1 = np.array([10, 255, 255])
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)

    lower_red2 = np.array([170, 120, 70])
    upper_red2 = np.array([180, 255, 255])
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)

    mask = cv2.bitwise_or(mask1, mask2)
    red_area = cv2.bitwise_and(img, img, mask=mask)
    gray = cv2.cvtColor(red_area, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)

    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
        epsilon = 0.04 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        if len(approx) == 4 and cv2.contourArea(contour) > 1000:
            return "OK"
    return "ERROR"


@app.route('/')
def index():
    return render_template('index.html', mode=mode, message="")


@app.route('/upload', methods=['POST'])
def upload_image():
    global latest_result, mode
    now = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = "latest.jpg"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
#xóa ảnh cũ 
    if os.path.exists(filepath):
        os.remove(filepath)

    with open(filepath, 'wb') as f:
        f.write(request.data)

    if mode == "auto":
        result = detect_defect(filepath)
        latest_result = {"status": result, "timestamp": now, "image": filename}

        db.collection("results").add({
            "status": result,
            "timestamp": now,
            "image": filename,
            "mode": mode
        })
        return jsonify({"result": result})  # Gửi kết quả đơn giản cho ESP32
   


@app.route('/status')
def get_status():
    return jsonify(latest_result)


@app.route('/set-mode', methods=['POST'])
def set_mode():
    global mode
    mode = request.json.get("mode")
    return jsonify({"mode": mode})


@app.route('/manual-result', methods=['POST'])
def manual_result():
    global latest_result, mode
    if latest_result["status"] != "WAITING":
        return jsonify({"error": "Already evaluated."}), 400

    result = request.json.get("result")
    latest_result["status"] = result

    db.collection("results").add({
        "status": result,
        "timestamp": latest_result["timestamp"],
        "image": latest_result["image"],
        "mode": mode
    })

    return jsonify({"result": result})  # Gửi kết quả đơn giản cho ESP32


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
