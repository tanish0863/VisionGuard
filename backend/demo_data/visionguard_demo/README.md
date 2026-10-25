# VisionGuard Demo Dataset (`visionguard_demo`)

This directory is the default location for demo images evaluated by VisionGuard. When present, the ML evaluation pipeline automatically registers this directory under the dataset ID `"visionguard_demo"`.

## Specifications & Requirements

### Supported Image Formats
The pipeline automatically scans this directory and all subdirectories for images with the following file extensions (case-insensitive):
- `.jpg` / `.jpeg`
- `.png`
- `.bmp`
- `.webp`

### Recommended Image Dimensions
- **Resolution:** Between `640×480` and `1280×720` pixels.
- **Aspect Ratio:** Standard landscape (`4:3` or `16:9`) or square (`1:1`).
- **Minimum Dimensions:** At least `300×300` pixels to ensure effective detection by CNN/Transformer backbones.

### Color & Channel Format
- Images must be 3-channel **RGB**.
- Images are decoded as `H×W×3 uint8` arrays with pixel intensity values in the range `[0, 255]`.
- Grayscale images will be converted to 3-channel RGB upon loading.

### Recommended Content for Object Detection
For best results with default COCO-pretrained object detectors (e.g. `fasterrcnn_resnet50_fpn`):
- Include common COCO categories: **people, cars, bicycles, traffic lights, animals (dogs, cats), furniture (chairs)**.
- Well-lit, in-focus clean captures so the baseline model produces confident clean detections before corruptions are applied.
- Recommended sample size for demo: **3 to 10 images** (balances evaluation speed on CPU with meaningful consistency metrics).

### Image Licensing & Provenance
- All images placed in this directory must have permissive, open licenses (e.g., Creative Commons CC0, CC-BY, public domain, or COCO val2017 open dataset).
- Do **not** commit copyrighted or restricted media.
