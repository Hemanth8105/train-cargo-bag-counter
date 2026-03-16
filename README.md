# 🚂 Train Cargo Bag Counter

An AI-powered web application for counting cargo bags loaded/unloaded from train wagons using YOLOv8 object detection and a centroid-based tracker.

---

## 📸 Features

- 🎯 **Real-time bag detection** using YOLOv8 custom trained model
- 📊 **IN / OUT counting** with horizontal line crossing detection
- 🌐 **Web dashboard** built with Flask
- 👥 **User roles** — Admin, Operator, Viewer
- 📁 **CSV reports** — every bag logged with timestamp and direction
- 🎥 **Video upload** or **Live RTSP camera** support
- 🔍 **Filter reports** by date, month, year
- 🔐 **Authentication** — Login, Forgot password, Change password
- ⚡ **GPU accelerated** with CUDA + FP16 inference (RTX 3050 Ti)

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| AI Detection | YOLOv8 (Ultralytics) |
| Tracking | Custom centroid-based tracker |
| Computer Vision | OpenCV |
| GPU | CUDA + FP16 (PyTorch) |
| Database | SQLite |
| Frontend | HTML, CSS, Jinja2 |

---

## 📁 Project Structure

```
train_cargo_box_counter/
│
├── app.py                  ← Flask web server
├── run_count.py            ← Counting pipeline script
├── requirements.txt
│
├── templates/              ← HTML pages
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── count.html
│   ├── live.html
│   ├── reports.html
│   ├── users.html
│   ├── add_user.html
│   ├── change_password.html
│   ├── forgot_password.html
│   └── reset_password.html
│
├── core/                   ← AI pipeline
│   ├── __init__.py
│   ├── tracker.py          ← Centroid tracker
│   └── counter.py          ← Line crossing counter
│
├── ai/
│   ├── __init__.py
│   └── model_loader.py     ← YOLO model loader
│
├── model/
│   └── best.pt             ← Trained YOLOv8 model (not included)
│
├── uploads/                ← Uploaded videos (not included)
└── reports/                ← Generated CSV reports (not included)
```

---

## ⚙️ Installation

### 1. Clone the repository
```bash
git clone https://github.com/Hemanth8105/train-cargo-bag-counter.git
cd train-cargo-bag-counter
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Add your trained model
Place your `best.pt` file in the `model/` folder:
```
model/best.pt
```

### 4. Create required folders
```bash
mkdir uploads reports
```

### 5. Run the web app
```bash
python app.py
```

### 6. Open browser
```
http://localhost:5000
```

---

## 🔐 Default Login

| Username | Password | Role |
|---|---|---|
| admin | admin123 | Admin |

> ⚠️ Change the default password after first login!

---

## 👥 User Roles

| Feature | Admin | Operator | Viewer |
|---|---|---|---|
| Dashboard | ✅ | ✅ | ✅ |
| Start counting | ✅ | ✅ | ❌ |
| View reports | ✅ | ✅ | ✅ |
| Download CSV | ✅ | ✅ | ✅ |
| Manage users | ✅ | ❌ | ❌ |
| Delete sessions | ✅ | ❌ | ❌ |

---

## 🎮 Video Window Controls

Once counting starts a video window opens automatically:

| Key | Action |
|---|---|
| `W` | Move counting line UP |
| `S` | Move counting line DOWN |
| `R` | Reset counter to 0 |
| `Q` | Quit and save results |

---

## 📊 Counting Logic

- Bag moves **UP** on screen → counted as **IN** (loaded into wagon)
- Bag moves **DOWN** on screen → counted as **OUT** (unloaded from wagon)
- **Total** = bags currently inside the wagon
- Total never goes below 0 — if total is 0 and bag goes OUT, only OUT count increases

---

## 🧠 Model Training

- Dataset: Custom labeled using Roboflow
- Model: YOLOv8n
- Epochs: 50
- Image size: 640
- Class: `bag`

---

## 💻 System Requirements

- Python 3.10+
- NVIDIA GPU with CUDA (recommended)
- 4GB+ VRAM for FP16 inference
- Windows 10/11

---

## 📦 Requirements

```
flask>=3.0.0
ultralytics>=8.0.0
opencv-python>=4.8.0
numpy>=1.24.0
torch>=2.0.0
torchvision>=0.15.0
```

---

## 🚀 Future Improvements

- [ ] Multiple camera support
- [ ] Auto daily CSV email reports
- [ ] Alert system for bag count threshold
- [ ] Mobile responsive UI
- [ ] Docker deployment

---

## 👨‍💻 Author

**Hemanth** — [GitHub](https://github.com/Hemanth8105)
