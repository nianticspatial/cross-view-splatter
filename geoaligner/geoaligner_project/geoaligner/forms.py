from django import forms
import os
from pathlib import Path
import tempfile
from geoaligner.models import ImageCamera, PointCloudSet, default_point_cloud_transform

from geoaligner.utils.point_cloud_file import convert_and_save_colmap_points
from geoaligner.utils.camera_convention_converter import convert_and_save_posed_images


class PointCloudSetAdminAddForm(forms.ModelForm):
    # This field will be visible in the admin add/change form
    # but is NOT directly mapped to a model field.
    points3D_bin_path = forms.FileField(
        label='Path to COLMAP points3D.bin file (in e.g. "gaussian_splat/sparse/0" folder)',
        help_text='Upload points3D.bin file',
        required=True
    )
    to_enu = forms.BooleanField(
        label="Convert point cloud to ENU format when ingesting",
        help_text='Convert point cloud coordinate convention to ENU when ingesting points',
        required=True
    )

    class Meta:
        model = PointCloudSet
        # Include fields that are directly mapped to the model,
        # plus the 'input_file' which is a form-only field.
        # Exclude 'converted_file', 'original_filename', 'conversion_status',
        # 'conversion_error_message', 'uploaded_at' as they're populated by our logic.
        fields = ['name', 'latitude', 'longitude']

    def save(self, commit=True):
        # Get the model instance first, but don't save it to DB yet (commit=False)
        pc_set = super().save(commit=False)

        colmap_points3D = self.cleaned_data.get('points3D_bin_path')
        to_enu = self.cleaned_data.get('to_enu')
        pc_set.transform = default_point_cloud_transform()

        if colmap_points3D:
            # Create a temporary file to store the input for the converter
            temp_input_fid, temp_file_path = tempfile.mkstemp(prefix='django_upload_', suffix='.bin')
            try:
                points_path = colmap_points3D.name

                if Path(points_path).name != 'points3D.bin':
                    raise forms.ValidationError("Uploaded file is not points3D.bin")

                # Sanitize filename for safety
                safe_scene_name = ''.join(c for c in pc_set.name if c.isalnum() or c in (' ', '.', '_', '-')).replace(' ', '_')

                # Write the uploaded file content to the temporary input file
                with os.fdopen(temp_input_fid, 'wb') as temp_f:
                    for chunk in colmap_points3D.chunks():
                        temp_f.write(chunk)

                # Perform the conversion
                web_file_path = convert_and_save_colmap_points(
                    temp_file_path, scene=safe_scene_name, to_enu=to_enu,
                )

                if web_file_path:
                    pc_set.point_cloud_file = web_file_path
            except:
                raise forms.ValidationError("Points3D.bin conversion failed")
            finally:
                if temp_file_path and os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
        else:
            raise forms.ValidationError("Upload of points3d.bin file failed")

        if commit:
            pc_set.save()
        return pc_set


class PointCloudSetAdminChangeForm(forms.ModelForm):
    class Meta:
        model = PointCloudSet 
        fields = [
            'name', 
            'latitude', 
            'longitude', 
            'point_cloud_file', 
            'transform', 
        ]
