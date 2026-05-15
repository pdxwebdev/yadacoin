<template>
  <div class="map-component-wrap">
    <div class="search-bar">
      <input
        ref="searchEl"
        type="text"
        class="search-input"
        placeholder="Search address or place…"
        autocomplete="off"
      />
    </div>
    <div ref="mapEl" :style="mapContainerStyle" />
  </div>
</template>

<script setup>
// Ported from plugins/yadacoinwallet/ui/src/components/Map.vue
// (originally adapted from centeridentityreact's Map.tsx). Renders a Google
// Map with an overlayable lat/lng grid; emits the selected square's coords
// when the user clicks a grid cell. Used by location-recovery setup &
// recovery flows to capture three private "memorable" locations.
import { ref, onMounted, onUnmounted, watch, shallowRef } from "vue";

const GOOGLE_MAPS_API_KEY = "AIzaSyDEbmqlzlkU3mErAG-PPdPEbTrv6opHmag";

const mapStyles = [
  {
    featureType: "all",
    elementType: "labels",
    stylers: [{ visibility: "off" }],
  },
  {
    featureType: "administrative.country",
    elementType: "labels",
    stylers: [{ visibility: "on" }],
  },
  {
    featureType: "administrative.province",
    elementType: "labels",
    stylers: [{ visibility: "on" }],
  },
  {
    featureType: "administrative.locality",
    elementType: "labels",
    stylers: [{ visibility: "on" }],
  },
  {
    featureType: "road",
    elementType: "labels",
    stylers: [{ visibility: "on" }],
  },
  {
    featureType: "poi",
    elementType: "labels",
    stylers: [{ visibility: "off" }],
  },
];

const optionsDefault = {
  gestureHandling: "greedy",
  streetViewControl: false,
  styles: mapStyles,
  disableDefaultUI: true,
  zoomControl: false,
};

const props = defineProps({
  zoom: { type: Number, default: 2 },
  selectedLocation: {
    type: Object,
    default: () => ({ lat: 0, lng: 0, confirmed: false }),
  },
  center: { type: Object, default: () => ({ lat: 0, lng: 0 }) },
  mapContainerStyle: {
    type: Object,
    default: () => ({ width: "100%", height: "250px" }),
  },
  options: { type: Object, default: null },
  selectedSquareId: { type: String, default: "" },
  disableDefaultUI: { type: Boolean, default: true },
  hoverIndex: { type: Number, default: -1 },
  precision: { type: Number, default: 4 },
  disabledLocations: { type: Array, default: () => [] },
});

const emit = defineEmits([
  "update:selectedLocation",
  "update:selectedSquareId",
  "update:hoverIndex",
  "zoomWithGrid",
  "zoomWithoutGrid",
  "gridSquareClicked",
  "mapReady",
]);

const mapEl = ref(null);
const searchEl = ref(null);
const mapInstance = shallowRef(null);
const showGrid = ref(false);
const mapZoom = ref(props.zoom);

let polygons = [];
let gmListeners = [];

function addGmListener(target, event, handler) {
  const l = target.addListener(event, handler);
  gmListeners.push(l);
  return l;
}

function removeAllGmListeners() {
  for (const l of gmListeners) {
    window.google?.maps.event.removeListener(l);
  }
  gmListeners = [];
}

function drawGridSquares(mapRef, precision) {
  const bounds = mapRef.getBounds();
  const ne = bounds.getNorthEast();
  const sw = bounds.getSouthWest();
  const stepSize = 1 / Math.pow(10, precision);
  const squares = [];
  for (let lat = sw.lat() - 0.0001; lat < ne.lat(); lat += stepSize) {
    for (let lng = sw.lng() - 0.0001; lng < ne.lng(); lng += stepSize) {
      let paths = [
        { lat: lat + stepSize, lng },
        { lat, lng },
        { lat, lng: lng + stepSize },
        { lat: lat + stepSize, lng: lng + stepSize },
      ];
      paths = paths.map((p) => ({
        lat: parseFloat(p.lat.toFixed(precision)) + 0.00005,
        lng: parseFloat(p.lng.toFixed(precision)) + 0.00005,
      }));
      squares.push({
        id: `lat${lat.toFixed(precision)}lng${lng.toFixed(precision)}`,
        paths,
      });
    }
  }
  return squares;
}

