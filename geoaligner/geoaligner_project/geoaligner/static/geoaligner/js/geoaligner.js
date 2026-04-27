import * as THREE from 'three';
import * as L from 'leaflet';

const layerConfigs = {
    current: {
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attribution: 'Tiles &copy; Esri'
    },
    vintage1: {
        url: 'https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/WMTS/1.0.0/default028mm/MapServer/tile/10/{z}/{y}/{x}',
        attribution: 'Tiles &copy; Esri, via Wayback (Vintage: 2014-02-20)'
    },
    vintage2: {
        url: 'https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/WMTS/1.0.0/default028mm/MapServer/tile/8249/{z}/{y}/{x}',
        attribution: 'Tiles &copy; Esri, via Wayback (Vintage: 2018-06-06)'
    }
};

document.addEventListener('DOMContentLoaded', () => {
 // --- Three.js Components ---
 let scene3d;
 let camera3d_topDown, renderer3d_topDown;
 let camera3d_frontal, renderer3d_frontal;
 let sceneOverlay, cameraOverlay, rendererOverlay;
 let frontalViewport = { x: 0, y: 0, width: 0, height: 0 };
 let frontalCameraYaw = 0;
 let frontalCameraPitch = 0;
 let frontalCameraDistanceFactor = 1.0; // For zooming the camera
 let frontalCameraTarget = new THREE.Vector3();

 let camData;
 let pointsObject3D;
 let pointsObjectOverlay;
 let groundPlane;

 let sharedGeometry;
 let sharedMaterial;
 let initialTopDownOffset, initialFrontalOffset; // Store base camera positions

 // For interactive mouse events (Map Overlay View)
 let raycasterOverlay;
 let pointerOverlay = new THREE.Vector2();
 let isDraggingOverlay = false;
 let dragStartPointOverlay = new THREE.Vector3();
 let dragStartPointOverlay_y = 0;
 let dragStartPointTopDown = new THREE.Vector2();
 let initialTx, initialTy, initialTz;
 let initialRx, initialRy, initialRz;

 // For interactive mouse events (both 3D Views)
 let raycaster3D;
 let isDragging3D = false;
 let active3dCamera;

 // --- Leaflet Components ---
 let activeLayer;
 let map;

 // --- Django Data ---
 const objectId = document.body.dataset.objectId;
 const csrfToken = document.body.dataset.csrfToken;
 let allImageData = [];
 let activeImageCameraId = null;

 // --- UI Elements ---
 const controls = {
 tx: document.getElementById('tx'), ty: document.getElementById('ty'), tz: document.getElementById('tz'),
 rx: document.getElementById('rx'), ry: document.getElementById('ry'), rz: document.getElementById('rz'),
 s: document.getElementById('s')
 };
 const valueSpans = {
 tx: document.getElementById('tx_val'), ty: document.getElementById('ty_val'), tz: document.getElementById('tz_val'),
 rx: document.getElementById('rx_val'), ry: document.getElementById('ry_val'), rz: document.getElementById('rz_val'),
 s: document.getElementById('s_val')
 };
 const saveButton = document.getElementById('save-button');
 const saveStatus = document.getElementById('save-status');
 const pointSizeSlider = document.getElementById('point_size');
 const pointSizeValSpan = document.getElementById('point_size_val');
 const togglePointsCheckbox = document.getElementById('toggle-points-checkbox');
 const mapZoomSlider = document.getElementById('map_zoom_slider');
 const mapZoomValSpan = document.getElementById('map_zoom_val');
 const imageViewButtonsContainer = document.getElementById('image-view-buttons');
 const toggleBgImageCheckbox = document.getElementById('toggle-background-image');

 // --- Global Configuration ---
 const keyboardTranslationStep = 0.5;
 let mapZoomFactor = 1.0;
 let isPointsOverlayVisible = true;

 function init() {
 fetch(`/api/data/${objectId}/`)
 .then(response => { if (!response.ok) { throw new Error(`HTTP error! status: ${response.status}`); } return response.json(); })
 .then(data => {
  allImageData = data.images; // Store image data

  initSharedPointCloud(data.points, data.colors);
  init3DViews();
  initMapView(data.lat, data.lon);
  switchLayer('current');
  initOverlayView();
  setupControls(data.initial_transform, data.lat, data.lon);
  setupViewControls();
  populateImageViewsUI(); // Populate new UI elements
  animate();
 })
 .catch(error => console.error('Error fetching data:', error));
 }

 function switchLayer(layerKey) {
    const config = layerConfigs[layerKey];

    // If a layer is already active, remove it first
    if (activeLayer) {
        map.removeLayer(activeLayer);
    }

    // Create the new tile layer and add it to the map
    activeLayer = L.tileLayer(config.url, {
        attribution: config.attribution,
        maxZoom: 19 // Standard max zoom for Esri layers
    }).addTo(map);

    console.log(`Map layer switched to: ${layerKey}`);
}

 function populateImageViewsUI() {
  imageViewButtonsContainer.innerHTML = ''; // Clear

  const defaultViewButton = document.createElement('button');
  defaultViewButton.textContent = 'Default Frontal View';
  defaultViewButton.addEventListener('click', switchToDefaultFrontalView);
  imageViewButtonsContainer.appendChild(defaultViewButton);

  allImageData.forEach(imgData => {
    const button = document.createElement('button');
    button.textContent = imgData.name || `Image ${imgData.id}`;
    button.dataset.imageId = imgData.id;
    button.addEventListener('click', () => switchToImageView(imgData.id));
    imageViewButtonsContainer.appendChild(button);
  });

  toggleBgImageCheckbox.addEventListener('change', updateFrontalViewBackground);
 }

 function createCheckerboardTexture(color1 = '#bbbbbb', color2 = '#a0a0a0', size = 256, squares = 8) {
   const canvas = document.createElement('canvas');
   canvas.width = size;
   canvas.height = size;
   const context = canvas.getContext('2d');
   const squareSize = size / squares;

   for (let i = 0; i < squares; i++) {
       for (let j = 0; j < squares; j++) {
           context.fillStyle = (i + j) % 2 === 0 ? color1 : color2;
           context.fillRect(i * squareSize, j * squareSize, squareSize, squareSize);
       }
   }
   return new THREE.CanvasTexture(canvas);
 }

 function setupViewControls() {
   pointSizeSlider.addEventListener('input', updatePointSize);
   updatePointSize();
   mapZoomSlider.addEventListener('input', updateMapZoom);
   updateMapZoom();
   togglePointsCheckbox.addEventListener('change', togglePointsOverlayVisibility);
 }

 function updatePointSize() {
   const newSize = parseFloat(pointSizeSlider.value);
   if (sharedMaterial) { sharedMaterial.size = newSize; }
   pointSizeValSpan.textContent = newSize.toFixed(1);
 }

function updateMapZoom() {
  mapZoomFactor = parseFloat(mapZoomSlider.value);
  const mapContainer = document.getElementById('map-container');
  mapZoomValSpan.textContent = `${mapZoomFactor.toFixed(1)}x`;
  mapContainer.style.transform = `scale(${mapZoomFactor})`;
   
  // The overlay needs to know about the zoom for its frustum calculation.
  updateOverlayFrustum();
}

 function togglePointsOverlayVisibility() {
  if (!pointsObjectOverlay) return;
  isPointsOverlayVisible = togglePointsCheckbox.checked; 
  pointsObjectOverlay.visible = isPointsOverlayVisible;
 }

 function initSharedPointCloud(pointData, colorData) {
   sharedGeometry = new THREE.BufferGeometry();
   const vertices = new Float32Array(pointData.flat());
   const colors = new Uint8Array(colorData.flat());
   sharedGeometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
   sharedGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3, true));
   sharedGeometry.computeBoundingSphere();
   sharedMaterial = new THREE.PointsMaterial({ color: 0xffffff, size: 0.1, vertexColors: true });
 }

 function init3DViews() {
   const containerTopDown = document.getElementById('scene-3d-top-down');
   const containerFrontal = document.getElementById('scene-3d-frontal');

   scene3d = new THREE.Scene();
   pointsObject3D = new THREE.Points(sharedGeometry, sharedMaterial);
   scene3d.add(pointsObject3D);

   const checkerTexture = createCheckerboardTexture();
   checkerTexture.wrapS = THREE.RepeatWrapping;
   checkerTexture.wrapT = THREE.RepeatWrapping;
   checkerTexture.repeat.set(50, 50); // How many checkers repeat across the plane

   const planeGeometry = new THREE.PlaneGeometry(2000, 2000); // A very large plane
   const planeMaterial = new THREE.MeshBasicMaterial({
       map: checkerTexture,
       transparent: true,
       opacity: 0.4,
       side: THREE.DoubleSide
   });
   groundPlane = new THREE.Mesh(planeGeometry, planeMaterial);
   //groundPlane.rotation.x = -Math.PI / 2;
   groundPlane.position.z = 0;
   scene3d.add(groundPlane);


   raycaster3D = new THREE.Raycaster();

   // positive Z is UP in our world.
   const radius = sharedGeometry.boundingSphere.radius;
 
   // For a top-down view, position the camera "above" the world origin along the positive Z-axis.
   initialTopDownOffset = new THREE.Vector3(0, 0, radius * 2.5); 
 
   // For a frontal view, we position the camera along the Y-axis.
   initialFrontalOffset = new THREE.Vector3(0, -radius * 0.5, 0);

   // --- CAMERA INITIALIZATION ---
   camera3d_topDown = new THREE.PerspectiveCamera(75, containerTopDown.clientWidth / containerTopDown.clientHeight, 0.1, 1000);
   camera3d_topDown.up.set(0, 1, 0); // North is "up" in the viewport

   camera3d_frontal = new THREE.PerspectiveCamera(75, containerFrontal.clientWidth / containerFrontal.clientHeight, 0.1, 1000);
   camera3d_frontal.up.set(0, 0, 1); // World's Z is "up" in the viewport

   // --- RENDERER SETUP ---
   renderer3d_topDown = new THREE.WebGLRenderer({ antialias: true });
   renderer3d_topDown.setSize(containerTopDown.clientWidth, containerTopDown.clientHeight);
   renderer3d_topDown.setPixelRatio(window.devicePixelRatio);
   renderer3d_topDown.setClearColor(0x000000, 0);
   containerTopDown.appendChild(renderer3d_topDown.domElement);

   renderer3d_frontal = new THREE.WebGLRenderer({ antialias: true, alpha: true });
   renderer3d_frontal.setSize(containerFrontal.clientWidth, containerFrontal.clientHeight);
   renderer3d_frontal.setPixelRatio(window.devicePixelRatio);
   renderer3d_frontal.setClearColor(0x000000, 0);
   containerFrontal.appendChild(renderer3d_frontal.domElement);
    
   [renderer3d_topDown.domElement, renderer3d_frontal.domElement].forEach(element => {
    element.addEventListener('mousedown', onMouseDown3D);
    element.addEventListener('mousemove', onMouseMove3D);
    element.addEventListener('mouseup', onMouseUp3D);
    element.addEventListener('wheel', onMouseWheel3D, { passive: false });
    element.addEventListener('contextmenu', (event) => event.preventDefault());
   });
 }

 function initMapView(lat, lon) {
   const container = document.getElementById('map-container');
   map = L.map(container, {
    zoomControl: false, attributionControl: false, scrollWheelZoom: false,
    doubleClickZoom: false, boxZoom: false, dragging: false,
    touchZoom: false, tapHold: false, keyboard: false,
    zoomAnimation: false, fadeAnimation: false,
   }).setView([lat, lon], 18);

   const layerSwitcher = document.getElementById('layer-switcher');
   layerSwitcher.addEventListener('change', (event) => {
   if (event.target.name === 'map-layer') {
     const selectedLayer = event.target.value;
     switchLayer(selectedLayer);
     }
   });

   map.on('zoomend', updateOverlayFrustum);
   map.on('resize', updateOverlayFrustum);
   updateOverlayFrustum();
 }

 function initOverlayView() {
   const mapWrapper = document.getElementById('map-wrapper');
   const overlayCanvas = document.getElementById('overlay-canvas');
   overlayCanvas.width = mapWrapper.clientWidth;
   overlayCanvas.height = mapWrapper.clientHeight;
   sceneOverlay = new THREE.Scene();
   cameraOverlay = new THREE.OrthographicCamera(-mapWrapper.clientWidth / 2, mapWrapper.clientWidth / 2, mapWrapper.clientHeight / 2, -mapWrapper.clientHeight / 2, 0.1, 1000);
   cameraOverlay.position.set(0, 0, 100);
   cameraOverlay.lookAt(0, 0, 0);
  
   rendererOverlay = new THREE.WebGLRenderer({ canvas: overlayCanvas, alpha: true, antialias: true });
   rendererOverlay.setSize(mapWrapper.clientWidth, mapWrapper.clientHeight);
   rendererOverlay.setPixelRatio(window.devicePixelRatio);
   rendererOverlay.setClearColor(0x000000, 0);
   pointsObjectOverlay = new THREE.Points(sharedGeometry, sharedMaterial);
   sceneOverlay.add(pointsObjectOverlay);
   raycasterOverlay = new THREE.Raycaster();
   const eventHandlerElement = document.getElementById('map-wrapper');
   eventHandlerElement.addEventListener('mousedown', onMouseDownOverlay, { passive: false });
   eventHandlerElement.addEventListener('mousemove', onMouseMoveOverlay, { passive: false });
   eventHandlerElement.addEventListener('mouseup', onMouseUpOverlay);
   eventHandlerElement.addEventListener('wheel', onMouseWheelOverlay, { passive: false });
   eventHandlerElement.addEventListener('contextmenu', (event) => event.preventDefault());
 }

 function updateOverlayFrustum() {
   if (!map || !cameraOverlay) return;
   const mapWrapper = document.getElementById('map-wrapper');
   const overlayCanvas = document.getElementById('overlay-canvas');
   const width = mapWrapper.clientWidth;
   const height = mapWrapper.clientHeight;
   rendererOverlay.setSize(width, height);
   overlayCanvas.width = rendererOverlay.domElement.width;
   overlayCanvas.height = rendererOverlay.domElement.height;
   const centerLatLng = map.getCenter();
   const zoom = map.getZoom();
   const metersPerPixel = 156543.03392 * Math.cos(centerLatLng.lat * Math.PI / 180) / Math.pow(2, zoom);
   const scaleFactor = mapZoomFactor;
   const worldWidth = (width / scaleFactor) * metersPerPixel;
   const worldHeight = (height / scaleFactor) * metersPerPixel;
   cameraOverlay.left = -worldWidth / 2;
   cameraOverlay.right = worldWidth / 2;
   cameraOverlay.top = worldHeight / 2;
   cameraOverlay.bottom = -worldHeight / 2;
   cameraOverlay.updateProjectionMatrix();
 }

 function setupControls(initialTransform, lat, lon) {
   const gmapLink = document.getElementById('gmap_link');
   gmapLink.setAttribute("href", 'https://www.google.com/maps/@' + lat + ',' + lon + ',74m');
   const initialRotation = initialTransform.rotation;
   const euler = new THREE.Euler();
   if (initialRotation && initialRotation._w !== undefined) {
    const quaternion = new THREE.Quaternion(initialRotation._x, initialRotation._y, initialRotation._z, initialRotation._w);
    euler.setFromQuaternion(quaternion, 'ZXY');
   } else {
    euler.set(initialRotation?.x || 0, initialRotation?.y || 0, initialRotation?.z || 0, 'ZXY');
   }
   controls.rx.value = THREE.MathUtils.radToDeg(euler.x);
   controls.ry.value = THREE.MathUtils.radToDeg(euler.y);
   controls.rz.value = THREE.MathUtils.radToDeg(euler.z);
   const initialTranslation = initialTransform.translation;
   const initialScale = initialTransform.scale;
   controls.tx.value = initialTranslation?.x || 0;
   controls.ty.value = initialTranslation?.y || 0;
   controls.tz.value = initialTranslation?.z || 0;
   controls.s.value = initialScale?.x || 1;
   Object.values(controls).forEach(input => {
    input.addEventListener('input', applyTransformationToObjects);
   });
   saveButton.addEventListener('click', saveTransformation);
   applyTransformationToObjects();
 }

 function applyTransformationToObjects() {
  if (!pointsObject3D || !pointsObjectOverlay) return;
  const rotX = THREE.MathUtils.degToRad(parseFloat(controls.rx.value));
  const rotY = THREE.MathUtils.degToRad(parseFloat(controls.ry.value));
  const rotZ = THREE.MathUtils.degToRad(parseFloat(controls.rz.value));
  const posX = parseFloat(controls.tx.value);
  const posY = parseFloat(controls.ty.value);
  const posZ = parseFloat(controls.tz.value);
  const scale = parseFloat(controls.s.value);
  pointsObject3D.scale.set(scale, scale, scale);
  pointsObject3D.rotation.set(rotX, rotY, rotZ, 'ZXY');
  pointsObject3D.position.set(posX, posY, posZ);
  pointsObject3D.updateMatrixWorld();
  pointsObjectOverlay.matrix.copy(pointsObject3D.matrix);
  pointsObjectOverlay.matrix.decompose(pointsObjectOverlay.position, pointsObjectOverlay.quaternion, pointsObjectOverlay.scale);
  if (activeImageCameraId !== null) {
    updateActiveImageViewPose();
  }
  for (const key in valueSpans) {
    valueSpans[key].textContent = parseFloat(controls[key].value).toFixed(2);
  }
 }

 function saveTransformation() {
   saveStatus.textContent = "Saving...";
   const euler = new THREE.Euler(THREE.MathUtils.degToRad(parseFloat(controls.rx.value)), THREE.MathUtils.degToRad(parseFloat(controls.ry.value)), THREE.MathUtils.degToRad(parseFloat(controls.rz.value)), 'ZXY');
   const quaternion = new THREE.Quaternion().setFromEuler(euler);
   const transformData = {
   rotation: { _x: quaternion.x, _y: quaternion.y, _z: quaternion.z, _w: quaternion.w },
   translation: { x: parseFloat(controls.tx.value), y: parseFloat(controls.ty.value), z: parseFloat(controls.tz.value) },
   scale: { x: parseFloat(controls.s.value), y: parseFloat(controls.s.value), z: parseFloat(controls.s.value) }
   };
   fetch(`/api/save/${objectId}/`, {
   method: 'POST',
   headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
   body: JSON.stringify(transformData)
   }).then(response => response.json()).then(data => {
   saveStatus.textContent = data.status === 'success' ? "Saved successfully!" : `Error: ${data.message}`;
   setTimeout(() => { saveStatus.textContent = ""; }, 3000);
   }).catch(err => {
   saveStatus.textContent = "Network error while saving.";
   console.error(err);
   });
 }

 function getOverlayWorldPoint(event) {
  const rect = document.getElementById('map-wrapper').getBoundingClientRect();
  pointerOverlay.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointerOverlay.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycasterOverlay.setFromCamera(pointerOverlay, cameraOverlay);
  const intersection = new THREE.Vector3();
  raycasterOverlay.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 0, 1), 0), intersection);
  return intersection;
 }

 function onMouseDownOverlay(event) {
  event.preventDefault();
  isDraggingOverlay = true;
  dragStartPointOverlay.copy(getOverlayWorldPoint(event));
  dragStartPointOverlay_y = event.clientY;
  initialTx = parseFloat(controls.tx.value);
  initialTy = parseFloat(controls.ty.value);
  initialTz = parseFloat(controls.tz.value);
 }

 function onMouseMoveOverlay(event) {
   if (!isDraggingOverlay) return;
   const currentPoint = getOverlayWorldPoint(event);
   const deltaX = currentPoint.x - dragStartPointOverlay.x;
   const deltaY = currentPoint.y - dragStartPointOverlay.y; 

   if (event.buttons === 1) {
     controls.tx.value = (initialTx + deltaX).toFixed(2);
     controls.ty.value = (initialTy + deltaY).toFixed(2);
   } else if (event.buttons === 2) {
     const deltaZ = dragStartPointOverlay_y - event.clientY;
     controls.tz.value = (initialTz + deltaZ).toFixed(2);
   }
   applyTransformationToObjects();
}

 function onMouseUpOverlay(event) { isDraggingOverlay = false; }

 function onMouseWheelOverlay(event) {
   event.preventDefault();
   const sensitivity = 0.002;
   let newZoom = parseFloat(mapZoomSlider.value) - (event.deltaY * sensitivity);
   const minZoom = parseFloat(mapZoomSlider.min);
   const maxZoom = parseFloat(mapZoomSlider.max);
   newZoom = Math.max(minZoom, Math.min(maxZoom, newZoom));
   mapZoomSlider.value = newZoom;
   updateMapZoom();
 }

