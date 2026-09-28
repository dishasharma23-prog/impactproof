import imagehash
from PIL import Image, ImageOps


class HashService:
    @staticmethod
    def calculate_phash(image_path: str) -> str:
        """64-bit perceptual hash. Visually similar images differ in only a few bits."""
        try:
            with Image.open(image_path) as im:
                return str(imagehash.phash(ImageOps.exif_transpose(im)))
        except Exception as e:
            print(f"Error calculating phash: {e}")
            return ""

    @staticmethod
    def hamming(a: str, b: str):
        if not a or not b or len(a) != len(b):
            return None
        try:
            return bin(int(a, 16) ^ int(b, 16)).count("1")
        except ValueError:
            return None
