#!/usr/bin/env python3
"""Export per-scene camera intrinsics, poses and benchmark splits as JSON.

Writes ``data/tanks_and_temples_outdoor/cameras/<Scene>.json`` and
``data/DL3DV-Benchmark/cameras/<scene_hash>.json``.  See the README files next to the
outputs for the conventions.  Needs only numpy and scipy.

    python data/export_cameras.py tandt --root /path/to/tanks_and_temples_outdoor
    python data/export_cameras.py dl3dv --root /path/to/DL3DV-Benchmark/DL3DV-10K-Benchmark_localizable
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import struct
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

HERE = Path(__file__).resolve().parent

TANDT_SCENES = [
    "Barn",
    "Courthouse",
    "Family",
    "Francis",
    "Horse",
    "Ignatius",
    "Lighthouse",
    "Playground",
    "Temple",
    "Truck",
]

# DL3DV COLMAP models were aligned in the geoaligner after this axis change (x, y, z) -> (x, z, -y),
# i.e. the published DL3DV transform expects points in that frame. Tanks and Temples does not need it.
DL3DV_PRE_TRANSFORM = np.array(
    [[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], dtype=np.float64
)

CONVENTIONS = {
    "world_to_camera": "4x4 OpenCV extrinsic (camera x right, y down, z forward) mapping COLMAP world points to camera: "
    "p_cam = world_to_camera @ p_world. qvec_wxyz/tvec are the same pose in COLMAP images.txt convention.",
    "enu": "Local east-north-up frame in metres: x = east, y = north, z = up, origin at (latitude, longitude), "
    "z ~ 0 at ground level. The satellite raster is centred on the same (latitude, longitude).",
    "colmap_to_enu": "4x4 similarity: p_enu = colmap_to_enu @ p_colmap (homogeneous). The 3x3 block is "
    "scale_colmap_to_metres * R (not orthonormal). For DL3DV the axis change (x, y, z) -> (x, z, -y) that precedes the "
    "published transform is already folded in.",
    "camera_to_world_enu": "4x4 metric SE(3) camera-to-world pose in the ENU frame with orthonormal rotation, "
    "i.e. colmap_to_enu @ inv(world_to_camera) with the scale divided out of the rotation block.",
    "frame_index": "Position of the frame in the sorted frame list below; benchmark_splits refer to these indices.",
}

Camera = collections.namedtuple("Camera", ["id", "model", "width", "height", "params"])
Image = collections.namedtuple("Image", ["id", "qvec", "tvec", "camera_id", "name"])


# ----------------------------------------------------------------------------- COLMAP readers
def _read_next_bytes(fid, num_bytes, fmt):
    return struct.unpack("<" + fmt, fid.read(num_bytes))


def read_cameras_bin(path: Path) -> dict[int, Camera]:
    models = {
        0: ("SIMPLE_PINHOLE", 3),
        1: ("PINHOLE", 4),
        2: ("SIMPLE_RADIAL", 4),
        3: ("RADIAL", 5),
        4: ("OPENCV", 8),
    }
    cameras = {}
    with open(path, "rb") as fid:
        (num,) = _read_next_bytes(fid, 8, "Q")
        for _ in range(num):
            cam_id, model_id, width, height = _read_next_bytes(fid, 24, "iiQQ")
            name, n_params = models[model_id]
            params = _read_next_bytes(fid, 8 * n_params, "d" * n_params)
            cameras[cam_id] = Camera(cam_id, name, width, height, list(params))
    return cameras


def read_images_bin(path: Path) -> dict[int, Image]:
    images = {}
    with open(path, "rb") as fid:
        (num,) = _read_next_bytes(fid, 8, "Q")
        for _ in range(num):
            props = _read_next_bytes(fid, 64, "idddddddi")
            image_id, qvec, tvec, camera_id = props[0], props[1:5], props[5:8], props[8]
            name = b""
            while True:
                c = fid.read(1)
                if c == b"\x00":
                    break
                name += c
            (n_pts,) = _read_next_bytes(fid, 8, "Q")
            fid.read(24 * n_pts)
            images[image_id] = Image(
                image_id, np.array(qvec), np.array(tvec), camera_id, name.decode()
            )
    return images


def qvec_tvec_to_w2c(qvec_wxyz, tvec) -> np.ndarray:
    w2c = np.eye(4)
    w2c[:3, :3] = Rotation.from_quat(
        [qvec_wxyz[1], qvec_wxyz[2], qvec_wxyz[3], qvec_wxyz[0]]
    ).as_matrix()
    w2c[:3, 3] = tvec
    return w2c


def w2c_to_qvec_tvec(w2c: np.ndarray):
    q = Rotation.from_matrix(w2c[:3, :3]).as_quat()  # x y z w
    q = np.array([q[3], q[0], q[1], q[2]])
    if q[0] < 0:
        q = -q
    return q, w2c[:3, 3].copy()


# ----------------------------------------------------------------------------- geo transforms
def load_geo(path: Path) -> dict[str, dict]:
    out = {}
    for item in json.load(open(path)):
        f = item["fields"]
        q, t, s = (
            f["transform"]["rotation"],
            f["transform"]["translation"],
            f["transform"]["scale"]["x"],
        )
        T = np.eye(4)
        T[:3, :3] = Rotation.from_quat([q["_x"], q["_y"], q["_z"], q["_w"]]).as_matrix() * s
        T[:3, 3] = [t["x"], t["y"], t["z"]]
        out[f["name"]] = {
            "T": T,
            "scale": s,
            "latitude": f["latitude"],
            "longitude": f["longitude"],
        }
    return out


def enu_pose(colmap_to_enu: np.ndarray, scale: float, w2c: np.ndarray) -> np.ndarray:
    c2w = colmap_to_enu @ np.linalg.inv(w2c)
    c2w[:3, :3] /= scale
    return c2w


# ----------------------------------------------------------------------------- output helpers
def _r(x, nd=10):
    if isinstance(x, np.ndarray):
        x = x.tolist()
    if isinstance(x, list):
        return [_r(v, nd) for v in x]
    return round(float(x), nd)


def load_splits(split_dir: Path, scene: str, names: list[str]) -> dict:
    out = {}
    for k in ("1view", "2view", "3view"):
        entry = json.load(open(split_dir / f"benchmark_{k}.json"))[scene]
        out[k] = {
            "context": entry["context"],
            "target": entry["target"],
            "context_files": [names[i] for i in entry["context"]],
            "target_files": [names[i] for i in entry["target"]],
        }
    return out


def write_scene(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=1)
        f.write("\n")


def sanity(frames: list[dict], scene: str) -> None:
    c2w = np.array([f["camera_to_world_enu"] for f in frames])
    ups = -c2w[:, :3, 1]  # OpenCV camera -y is up
    z = c2w[:, 2, 3]
    err = np.abs(np.einsum("nij,nkj->nik", c2w[:, :3, :3], c2w[:, :3, :3]) - np.eye(3)).max()
    print(
        f"{scene:66s} n={len(frames):4d}  mean_up={np.round(ups.mean(0), 2)}  z[m] med={np.median(z):5.2f}  orthoerr={err:.1e}"
    )


# ----------------------------------------------------------------------------- Tanks and Temples
def read_cam_txt(path: Path):
    lines = [ln.rstrip() for ln in open(path)]
    ext = np.fromstring(" ".join(lines[1:5]), dtype=np.float64, sep=" ").reshape(4, 4)
    K = np.fromstring(" ".join(lines[7:10]), dtype=np.float64, sep=" ").reshape(3, 3)
    return K, ext


def export_tandt(root: Path, out_dir: Path) -> None:
    geo = load_geo(HERE / "tanks_and_temples_outdoor_point_cloud_transform_enu.json")
    split_dir = HERE / "tanks_and_temples_outdoor" / "splits"
    summary = []
    for scene in TANDT_SCENES:
        g = geo[scene]
        cam_files = sorted(
            p for p in (root / scene / "cams").iterdir() if p.name.endswith("_cam.txt")
        )
        names = [f"images/{p.name.replace('_cam.txt', '.jpg')}" for p in cam_files]
        Ks, w2cs = zip(*(read_cam_txt(p) for p in cam_files))
        assert all(np.allclose(K, Ks[0]) for K in Ks), scene
        from PIL import Image as PILImage  # only used to record the image size

        width, height = PILImage.open(root / scene / names[0]).size
        # cross-check against the released COLMAP model (poses were fixed to the cam.txt values)
        colmap_images = root / "colmap" / scene / "sparse" / "0" / "images.bin"
        if colmap_images.exists():
            by_name = {im.name: im for im in read_images_bin(colmap_images).values()}
            for name, w2c in zip(names, w2cs):
                im = by_name[Path(name).name]
                assert np.allclose(qvec_tvec_to_w2c(im.qvec, im.tvec), w2c, atol=1e-4), (
                    scene,
                    name,
                )
        frames = []
        for i, (name, w2c) in enumerate(zip(names, w2cs)):
            q, t = w2c_to_qvec_tvec(w2c)
            frames.append(
                {
                    "index": i,
                    "file": name,
                    "camera_id": 1,
                    "qvec_wxyz": _r(q),
                    "tvec": _r(t),
                    "world_to_camera": _r(w2c),
                    "camera_to_world_enu": _r(enu_pose(g["T"], g["scale"], w2c)),
                }
            )
        K = Ks[0]
        payload = {
            "dataset": "tanks_and_temples_outdoor",
            "scene": scene,
            "latitude": g["latitude"],
            "longitude": g["longitude"],
            "conventions": CONVENTIONS,
            "colmap_to_enu": _r(g["T"]),
            "scale_colmap_to_metres": g["scale"],
            "cameras": {
                "1": {
                    "model": "PINHOLE",
                    "width": width,
                    "height": height,
                    "fx": _r(K[0, 0]),
                    "fy": _r(K[1, 1]),
                    "cx": _r(K[0, 2]),
                    "cy": _r(K[1, 2]),
                }
            },
            "frames": frames,
            "benchmark_splits": load_splits(split_dir, scene, names),
        }
        write_scene(out_dir / f"{scene}.json", payload)
        sanity(frames, scene)
        summary.append(
            {
                "scene": scene,
                "latitude": g["latitude"],
                "longitude": g["longitude"],
                "num_frames": len(frames),
                "width": width,
                "height": height,
            }
        )
    with open(out_dir.parent / "scenes.json", "w") as f:
        json.dump(summary, f, indent=1)
        f.write("\n")


# ----------------------------------------------------------------------------- DL3DV
def export_dl3dv(root: Path, out_dir: Path) -> None:
    geo = load_geo(HERE / "dl3dv_point_cloud_transform_enu.json")
    split_dir = HERE / "DL3DV-Benchmark" / "splits"
    places = {}
    csv_path = HERE / "DL3DV-Benchmark" / "dl3dv.csv"
    if csv_path.exists():
        for row in csv.DictReader(open(csv_path)):
            places[row["scene"]] = row.get("Location Name", "")
    summary = []
    for scene in sorted(geo):
        g = geo[scene]
        sparse = root / scene / "gaussian_splat" / "sparse" / "0"
        cameras = read_cameras_bin(sparse / "cameras.bin")
        images = read_images_bin(sparse / "images.bin")
        by_name = {im.name: im for im in images.values()}
        img_dir = root / scene / "gaussian_splat" / "images_4"
        on_disk = sorted(p.name for p in img_dir.iterdir() if p.suffix.lower() in (".png", ".jpg"))
        names = [
            n for n in on_disk if n in by_name
        ]  # loader convention: sorted files present in COLMAP
        from PIL import Image as PILImage

        w4, h4 = PILImage.open(img_dir / names[0]).size
        frames = []
        for i, name in enumerate(names):
            im = by_name[name]
            w2c = qvec_tvec_to_w2c(im.qvec, im.tvec)
            frames.append(
                {
                    "index": i,
                    "file": f"images_4/{name}",
                    "colmap_image_id": im.id,
                    "camera_id": im.camera_id,
                    "qvec_wxyz": _r(im.qvec),
                    "tvec": _r(im.tvec),
                    "world_to_camera": _r(w2c),
                    "camera_to_world_enu": _r(
                        enu_pose(g["T"] @ DL3DV_PRE_TRANSFORM, g["scale"], w2c)
                    ),
                }
            )
        cams = {}
        for cid, cam in cameras.items():
            assert cam.model == "PINHOLE", cam
            fx, fy, cx, cy = cam.params
            cams[str(cid)] = {
                "model": "PINHOLE",
                "width": cam.width,
                "height": cam.height,
                "fx": _r(fx),
                "fy": _r(fy),
                "cx": _r(cx),
                "cy": _r(cy),
                "images_4": {
                    "width": w4,
                    "height": h4,
                    "fx": _r(fx * w4 / cam.width),
                    "fy": _r(fy * h4 / cam.height),
                    "cx": _r(cx * w4 / cam.width),
                    "cy": _r(cy * h4 / cam.height),
                },
            }
        payload = {
            "dataset": "DL3DV-Benchmark",
            "scene": scene,
            "place": places.get(scene, ""),
            "latitude": g["latitude"],
            "longitude": g["longitude"],
            "conventions": CONVENTIONS,
            "colmap_to_enu": _r(g["T"] @ DL3DV_PRE_TRANSFORM),
            "scale_colmap_to_metres": g["scale"],
            "cameras": cams,
            "frames": frames,
            "benchmark_splits": load_splits(split_dir, scene, [f["file"] for f in frames]),
        }
        write_scene(out_dir / f"{scene}.json", payload)
        sanity(frames, scene)
        summary.append(
            {
                "scene": scene,
                "place": places.get(scene, ""),
                "latitude": g["latitude"],
                "longitude": g["longitude"],
                "num_frames": len(frames),
                "width": w4,
                "height": h4,
            }
        )
    with open(out_dir.parent / "scenes.json", "w") as f:
        json.dump(summary, f, indent=1)
        f.write("\n")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("dataset", choices=["tandt", "dl3dv"])
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None, help="output cameras/ directory")
    args = ap.parse_args()
    if args.dataset == "tandt":
        export_tandt(args.root, args.out or HERE / "tanks_and_temples_outdoor" / "cameras")
    else:
        export_dl3dv(args.root, args.out or HERE / "DL3DV-Benchmark" / "cameras")


if __name__ == "__main__":
    main()
