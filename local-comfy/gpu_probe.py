"""Run inside our container; finite CUDA arithmetic, not model-quality evaluation."""
import json
import torch

if not torch.cuda.is_available():
    raise RuntimeError('NVIDIA GPU is not available inside the container.')
x = torch.randn(512, 512, device='cuda')
y = x @ x
torch.cuda.synchronize()
if not torch.isfinite(y).all().item():
    raise RuntimeError('CUDA matrix arithmetic returned non-finite values.')
print(json.dumps({
    'torch':torch.__version__, 'cuda':torch.version.cuda,
    'gpu':torch.cuda.get_device_name(0),
    'vram_gib':torch.cuda.get_device_properties(0).total_memory / 2**30,
    'cuda_matrix_test':'passed', 'model_inference_tested':False,
}))
