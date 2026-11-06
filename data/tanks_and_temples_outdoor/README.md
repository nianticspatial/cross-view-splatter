# Tanks and Temples (outdoor) — georeferenced benchmark scenes

Ten outdoor scenes from [Tanks and Temples](https://www.tanksandtemples.org/) (Knapitsch et al. 2017,
CC BY-NC-SA 4.0): Barn, Courthouse, Family, Francis, Horse, Ignatius, Lighthouse, Playground, Temple, Truck.

## Files in this folder

| File | Content |
|---|---|
| `cameras/<Scene>.json` | intrinsics, per-frame COLMAP-frame poses, metric ENU poses, benchmark splits (one file per scene) |
| `splits/benchmark_{1,2,3}view.json` | context / target frame indices used in the paper (1, 2 or 3 context views) |
| `scenes.json` | scene list with latitude / longitude, frame count and image size |
| `lat_lon.json` | satellite query coordinate per scene (same values as in `cameras/`) |
| `../tanks_and_temples_outdoor_point_cloud_transform_enu.json` | raw geoaligner export (COLMAP -> satellite transform) |
| `make_sparse.py`, `run.sh`, `add.sh` | how the COLMAP point clouds were triangulated from the fixed poses and loaded into the geoaligner |

## Images

The images (1920x1080, Lighthouse 2048x1080; JPEG) are **not** the official Tanks and Temples video frames but a
pre-processed set with COLMAP-derived camera poses in MVSNet camera-file format (`cams/<frame>_cam.txt`:
4x4 world-to-camera extrinsic, 3x3 intrinsic). We did not run SfM ourselves; the released point clouds
(`run.sh`) were triangulated with these poses held fixed, so the poses in `cameras/<Scene>.json` are the
single source of truth and are identical to `colmap/<Scene>/sparse/0`.

Download (images + the original `cams/*_cam.txt` and `pair.txt`, one tar per scene, ~2.1 GB total):
**[Google Drive folder](https://drive.google.com/drive/folders/1-9Qm4x_acpEfclWggGFwuhXtXaQNSoF8)** (checksums in
`SHA256SUMS`). The images are redistributed under the Tanks and Temples CC BY-NC-SA 4.0 terms.

```bash
pip install gdown
gdown --folder https://drive.google.com/drive/folders/1-9Qm4x_acpEfclWggGFwuhXtXaQNSoF8 -O tanks_and_temples_outdoor
cd tanks_and_temples_outdoor && sha256sum -c SHA256SUMS && for f in *.tar; do tar -xf "$f"; done
```

Result:

```
tanks_and_temples_outdoor/
└── <Scene>/images/00000000.jpg ...   <Scene>/cams/00000000_cam.txt ...   <Scene>/pair.txt
```

## Camera JSON format

```jsonc
{
  "dataset": "tanks_and_temples_outdoor", "scene": "Barn",
  "latitude": 37.3926, "longitude": -121.9619,       // satellite query point = ENU origin
  "conventions": { ... },                             // human-readable description of every field below
  "colmap_to_enu": [[4x4]],                           // p_enu = colmap_to_enu @ p_colmap ; 3x3 block = scale * R
  "scale_colmap_to_metres": 6.66,
  "cameras": {"1": {"model": "PINHOLE", "width": 1920, "height": 1080, "fx": ..., "fy": ..., "cx": ..., "cy": ...}},
  "frames": [
    {"index": 0, "file": "images/00000000.jpg", "camera_id": 1,
     "qvec_wxyz": [...], "tvec": [...],              // COLMAP images.txt convention (world-to-camera)
     "world_to_camera": [[4x4]],                     // OpenCV extrinsic in the COLMAP frame (same pose as above)
     "camera_to_world_enu": [[4x4]]}                 // metric SE(3) pose in east-north-up, z ~ 0 at ground
  ],
  "benchmark_splits": {"1view": {"context": [0], "target": [...], "context_files": [...], "target_files": [...]},
                       "2view": {...}, "3view": {...}}
}
```

* COLMAP frame: arbitrary scale and orientation (whatever the original SfM produced).
* ENU frame: x = east, y = north, z = up, metres, origin at `(latitude, longitude)`. The satellite raster we use is
  a north-up, locally metric 1024x1024 px image at 2 px/m centred on the same coordinate. A camera at ENU position
  `(e, n, u)` therefore sits at pixel `(512 + 2e, 512 - 2n)` of that raster.
* `camera_to_world_enu = colmap_to_enu @ inv(world_to_camera)` with the rotation block renormalised
  (divided by `scale_colmap_to_metres`).
* `index` is the position in the `frames` list, which is sorted by filename; the split files refer to these indices.

## Benchmark protocol

Each scene is evaluated with 1, 2 or 3 context (input) views and 4 target (held-out) views, see
`splits/benchmark_{1,2,3}view.json` (also embedded in each camera JSON). Frame 0 is always the first context view;
additional context views are the frames whose COLMAP co-visibility IoU with frame 0 is closest to 0.15; the four
targets were picked from a uniform 20 % subsample of the frames to have co-visibility IoU closest to 0.1, 0.2, 0.3
and 0.4 with the context set. Inputs are resized so the short side is 518 px and centre-cropped to 518x518; PSNR,
SSIM and LPIPS are computed on the target views at that resolution.

## Regenerating

```bash
python data/export_cameras.py tandt --root /path/to/tanks_and_temples_outdoor
```