function getSquareCenter(square) {
  const latSum = square.paths.reduce((s, p) => s + p.lat, 0);
  const lngSum = square.paths.reduce((s, p) => s + p.lng, 0);
  return {
    lat: latSum / square.paths.length,
    lng: lngSum / square.paths.length,
  };
}

function isCoordinateDisabled(coord) {
  for (const dl of props.disabledLocations) {
    const dist = window.google.maps.geometry.spherical.computeDistanceBetween(
      new window.google.maps.LatLng(coord.lat, coord.lng),
      new window.google.maps.LatLng(dl.lat, dl.lng),
    );
    if (dist <= dl.radius) return true;
  }
  return false;
}

function isSquareDisabled(square) {
  return isCoordinateDisabled(getSquareCenter(square));
}

function getZoomThreshold() {
  switch (props.precision) {
    case 2:
      return 14;
    case 3:
      return 16;
    case 4:
      return 18;
    case 5:
      return 20;
    case 6:
      return 20;
    default:
      return 18;
  }
}

function getPolygonOptions(square, index) {
  const isSelected = props.selectedSquareId === square.id;
  const isDisabled = isSquareDisabled(square);
  const isHovered = props.hoverIndex === index;
  return {
    strokeColor: isSelected ? "lightgreen" : isDisabled ? "red" : "#000000",
    strokeOpacity: 0.8,
    strokeWeight: isSelected ? 5 : 1,
    fillColor: isSelected ? "lightgreen" : isDisabled ? "red" : "#000000",
    fillOpacity: isSelected ? 0.5 : isHovered ? 0.3 : 0.1,
    clickable: !isDisabled,
    zIndex: isSelected ? 1000 : 100,
  };
}

function clearPolygons() {
  for (const { polygon } of polygons) polygon.setMap(null);
  polygons = [];
}

function renderGrid(mapRef) {
  clearPolygons();
  const squares = drawGridSquares(mapRef, props.precision);
  for (let i = 0; i < squares.length; i++) {
    const square = squares[i];
    const disabled = isSquareDisabled(square);
    const polygon = new window.google.maps.Polygon({
      paths: square.paths,
      map: mapRef,
      ...getPolygonOptions(square, i),
    });
    if (!disabled) {
      polygon.addListener("click", (e) => {
        const lat = e.latLng.lat();
        const lng = e.latLng.lng();
        emit("update:selectedSquareId", square.id);
        emit("update:selectedLocation", { lat, lng, confirmed: false });
        emit("gridSquareClicked", { squareId: square.id, lat, lng });
        mapRef.panTo({ lat, lng });
        mapRef.setCenter({ lat, lng });
        let newZoom = mapRef.getZoom();
        if (newZoom < 7) newZoom += 3;
        mapRef.setZoom(newZoom);
        mapZoom.value = newZoom;
      });
      polygon.addListener("mouseover", () => emit("update:hoverIndex", i));
      polygon.addListener("mouseout", () => emit("update:hoverIndex", -1));
    }
    polygons.push({ polygon, square, index: i });
  }
}

function updatePolygonStyles() {
  for (const { polygon, square, index } of polygons) {
    polygon.setOptions(getPolygonOptions(square, index));
  }
}

function drawGridIfZoomedIn(mapRef) {
  const zoomLevel = mapRef.getZoom();
  const zoomThreshold = getZoomThreshold();
  mapRef.setMapTypeId("hybrid");
  if (zoomLevel >= zoomThreshold) {
    showGrid.value = true;
    renderGrid(mapRef);
    emit("zoomWithGrid", zoomLevel);
  } else {
    showGrid.value = false;
    clearPolygons();
    emit("zoomWithoutGrid", zoomLevel);
  }
}