function onMouseDown3D(event) {
  event.preventDefault();
  isDragging3D = true;
  const active3dRenderer = (event.target === renderer3d_topDown.domElement) ? renderer3d_topDown : renderer3d_frontal;
  active3dCamera = (active3dRenderer === renderer3d_topDown) ? camera3d_topDown : camera3d_frontal;

  dragStartPointTopDown.x = event.clientX;
  dragStartPointTopDown.y = event.clientY;

  initialTx = parseFloat(controls.tx.value);
  initialTy = parseFloat(controls.ty.value);
  initialTz = parseFloat(controls.tz.value);
  initialRx = parseFloat(controls.rx.value);
  initialRy = parseFloat(controls.ry.value);
  initialRz = parseFloat(controls.rz.value);
}

function updateActiveImageViewPose() {
  if (!camData) return;
  const basePosition = new THREE.Vector3(camData.translation.x, camData.translation.y, camData.translation.z);
  const baseQuaternion = new THREE.Quaternion(camData.rotation._x, camData.rotation._y, camData.rotation._z, camData.rotation._w);
  const baseMatrix = new THREE.Matrix4().compose(basePosition, baseQuaternion, new THREE.Vector3(1, 1, 1));
  const worldMatrix = pointsObject3D.matrixWorld;
  const finalMatrix = new THREE.Matrix4();
  finalMatrix.multiplyMatrices(worldMatrix, baseMatrix);
  finalMatrix.decompose(camera3d_frontal.position, camera3d_frontal.quaternion, camera3d_frontal.scale);
}

