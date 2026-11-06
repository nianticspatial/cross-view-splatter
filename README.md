# Cross-View Splatter: Feed-Forward View Synthesis with Georeferenced Images


[Matias Turkulainen](https://maturk.github.io/)<sup>1*</sup>, [Akshay Krishnan](https://akshay-krishnan.github.io)<sup>2</sup>, [Filippo Aleotti](https://filippoaleotti.github.io/website/)<sup>3</sup>, [Mohamed Sayed](https://masayed.com)<sup>3</sup>, [Guillermo Garcia-Hernando](https://guiggh.github.io)<sup>3</sup>, [Juho Kannala](https://users.aalto.fi/~kannalj1/)<sup>1,4</sup>, [Arno Solin](https://users.aalto.fi/~asolin/)<sup>1,5</sup>, [Gabriel Brostow](http://www0.cs.ucl.ac.uk/staff/g.brostow/)<sup>3,6</sup>, [Daniyar Turmukhambetov](https://dantkz.github.io/)<sup>3</sup>

<sup>1</sup>Aalto University, <sup>2</sup>Georgia Tech, <sup>3</sup>Niantic Spatial, <sup>4</sup>University of Oulu, <sup>5</sup>ELLIS Institute Finland, <sup>6</sup>UCL


[🏠 `Website`](https://nianticspatial.github.io/cross-view-splatter/) [📚 `BibTeX`](#bibtex)

## News

[2026-11-06] Release per-scene camera poses, benchmark splits and the Tanks and Temples images.

[2026-03-26] Release geolocalized Tanks and Temples and DL3DV dataset information.


## Overview
This repository contains code and data for `Cross-View Splatter`.

Code coming soon...

## Geolocalized Benchmark Dataset
We propose a new task, referred to as "novel-view synthesis with georeferenced images", and construct a suitable benchmark dataset by pairing selected outdoor scenes from Tanks and Temples (10 scenes) and DL3DV (40 scenes) with orthographic satellite imagery.
We manually registered the COLMAP reconstructions of these scenes to north-up satellite images with the [geoaligner](geoaligner/) tool.

The `./data` folder contains, per dataset:

| | Tanks and Temples | DL3DV-Benchmark |
|---|---|---|
| Per-scene cameras (intrinsics, poses, metric georeferenced poses, splits) | [`data/tanks_and_temples_outdoor/cameras/`](data/tanks_and_temples_outdoor/cameras/) | [`data/DL3DV-Benchmark/cameras/`](data/DL3DV-Benchmark/cameras/) |
| Benchmark splits (1 / 2 / 3 context views, 4 targets) | [`data/tanks_and_temples_outdoor/splits/`](data/tanks_and_temples_outdoor/splits/) | [`data/DL3DV-Benchmark/splits/`](data/DL3DV-Benchmark/splits/) |
| Scene list with coordinates | [`scenes.json`](data/tanks_and_temples_outdoor/scenes.json) | [`scenes.json`](data/DL3DV-Benchmark/scenes.json) |
| Raw geoaligner export (COLMAP -> satellite transform) | [`tanks_and_temples_outdoor_point_cloud_transform_enu.json`](data/tanks_and_temples_outdoor_point_cloud_transform_enu.json) | [`dl3dv_point_cloud_transform_enu.json`](data/dl3dv_point_cloud_transform_enu.json) |
| Images | Google Drive, see [`data/tanks_and_temples_outdoor/README.md`](data/tanks_and_temples_outdoor/README.md) | official DL3DV-10K Benchmark release |
| Conventions and protocol | [README](data/tanks_and_temples_outdoor/README.md) | [README](data/DL3DV-Benchmark/README.md) |

Satellite imagery is not redistributed; fetch a north-up raster centred on each scene's `latitude` / `longitude` from the provider of your choice (we use 1024x1024 px at 2 px/m).

### Camera poses

Every `cameras/<scene>.json` lists, per frame, the world-to-camera pose in the COLMAP frame (`qvec_wxyz`, `tvec`, `world_to_camera`) and a metric camera-to-world pose in a local east-north-up frame (`camera_to_world_enu`: x = east, y = north, z = up, origin at the scene's `latitude` / `longitude`, z ≈ 0 at ground level). The 4x4 similarity `colmap_to_enu` relates the two:

```python
import json, numpy as np

scene = json.load(open("data/tanks_and_temples_outdoor/cameras/Barn.json"))
T = np.array(scene["colmap_to_enu"])                      # p_enu = T @ p_colmap, 3x3 block = scale * R
for f in scene["frames"][:3]:
    w2c = np.array(f["world_to_camera"])                  # OpenCV, COLMAP frame
    c2w_enu = np.array(f["camera_to_world_enu"])          # metric SE(3), == T @ inv(w2c) with R renormalised
    print(f["file"], "east/north/up [m]:", c2w_enu[:3, 3])
```

<details>
<summary>Building the transform from the raw geoaligner JSON instead</summary>

The raw export stores a quaternion (`_x, _y, _z, _w`, scalar last), a translation and an isotropic scale; the point cloud is rotated, then scaled, then translated:

```python
import json
import numpy as np
from scipy.spatial.transform import Rotation as R

def colmap_to_geoaligned(scene):
	t = scene["fields"]["transform"]
	q = t["rotation"]
	T = np.identity(4)
	T[:3, :3] = R.from_quat([q["_x"], q["_y"], q["_z"], q["_w"]]).as_matrix() * t["scale"]["x"]
	T[:3, 3] = [t["translation"]["x"], t["translation"]["y"], t["translation"]["z"]]
	return T

# Tanks and Temples: applies directly to COLMAP coordinates.
scene = json.load(open("data/tanks_and_temples_outdoor_point_cloud_transform_enu.json"))[0]
T = colmap_to_geoaligned(scene)                                   # p_enu = T @ p_colmap

# DL3DV: the point clouds were aligned after the axis change (x, y, z) -> (x, z, -y).
M = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], dtype=float)
scene = json.load(open("data/dl3dv_point_cloud_transform_enu.json"))[0]
T = colmap_to_geoaligned(scene) @ M                               # p_enu = T @ p_colmap
```

</details>

### Benchmark protocol

Each scene is evaluated with 1, 2 or 3 context (input) views and 4 held-out target views (`splits/benchmark_{1,2,3}view.json`; indices refer to the `frames` list of the camera JSON, filenames are given alongside). Frame 0 is always a context view; the other context views are the frames with COLMAP co-visibility IoU closest to 0.15 to frame 0, and the targets were chosen (from a uniform 20 % subsample) to have co-visibility IoU closest to 0.1, 0.2, 0.3 and 0.4 with the context set. Images are resized to a short side of 518 px and centre-cropped to 518x518; PSNR, SSIM and LPIPS are reported on the target views.

## BibTeX

If you find this work useful for your research, please consider citing our paper:

```bibtex
@inproceedings{turkulainen2026crossviewsplatter,
	title     = {{Cross-View Splatter: Feed-Forward View Synthesis with Georeferenced Images}},
	author    = {Turkulainen, Matias and Krishnan, Akshay and Aleotti, Filippo and Sayed, Mohamed and Garcia-Hernando, Guillermo and Kannala, Juho and Solin, Arno and Brostow, Gabriel and Turmukhambetov, Daniyar},
	booktitle = {Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)},
	year      = {2026}
}
```