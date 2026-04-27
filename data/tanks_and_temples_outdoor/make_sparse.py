from pathlib import Path
import sqlite3
from PIL import Image
import numpy as np

from scipy.spatial.transform import Rotation as R


def make_cameras_txt(model_folder, images_path, image_names, image_ids, intrinsics):
    mean_intrinsics = np.stack(list(intrinsics.values())).mean(0)
    share_intrinsics = True
    for intrinsic in intrinsics.values():
        share_intrinsics = share_intrinsics and np.allclose(mean_intrinsics, intrinsic)
    
    widths, heights = [], []
    for image_name in image_names:
        image_width, image_height = Image.open(images_path / image_name).size
        widths.append(image_width)
        heights.append(image_height)
    share_intrisics = share_intrinsics and all([widths[0] == w for w in widths]) and all([heights[0] == h for h in heights])
    
    if share_intrinsics:
        with open(model_folder / 'cameras.txt', 'w') as f:
            f.write('# Camera list with one line of data per camera:\n')
            f.write('#   CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]\n')
            f.write(f'# Number of cameras: 1\n')
            fx = intrinsics[image_names[0]][0, 0]
            fy = intrinsics[image_names[0]][1, 1]
            cx = intrinsics[image_names[0]][0, 2]
            cy = intrinsics[image_names[0]][1, 2]
            f.write(f'1 PINHOLE {widths[0]} {heights[0]} {fx} {fy} {cx} {cy}\n')
    else:
        with open(model_folder / 'cameras.txt', 'w') as f:
            f.write('# Camera list with one line of data per camera:\n')
            f.write('#   CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]\n')
            f.write(f'# Number of cameras: {len(image_names)}\n')
            for image_name in image_names:
                image_idx = image_ids[image_name]
                fx = intrinsics[image_name][0, 0]
                fy = intrinsics[image_name][1, 1]
                cx = intrinsics[image_name][0, 2]
                cy = intrinsics[image_name][1, 2]
                image_width, image_height = Image.open(images_path / image_name).size
                f.write(f'{image_idx} PINHOLE {image_width} {image_height} {fx} {fy} {cx} {cy}\n')
    return share_intrinsics


def make_images_txt(model_folder, images_path, image_names, image_ids, extrinsics, share_intrinsics):
    with open(model_folder / 'images.txt', 'w') as f:
        for image_name in image_names:
            image_idx = image_ids[image_name]
            Tmat = extrinsics[image_name]
            Rmat = Tmat[:3, :3]
            tvec = Tmat[:3, 3]
            qvec = R.from_matrix(Rmat).as_quat(scalar_first=True)
            cam_id = 1 if share_intrinsics else image_idx
            f.write(f'{image_idx} {qvec[0]} {qvec[1]} {qvec[2]} {qvec[3]} {tvec[0]} {tvec[1]} {tvec[2]} {cam_id} {image_name}\n')
            f.write('\n')


def make_sparse(output_path, images_path, image_names, image_ids, extrinsics, intrinsics):
    model_folder = output_path / 'input_sparse' / '0'
    model_folder.mkdir(exist_ok=True, parents=True)

    if not (output_path / 'images').exists():
        (output_path / 'images').symlink_to(images_path.absolute())

    share_intrinsics = make_cameras_txt(model_folder, images_path, image_names, image_ids, intrinsics)
    make_images_txt(model_folder, images_path, image_names, image_ids, extrinsics, share_intrinsics)
    open(model_folder / 'points3D.txt', 'w').close()
 

def get_image_names(images_path):
    image_names = sorted([img.name for img in images_path.glob('*.jpg')])
    return image_names


def get_image_ids(database_path):
    image_ids = {}
    db = sqlite3.connect(database_path)
    for image_id, image_name in db.execute('SELECT image_id, name FROM images'):
        image_ids[image_name] = image_id
    return image_ids


def get_cams(cams_path):
    cam_files = cams_path.glob('*_cam.txt')
    extrinsics, intrinsics = {}, {}
    for cam_file in cam_files:
        with open(cam_file) as f:
            lines = [line.rstrip() for line in f.readlines()]
        # extrinsics: line [1,5), 4x4 matrix
        extrinsic = np.fromstring(" ".join(lines[1:5]), dtype=np.float32, sep=" ")
        extrinsic = extrinsic.reshape((4, 4))
        # intrinsics: line [7-10), 3x3 matrix
        intrinsic = np.fromstring(" ".join(lines[7:10]), dtype=np.float32, sep=" ")
        intrinsic = intrinsic.reshape((3, 3))
        extrinsics[cam_file.name.replace('_cam.txt', '.jpg')] = extrinsic
        intrinsics[cam_file.name.replace('_cam.txt', '.jpg')] = intrinsic
    return extrinsics, intrinsics


if __name__ == "__main__":
    scenes = ["Barn", "Courthouse", "Family", "Francis", "Horse", "Ignatius", "Lighthouse", "Playground", "Temple", "Truck",]

    for scene in scenes:
        target = Path('data') / scene
        images_path = target / 'images'
        output_path = Path("colmap") / scene
        output_path.mkdir(exist_ok=True, parents=True)
        image_names = get_image_names(images_path)
        image_ids = get_image_ids(output_path / 'database.db')
        extrinsics, intrinsics = get_cams(target / 'cams')

        for image_name in image_names:
            assert image_name in extrinsics
            assert image_name in intrinsics

        make_sparse(output_path, images_path, image_names, image_ids, extrinsics, intrinsics)