function switchToImageView(imageId) {
  activeImageCameraId = imageId;
  const imageData = allImageData.find(img => img.id === imageId);
  if (!imageData) {
    console.error('Image data not found for ID:', imageId);
    switchToDefaultFrontalView();
    return;
  }
  camData = imageData.camera;
  const container = document.getElementById('scene-3d-frontal');
  updateImageViewportAndProjection(imageData, container);
  renderer3d_frontal.setViewport(frontalViewport.x, frontalViewport.y, frontalViewport.width, frontalViewport.height);
  updateActiveImageViewPose();
  updateFrontalViewBackground();
}

function updateImageViewportAndProjection(imageData, container) {
  const intrinsics = imageData.camera.intrinsics;
  const { fx, fy, cx, cy, w: imgWidth, h: imgHeight } = intrinsics;
  const canvasWidth = container.clientWidth;
  const canvasHeight = container.clientHeight;
  const near = camera3d_frontal.near;
  const top = (cy / fy) * near;
  const bottom = -(imgHeight - cy) / fy * near;
  const left = -(cx / fx) * near;
  const right = (imgWidth - cx) / fx * near;
  camera3d_frontal.projectionMatrix.makePerspective(left, right, top, bottom, near, camera3d_frontal.far);
  const imageAspectRatio = imgWidth / imgHeight;
  const canvasAspectRatio = canvasWidth / canvasHeight;
  let viewportWidth, viewportHeight, viewportX, viewportY;
  if (canvasAspectRatio > imageAspectRatio) {
    viewportHeight = canvasHeight;
    viewportWidth = viewportHeight * imageAspectRatio;
    viewportX = (canvasWidth - viewportWidth) / 2;
    viewportY = 0;
  } else {
    viewportWidth = canvasWidth;
    viewportHeight = viewportWidth / imageAspectRatio;
    viewportX = 0;
    viewportY = (canvasHeight - viewportHeight) / 2;
  }
  frontalViewport = { x: viewportX, y: viewportY, width: viewportWidth, height: viewportHeight };
}

