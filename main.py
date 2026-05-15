import argparse
import pathlib
import shutil
from concurrent.futures import ProcessPoolExecutor

from PIL import Image

RESIZED_PATH = "resized"
THUMBNAIL_PATH = "thumbnails"

MAX_WORKERS = 10


class FilenameObject:
    def __init__(self, resized: str, thumbnail: str, original: str):
        self.resized = resized
        self.thumbnail = thumbnail
        self.original = original


def dumps_js(filenames: list[FilenameObject], folders: list[str], outpath: pathlib.Path):
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
        print(f"Skipping {file.name} because it already exists")
        return f"{out_path_name}/{file.name}"

    img = Image.open(file)
    if img.size[1] < height:
        print(f"Skipping {file.name} because it is smaller than {height}")
        return file.name
    # Calculate width to maintain aspect ratio
    ratio = height / img.size[1]
    width = int(img.size[0] * ratio)
    # Resize with LANCZOS resampling for better quality
    resized_image = img.resize((width, height), Image.Resampling.LANCZOS)
    # Save with high quality
    resized_image.save(out_path / file.name, quality=95, optimize=True)
    print(f"Resized {file.name} to {out_path / file.name}")

    return f"{out_path_name}/{file.name}"


def resize_job(target: str):
    images_files = get_image_files(pathlib.Path(target))

    resized_path = pathlib.Path(target) / RESIZED_PATH
    if not resized_path.exists():
        resized_path.mkdir(parents=True)

    thumbnail_path = pathlib.Path(target) / THUMBNAIL_PATH
    if not thumbnail_path.exists():
        thumbnail_path.mkdir(parents=True)

    resized_images = resize_images(images_files, RESIZED_PATH, 2160)
    thumbnail_images = resize_images(images_files, THUMBNAIL_PATH, 250)

    if len(resized_images) <= 0:
        print(f"No resized images found in {target}")
        return

    file_names = [
        FilenameObject(resized_filepath, thumbnail_filepath, original_filepath.name)
        for resized_filepath, thumbnail_filepath, original_filepath in zip(
            resized_images, thumbnail_images, images_files
        )
    ]

    sub_dirs = get_immediate_sub_dirs(pathlib.Path(target))
    folder_names = [d.name for d in sorted(sub_dirs)]

    dumps_js(file_names, folder_names, pathlib.Path(target) / "files.js")
    cp_index(pathlib.Path(target))


def get_immediate_sub_dirs(target: pathlib.Path) -> list[pathlib.Path]:
    excluded = {RESIZED_PATH, THUMBNAIL_PATH}
    return [x for x in target.iterdir() if x.is_dir() and x.name not in excluded]


def get_sub_dirs(target: str):
    target_path = pathlib.Path(target)
    return list(filter(lambda x: x.is_dir(), target_path.glob("**/*")))


def recursive_resize_job(target: str):
    target_path = pathlib.Path(target)
    # resize_job(target)

    sub_dirs = get_sub_dirs(target)
    # for sub_dir in sub_dirs:
    #     resize_job(str(sub_dir))


def main():
    print("Hello, Gallery Maker!")

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

    args = parser.parse_args()

    if not pathlib.Path(args.target).exists():
        print(f"Target directory {args.target} does not exist")
        return

    if not pathlib.Path(args.target).is_dir():
        print(f"Target {args.target} is not a directory")
        return

    resize_job(args.target)


if __name__ == "__main__":
    main()
