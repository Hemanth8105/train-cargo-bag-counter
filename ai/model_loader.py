import os
import torch
from ultralytics import YOLO

def load_model(model_path: str) -> YOLO:
    """
    Load YOLO model with GPU acceleration.
    FP16 is handled during inference, NOT at model load time.
    """
    if not os.path.exists(model_path):
        raise FileNotFoundError(
            f"\n[ERROR] Model not found: '{model_path}'\n"
            f"        → Place your trained 'best.pt' inside the 'model/' folder.\n"
        )

    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        vram     = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"[INFO] GPU    : {gpu_name}")
        print(f"[INFO] VRAM   : {vram:.1f} GB")
        device = "cuda"
    else:
        print("[WARN] No GPU found — running on CPU")
        device = "cpu"

    model = YOLO(model_path)
    model.to(device)
    # ⚠️ DO NOT call model.half() here — causes dtype conflict with YOLO fusing
    # FP16 is passed during inference via half=True in model()

    print(f"[INFO] Model  : {model_path}  |  Device : {device.upper()}\n")
    return model
