import os
import pathlib
import shutil
from concurrent.futures import ProcessPoolExecutor

from PIL import Image

target_path = "C:\\Users\\ricepotato\\dev\\gallery-maker\\images"
resized_path = "resized"
thumbnail_path = "thumbnails"


class FilenameObject:
    def __init__(self, resized: str, thumbnail: str):
        self.resized = resized
        self.thumbnail = thumbnail


def dumps_js(filenames: list[FilenameObject], outpath: pathlib.Path):
    with open(outpath, "w", encoding="utf-8") as f:
        f.write("const files = [\n")
        for filename in filenames:
            f.write(
                f'{{"resized": "{filename.resized}", "thumbnail": "{filename.thumbnail}"}}'
            )
            if filename != filenames[-1]:
                f.write(",\n")
        f.write("\n];")


def get_file_list(path: pathlib.Path):
    exts = [".jpg", ".png", ".jpeg", ".tiff", ".webp"]
    if not path.exists():
        print(f"Path {path} does not exist")
        return []

    file_list = list(path.glob("*"))
    file_list = [file for file in file_list if file.suffix in exts]
    return file_list


def cp_index(path: pathlib.Path):
    shutil.copy("index.html", path / "index.html")


def resize_images(path: pathlib.Path, out_path_name: str, height: int):
    """
    이미지 높이를 resize. height 로 지정하고 비율에 맞게 너비 조절
    이미지 화질은 높게 유지
    """

    out_path = path / out_path_name
    if not out_path.exists():
        out_path.mkdir(parents=True)

    image_files = filter(
        lambda x: x.suffix in [".jpg", ".png", ".jpeg", ".tiff", ".webp"],
        path.glob("*"),
    )
    with ProcessPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(resize_image, file, out_path_name, height)
            for file in image_files
        ]
    return [future.result() for future in futures]


def resize_image(file: pathlib.Path, out_path_name: str, height: int):
    out_path = pathlib.Path(target_path) / out_path_name
    img = Image.open(file)
    if img.size[1] < height:
        print(
            f"[{os.getpid()}]Skipping {file.name} because it is smaller than {height}"
        )
        return file.name
    # Calculate width to maintain aspect ratio
    ratio = height / img.size[1]
    width = int(img.size[0] * ratio)
    # Resize with LANCZOS resampling for better quality
    resized_image = img.resize((width, height), Image.Resampling.LANCZOS)
    # Save with high quality
    resized_image.save(out_path / file.name, quality=95, optimize=True)
    print(f"[{os.getpid()}]Resized {file.name} to {out_path / file.name}")

    return f"{out_path_name}/{file.name}"


def main():
    print("Hello, Gallery Maker!")
    resized_images = resize_images(pathlib.Path(target_path), resized_path, 2160)
    thumbnail_images = resize_images(pathlib.Path(target_path), thumbnail_path, 250)

    file_names = [
        FilenameObject(resized_filepath, thumbnail_filepath)
        for resized_filepath, thumbnail_filepath in zip(
            resized_images, thumbnail_images
        )
    ]
    dumps_js(file_names, pathlib.Path(target_path) / "files.js")
    cp_index(pathlib.Path(target_path))


if __name__ == "__main__":
    main()
