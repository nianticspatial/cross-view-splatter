import numpy as np
from pathlib import Path
from geoaligner.utils.colmap_parsing_utils import read_model, write_model, Point3D, Image
from geoaligner.utils.colmap_parsing_utils import qvec2rotmat, rotmat2qvec


CV_TO_ENU_CONVERSION = np.array([
        [1,  0,  0,  0],
        [0, 0,  1,  0],
        [0,  -1, 0,  0],
        [0,  0,  0,  1]
    ])


def opencv_points_transform_to_enu(qvec, tvec):
    # points transform T get converted with CV_TO_ENU_CONVERSION @ T @ np.linalg.inv(CV_TO_ENU_CONVERSION)
    # so that
    # Original relation of w2c @ T @ xyz
    # is still consistent:
    # (w2c @ np.linalg.inv(CV_TO_ENU_CONVERSION) @ CV_TO_ENU_CONVERSION @ T @ np.linalg.inv(CV_TO_ENU_CONVERSION) @ CV_TO_ENU_CONVERSION @ xyz)
    R = qvec2rotmat(qvec)
    t = tvec.reshape(3, 1)

    T = np.concatenate([R, t], axis=1)
    T = np.concatenate([T, np.eye(4)[3:4, :]], axis=0)

    enu_T = CV_TO_ENU_CONVERSION @ T @ np.linalg.inv(CV_TO_ENU_CONVERSION)
    enu_qvec = rotmat2qvec(enu_T[:3, :3])
    enu_tvec= enu_T[:3, 3]

    return enu_qvec, enu_tvec


def convert_point_to_enu(xyz):
    # points get converted with CV_TO_ENU_CONVERSION
    if xyz.ndim == 1:
        return CV_TO_ENU_CONVERSION[:3, :3] @ xyz
    elif xyz.ndim == 2 and xyz.shape[1] == 3:
        return (CV_TO_ENU_CONVERSION[np.newaxis, :3, :3] @ xyz[:, :, np.newaxis])[:, :, 0]
    else:
        raise NotImplementedError()


def opencv_w2c_to_enu_w2c(qvec, tvec):
    # poses get converted with inverse of CV_TO_ENU_CONVERSION
    # so that
    # Original relation of w2c @ xyz
    # is still consistent:
    # (w2c @ np.linalg.inv(CV_TO_ENU_CONVERSION) @ CV_TO_ENU_CONVERSION @ xyz)
    R_w2c = qvec2rotmat(qvec)
    t_w2c = tvec.reshape(3, 1)

    w2c = np.concatenate([R_w2c, t_w2c], axis=1)
    w2c = np.concatenate([w2c, np.eye(4)[3:4, :]], axis=0)

    enu_w2c = w2c @ np.linalg.inv(CV_TO_ENU_CONVERSION)
    enu_qvec = rotmat2qvec(enu_w2c[:3, :3])
    enu_tvec = enu_w2c[:3, 3]
    return enu_qvec, enu_tvec
