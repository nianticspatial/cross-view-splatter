from django.db import models

# A default transform for the entire point cloud set (scale, rotation, translation)
def default_point_cloud_transform():
  return {
    "rotation": {"_x": 0, "_y": 0, "_z": 0, "_w": 1},
    "translation": {"x": 0, "y": 0, "z": 0},
    "scale": {"x": 1, "y": 1, "z": 1}
  }

# A default pose and intrinsics for a camera. A camera pose is just rotation and translation. Intrinsics is focal lengths, camera center, camera width and heigth.
def default_camera():
  return {
    "rotation": {"_x": 0, "_y": 0, "_z": 0, "_w": 1}, # Identity quaternion
    "translation": {"x": 0, "y": 0, "z": 0},       # Origin
    "intrinsics": {"fx": 50, "fy": 50, "cx": 50, "cy": 50, "w": 100, "h": 100},
  }


class PointCloudSet(models.Model):
  name = models.CharField(max_length=200, help_text="A descriptive name for this set")
  point_cloud_file = models.FileField(upload_to='point_clouds/')
  latitude = models.FloatField()
  longitude = models.FloatField()

  # We will store the transformation for the whole set as a flexible JSON object
  # Default values represent no transformation.
  transform = models.JSONField(default=default_point_cloud_transform, blank=True)

  def __str__(self):
    return self.name


class ImageCamera(models.Model):
  """
  Represents a single image and its camera, including 3D pose and inrinsics, associated with a PointCloudSet.
  The pose describes the camera's position and orientation in the same coordinate system as the point cloud.
  The intrinsics are focal lengths, camera center and camera width and height.
  """
  # Link back to the parent PointCloudSet
  point_cloud_set = models.ForeignKey(
    PointCloudSet,
    related_name='images', # This lets you do a_set.images.all()
    on_delete=models.CASCADE # If the set is deleted, delete its images too
  )

  # The image file itself
  image = models.ImageField(
      upload_to='posed_images/',
      help_text="The image associated with this camera."
  )

  # The camera when the image was taken
  camera = models.JSONField(
      default=default_camera,
      help_text="intrinsics (focal lengths, camera center and camera width and height) and 3D pose (rotation as quaternion, translation as vector) of the camera."
  )

  # Optional fields for better organization
  name = models.CharField(max_length=200, blank=True, help_text="An optional name for this image camera.")
  captured_at = models.DateTimeField(null=True, blank=True, help_text="Optional: when the image was captured.")

  def __str__(self):
    return f"Image '{self.name or self.id}' for {self.point_cloud_set.name}"