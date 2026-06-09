import cv2, torch, threading, time, numpy as np, os, json, tempfile
from flask import Flask, render_template, Response, jsonify, request
from ultralytics import YOLO
from torchvision import models, transforms
from PIL import Image
from collections import deque

app = Flask(__name__)

DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
yolo_model = YOLO(r"D:\CODE\PYCHARM\SAVE FILES\project1\work\runs\detect\train\weights\best.pt").to(DEVICE)
resnet_model = models.resnet50()
resnet_model.fc = torch.nn.Linear(resnet_model.fc.in_features, 2)
resnet_model.load_state_dict(torch.load(r"D:\project mini\step1\restnet_model\resnet50_best.pth", map_location=DEVICE, weights_only=True))
resnet_model.to(DEVICE).eval()

resnet_transform = transforms.Compose([
    transforms.Resize((224, 224)), transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

input_q = deque(maxlen=1)
processed_frame = None
telemetry = {"core_temp": 0, "amb_temp": 0, "hum": 0, "dist": 0}
stats = {"total": 0, "blight": 0}
last_seen = {"cam": 0, "s3": 0}
tracked_history = {}
current_command = "STOP"
cam_led = "LED_OFF"
is_test = False
stop_test = False
lock = threading.Lock()

def process_frame(frame):
    global stats
    results = yolo_model.track(frame, persist=True, verbose=False, conf=0.5, tracker="bytetrack.yaml")
    annotated = frame.copy()
    if results[0].boxes.id is not None:
        ids = results[0].boxes.id.cpu().numpy().astype(int)
        boxes = results[0].boxes.xyxy.cpu().numpy()
        for box, obj_id in zip(boxes, ids):
            if obj_id not in tracked_history:
                crop = frame[max(0,int(box[1])):int(box[3]), max(0,int(box[0])):int(box[2])]
                if crop.size > 0:
                    img_pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
                    tensor = resnet_transform(img_pil).unsqueeze(0).to(DEVICE)
                    with torch.no_grad():
                        pred = torch.argmax(resnet_model(tensor), dim=1).item()
                    tracked_history[obj_id] = "HEALTHY" if pred == 0 else "BLIGHT"
                    stats["total"] += 1
                    if pred == 1: stats["blight"] += 1
            color = (46, 204, 113) if tracked_history[obj_id] == "HEALTHY" else (231, 76, 60)
            cv2.rectangle(annotated, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), color, 3)
            cv2.putText(annotated, f"ID:{obj_id} {tracked_history[obj_id]}", (int(box[0]), int(box[1])-10), 0, 0.6, color, 2)
    return annotated

def ai_worker():
    global processed_frame
    while True:
        if not is_test and input_q:
            f = input_q.popleft()
            res = process_frame(f)
            with lock: processed_frame = res
        time.sleep(0.01)

# --- 4. ROUTES ---
@app.route('/')
def index(): return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    last_seen["cam"] = time.time()
    img = cv2.imdecode(np.frombuffer(request.data, np.uint8), cv2.IMREAD_COLOR)
    if img is not None: input_q.append(img)
    return cam_led

@app.route('/telemetry', methods=['POST'])
def receive_telem():
    global telemetry, last_seen
    last_seen["s3"] = time.time()
    try: telemetry.update(request.get_json(force=True))
    except: pass
    return current_command

@app.route('/get_data')
def get_data():
    now = time.time()

    status = {
        "cam": (now - last_seen["cam"]) < 5.0,
        "s3": (now - last_seen["s3"]) < 5.0
    }
    return jsonify({
        "telemetry": telemetry,
        "stats": stats,
        "status": status,
        "is_test": is_test
    })

@app.route('/upload_test_video', methods=['POST'])
def upload_video():
    global is_test, stop_test
    file = request.files['video_file']
    if file:
        is_test = True; stop_test = False
        stats["total"]=0; stats["blight"]=0; tracked_history.clear()
        tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        file.save(tfile.name)
        def run():
            global is_test, processed_frame
            cap = cv2.VideoCapture(tfile.name)
            while cap.isOpened() and not stop_test:
                ret, frame = cap.read()
                if not ret: break
                res = process_frame(frame)
                with lock: processed_frame = res
                time.sleep(0.02)
            cap.release(); is_test = False; os.remove(tfile.name)
        threading.Thread(target=run).start()
    return "OK"

@app.route('/stop_test')
def kill_test():
    global stop_test
    stop_test = True
    return "OK"

@app.route('/video_feed')
def video_feed():
    def gen():
        while True:
            if processed_frame is not None:
                with lock: _, jpeg = cv2.imencode('.jpg', processed_frame)
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
            time.sleep(0.05)
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/set_cmd')
def set_cmd():
    global current_command
    current_command = request.args.get('cmd', 'STOP')
    return "OK"

@app.route('/set_feature')
def set_feat():
    global cam_led, stats, tracked_history
    f = request.args.get('feat')
    if f == "toggle_led": cam_led = "LED_ON" if cam_led == "LED_OFF" else "LED_OFF"
    elif f == "reset": stats["total"]=0; stats["blight"]=0; tracked_history.clear()
    return jsonify({"led": cam_led})


if __name__ == '__main__':
    threading.Thread(target=ai_worker, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, threaded=True)