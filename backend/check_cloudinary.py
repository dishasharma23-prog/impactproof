import sys
import cloudinary
import cloudinary.uploader
from app.core.config import settings

def check_cloudinary():
    config = cloudinary.config()
    print(f"configured: {'yes' if config.api_key else 'no'}")
    
    if not config.api_key:
        print("Please configure Cloudinary in .env")
        sys.exit(1)
        
    print(f"cloud_name: {config.cloud_name}")
    
    try:
        print("\nPerforming test upload...")
        res = cloudinary.uploader.upload("../test_image.jpg")
        print("Upload successful!")
        print(f"public_id: {res.get('public_id')}")
        print(f"secure_url: {res.get('secure_url')}")
        print(f"version: {res.get('version')}")
    except Exception as e:
        print(f"Upload failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_cloudinary()

