import requests

# Sample plant leaf image URL (Potato Late Blight)
image_url = "https://upload.wikimedia.org/wikipedia/commons/e/ec/Potato_late_blight.jpg"
img_data = requests.get(image_url).content

with open("sample_leaf.jpg", "wb") as f:
    f.write(img_data)

# Send to FastAPI local endpoint
api_url = "http://127.0.0.1:8000/predict-disease"
with open("sample_leaf.jpg", "rb") as f:
    files = {"file": ("sample_leaf.jpg", f, "image/jpeg")}
    response = requests.post(api_url, files=files)

print("API Response:", response.json())