async function loadGoogleMaps() {
  if (window.google?.maps) return;
  return new Promise((resolve, reject) => {
    const existing = document.getElementById("google-maps-script");
    if (existing) {
      const check = setInterval(() => {
        if (window.google?.maps) {
          clearInterval(check);
          resolve();
        }
      }, 50);
      return;
    }
    const script = document.createElement("script");
    script.id = "google-maps-script";
    script.src = `https://maps.googleapis.com/maps/api/js?key=${GOOGLE_MAPS_API_KEY}&libraries=places,geometry,drawing,visualization`;
    script.async = true;
    script.defer = true;
    script.onload = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });
}

onMounted(async () => {
  await loadGoogleMaps();

  const mapOptions = props.options || { ...optionsDefault };
  const mapRef = new window.google.maps.Map(mapEl.value, {
    center: props.center,
    zoom: props.zoom,
    ...mapOptions,
  });

  mapInstance.value = mapRef;
  mapZoom.value = props.zoom;
  emit("mapReady", mapRef);

  addGmListener(mapRef, "zoom_changed", () => {
    mapZoom.value = mapRef.getZoom();
    drawGridIfZoomedIn(mapRef);
  });

  addGmListener(mapRef, "click", (e) => {
    const zoomLevel = mapRef.getZoom() ?? mapZoom.value;
    const zoomThreshold = getZoomThreshold();
    const coord = { lat: e.latLng.lat(), lng: e.latLng.lng() };

    if (isCoordinateDisabled(coord) && zoomLevel >= zoomThreshold) return;

    mapRef.panTo(coord);
    mapRef.setCenter(coord);

    let newZoom = zoomLevel;
    if (zoomLevel < 7) {
      newZoom = zoomLevel + 3;
    } else {
      newZoom = zoomLevel + 2;
    }

    if (newZoom >= 20) {
      emit("update:selectedLocation", { ...coord, confirmed: false });
      newZoom = Math.min(newZoom, 20);
    }

    mapRef.setZoom(newZoom);
    mapZoom.value = newZoom;
  });

  drawGridIfZoomedIn(mapRef);

  const autocomplete = new window.google.maps.places.Autocomplete(
    searchEl.value,
    { fields: ["geometry", "name"] },
  );
  autocomplete.addListener("place_changed", () => {
    const place = autocomplete.getPlace();
    if (!place.geometry?.location) return;
    const lat = place.geometry.location.lat();
    const lng = place.geometry.location.lng();
    mapRef.panTo({ lat, lng });
    mapRef.setCenter({ lat, lng });
    mapRef.setZoom(12);
    mapZoom.value = 12;
    showGrid.value = false;
    clearPolygons();
    searchEl.value.value = "";
  });
});

onUnmounted(() => {
  removeAllGmListeners();
  clearPolygons();
});

watch(
  () => props.selectedSquareId,
  () => updatePolygonStyles(),
);
watch(
  () => props.hoverIndex,
  () => updatePolygonStyles(),
);

watch(
  () => props.center,
  (newCenter) => {
    mapInstance.value?.setCenter(newCenter);
  },
  { deep: true },
);

defineExpose({
  reset(initialZoom = 2, initialCenter = { lat: 0, lng: 0 }) {
    const mapRef = mapInstance.value;
    if (!mapRef) return;
    clearPolygons();
    showGrid.value = false;
    mapRef.setMapTypeId("roadmap");
    mapRef.setCenter(initialCenter);
    mapRef.setZoom(initialZoom);
    mapZoom.value = initialZoom;
    if (searchEl.value) searchEl.value.value = "";
  },
});
</script>

<style scoped>
.map-component-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.search-bar {
  width: 100%;
}
.search-input {
  width: 100%;
  box-sizing: border-box;
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--border, #333);
  border-radius: 8px;
  background: var(--input-bg, #12121e);
  color: var(--text, #e0e0e0);
  font-size: 0.9rem;
  outline: none;
}
.search-input:focus {
  border-color: var(--accent, #7c6af7);
  box-shadow: 0 0 0 2px rgba(124, 106, 247, 0.25);
}
</style>
