"""
run_count.py — Run bag counting for a web session
Usage: python run_count.py <session_id>
"""
import sys, os, cv2, csv, time, sqlite3, requests, numpy as np, torch
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ai.model_loader import load_model
from core.tracker import BoxTracker
from core.counter import BoxCounter

DB           = "database.db"
MODEL_PATH   = "model/best.pt"
PROCESS_SIZE = (416, 234)
USE_FP16     = True
API_BASE     = "http://localhost:5000"

def get_session(session_id):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    sess = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    conn.close()
    return sess

def update_db(session_id, total, count_in, count_out, csv_path, status):
    conn = sqlite3.connect(DB)
    conn.execute(
        "UPDATE sessions SET total_count=?,count_in=?,count_out=?,csv_path=?,status=?,ended_at=? WHERE id=?",
        (total, count_in, count_out, csv_path, status,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status=="done" else None,
         session_id))
    conn.commit()
    conn.close()

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_count.py <session_id>")
        sys.exit(1)

    session_id  = int(sys.argv[1])
    line_pos    = float(sys.argv[2]) if len(sys.argv) > 2 else 0.17
    conf_thresh = float(sys.argv[3]) if len(sys.argv) > 3 else 0.60
    save_video  = sys.argv[4] == "1" if len(sys.argv) > 4 else False
    save_csv    = sys.argv[5] == "1" if len(sys.argv) > 5 else True

    sess = get_session(session_id)
    if not sess:
        print(f"[ERROR] Session {session_id} not found!")
        sys.exit(1)

    source = sess["video_path"]
    print(f"\n[INFO] Session   : {sess['session_name']}")
    print(f"[INFO] Source    : {source}")
    print(f"[INFO] Line pos  : {line_pos*100:.0f}%")
    print(f"[INFO] Confidence: {conf_thresh}")
    print(f"[INFO] Save video: {save_video}")
    print(f"[INFO] Save CSV  : {save_csv}")
    print(f"[INFO] Session ID: {session_id}\n")

    model  = load_model(MODEL_PATH)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    fp16   = USE_FP16 and device == "cuda"

    if device == "cuda":
        blank = np.zeros((PROCESS_SIZE[1], PROCESS_SIZE[0], 3), dtype=np.uint8)
        model(blank, verbose=False, half=fp16)
        torch.cuda.empty_cache()

    tracker = BoxTracker(max_distance=90, max_missing=25)
    counter = BoxCounter(line_position=line_pos, axis="horizontal")

    # CSV
    csv_path = None
    if save_csv:
        csv_path = f"reports/session_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        os.makedirs("reports", exist_ok=True)
        with open(csv_path, "w", newline="") as f:
            csv.writer(f).writerow(["Bag #","Direction","Time","Total","IN","OUT"])

    cap = cv2.VideoCapture(source if not source.isdigit() else int(source))
    if not cap.isOpened():
        print(f"[ERROR] Cannot open source: {source}")
        sys.exit(1)

    frame_w  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps_src  = cap.get(cv2.CAP_PROP_FPS) or 25

    DISP_W, DISP_H = 720, 540
    scale_x  = frame_w / PROCESS_SIZE[0]
    scale_y  = frame_h / PROCESS_SIZE[1]
    disp_sx  = DISP_W / frame_w
    disp_sy  = DISP_H / frame_h
    line_coord = int(frame_h * line_pos)
    disp_line  = int(line_coord * disp_sy)
    STEP       = max(1, int(frame_h * 0.02))

    # Video writer
    writer = None
    if save_video:
        out_path = f"reports/video_session_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        fourcc   = cv2.VideoWriter_fourcc(*"mp4v")
        writer   = cv2.VideoWriter(out_path, fourcc, fps_src, (DISP_W, DISP_H))
        print(f"[INFO] Saving video to: {out_path}")

    cv2.namedWindow("BagCounter Pro", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("BagCounter Pro", 1280, 960)

    fps_display  = 0.0
    t_prev       = time.time()
    prev_counted = set()
    last_db_update = time.time()

    print("[INFO] Running! Controls: W/S=line  R=reset  Q=quit\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        small      = cv2.resize(frame, PROCESS_SIZE)
        results    = model(small, verbose=False, half=fp16)
        detections = []
        for box in results[0].boxes:
            x1,y1,x2,y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])
            if conf >= conf_thresh:
                x1=int(x1*scale_x); y1=int(y1*scale_y)
                x2=int(x2*scale_x); y2=int(y2*scale_y)
                detections.append((x1,y1,x2,y2,conf,0))

        tracked = tracker.update(detections)
        counter.update(tracked, line_coord)

        # CSV
        if csv_path:
            new_c = counter.counted_ids - prev_counted
            for oid in new_c:
                direction = "IN" if oid in getattr(counter,'_in_ids',set()) else "OUT"
                with open(csv_path, "a", newline="") as f:
                    csv.writer(f).writerow([oid, direction,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        counter.count, counter.count_in, counter.count_out])
        prev_counted = set(counter.counted_ids)

        # Update DB every 2 seconds
        if time.time() - last_db_update > 2:
            update_db(session_id, counter.count, counter.count_in,
                      counter.count_out, csv_path, "running")
            last_db_update = time.time()

        display = cv2.resize(frame, (DISP_W, DISP_H))
        for oid, (x1,y1,x2,y2) in tracked.items():
            dx1,dy1 = int(x1*disp_sx), int(y1*disp_sy)
            dx2,dy2 = int(x2*disp_sx), int(y2*disp_sy)
            color = (0,80,255) if oid in counter.counted_ids else (0,200,0)
            cv2.rectangle(display,(dx1,dy1),(dx2,dy2),color,2)
            cv2.circle(display,((dx1+dx2)//2,(dy1+dy2)//2),4,(0,0,255),-1)
            cv2.putText(display,f"#{oid}",(dx1,dy1-6),cv2.FONT_HERSHEY_SIMPLEX,0.48,color,2)

        t_now = time.time()
        fps_display = 0.9*fps_display + 0.1*(1.0/max(t_now-t_prev,1e-6))
        t_prev = t_now

        cv2.line(display,(0,disp_line),(DISP_W,disp_line),(0,255,255),2)
        cv2.rectangle(display,(8,8),(230,95),(0,0,0),-1)
        cv2.rectangle(display,(8,8),(230,95),(0,180,0),1)
        cv2.putText(display,f"BAGS: {counter.count}",(14,35),cv2.FONT_HERSHEY_SIMPLEX,0.8,(0,255,0),2)
        cv2.putText(display,f"IN:{counter.count_in}  OUT:{counter.count_out}",(14,60),cv2.FONT_HERSHEY_SIMPLEX,0.55,(200,200,200),1)
        cv2.putText(display,f"FPS:{fps_display:.0f}  {device.upper()}",(14,82),cv2.FONT_HERSHEY_SIMPLEX,0.45,(0,180,255),1)
        cv2.putText(display,"W/S=line  R=reset  Q=quit",(10,DISP_H-10),cv2.FONT_HERSHEY_SIMPLEX,0.40,(150,150,0),1)

        if writer:
            writer.write(display)
        cv2.imshow("BagCounter Pro", display)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == 82 or key == ord('w'):
            line_coord = max(10, line_coord-STEP)
            disp_line  = int(line_coord*disp_sy)
            counter.prev_pos = {}
        elif key == 84 or key == ord('s'):
            line_coord = min(frame_h-10, line_coord+STEP)
            disp_line  = int(line_coord*disp_sy)
            counter.prev_pos = {}
        elif key == ord('r'):
            counter.count=0; counter.count_in=0; counter.count_out=0
            counter.counted_ids=set(); counter.prev_pos={}
            prev_counted=set()

    cap.release()
    if writer:
        writer.release()
    cv2.destroyAllWindows()

    # Final CSV summary
    if csv_path:
        with open(csv_path, "a", newline="") as f:
            w = csv.writer(f)
            w.writerow([])
            w.writerow(["SUMMARY","",datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        counter.count, counter.count_in, counter.count_out])

    # Final DB update
    update_db(session_id, counter.count, counter.count_in,
              counter.count_out, csv_path, "done")

    print(f"\n{'='*45}")
    print(f"  ✅  Total bags : {counter.count}")
    print(f"      IN         : {counter.count_in}")
    print(f"      OUT        : {counter.count_out}")
    print(f"  📊  CSV        : {csv_path}")
    print(f"{'='*45}\n")

if __name__ == "__main__":
    main()
