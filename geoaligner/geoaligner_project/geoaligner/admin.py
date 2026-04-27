from django.contrib import admin
from geoaligner.models import PointCloudSet, ImageCamera
from geoaligner.forms import PointCloudSetAdminAddForm, PointCloudSetAdminChangeForm


# You can use an inline to manage images directly from the PointCloudSet admin page
class ImageCameraInline(admin.TabularInline):
    model = ImageCamera
    extra = 1 # Show one extra empty form by default


@admin.register(PointCloudSet)
class PointCloudSetAdmin(admin.ModelAdmin):
    list_display = (
        'name', 
        'latitude', 
        'longitude',
        'point_cloud_file',
        'transform'
    )
    search_fields = ('name',)

    def get_form(self, request, obj=None, **kwargs):
        """
        Returns the appropriate form based on whether PointCloudSet is being added or changed.
        `obj` is None for add view, and the instance for change view.
        """
        if obj: # obj is not None, so it's a change view
            return PointCloudSetAdminChangeForm
        else:   # obj is None, so it's an add view
            return PointCloudSetAdminAddForm
    
    def get_fieldsets(self, request, obj=None):
        """
        Defines the fieldsets dynamically based on add or change view.
        This allows us to show 'input_file' only on add, and hide it on change.
        """

        if obj: # Change view
            return (
                (None, {
                    'fields': ('name', 'latitude', 'longitude', 'transform')
                }),
            )
        else:   # Add view
            return (
                (None, {
                    'fields': ('name', 'latitude', 'longitude', 'points3D_bin_path', 'to_enu')
                }),
            )


# You can also register ImagePose on its own if you want a separate admin page for it
@admin.register(ImageCamera)
class ImagePoseAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'point_cloud_set', 'captured_at')
    list_filter = ('point_cloud_set',)
