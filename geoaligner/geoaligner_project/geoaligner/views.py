import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from .models import PointCloudSet
from geoaligner.utils.point_cloud_file import PointCloudFile


def list_view(request):
    """Lists all available PointCloudSets."""
    sets = PointCloudSet.objects.all()
    return render(request, 'geoaligner/list.html', {'sets': sets})

def alignment_view(request, pk):
    """The main alignment page for a single PointCloudSet."""
    pc_set = get_object_or_404(PointCloudSet, pk=pk)
    return render(request, 'geoaligner/geoaligner.html', {'set': pc_set})

def export_view(request):
    """The page to export all PointCloudSet transforms."""
    sets = PointCloudSet.objects.all()
    data = [{'id': pc_set.id,
             'name': pc_set.name,
             'transform': pc_set.transform,
             'lat': pc_set.latitude,
             'lon': pc_set.longitude,
             } for pc_set in sets]
    return JsonResponse(data, safe=False)

# --- API VIEWS ---

def point_cloud_data_api(request, pk):
    """API endpoint to get point cloud data."""
    pc_set = get_object_or_404(PointCloudSet, pk=pk)
    
    try:
        # Read and parse the point cloud file (assuming simple XYZ text format)
        points = PointCloudFile.load(pc_set.point_cloud_file.path)
    except Exception as e:
        return JsonResponse({'error': f'Failed to parse file: {e}'}, status=500)

    # Fetch all related ImageCameraobjects using the related_name 'images'
    # .all() gets a QuerySet of all associated images.
    images = pc_set.images.all()
    images_data_for_js = [
        {
            "id": img.id,
            "name": img.name,
            "url": img.image.url,
            "camera": img.camera, # This is already a dictionary-like object
        }
        for img in images
    ]

    data = {
        'id': pc_set.id,
        'name': pc_set.name,
        'lat': pc_set.latitude,
        'lon': pc_set.longitude,
        'initial_transform': pc_set.transform,
        'points': points.xyz,
        'colors': points.rgb,
        'images': images_data_for_js,
    }
    return JsonResponse(data)

def save_transform_api(request, pk):
    """API endpoint to save the transformation."""
    if request.method != 'POST':
        return HttpResponseBadRequest("Only POST method is allowed")

    pc_set = get_object_or_404(PointCloudSet, pk=pk)
    
    try:
        data = json.loads(request.body)
        # You could add validation here to ensure the data structure is correct
        print(data)
        pc_set.transform = data
        pc_set.save()
        return JsonResponse({'status': 'success', 'message': f'Transform for {pc_set.name} saved.'})
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)