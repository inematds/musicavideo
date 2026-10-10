import sys, subprocess, numpy as np, torch, soundfile as sf
from demucs.pretrained import get_model
from demucs.apply import apply_model

src, out_voc, out_inst = sys.argv[1:4]
sr = 44100
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-f", "f32le", "-ac", "2", "-ar", str(sr), "-"],
                     capture_output=True, check=True).stdout
wav = torch.from_numpy(np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).T.copy())
model = get_model("htdemucs").cuda().eval()
ref = wav.mean(0)
x = (wav - ref.mean()) / ref.std()
with torch.no_grad():
    srcs = apply_model(model, x[None].cuda(), device="cuda", progress=False)[0]
srcs = srcs * ref.std() + ref.mean()
vi = model.sources.index("vocals")
voc = srcs[vi].cpu()
inst = (srcs.sum(0).cpu() - voc)
sf.write(out_voc, voc.T.numpy(), sr)
sf.write(out_inst, inst.T.numpy(), sr)
print("ok", model.sources)
