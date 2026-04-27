from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

import os
import numpy as np
from pathlib import Path
from typing import Union, Tuple
from geoaligner.utils.colmap_parsing_utils import qvec2rotmat, rotmat2qvec, read_cameras_binary, read_images_binary
from geoaligner.utils.colmap_to_enu import opencv_w2c_to_enu_w2c


CV_TO_GL_CONVERSION = np.array([
        [1,  0,  0,  0],
        [0, -1,  0,  0],
        [0,  0, -1,  0],
        [0,  0,  0,  1]
    ])


def opengl_c2w_to_opencv_w2c(qvec_gl, tvec_gl):
    # Convert OpenGL c2w quaternion and translation into matrix
    c2w_gl = transform_vecs_to_mat(qvec_gl, tvec_gl)
    # convert OpenGL c2w into OpenGL w2c
    w2c_gl = invert_transform_mat(c2w_gl)

    # OpenGL w2c_gl is actually w2c_gl = CV_TO_GL_CONVERSION @ w2c_cv
    # So we invert it like so:
    w2c_cv = np.linalg.inv(CV_TO_GL_CONVERSION) @ w2c_gl

    # Decompose OpenCV w2c into quaternion and translation
    qvec_cv, tvec_cv = transform_mat_to_vecs(w2c_cv)
    return qvec_cv, tvec_cv


def invert_transform_vecs(qvec, tvec):
    Tmat = transform_vecs_to_mat(qvec, tvec)
    invTmat = invert_transform_mat(Tmat)
    return transform_mat_to_vecs(invTmat)


def transform_mat_to_vecs(Tmat):
    qvec = rotmat2qvec(Tmat[:3, :3])
    tvec = Tmat[:3, 3]
    return qvec, tvec


def transform_vecs_to_mat(qvec, tvec):
    Rmat = qvec2rotmat(qvec)
    tvec = tvec.reshape(3, 1)

    Tmat = np.concatenate([Rmat, tvec], axis=1)
    Tmat = np.concatenate([Tmat, np.eye(4)[3:4, :]], axis=0)
    return Tmat


def invert_transform_mat(transform):
    return np.linalg.inv(transform)


def opencv_w2c_to_opengl_c2w(qvec, tvec):
    """
    qvec: wxyz
    tvec: xyz
    """
    # The R_w2c and t_w2c from COLMAP represent the transformation X_cam = R * X_world + t
    w2c = transform_vecs_to_mat(qvec, tvec)

    # apply transform
    w2c_gl = CV_TO_GL_CONVERSION @ w2c

    # To get the camera-to-world matrix (c2w), we need to invert this.
    c2w_gl = invert_transform_mat(w2c_gl)

    # Decompose the final OpenGL c2w matrix into quaternion and translation
    # for three.js
    qvec_gl, tvec_gl = transform_mat_to_vecs(c2w_gl)

    return qvec_gl, tvec_gl


def get_camera_json_from_colmap(submodel_path: Union[str, Path], image_path: Union[str, Path], to_enu: bool) -> str:
    # load colmap submodel (sparse/0/*.bin files),
    # find the pose and camera parameters of an image,
    #
    # if to_enu: convert extrinsics from opencv to enu to opengl
    # else: convert the extrinsics from opencv to opengl coordinate system
    #
    # compute correct intrinsics
    # return json of the extrinsics and intrinsics suitable for geoaligner.js renderers
    if isinstance(submodel_path, str):
        submodel_path = Path(submodel_path)
    if isinstance(image_path, str):
        image_path = Path(image_path)
    cameras = read_cameras_binary(submodel_path / 'cameras.bin')
    images = read_images_binary(submodel_path / 'images.bin')
    print(cameras[1])

    image_name = image_path.name
    image_name_to_colmap_id = dict([(image_data.name, image_id) for image_id, image_data in images.items()])
    image_id = image_name_to_colmap_id[image_name]

    qvec, tvec = images[image_id].qvec, images[image_id].tvec

    if to_enu:
        qvec, tvec = opencv_w2c_to_enu_w2c(qvec, tvec)

    qvec, tvec = opencv_w2c_to_opengl_c2w(qvec, tvec)
    camera_id = images[image_id].camera_id

    scale_factor = 1
    if "/images_" in str(image_path):
        images_folder_name = [p for p in image_path.parts if p.startswith("images_")][0]
        scale_factor = int(images_folder_name.removeprefix("images_"))

    result = {
        "rotation": dict([(name, value.item()) for name, value in zip(["_w", "_x", "_y", "_z"], qvec)]),
        "translation": dict([(name, value.item()) for name, value in zip(["x", "y", "z"], tvec)]),
        "intrinsics": {
            "fx": cameras[camera_id].params[0] / scale_factor,
            "fy": cameras[camera_id].params[1] / scale_factor,
            "cx": cameras[camera_id].params[2] / scale_factor,
            "cy": cameras[camera_id].params[3] / scale_factor,
            "w": cameras[camera_id].width / scale_factor,
            "h": cameras[camera_id].height / scale_factor,
        }
    }
    return result


def convert_and_save_posed_images(submodel_path, image_path, scene, to_enu) -> Tuple[str, dict]:
    camera_json = get_camera_json_from_colmap(submodel_path, image_path, to_enu)
    web_image_name = f"{scene}_{image_path.name}"
    # copy the image
    image_path_in_media = default_storage.get_available_name(os.path.join('posed_images', web_image_name))
    saved_image_name = default_storage.save(image_path_in_media, ContentFile(image_path.read_bytes()))
    return saved_image_name, camera_json
