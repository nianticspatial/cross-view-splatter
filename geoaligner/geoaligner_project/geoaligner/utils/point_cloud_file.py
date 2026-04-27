from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import os
from pathlib import Path
import numpy as np
import pandas as pd
from geoaligner.utils.colmap_parsing_utils import read_points3D_binary
from geoaligner.utils.colmap_to_enu import convert_point_to_enu


class PointCloudFile:
    def __init__(self):
        self._xyz = None
        self._rgb = None
        pass

    def save(self, save_path=None):
        data_dict = {'xyz': self._xyz.astype(np.float32).reshape(-1), 'rgb': self._rgb.astype(np.uint8).reshape(-1)}
        df = pd.DataFrame.from_dict(data_dict)
        return df.to_parquet(path=save_path, index=False)

    @staticmethod
    def load(load_path):
        if Path(load_path).suffix != ".parquet":
            raise ValueError('PointCloudFile loads .parquet files only')
        df = pd.read_parquet(load_path)
        point_cloud = PointCloudFile()
        point_cloud._xyz = df['xyz'].to_numpy().reshape(-1, 3)
        point_cloud._rgb = df['rgb'].to_numpy().reshape(-1, 3)
        return point_cloud

    @staticmethod
    def from_colmap_points3D(points3D_path, to_enu):
        point_cloud = PointCloudFile()
        colmap_points = read_points3D_binary(points3D_path)
        xyz = np.stack([p.xyz for p in colmap_points.values()]).astype(np.float32)

        if to_enu:
            # first convert opencv to enu
            xyz = convert_point_to_enu(xyz)

        point_cloud._xyz = xyz

        rgb = np.stack([p.rgb for p in colmap_points.values()]).astype(np.uint8)
        point_cloud._rgb = rgb
        return point_cloud

    @property
    def xyz(self):
        return self._xyz.reshape(-1).tolist()

    @property
    def rgb(self):
        return self._rgb.reshape(-1).tolist()


def convert_and_save_colmap_points(points_path, scene, to_enu):
    if Path(points_path).is_dir():
        points_path = Path(points_path) / 'points3D.bin'
    point_cloud = PointCloudFile.from_colmap_points3D(points_path, to_enu=to_enu)
    point_cloud_path_in_media = default_storage.get_available_name(os.path.join('point_clouds', f"{scene}.parquet"))
    saved_point_cloud_name = default_storage.save(point_cloud_path_in_media, ContentFile(point_cloud.save()))
    return saved_point_cloud_name
