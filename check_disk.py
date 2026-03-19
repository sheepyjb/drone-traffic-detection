import os
import shutil

d = "D:\\"
dirs = []
for entry in os.scandir(d):
    if entry.is_dir():
        total = 0
        for root, ds, fs in os.walk(entry.path):
            for f in fs:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except:
                    pass
        dirs.append((entry.name, total))
dirs.sort(key=lambda x: -x[1])
for name, size in dirs[:20]:
    print(f"{name:40s} {size/1024**3:10.2f} GB")
print()
t, u, f = shutil.disk_usage("D:\\")
print(f"Total: {t/1024**3:.1f} GB | Used: {u/1024**3:.1f} GB | Free: {f/1024**3:.1f} GB")