function switchToDefaultFrontalView() {
  activeImageCameraId = null;
  camData = null;
  const containerFrontal = document.getElementById('scene-3d-frontal');
  frontalCameraYaw = 0;
  frontalCameraPitch = 0;
  frontalCameraDistanceFactor = 1.0;
  if (pointsObject3D) {
    pointsObject3D.getWorldPosition(frontalCameraTarget);
  }
  camera3d_frontal.fov = 75;
  camera3d_frontal.aspect = containerFrontal.clientWidth / containerFrontal.clientHeight;
  camera3d_frontal.updateProjectionMatrix();
  renderer3d_frontal.setViewport(0, 0, containerFrontal.clientWidth, containerFrontal.clientHeight);
  updateFrontalViewBackground();
}

function updateFrontalViewBackground() {
  const container = document.getElementById('scene-3d-frontal');
  if (activeImageCameraId === null || !toggleBgImageCheckbox.checked) {
    container.style.backgroundImage = 'none';
    return;
  }
  const imageData = allImageData.find(img => img.id === activeImageCameraId);
  if (imageData && imageData.url) {
    container.style.backgroundImage = `url(${imageData.url})`;
  } else {
    container.style.backgroundImage = 'none';
  }
}

function onMouseMove3D(event) {
  if (!isDragging3D || !active3dCamera) return;

  if (active3dCamera === camera3d_frontal && activeImageCameraId !== null) {
    return;
  }

  if (active3dCamera === camera3d_frontal) {
    if (event.buttons === 1) {
      const right = new THREE.Vector3().setFromMatrixColumn(camera3d_frontal.matrix, 0);
      const up = new THREE.Vector3().setFromMatrixColumn(camera3d_frontal.matrix, 1);
      const distance = camera3d_frontal.position.distanceTo(frontalCameraTarget);
      const panSpeed = distance * 0.001; 
      const panOffset = new THREE.Vector3();
      panOffset.add(right.multiplyScalar(-event.movementX * panSpeed));
      panOffset.add(up.multiplyScalar(event.movementY * panSpeed));
      frontalCameraTarget.add(panOffset);
    } else if (event.buttons === 2) {
      const orbitSensitivity = 0.005;
      frontalCameraYaw -= event.movementX * orbitSensitivity;
      frontalCameraPitch -= event.movementY * orbitSensitivity;
      const maxPitch = (Math.PI / 2) - 0.01;
      frontalCameraPitch = Math.max(-maxPitch, Math.min(maxPitch, frontalCameraPitch));
    }
  }
  else if (active3dCamera === camera3d_topDown) {
    if (event.buttons === 1) {
      controls.ry.value = (initialRy + (dragStartPointTopDown.y -event.clientY)).toFixed(0);
      controls.rz.value = (initialRz + (dragStartPointTopDown.x -event.clientX)).toFixed(0);
    } else if (event.buttons === 2) {
      controls.rx.value = (initialRx + (dragStartPointTopDown.y-event.clientY)).toFixed(0);
      controls.rz.value = (initialRz + (dragStartPointTopDown.x-event.clientX)).toFixed(0);
    }
    
    applyTransformationToObjects();
  }
}

 function onMouseUp3D(event) {
   isDragging3D = false;
   active3dCamera = null;
 }

