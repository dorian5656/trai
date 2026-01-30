import torch
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_free_gpu_id() -> int:
    """
    获取显存占用最小的 GPU ID
    如果无 GPU 或 GPU 都不可用，返回 -1 (表示使用 CPU)
    """
    try:
        if not torch.cuda.is_available():
            logger.warning("未检测到可用 GPU，将使用 CPU 进行 OCR 推理")
            return -1
        
        device_count = torch.cuda.device_count()
        print(f"Device count: {device_count}")
        max_free_memory = 0
        best_gpu_id = -1
        
        for i in range(device_count):
            # 获取当前显存剩余量 (byte)
            try:
                free_mem = torch.cuda.mem_get_info(i)[0]
                print(f"GPU {i} free memory: {free_mem / 1024**3:.2f} GB")
                if free_mem > max_free_memory:
                    max_free_memory = free_mem
                    best_gpu_id = i
            except Exception as e:
                logger.warning(f"获取 GPU {i} 信息失败: {e}")
        
        if best_gpu_id != -1:
            logger.info(f"选择 GPU {best_gpu_id} (剩余显存: {max_free_memory / 1024**3:.2f} GB)")
            return best_gpu_id
        else:
            return -1

    except Exception as e:
        logger.warning(f"GPU 检测失败: {e}，将回退到 CPU")
        return -1

if __name__ == "__main__":
    gpu_id = get_free_gpu_id()
    print(f"Selected GPU ID: {gpu_id}")
