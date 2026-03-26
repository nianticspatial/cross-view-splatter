# Cross-View Splatter: Feed-Forward View Synthesis with Georeferenced Images


[Matias Turkulainen](https://maturk.github.io/)<sup>1*</sup>, [Akshay Krishnan](https://akshay-krishnan.github.io)<sup>2</sup>, [Filippo Aleotti](https://filippoaleotti.github.io/website/)<sup>3</sup>, [Mohamed Sayed](https://masayed.com)<sup>3</sup>, [Guillermo Garcia-Hernando](https://guiggh.github.io)<sup>3</sup>, [Juho Kannala](https://users.aalto.fi/~kannalj1/)<sup>1,4</sup>, [Arno Solin](https://users.aalto.fi/~asolin/)<sup>1,5</sup>, [Gabriel Brostow](http://www0.cs.ucl.ac.uk/staff/g.brostow/)<sup>3,6</sup>, [Daniyar Turmukhambetov](https://dantkz.github.io/)<sup>3</sup>

<sup>1</sup>Aalto University, <sup>2</sup>Georgia Tech, <sup>3</sup>Niantic Spatial, <sup>4</sup>University of Oulu, <sup>5</sup>ELLIS Institute Finland, <sup>6</sup>UCL


[🏠 `Website`](https://nianticspatial.github.io/cross-view-splatter/) [📚 `BibTeX`](#bibtex)

## News

[2026-03-26] Release geolocalized Tanks and Temples and DL3DV dataset information.


## Overview
This repository contains code and data for `Cross-View Splatter`.

Code coming soon...

## Geolocalized Benchmark Dataset
We propose a new task, referred to as "novel-view synthesis with georeferenced images" and construct a suitable benchmark dataset by pairing selected outdoor scenes from Tanks and Temples and DL3DV datasets with orhographic satellite imagery.
We manually register and 3DoF align satellite images to COLMAP reconstructions for these scenes. In `./data` folder, we release JSON files for Tanks and Temples and DL3DV containing, for each scene, the queried satellite image location (`latitude`, `longitude`) together with an SE(3) transform that maps the COLMAP point cloud into the satellite-aligned reference frame.

Each JSON entry provides the scene identifier (`name`), the satellite query location (`latitude`, `longitude`), and a `transform` with quaternion rotation, 3D translation, and isotropic scale.

<details>
<summary>COLMAP-to-geoaligned transform for a scene entry can be constructed as follows: </summary>

```python
import json
import numpy as np
from scipy.spatial.transform import Rotation as R

def colmap_to_geoaligned(scene):
	"""Return the 4x4 transform that aligns the COLMAP point cloud to the satellite image at the query location."""
	transform_data = scene["fields"]["transform"]
	rot = transform_data["rotation"]
	trans = transform_data["translation"]
	scale = transform_data["scale"]["x"]

	rot = [rot["_x"], rot["_y"], rot["_z"], rot["_w"]]
	translation_vec = [trans["x"], trans["y"], trans["z"]]

	colmap2georef = np.identity(4)
	rotation_matrix_3x3 = R.from_quat(np.array(rot)).as_matrix()
	colmap2georef[0:3, 0:3] = rotation_matrix_3x3 * scale
	colmap2georef[0:3, 3] = np.array(translation_vec)
	return colmap2georef

with open("./data/dl3dv_point_cloud_transform_enu.json", "r") as f:
	scene_entries = json.load(f)

scene = scene_entries[0]
colmap2georef = colmap_to_geoaligned(scene)
```

</details>





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