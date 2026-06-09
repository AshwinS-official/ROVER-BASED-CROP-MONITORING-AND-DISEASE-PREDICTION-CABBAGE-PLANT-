import os
import shutil
import random

# ---------------- CONFIG ----------------
IMG_SRC = "/cabbage train data\images"
LBL_SRC = "/cabbage train data\labels"

OUT_IMG = "images"
OUT_LBL = "labels"

TRAIN_RATIO = 0.7
VAL_RATIO   = 0.2
TEST_RATIO  = 0.1

random.seed(42)  # reproducible split
# ----------------------------------------

# Create output folders
for split in ["train", "val", "test"]:
    os.makedirs(os.path.join(OUT_IMG, split), exist_ok=True)
    os.makedirs(os.path.join(OUT_LBL, split), exist_ok=True)

# Collect images
images = [f for f in os.listdir(IMG_SRC)
          if f.lower().endswith((".jpg", ".jpeg", ".png"))]

assert len(images) > 0, "No images found in all_images!"

random.shuffle(images)

n = len(images)
train_end = int(TRAIN_RATIO * n)
val_end   = train_end + int(VAL_RATIO * n)

splits = {
    "train": images[:train_end],
    "val":   images[train_end:val_end],
    "test":  images[val_end:]
}

# Copy files
for split, files in splits.items():
    for img in files:
        name, _ = os.path.splitext(img)

        img_src = os.path.join(IMG_SRC, img)
        lbl_src = os.path.join(LBL_SRC, name + ".txt")

        img_dst = os.path.join(OUT_IMG, split, img)
        lbl_dst = os.path.join(OUT_LBL, split, name + ".txt")

        shutil.copy(img_src, img_dst)

        if os.path.exists(lbl_src):
            shutil.copy(lbl_src, lbl_dst)
        else:
            # create empty label if missing
            open(lbl_dst, "w").close()

print("✅ Dataset split completed")
print(f"Train: {len(splits['train'])} images")
print(f"Val:   {len(splits['val'])} images")
print(f"Test:  {len(splits['test'])} images")