function onMouseWheel3D(event) {
  event.preventDefault();
  const targetRenderer = (event.target === renderer3d_topDown.domElement) ? renderer3d_topDown : renderer3d_frontal;
  if (!targetRenderer) return;

  if (targetRenderer === renderer3d_frontal && activeImageCameraId === null) {
    const zoomSensitivity = 0.1;
    frontalCameraDistanceFactor -= event.deltaY * 0.001 * zoomSensitivity;
    frontalCameraDistanceFactor = Math.max(0.1, Math.min(5.0, frontalCameraDistanceFactor));
    return;
  }
   
  if (targetRenderer === renderer3d_topDown) {
    let scaleValue = parseFloat(controls.s.value) + (-event.deltaY * 0.001);
    console.log(controls.s.max);
    controls.s.value = Math.max(0.01, Math.min(controls.s.max, scaleValue)).toFixed(2);
    applyTransformationToObjects();
  }
}

function animate() {
  requestAnimationFrame(animate);

  if (pointsObject3D && initialFrontalOffset) { 
    const objectWorldCenter = new THREE.Vector3();
    pointsObject3D.getWorldPosition(objectWorldCenter);

    // --- Top-down camera logic ---
    if (camera3d_topDown && initialTopDownOffset) {
      const dynamicOffset = initialTopDownOffset.clone().divideScalar(mapZoomFactor);
      const topDownPosition = objectWorldCenter.clone().add(dynamicOffset);
      camera3d_topDown.position.copy(topDownPosition);
      camera3d_topDown.lookAt(objectWorldCenter);  
    }
     
    // --- Frontal camera logic ---
    if (camera3d_frontal) {
      if (activeImageCameraId === null) {
        const offset = initialFrontalOffset.clone().multiplyScalar(frontalCameraDistanceFactor);
        const quat = new THREE.Quaternion().setFromEuler(new THREE.Euler(frontalCameraPitch, 0, frontalCameraYaw, 'ZXY'));
        offset.applyQuaternion(quat);
        camera3d_frontal.position.copy(frontalCameraTarget).add(offset);
        camera3d_frontal.lookAt(frontalCameraTarget);
      }
    }
  }

  renderer3d_topDown.render(scene3d, camera3d_topDown);
  renderer3d_frontal.render(scene3d, camera3d_frontal);
  rendererOverlay.render(sceneOverlay, cameraOverlay);
}

