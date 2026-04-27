from django.core.management.base import BaseCommand
from pathlib import Path
import pandas as pd
from geoaligner.models import PointCloudSet, ImageCamera
from geoaligner.utils.point_cloud_file import convert_and_save_colmap_points
from geoaligner.utils.camera_convention_converter import convert_and_save_posed_images


class Command(BaseCommand):
    help = (
        "Adds a DL3DV-10K localizable scene to the database.\n\n"
        "Creates a PointCloudSet from the scene's COLMAP sparse model and saves\n"
        "the provided posed images as ImageCamera entries.  The point cloud and\n"
        "camera poses are converted to ENU world coordinates before saving.\n\n"
        "Expected dataset layout:\n"
        "  <dataset_path>/<scene>/gaussian_splat/sparse/0/  (cameras.bin, images.bin, points3D.bin)\n\n"
        "Expected CSV format (--dl3dv_csv_path):\n"
        "  scene,Lat-Long,...\n"
        "  <scene_hash>,\"<lat>, <lon>\",...\n\n"
        "Example:\n"
        "  python manage.py add_dl3dv_benchmark_localizable \\\n"
        "    --dl3dv_csv_path /data/dl3dv.csv \\\n"
        "    --dataset_path /data/DL3DV-10K-Benchmark_localizable \\\n"
        "    --scene 54bf355ca7e08ed1bc86f5772e564ac0f92981ca25dab24d86b694e915fc4c43 \\\n"
        "    --images /data/.../images_4/frame_00010.png /data/.../images_4/frame_00020.png"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dl3dv_csv_path",
            type=str,
            required=True,
            help="Path to the DL3DV CSV file. Must have 'scene' and 'Lat-Long' columns, "
                 "where 'Lat-Long' is formatted as '<lat>, <lon>'.",
        )
        parser.add_argument(
            "--dataset_path",
            type=str,
            required=True,
            help="Root directory of the DL3DV-10K localizable dataset. "
                 "Scenes are expected at <dataset_path>/<scene>/gaussian_splat/sparse/0/.",
        )
        parser.add_argument(
            "--scene",
            type=str,
            required=True,
            help="Scene hash to process (must match a row in the CSV).",
        )
        parser.add_argument(
            "--images",
            nargs="+",
            type=str,
            required=True,
            help="One or more absolute paths to posed images for this scene. "
                 "If the path contains an 'images_N' folder the intrinsics are scaled by N. "
                 "Note: re-running with the same images creates duplicate ImageCamera entries.",
        )

    def handle(self, *args, **options):
        # DL3DV points are in OpenCV convention, so we convert poses to ENU world coordinates.
        to_enu = True

        dl3dv_csv_path = Path(options["dl3dv_csv_path"])
        dataset_path = Path(options["dataset_path"])
        scene = options["scene"]
        images = [Path(p) for p in options["images"]]

        df = pd.read_csv(dl3dv_csv_path)
        df = df[~df['Lat-Long'].isna()]
        df = df[['scene', 'Lat-Long']]
        df = df.loc[df['scene'] == scene]

        for _, row in df.iterrows():
            row_scene = row['scene']
            latlon = row['Lat-Long']
            submodel_path = dataset_path / row_scene / 'gaussian_splat' / 'sparse' / '0'

            if PointCloudSet.objects.filter(name__exact=row_scene).exists():
                pc_set = PointCloudSet.objects.get(name__exact=row_scene)
                self.stdout.write(
                    self.style.WARNING(f"Found {row_scene} PointCloudSet")
                )
            else:
                lat, lon = latlon.split(', ')

                saved_point_cloud_name = convert_and_save_colmap_points(submodel_path, row_scene, to_enu=to_enu)

                pc_set = PointCloudSet(
                    name=str(row_scene),
                    latitude=lat,
                    longitude=lon,
                    point_cloud_file=saved_point_cloud_name,
                )
                pc_set.save()

                self.stdout.write(
                    self.style.SUCCESS(f"Successfully added {row_scene} point cloud")
                )

            for image_path in images:
                saved_image_name, camera_json = convert_and_save_posed_images(submodel_path, image_path, row_scene, to_enu=to_enu)
                ic = ImageCamera(
                      point_cloud_set=pc_set,
                      image=saved_image_name,
                      camera=camera_json,
                      name=image_path.name,
                )
                ic.save()
