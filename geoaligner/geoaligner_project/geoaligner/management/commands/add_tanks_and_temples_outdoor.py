from django.core.management.base import BaseCommand
from pathlib import Path
import json
from geoaligner.models import PointCloudSet, ImageCamera
from geoaligner.utils.point_cloud_file import convert_and_save_colmap_points
from geoaligner.utils.camera_convention_converter import convert_and_save_posed_images


class Command(BaseCommand):
    help = (
        "Adds a Tanks and Temples outdoor scene to the database.\n\n"
        "Creates a PointCloudSet from the scene's COLMAP sparse model and saves\n"
        "the provided posed images as ImageCamera entries.  Camera poses stay in\n"
        "the original COLMAP/OpenCV world coordinates (not converted to ENU).\n\n"
        "Expected dataset layout:\n"
        "  <dataset_path>/<scene>/sparse/0/  (cameras.bin, images.bin, points3D.bin)\n\n"
        "Expected JSON format (--lat_lon_json_path):\n"
        "  { \"<scene_lowercase>\": [<lat>, <lon>], ... }\n"
        "  e.g. { \"barn\": [38.01, -122.49], \"meetingroom\": [...] }\n\n"
        "Example:\n"
        "  python manage.py add_tanks_and_temples_outdoor \\\n"
        "    --lat_lon_json_path /data/tt_latlons.json \\\n"
        "    --dataset_path /data/tanks_and_temples_outdoor \\\n"
        "    --scene Barn \\\n"
        "    --images /data/tanks_and_temples_outdoor/Barn/images/00000080.jpg"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--lat_lon_json_path",
            type=str,
            required=True,
            help="Path to a JSON file mapping lowercase scene names to [lat, lon] pairs, "
                 "e.g. {\"barn\": [38.01, -122.49]}.",
        )
        parser.add_argument(
            "--dataset_path",
            type=str,
            required=True,
            help="Root directory of the Tanks and Temples outdoor dataset. "
                 "Scenes are expected at <dataset_path>/<scene>/sparse/0/.",
        )
        parser.add_argument(
            "--scene",
            type=str,
            required=True,
            help="Scene name as it appears in the dataset folder (e.g. 'Barn'). "
                 "The JSON lookup uses scene.lower().",
        )
        parser.add_argument(
            "--images",
            nargs="+",
            type=str,
            required=True,
            help="One or more absolute paths to posed images for this scene. "
                 "Note: re-running with the same images creates duplicate ImageCamera entries.",
        )

    def handle(self, *args, **options):
        # For Tanks and Temples, we opted for no ENU conversion,
        # So poses stay in the original COLMAP/OpenCV world space.
        to_enu = False

        tt_json_path = Path(options["lat_lon_json_path"])
        dataset_path = Path(options["dataset_path"])
        images = [Path(p) for p in options["images"]]
        scene = options["scene"]

        with open(tt_json_path, 'r') as f:
            scene_latlons = json.load(f)

        latlon = scene_latlons[scene.lower()]
        submodel_path = dataset_path / scene / 'sparse' / '0'

        if PointCloudSet.objects.filter(name__exact=scene).exists():
            pc_set = PointCloudSet.objects.get(name__exact=scene)
            self.stdout.write(
                self.style.WARNING(f"Found {scene} PointCloudSet")
            )
        else:
            lat, lon = latlon

            saved_point_cloud_name = convert_and_save_colmap_points(submodel_path, scene, to_enu=to_enu)

            pc_set = PointCloudSet(
                name=str(scene),
                latitude=lat,
                longitude=lon,
                point_cloud_file=saved_point_cloud_name,
            )
            pc_set.save()

            self.stdout.write(
                self.style.SUCCESS(f"Successfully added {scene} point cloud")
            )

        for image_path in images:
            saved_image_name, camera_json = convert_and_save_posed_images(submodel_path, image_path, scene, to_enu=to_enu)
            ic = ImageCamera(
                  point_cloud_set=pc_set,
                  image=saved_image_name,
                  camera=camera_json,
                  name=image_path.name,
            )
            ic.save()