const resizeObserverTopDown = new ResizeObserver(entries => {
 if (!camera3d_topDown || !renderer3d_topDown) return;
 for (let entry of entries) {
 const {width, height} = entry.contentRect;
 camera3d_topDown.aspect = width / height;
 camera3d_topDown.updateProjectionMatrix();
 renderer3d_topDown.setSize(width, height);
 }
 });
 resizeObserverTopDown.observe(document.getElementById('scene-3d-top-down'));

const resizeObserverFrontal = new ResizeObserver(entries => {
  if (!camera3d_frontal || !renderer3d_frontal) return;
  for (let entry of entries) {
    const { width, height } = entry.contentRect;
    renderer3d_frontal.setSize(width, height);
    if (activeImageCameraId !== null) {
      const imageData = allImageData.find(img => img.id === activeImageCameraId);
      if (imageData) {
        updateImageViewportAndProjection(imageData, entry.target);
        renderer3d_frontal.setViewport(frontalViewport.x, frontalViewport.y, frontalViewport.width, frontalViewport.height);
      }
    } else {
      camera3d_frontal.aspect = width / height;
      camera3d_frontal.updateProjectionMatrix();
      renderer3d_frontal.setViewport(0, 0, width, height);
    }
  }
});
resizeObserverFrontal.observe(document.getElementById('scene-3d-frontal'));

 const resizeObserverOverlay = new ResizeObserver(entries => {
 updateOverlayFrustum();
 });
 resizeObserverOverlay.observe(document.getElementById('map-wrapper'));

 init();
});