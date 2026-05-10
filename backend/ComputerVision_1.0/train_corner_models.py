import argparse
import random
import shutil
from pathlib import Path

from ultralytics import YOLO


RANK_CLASSES = ["2", "3", "4", "5", "6", "7", "11", "12", "13", "Ace"]
SUIT_CLASSES = ["Clubs", "Diamonds", "Hearts", "Spades"]
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def safe_link_or_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    try:
        src.link_to(dst)
    except Exception:
        shutil.copy2(src, dst)


def build_split_dataset(source_root: Path, class_names: list[str], out_root: Path, val_ratio: float, seed: int) -> None:
    if out_root.exists():
        shutil.rmtree(out_root)

    rng = random.Random(seed)

    for class_name in class_names:
        src_dir = source_root / class_name
        if not src_dir.exists() or not src_dir.is_dir():
            raise FileNotFoundError(f"Missing class folder: {src_dir}")

        files = [p for p in src_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
        if len(files) < 2:
            raise ValueError(f"Not enough images in {src_dir} (found {len(files)})")

        rng.shuffle(files)
        n_val = max(1, int(len(files) * val_ratio))
        val_files = files[:n_val]
        train_files = files[n_val:]

        for src in train_files:
            dst = out_root / "train" / class_name / src.name
            safe_link_or_copy(src, dst)

        for src in val_files:
            dst = out_root / "val" / class_name / src.name
            safe_link_or_copy(src, dst)

        print(f"[split] {class_name}: train={len(train_files)} val={len(val_files)}")


def train_classifier(data_dir: Path, run_name: str, epochs: int, imgsz: int, batch: int, device: str, project_dir: Path) -> None:
    model = YOLO("yolov8n-cls.pt")
    model.train(
        data=str(data_dir),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        workers=4,
        patience=20,
        pretrained=True,
        project=str(project_dir),
        name=run_name,
        exist_ok=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Train corner rank/suit YOLO classifiers from Sueca_dataset.")
    parser.add_argument("--source", default="Sueca_dataset", help="Source dataset root with class subfolders")
    parser.add_argument("--epochs", type=int, default=35, help="Training epochs for each model")
    parser.add_argument("--imgsz", type=int, default=224, help="Training image size")
    parser.add_argument("--batch", type=int, default=32, help="Batch size")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="Validation split ratio")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--device", default="0", help="Device for Ultralytics (e.g. 0, cpu)")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    source_root = (root / args.source).resolve()
    project_dir = root / "runs" / "classify"

    rank_data = root / "dataset_corner_rank"
    suit_data = root / "dataset_corner_suit"

    print("[1/4] Building rank split dataset...")
    build_split_dataset(source_root, RANK_CLASSES, rank_data, args.val_ratio, args.seed)

    print("[2/4] Building suit split dataset...")
    build_split_dataset(source_root, SUIT_CLASSES, suit_data, args.val_ratio, args.seed)

    print("[3/4] Training rank classifier...")
    train_classifier(rank_data, "sueca_corner_rank_classifier", args.epochs, args.imgsz, args.batch, args.device, project_dir)

    print("[4/4] Training suit classifier...")
    train_classifier(suit_data, "sueca_corner_suit_classifier", args.epochs, args.imgsz, args.batch, args.device, project_dir)

    print("Done. Models saved under runs/classify/sueca_corner_*_classifier/weights/best.pt")


if __name__ == "__main__":
    main()
