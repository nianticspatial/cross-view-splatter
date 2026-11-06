# DL3DV-Benchmark — georeferenced outdoor scenes

Forty outdoor scenes from the [DL3DV-10K Benchmark](https://github.com/DL3DV-10K/Dataset) (Ling et al. 2024,
CC BY-NC 4.0) that we could localise on satellite imagery. Scenes are identified by their DL3DV hash; `dl3dv.csv`
gives the place name, coordinate and map link of each.

## Files in this folder

| File | Content |
|---|---|
| `cameras/<hash>.json` | intrinsics, per-frame COLMAP-frame poses, metric ENU poses, benchmark splits (one file per scene) |
| `splits/benchmark_{1,2,3}view.json` | context / target frame indices used in the paper (1, 2 or 3 context views) |
| `scenes.json` | scene list with place name, latitude / longitude, frame count and image size |
| `dl3dv.csv` | place name, Google Maps link and coordinate per scene |
| `../dl3dv_point_cloud_transform_enu.json` | raw geoaligner export (COLMAP -> satellite transform) |
| `add.sh` | how a scene was loaded into the geoaligner |

## Images and poses

We use the official DL3DV-10K Benchmark release unchanged: download the 40 scenes listed in `scenes.json` from
DL3DV and keep `gaussian_splat/images_4/` (960x540 PNG) and `gaussian_splat/sparse/0/` (COLMAP, one PINHOLE camera at
the undistorted full resolution, about 3800x2130, slightly different per scene). The poses in `cameras/<hash>.json` are copied from that COLMAP model, so
nothing else is needed to reproduce our setup.

Frames are listed in sorted filename order, restricted to the files that have a COLMAP pose. Two scenes have gaps:
`286239bd…` lacks `frame_00220.png`, and `d9b63766…` has no pose for frames 209–212. Because of this, `index` is not
always `frame number - 1`; always resolve indices through the `frames` list (or use the `*_files` entries of the splits).

## Camera JSON format

Same layout as for Tanks and Temples (see `../tanks_and_temples_outdoor/README.md`), with these differences:

* `frames[*].file` is `images_4/frame_XXXXX.png` and `colmap_image_id` is the id in `images.bin`.
* `cameras["1"]` holds the COLMAP intrinsics at the full undistorted resolution plus an `images_4` sub-entry rescaled
  to 960x540 (`fx * 960 / width`, `fy * 540 / height`, …), which is what the released images need.
* **Axis change.** The DL3DV point clouds were loaded into the geoaligner after the axis change
  `(x, y, z) -> (x, z, -y)`, so the raw transform in `../dl3dv_point_cloud_transform_enu.json` applies to points in
  that frame, *not* directly to COLMAP coordinates. `colmap_to_enu` in `cameras/<hash>.json` already includes the
  axis change (`T_raw @ [[1,0,0],[0,0,1],[0,-1,0]]`), so `p_enu = colmap_to_enu @ p_colmap` works directly.
  Tanks and Temples does not need this step.

## Benchmark protocol

Identical to Tanks and Temples: 1 / 2 / 3 context views (frame 0 plus frames at co-visibility IoU ≈ 0.15), 4 target
views at IoU ≈ 0.1, 0.2, 0.3, 0.4, images resized to short side 518 px and centre-cropped to 518x518, PSNR / SSIM /
LPIPS on the targets.

## Regenerating

```bash
python data/export_cameras.py dl3dv --root /path/to/DL3DV-10K-Benchmark_localizable
```
