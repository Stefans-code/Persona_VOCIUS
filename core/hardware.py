import torch
import os
import sys

try:
    import torch_directml
    HAS_DIRECTML = True
except ImportError:
    HAS_DIRECTML = False

def detect_hardware():
    """
    Detects the best available hardware for transcription.
    Returns a dict with device, compute_type, and label.
    """
    # 1. macOS (Darwin) Support
    if sys.platform == "darwin":
        # Apple Silicon / Intel Mac
        # Faster-whisper works best on CPU for now on Mac
        return {
            "device": "cpu",
            "compute_type": "int8", 
            "label": "CPU (Ottimizzato per Mac)",
            "type": "cpu"
        }

    # 2. Windows/Linux Nvidia GPU
    if torch.cuda.is_available():
        # Nvidia GPU detected
        device = "cuda"
        compute_type = "float16"
        gpu_name = torch.cuda.get_device_name(0)
        label = f"Nvidia GPU: {gpu_name}"
        
        try:
            free_vram, _ = torch.cuda.mem_get_info()
            vram_gb = free_vram / (1024**3)
            label += f" ({vram_gb:.1f}GB VRAM libera)"
        except:
            pass
            
        return {
            "device": device,
            "compute_type": compute_type,
            "label": label,
            "type": "cuda"
        }
    
    # 3. Windows DirectML (AMD/Intel GPU)
    elif HAS_DIRECTML and torch_directml.is_available():
        device = torch_directml.device()
        compute_type = "float32"
        label = "GPU Universale (DirectML)"
        return {
            "device": device,
            "compute_type": compute_type,
            "label": label,
            "type": "directml"
        }
    
    # 4. Fallback to CPU
    else:
        device = "cpu"
        compute_type = "int8"
        label = "CPU (Lenta)"
        return {
            "device": device,
            "compute_type": compute_type,
            "label": label,
            "type": "cpu"
        }

def get_recommended_model(hw_info):
    """Suggests a model based on hardware capabilities."""
    hw_type = hw_info["type"]
    
    if hw_type == "cuda":
        # If we have a good GPU, large-v3 is usually fine
        return "large-v3"
    elif hw_type == "directml":
        return "medium"
    else:
        return "base"
