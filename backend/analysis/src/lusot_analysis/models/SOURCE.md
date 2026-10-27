# YuNet face detection model

`face_detection_yunet_2023mar.onnx` is the face detector behind the face blur (`../face_blur.py`), vendored so every build uses the same file (C36).

| Field | Value |
|---|---|
| Model | YuNet, 2023mar version, by Shiqi Yu and contributors ([libfacedetection](https://github.com/ShiqiYu/libfacedetection)), as published in OpenCV Zoo |
| Source folder | [opencv/opencv_zoo `models/face_detection_yunet/`](https://github.com/opencv/opencv_zoo/tree/4.10.0/models/face_detection_yunet) |
| Downloaded from | `https://media.githubusercontent.com/media/opencv/opencv_zoo/4.10.0/models/face_detection_yunet/face_detection_yunet_2023mar.onnx`. GitHub stores the file with Git LFS, and this media URL returns the binary, not the pointer. |
| Tag and commit | Tag `4.10.0`, commit `f88e9b2bafd21f1cad242fb5af6d78f2bcba16a3`. The file last changed in commit `f12e12798e8314f7c074a6656816c048dcc95b7a` ("update yunet to v2 (#151)", June 6, 2023). `main` at `48b10fa505aeb51fbd127fc60a5c660040e823b7` (Oct 20, 2026) has the same file. |
| Size | 232,589 bytes |
| SHA-256 | `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`. It equals the `oid` in the Git LFS pointer at the tag and on `main`, and `YUNET_SHA256` in `face_blur.py`, which a test checks. |
| Licence | MIT. [LICENSE](LICENSE) is copied unchanged from the same folder at the same tag. The folder's README says: "All files in this directory are licensed under [MIT License](./LICENSE)." |
| Downloaded | Oct 28, 2026 |

## Notes from the model's README

- **OpenCV version.** This model has a fixed input shape. OpenCV 4.x DNN runs it at each image's exact size, but the ONNX Runtime engine in OpenCV 5.x needs the dynamic-shape `face_detection_yunet_2026may.onnx`. So `pyproject.toml` keeps `opencv-python-headless` below 5.
- **Face sizes.** The README says the model "can detect faces of pixels between around 10x10 to 300x300 due to the training scheme."
