import argparse
import pathlib
import shutil
import logging
from concurrent.futures import ProcessPoolExecutor

from PIL import Image

RESIZED_PATH = ".resized"
THUMBNAIL_PATH = ".thumbnails"

MAX_WORKERS = 10

log = logging.getLogger()
log.addHandler(logging.StreamHandler())
log.setLevel(logging.INFO)


class FilenameObject:
    def __init__(self, resized: str, thumbnail: str, original: str):
        self.resized = resized
        self.thumbnail = thumbnail
        self.original = original


def dumps_js(
    filenames: list[FilenameObject], folders: list[str], outpath: pathlib.Path
):
    with open(outpath, "w", encoding="utf-8") as f:
        f.write("const files = [\n")
        for i, filename in enumerate(filenames):
            f.write(
                f'{{"resized": "{filename.resized}", "thumbnail": "{filename.thumbnail}", "original": "{filename.original}"}}'
            )
            if i != len(filenames) - 1:
                f.write(",\n")
        f.write("\n];\n")
        f.write("const folders = [\n")
        for i, folder in enumerate(folders):
            f.write(f'"{folder}"')
            if i != len(folders) - 1:
                f.write(",\n")
        f.write("\n];")


def cp_index(path: pathlib.Path):
    shutil.copy("gallery.html", path / "gallery.html")


def get_image_files(target_path: pathlib.Path):
    return list(
        filter(
            lambda x: x.suffix.lower() in [".jpg", ".png", ".jpeg", ".tiff", ".webp"],
            target_path.glob("*"),
        )
    )


def resize_images(image_files: list[pathlib.Path], out_path_name: str, height: int):
    """
    이미지 높이를 resize. height 로 지정하고 비율에 맞게 너비 조절
    이미지 화질은 높게 유지
    """

    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(resize_image, file, out_path_name, height)
            for file in image_files
        ]
    return [future.result() for future in futures]


def resize_image(file: pathlib.Path, out_path_name: str, height: int):
    out_path = file.parent / out_path_name
    out_filepath = out_path / file.name
    if out_filepath.exists():
        log.info(f"Skipping {file.name} because it already exists")
        return f"{out_path_name}/{file.name}"

    img = Image.open(file)
    if img.size[1] < height:
        log.info(f"Skipping {file.name} because it is smaller than {height}")
        return file.name
    # Calculate width to maintain aspect ratio
    ratio = height / img.size[1]
    width = int(img.size[0] * ratio)
    # Resize with LANCZOS resampling for better quality
    resized_image = img.resize((width, height), Image.Resampling.LANCZOS)
    # Save with high quality
    resized_image.save(out_path / file.name, quality=95, optimize=True)
    log.info(f"Resized {file.name} to {out_path / file.name}")

    return f"{out_path_name}/{file.name}"


def resize_job(target: str, resize: bool):
    target_path = pathlib.Path(target)
    images_files = get_image_files(target_path)

    resized_images: list[str] = [f"{RESIZED_PATH}/{file.name}" for file in images_files]
    thumbnail_images: list[str] = [
        f"{THUMBNAIL_PATH}/{file.name}" for file in images_files
    ]

    if resize and images_files and not (target_path / RESIZED_PATH).exists():
        (target_path / RESIZED_PATH).mkdir(parents=True, exist_ok=True)
        resized_images = resize_images(images_files, RESIZED_PATH, 2160)
    else:
        log.info(
            f"Resized images already exist in {target_path / RESIZED_PATH}, skipping resizing."
        )
        resized_images = [f"{file.name}" for file in images_files]

    if images_files and not (target_path / THUMBNAIL_PATH).exists():
        (target_path / THUMBNAIL_PATH).mkdir(parents=True, exist_ok=True)
        thumbnail_images = resize_images(images_files, THUMBNAIL_PATH, 250)
    else:
        log.info(
            f"Thumbnail images already exist in {target_path / THUMBNAIL_PATH}, skipping resizing."
        )

    file_names = [
        FilenameObject(resized_filepath, thumbnail_filepath, original_filepath.name)
        for resized_filepath, thumbnail_filepath, original_filepath in zip(
            resized_images, thumbnail_images, images_files
        )
    ]

    sub_dirs = get_immediate_sub_dirs(target_path)
    folder_names = [d.name for d in sorted(sub_dirs)]

    if not file_names and not folder_names:
        log.info(f"No images or subdirectories found in {target}")
        return

    dumps_js(file_names, folder_names, target_path / "files.js")
    cp_index(target_path)


def get_immediate_sub_dirs(target: pathlib.Path) -> list[pathlib.Path]:
    excluded = {RESIZED_PATH, THUMBNAIL_PATH}
    return [
        x
        for x in target.iterdir()
        if x.is_dir() and x.name not in excluded and not x.name.startswith(".")
    ]


def recursive_resize_job(target: str, resize: bool):
    resize_job(target, resize)
    for sub_dir in get_immediate_sub_dirs(pathlib.Path(target)):
        recursive_resize_job(str(sub_dir), resize)


def main():
    log.info("Hello, Gallery Maker!")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-t", "--target", type=str, help="Target directory", required=True
    )
    parser.add_argument(
        "-r",
        "--recursive",
        help="Recursive",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--resize",
        help="Resize images",
        default=False,
        action="store_true",
    )

    args = parser.parse_args()

    if not pathlib.Path(args.target).exists():
        log.info(f"Target directory {args.target} does not exist")
        return

    if not pathlib.Path(args.target).is_dir():
        log.info(f"Target {args.target} is not a directory")
        return

    if args.recursive:
        recursive_resize_job(args.target, args.resize)
    else:
        resize_job(args.target, args.resize)


if __name__ == "__main__":
    main()
